SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Akun = personel yang bisa login (ERD: User + PasswordManager).
   - personel.nik boleh kosong (akun lama belum punya NIK); bila diisi tetap unik & 16 digit (dicek aplikasi).
   - personel.email.
   - Setiap akun wajib terhubung ke personel: akun lama tanpa personel dibuatkan personel kategori Karyawan /
     Security (sesuai jabatan). Satu personel paling banyak satu akun.
   - akun.masa_berlaku_password: hari, khusus pengguna ini (NULL = ikut Pengaturan, 0 = tidak pernah kedaluwarsa).
   - password_riwayat (History): hash password lama, untuk menolak pemakaian ulang.
   - akun_akses: hak akses khusus per pengguna, menggantikan hak jabatan untuk menu itu saja.
   Aman dijalankan ulang.
   ===================================================================================== */
-- Lepas SEMUA unique lama di personel.nik, apa pun namanya (database lama: UQ__driver__... dari tabel driver),
-- kecuali index terfilter UX_Personel_Nik yang dibuat di bawah. Tanpa ini NIK kosong kedua ditolak.
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += N'ALTER TABLE dbo.personel DROP CONSTRAINT ' + QUOTENAME(kc.name) + N'; '
FROM sys.key_constraints kc
JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE kc.parent_object_id = OBJECT_ID('dbo.personel') AND kc.type = 'UQ' AND c.name = 'nik';
SELECT @sql += N'DROP INDEX ' + QUOTENAME(i.name) + N' ON dbo.personel; '
FROM sys.indexes i
JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE i.object_id = OBJECT_ID('dbo.personel') AND i.is_unique = 1 AND i.is_unique_constraint = 0
  AND i.is_primary_key = 0 AND i.has_filter = 0 AND c.name = 'nik';
IF @sql <> N'' EXEC (@sql);
GO
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.personel') AND name = 'nik' AND is_nullable = 0)
    ALTER TABLE dbo.personel ALTER COLUMN nik VARCHAR(20) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Personel_Nik' AND object_id = OBJECT_ID('dbo.personel'))
    CREATE UNIQUE INDEX UX_Personel_Nik ON dbo.personel (nik) WHERE nik IS NOT NULL;
GO
IF COL_LENGTH('dbo.personel', 'email') IS NULL
    ALTER TABLE dbo.personel ADD email NVARCHAR(100) NULL;
GO

-- Akun lama tanpa personel: buatkan personelnya. XACT_ABORT: error pertama langsung menghentikan batch
-- (tidak berulang tanpa henti), dan id personel diambil dari OUTPUT INTO (bukan SCOPE_IDENTITY yang bisa
-- tertinggal dari baris sebelumnya bila INSERT gagal).
SET XACT_ABORT ON;
DECLARE @id_user INT;
DECLARE @baru TABLE (id INT);
WHILE EXISTS (SELECT 1 FROM dbo.akun WHERE id_personel IS NULL)
BEGIN
    SELECT TOP 1 @id_user = id_user FROM dbo.akun WHERE id_personel IS NULL ORDER BY id_user;
    DELETE FROM @baru;
    INSERT INTO dbo.personel (nik, nama_personel, kategori)
    OUTPUT INSERTED.id_personel INTO @baru (id)
    SELECT NULL, LEFT(u.nama, 100), CASE WHEN lv.kode = 'SECURITY' THEN 'SECURITY' ELSE 'EMPLOYEE' END
    FROM dbo.akun u JOIN dbo.level lv ON lv.id_level = u.id_level WHERE u.id_user = @id_user;
    UPDATE dbo.akun SET id_personel = (SELECT id FROM @baru) WHERE id_user = @id_user;
END
SET XACT_ABORT OFF;
GO
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.akun') AND name = 'id_personel' AND is_nullable = 1)
BEGIN
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Users_Personel' AND object_id = OBJECT_ID('dbo.akun'))
        DROP INDEX UX_Users_Personel ON dbo.akun;
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Akun_Personel' AND object_id = OBJECT_ID('dbo.akun'))
        DROP INDEX UX_Akun_Personel ON dbo.akun;
    ALTER TABLE dbo.akun ALTER COLUMN id_personel INT NOT NULL;
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Akun_Personel' AND object_id = OBJECT_ID('dbo.akun'))
    CREATE UNIQUE INDEX UX_Akun_Personel ON dbo.akun (id_personel);
GO

IF COL_LENGTH('dbo.akun', 'masa_berlaku_password') IS NULL
    ALTER TABLE dbo.akun ADD masa_berlaku_password INT NULL;
GO

IF OBJECT_ID('dbo.password_riwayat', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.password_riwayat (
        id_riwayat INT IDENTITY(1,1) PRIMARY KEY,
        id_user    INT NOT NULL CONSTRAINT FK_PwRiwayat_Akun REFERENCES dbo.akun (id_user),
        password   VARCHAR(255) NOT NULL,                       -- hash pbkdf2
        dibuat     DATETIME NOT NULL CONSTRAINT DF_PwRiwayat_Dibuat DEFAULT (GETDATE())
    );
    CREATE INDEX IX_PwRiwayat_User ON dbo.password_riwayat (id_user, dibuat DESC);
    INSERT INTO dbo.password_riwayat (id_user, password, dibuat)
    SELECT id_user, password, ISNULL(password_changed_at, created_at) FROM dbo.akun;
END
GO

IF OBJECT_ID('dbo.akun_akses', 'U') IS NULL
CREATE TABLE dbo.akun_akses (
    id_user      INT NOT NULL CONSTRAINT FK_AkunAkses_Akun REFERENCES dbo.akun (id_user),
    id_menu      INT NOT NULL CONSTRAINT FK_AkunAkses_Menu REFERENCES dbo.menu (id_menu),
    bisa_lihat   BIT NOT NULL CONSTRAINT DF_AkunAkses_Lihat DEFAULT (0),
    bisa_tambah  BIT NOT NULL CONSTRAINT DF_AkunAkses_Tambah DEFAULT (0),
    bisa_ubah    BIT NOT NULL CONSTRAINT DF_AkunAkses_Ubah DEFAULT (0),
    bisa_hapus   BIT NOT NULL CONSTRAINT DF_AkunAkses_Hapus DEFAULT (0),
    bisa_setujui BIT NOT NULL CONSTRAINT DF_AkunAkses_Setujui DEFAULT (0),
    CONSTRAINT PK_AkunAkses PRIMARY KEY (id_user, id_menu)
);
GO
