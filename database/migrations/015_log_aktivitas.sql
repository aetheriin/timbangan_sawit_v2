SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 5a: satu log untuk semua (log_aktivitas).
   - Isi lama/baru disimpan JSON (NVARCHAR(MAX) + ISJSON)
   - Rantai hash: hash_baris = SHA-256(hash_sebelum | waktu | pelaku | kategori | aksi | tabel | id_baris | lama | baru | ip)
     Baris yang diubah / dihapus / disisipkan di tengah ketahuan (Admin > Audit Admin > Verifikasi rantai)
   - Hanya INSERT lewat dbo.sp_catat_log; trigger menolak UPDATE / DELETE
   - Data 5 tabel log lama dipindah berurutan waktu. Tabel lama TIDAK dihapus di sini (dihapus di migrasi 016
     setelah jumlahnya dicek)
   Wajib setelah migrasi 014.
   ===================================================================================== */

IF OBJECT_ID('dbo.log_aktivitas', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.log_aktivitas (
        id_log         BIGINT IDENTITY(1,1) PRIMARY KEY,
        waktu          DATETIME2(3) NOT NULL,
        id_user        INT NULL CONSTRAINT FK_Log_User REFERENCES dbo.users (id_user),     -- NULL = kiosk / sistem
        id_comp_area   INT NULL CONSTRAINT FK_Log_Area REFERENCES dbo.comp_area (id_comp_area),
        kategori       VARCHAR(20)  NOT NULL,      -- ADMIN, SECURITY, PERSONEL, STANDAR_MUTU, TIMELINE, ...
        aksi           VARCHAR(40)  NOT NULL,
        tabel          VARCHAR(50)  NULL,
        id_baris       VARCHAR(100) NULL,
        nilai_lama     NVARCHAR(MAX) NULL,
        nilai_baru     NVARCHAR(MAX) NULL,
        ip             VARCHAR(45)  NULL,
        hash_sebelum   CHAR(64) NULL,              -- NULL hanya baris pertama
        hash_baris     CHAR(64) NOT NULL,
        CONSTRAINT CK_Log_JsonLama CHECK (nilai_lama IS NULL OR ISJSON(nilai_lama) = 1),
        CONSTRAINT CK_Log_JsonBaru CHECK (nilai_baru IS NULL OR ISJSON(nilai_baru) = 1)
    );
    CREATE INDEX IX_Log_Kategori_Waktu ON dbo.log_aktivitas (kategori, waktu DESC);
    CREATE INDEX IX_Log_Baris ON dbo.log_aktivitas (tabel, id_baris);
END
GO

/* Isi yang di-hash (dipakai juga untuk verifikasi) */
CREATE OR ALTER FUNCTION dbo.fn_hash_log (
    @hash_sebelum CHAR(64), @waktu DATETIME2(3), @id_user INT, @kategori VARCHAR(20), @aksi VARCHAR(40),
    @tabel VARCHAR(50), @id_baris VARCHAR(100), @nilai_lama NVARCHAR(MAX), @nilai_baru NVARCHAR(MAX), @ip VARCHAR(45))
RETURNS CHAR(64)
AS
BEGIN
    RETURN CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT(
        ISNULL(@hash_sebelum, REPLICATE('0', 64)), N'|', CONVERT(VARCHAR(30), @waktu, 121), N'|', @id_user, N'|',
        @kategori, N'|', @aksi, N'|', @tabel, N'|', @id_baris, N'|', @nilai_lama, N'|', @nilai_baru, N'|', @ip)), 2);
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_catat_log
    @kategori VARCHAR(20), @aksi VARCHAR(40), @tabel VARCHAR(50) = NULL, @id_baris VARCHAR(100) = NULL,
    @nilai_lama NVARCHAR(MAX) = NULL, @nilai_baru NVARCHAR(MAX) = NULL, @id_user INT = NULL,
    @id_comp_area INT = NULL, @ip VARCHAR(45) = NULL, @waktu DATETIME2(3) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRANSACTION;
    -- satu penulis pada satu waktu supaya rantai tidak bercabang
    EXEC sp_getapplock @Resource = 'log_aktivitas', @LockMode = 'Exclusive', @LockOwner = 'Transaction';
    DECLARE @prev CHAR(64) = (SELECT TOP 1 hash_baris FROM dbo.log_aktivitas ORDER BY id_log DESC);
    SET @waktu = COALESCE(@waktu, SYSDATETIME());
    IF @id_comp_area IS NULL AND @id_user IS NOT NULL
        SET @id_comp_area = (SELECT id_comp_area FROM dbo.users WHERE id_user = @id_user);
    INSERT INTO dbo.log_aktivitas (waktu, id_user, id_comp_area, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru,
                                   ip, hash_sebelum, hash_baris)
    VALUES (@waktu, @id_user, @id_comp_area, @kategori, @aksi, @tabel, @id_baris, @nilai_lama, @nilai_baru, @ip, @prev,
            dbo.fn_hash_log(@prev, @waktu, @id_user, @kategori, @aksi, @tabel, @id_baris, @nilai_lama, @nilai_baru, @ip));
    COMMIT TRANSACTION;
END
GO

CREATE OR ALTER TRIGGER dbo.TR_Log_HanyaTambah ON dbo.log_aktivitas INSTEAD OF UPDATE, DELETE AS
BEGIN
    RAISERROR('log_aktivitas hanya boleh ditambah (tidak bisa diubah / dihapus).', 16, 1);
    ROLLBACK TRANSACTION;
END
GO

/* Baris pertama yang rantainya putus; kosong = utuh */
CREATE OR ALTER VIEW dbo.v_log_rusak AS
SELECT x.id_log, x.waktu, x.kategori, x.aksi,
       CASE WHEN x.hash_baris <> x.hash_hitung THEN 'ISI_BERUBAH' ELSE 'RANTAI_PUTUS' END AS masalah
