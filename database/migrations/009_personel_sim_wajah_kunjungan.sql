SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 2: personel.
   - kategori_personel (PK = kode; personel.kategori menjadi FK), kategori baru TAMU
   - SIM pindah ke personel_sim (+ jenis_sim), wajah pindah ke personel_wajah
   - Kolom personel.no_sim, face_embedding_data, foto_path, foto_sumber DIHAPUS setelah datanya dipindah
   - v_personel: bentuk "lama" (no_sim, foto_path, ...) untuk dibaca aplikasi
   - Tamu: keperluan_kunjungan, kunjungan; menu KUNJUNGAN di Face Recognition
   Wajib setelah migrasi 008.
   ===================================================================================== */

/* ---------- 1. Kategori personel ---------- */
IF OBJECT_ID('dbo.kategori_personel', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.kategori_personel (
        kode        VARCHAR(20)   NOT NULL PRIMARY KEY,
        nama        NVARCHAR(50)  NOT NULL,
        wajib_sim   BIT NOT NULL CONSTRAINT DF_KatPersonel_Sim DEFAULT (0),
        boleh_akun  BIT NOT NULL CONSTRAINT DF_KatPersonel_Akun DEFAULT (0),
        is_active   BIT NOT NULL CONSTRAINT DF_KatPersonel_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.kategori_personel (kode, nama, wajib_sim, boleh_akun) VALUES
        ('DRIVER',   N'Driver',   1, 0),
        ('SECURITY', N'Security', 0, 1),
        ('EMPLOYEE', N'Karyawan', 0, 1),
        ('TAMU',     N'Tamu',     0, 0);
END
GO

/* CHECK lama (kategori tetap, SIM wajib driver, sumber foto) diganti FK + aturan aplikasi */
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += N'ALTER TABLE dbo.personel DROP CONSTRAINT ' + QUOTENAME(c.name) + N';'
FROM sys.check_constraints c
WHERE c.parent_object_id = OBJECT_ID('dbo.personel')
  AND (c.definition LIKE '%kategori%' OR c.definition LIKE '%no_sim%' OR c.definition LIKE '%foto_sumber%');
EXEC sp_executesql @sql;
GO

IF OBJECT_ID('dbo.FK_Personel_Kategori', 'F') IS NULL
    ALTER TABLE dbo.personel ADD CONSTRAINT FK_Personel_Kategori
        FOREIGN KEY (kategori) REFERENCES dbo.kategori_personel (kode);
GO

/* ---------- 2. SIM ---------- */
IF OBJECT_ID('dbo.jenis_sim', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.jenis_sim (
        id_jenis_sim INT IDENTITY(1,1) PRIMARY KEY,
        kode         VARCHAR(20)  NOT NULL CONSTRAINT UX_JenisSim_Kode UNIQUE,
        nama         NVARCHAR(50) NOT NULL,
        is_active    BIT NOT NULL CONSTRAINT DF_JenisSim_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.jenis_sim (kode, nama) VALUES
        ('A', N'SIM A'), ('B1', N'SIM B1'), ('B1_UMUM', N'SIM B1 Umum'), ('B2', N'SIM B2'), ('B2_UMUM', N'SIM B2 Umum');
    -- Penanda data lama (jenis & masa berlaku belum diketahui). Tidak muncul di pilihan form.
    INSERT INTO dbo.jenis_sim (kode, nama, is_active) VALUES ('BELUM_DIISI', N'Belum dilengkapi', 0);
END
GO

IF OBJECT_ID('dbo.personel_sim', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.personel_sim (
        id_sim          INT IDENTITY(1,1) PRIMARY KEY,
        id_personel     INT NOT NULL CONSTRAINT FK_PersonelSim_Personel REFERENCES dbo.personel (id_personel),
        id_jenis_sim    INT NOT NULL CONSTRAINT FK_PersonelSim_Jenis REFERENCES dbo.jenis_sim (id_jenis_sim),
        no_sim          VARCHAR(30) NOT NULL,
        berlaku_sampai  DATE NULL,                 -- NULL hanya untuk data lama yang belum dilengkapi
        is_active       BIT NOT NULL CONSTRAINT DF_PersonelSim_Aktif DEFAULT (1),
        created_by      INT NULL CONSTRAINT FK_PersonelSim_User REFERENCES dbo.users (id_user),
        created_at      DATETIME NOT NULL CONSTRAINT DF_PersonelSim_Created DEFAULT (GETDATE())
    );
    CREATE UNIQUE INDEX UX_PersonelSim_NoAktif ON dbo.personel_sim (no_sim) WHERE is_active = 1;
    CREATE INDEX IX_PersonelSim_Personel ON dbo.personel_sim (id_personel, is_active);
END
GO

IF COL_LENGTH('dbo.personel', 'no_sim') IS NOT NULL
    EXEC(N'INSERT INTO dbo.personel_sim (id_personel, id_jenis_sim, no_sim)
           SELECT p.id_personel, (SELECT id_jenis_sim FROM dbo.jenis_sim WHERE kode = ''BELUM_DIISI''), p.no_sim
           FROM dbo.personel p
           WHERE p.no_sim IS NOT NULL AND LTRIM(RTRIM(p.no_sim)) <> ''''
             AND NOT EXISTS (SELECT 1 FROM dbo.personel_sim s WHERE s.id_personel = p.id_personel)');
GO

/* ---------- 3. Wajah ---------- */
IF OBJECT_ID('dbo.personel_wajah', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.personel_wajah (
        id_wajah     INT IDENTITY(1,1) PRIMARY KEY,
        id_personel  INT NOT NULL CONSTRAINT FK_PersonelWajah_Personel REFERENCES dbo.personel (id_personel),
        embedding    VARBINARY(MAX) NOT NULL,
        foto_path    VARCHAR(255) NULL,
        sumber       VARCHAR(10)  NULL CONSTRAINT CK_PersonelWajah_Sumber CHECK (sumber IN ('UPLOAD', 'KAMERA')),
        is_utama     BIT NOT NULL CONSTRAINT DF_PersonelWajah_Utama DEFAULT (1),
        is_active    BIT NOT NULL CONSTRAINT DF_PersonelWajah_Aktif DEFAULT (1),
        created_by   INT NULL CONSTRAINT FK_PersonelWajah_User REFERENCES dbo.users (id_user),
        created_at   DATETIME NOT NULL CONSTRAINT DF_PersonelWajah_Created DEFAULT (GETDATE())
    );
    CREATE UNIQUE INDEX UX_PersonelWajah_Utama ON dbo.personel_wajah (id_personel) WHERE is_utama = 1 AND is_active = 1;
    CREATE INDEX IX_PersonelWajah_Aktif ON dbo.personel_wajah (is_active) INCLUDE (id_personel);
END
GO

IF COL_LENGTH('dbo.personel', 'face_embedding_data') IS NOT NULL
    EXEC(N'INSERT INTO dbo.personel_wajah (id_personel, embedding, foto_path, sumber)
           SELECT p.id_personel, p.face_embedding_data, p.foto_path, p.foto_sumber
           FROM dbo.personel p
           WHERE p.face_embedding_data IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM dbo.personel_wajah w WHERE w.id_personel = p.id_personel)');
GO

/* ---------- 4. Hapus kolom lama dari personel ---------- */
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += N'ALTER TABLE dbo.personel DROP CONSTRAINT ' + QUOTENAME(d.name) + N';'
FROM sys.default_constraints d
JOIN sys.columns col ON col.object_id = d.parent_object_id AND col.column_id = d.parent_column_id
WHERE d.parent_object_id = OBJECT_ID('dbo.personel')
  AND col.name IN ('no_sim', 'face_embedding_data', 'foto_path', 'foto_sumber');
EXEC sp_executesql @sql;
GO
IF COL_LENGTH('dbo.personel', 'no_sim') IS NOT NULL ALTER TABLE dbo.personel DROP COLUMN no_sim;
IF COL_LENGTH('dbo.personel', 'face_embedding_data') IS NOT NULL ALTER TABLE dbo.personel DROP COLUMN face_embedding_data;
IF COL_LENGTH('dbo.personel', 'foto_path') IS NOT NULL ALTER TABLE dbo.personel DROP COLUMN foto_path;
IF COL_LENGTH('dbo.personel', 'foto_sumber') IS NOT NULL ALTER TABLE dbo.personel DROP COLUMN foto_sumber;
GO

/* ---------- 5. View bentuk lama untuk dibaca aplikasi ---------- */
CREATE OR ALTER VIEW dbo.v_personel AS
SELECT p.id_personel, p.kode_personel, p.nik, p.nama_personel, p.kategori, p.is_updated, p.current_hash,
       p.is_blacklisted, p.is_active, p.created_at, p.updated_at,
       s.no_sim, s.id_jenis_sim, s.kode_jenis_sim, s.berlaku_sampai AS sim_berlaku_sampai,
       w.embedding AS face_embedding_data, w.foto_path, w.sumber AS foto_sumber
FROM dbo.personel p
OUTER APPLY (SELECT TOP 1 ps.no_sim, ps.id_jenis_sim, j.kode AS kode_jenis_sim, ps.berlaku_sampai
             FROM dbo.personel_sim ps JOIN dbo.jenis_sim j ON j.id_jenis_sim = ps.id_jenis_sim
             WHERE ps.id_personel = p.id_personel AND ps.is_active = 1
             ORDER BY ps.berlaku_sampai DESC, ps.id_sim DESC) s
OUTER APPLY (SELECT TOP 1 pw.embedding, pw.foto_path, pw.sumber
             FROM dbo.personel_wajah pw
             WHERE pw.id_personel = p.id_personel AND pw.is_active = 1
             ORDER BY pw.is_utama DESC, pw.id_wajah DESC) w;
GO

/* ---------- 6. Tamu & kunjungan ---------- */
IF OBJECT_ID('dbo.keperluan_kunjungan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.keperluan_kunjungan (
        id_keperluan INT IDENTITY(1,1) PRIMARY KEY,
        nama         NVARCHAR(100) NOT NULL CONSTRAINT UX_Keperluan_Nama UNIQUE,
        is_active    BIT NOT NULL CONSTRAINT DF_Keperluan_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.keperluan_kunjungan (nama) VALUES
        (N'Rapat / Bertemu'), (N'Pengiriman Barang'), (N'Perbaikan / Servis'), (N'Audit / Inspeksi'), (N'Lainnya');
END
GO

IF OBJECT_ID('dbo.kunjungan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.kunjungan (
        id_kunjungan     INT IDENTITY(1,1) PRIMARY KEY,
        id_personel      INT NOT NULL CONSTRAINT FK_Kunjungan_Tamu REFERENCES dbo.personel (id_personel),
        id_dituju        INT NOT NULL CONSTRAINT FK_Kunjungan_Dituju REFERENCES dbo.personel (id_personel),
        id_keperluan     INT NOT NULL CONSTRAINT FK_Kunjungan_Keperluan REFERENCES dbo.keperluan_kunjungan (id_keperluan),
        keterangan       NVARCHAR(255) NULL,
        asal_perusahaan  NVARCHAR(100) NULL,
        no_plat          VARCHAR(15)   NULL,
        id_comp_area     INT NOT NULL CONSTRAINT FK_Kunjungan_Area REFERENCES dbo.comp_area (id_comp_area),
        foto_masuk_path  VARCHAR(255)  NULL,      -- snapshot wajah saat datang
        waktu_masuk      DATETIME NOT NULL CONSTRAINT DF_Kunjungan_Masuk DEFAULT (GETDATE()),
        waktu_keluar     DATETIME NULL,           -- NULL = tamu masih di dalam
        dicatat_oleh     INT NOT NULL CONSTRAINT FK_Kunjungan_User REFERENCES dbo.users (id_user),
        CONSTRAINT CK_Kunjungan_Keluar CHECK (waktu_keluar IS NULL OR waktu_keluar >= waktu_masuk)
    );
    CREATE INDEX IX_Kunjungan_Masuk ON dbo.kunjungan (waktu_masuk DESC);
    CREATE INDEX IX_Kunjungan_Didalam ON dbo.kunjungan (id_personel) WHERE waktu_keluar IS NULL;
END
GO

/* ---------- 7. Menu & hak akses Kunjungan ---------- */
IF NOT EXISTS (SELECT 1 FROM dbo.menu WHERE kode = 'KUNJUNGAN')
BEGIN
    INSERT INTO dbo.menu (kode, nama, id_parent, urutan)
    SELECT 'KUNJUNGAN', N'Face Recognition › Kunjungan Tamu', id_menu, 5 FROM dbo.menu WHERE kode = 'FACE_RECOGNITION';
    INSERT INTO dbo.level_akses (id_level, id_menu, bisa_tambah, bisa_ubah, bisa_hapus)
    SELECT l.id_level, m.id_menu, 1, 1, 0
    FROM dbo.level l CROSS JOIN dbo.menu m
    WHERE l.kode = 'SECURITY' AND m.kode = 'KUNJUNGAN';
END
GO