FROM (SELECT l.id_log, l.waktu, l.kategori, l.aksi, l.hash_sebelum, l.hash_baris,
             LAG(l.hash_baris) OVER (ORDER BY l.id_log) AS hash_seharusnya,
             dbo.fn_hash_log(l.hash_sebelum, l.waktu, l.id_user, l.kategori, l.aksi, l.tabel, l.id_baris,
                             l.nilai_lama, l.nilai_baru, l.ip) AS hash_hitung
      FROM dbo.log_aktivitas l) x
WHERE x.hash_baris <> x.hash_hitung
   OR ISNULL(x.hash_sebelum, '') <> ISNULL(x.hash_seharusnya, '');
GO

/* ---------- Pindah data log lama (sekali saja: hanya bila log_aktivitas masih kosong) ---------- */
IF NOT EXISTS (SELECT 1 FROM dbo.log_aktivitas)
BEGIN
    DECLARE @lama TABLE (urut INT IDENTITY(1,1), waktu DATETIME2(3), id_user INT, kategori VARCHAR(20), aksi VARCHAR(40),
                         tabel VARCHAR(50), id_baris VARCHAR(100), nilai_lama NVARCHAR(MAX), nilai_baru NVARCHAR(MAX),
                         ip VARCHAR(45));

    IF OBJECT_ID('dbo.admin_audit_logs', 'U') IS NOT NULL
        INSERT INTO @lama (waktu, id_user, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru, ip)
        EXEC(N'SELECT created_at, user_id, ''ADMIN'', aksi, NULL, target, NULL,
                      CASE WHEN detail IS NULL THEN NULL
                           ELSE (SELECT a.detail AS detail FOR JSON PATH, WITHOUT_ARRAY_WRAPPER) END, ip_address
               FROM dbo.admin_audit_logs a ORDER BY created_at, id_log');

    IF OBJECT_ID('dbo.security_audit_logs', 'U') IS NOT NULL
        INSERT INTO @lama (waktu, id_user, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru, ip)
        EXEC(N'SELECT created_at, user_id, ''SECURITY'', action_type, ''transaksi'', no_tiket, NULL, details, ip_address
               FROM dbo.security_audit_logs ORDER BY created_at, id_log');

    IF OBJECT_ID('dbo.personel_audit_logs', 'U') IS NOT NULL
        INSERT INTO @lama (waktu, id_user, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru, ip)
        EXEC(N'SELECT a.updated_at, a.updated_by, ''PERSONEL'', a.aksi, ''personel'', CAST(a.id_personel AS VARCHAR(20)),
                      CASE WHEN a.aksi = ''TAMBAH'' THEN NULL ELSE
                          (SELECT a.kode_personel_lama AS kode_personel, a.nik_lama AS nik, a.nama_lama AS nama,
                                  a.no_sim_lama AS no_sim FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES) END,
                      (SELECT a.kode_personel_baru AS kode_personel, a.nik_baru AS nik, a.nama_baru AS nama,
                              a.no_sim_baru AS no_sim FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES),
                      NULL
               FROM dbo.personel_audit_logs a ORDER BY a.updated_at, a.id_log');

    IF OBJECT_ID('dbo.standar_mutu_log', 'U') IS NOT NULL
        INSERT INTO @lama (waktu, id_user, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru, ip)
        EXEC(N'SELECT l.updated_at, l.updated_by, ''STANDAR_MUTU'', ''STANDAR_UBAH'', ''standar_mutu'',
                      CAST(l.id_produk AS VARCHAR(20)), NULL,
                      (SELECT l.maks_ffa AS maks_ffa, l.maks_air AS maks_air, l.maks_kotoran AS maks_kotoran
                       FOR JSON PATH, WITHOUT_ARRAY_WRAPPER), NULL
               FROM dbo.standar_mutu_log l ORDER BY l.updated_at, l.id_log');

    IF OBJECT_ID('dbo.timeline_monitoring', 'U') IS NOT NULL
        INSERT INTO @lama (waktu, id_user, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru, ip)
        EXEC(N'SELECT [timestamp], processed_by, ''TIMELINE'', stage, ''transaksi'', no_tiket, NULL, NULL, NULL
               FROM dbo.timeline_monitoring ORDER BY [timestamp], id_timeline');

    DECLARE @w DATETIME2(3), @u INT, @k VARCHAR(20), @a VARCHAR(40), @t VARCHAR(50), @b VARCHAR(100),
            @nl NVARCHAR(MAX), @nb NVARCHAR(MAX), @ip VARCHAR(45);
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR
        SELECT waktu, id_user, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru, ip FROM @lama ORDER BY waktu, urut;
    OPEN c;
    FETCH NEXT FROM c INTO @w, @u, @k, @a, @t, @b, @nl, @nb, @ip;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        EXEC dbo.sp_catat_log @kategori = @k, @aksi = @a, @tabel = @t, @id_baris = @b, @nilai_lama = @nl,
                              @nilai_baru = @nb, @id_user = @u, @ip = @ip, @waktu = @w;
        FETCH NEXT FROM c INTO @w, @u, @k, @a, @t, @b, @nl, @nb, @ip;
    END
    CLOSE c;
    DEALLOCATE c;
END
GO

/* Cek: jumlah per kategori harus sama dengan jumlah baris tabel lama */
SELECT kategori, COUNT(*) AS jumlah FROM dbo.log_aktivitas GROUP BY kategori;
SELECT COUNT(*) AS rantai_rusak FROM dbo.v_log_rusak;     -- harus 0
GO
