SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 3: dokumen umum & pembatalan tiket.
   - jenis_dokumen -> dokumen -> dokumen_file (surat blacklist, berita acara void, COA, scan SIM / STNK, kontrak)
   - blacklist: no_surat_blacklist, file_surat_blacklist, tgl_blacklist pindah ke dokumen (blacklist.id_dokumen)
   - pembatalan_tiket: kolom transaksi.alasan_void, void_by, void_at, alasan_reject, rejected_by dipindah
   Wajib setelah migrasi 009.
   ===================================================================================== */

/* ---------- 1. Dokumen ---------- */
IF OBJECT_ID('dbo.jenis_dokumen', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.jenis_dokumen (
        id_jenis    INT IDENTITY(1,1) PRIMARY KEY,
        kode        VARCHAR(30)   NOT NULL CONSTRAINT UX_JenisDok_Kode UNIQUE,
        nama        NVARCHAR(100) NOT NULL,
        wajib_file  BIT NOT NULL CONSTRAINT DF_JenisDok_WajibFile DEFAULT (1),
        is_active   BIT NOT NULL CONSTRAINT DF_JenisDok_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.jenis_dokumen (kode, nama, wajib_file) VALUES
        ('SURAT_BLACKLIST', N'Surat Blacklist', 1),
        ('BA_VOID',         N'Berita Acara Void Tiket', 1),
        ('COA',             N'Certificate of Analysis (Lab)', 0),
        ('SIM',             N'Scan SIM', 1),
        ('STNK',            N'Scan STNK', 1),
        ('KONTRAK',         N'Dokumen Kontrak', 0);
END
GO

IF OBJECT_ID('dbo.dokumen', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.dokumen (
        id_dokumen  INT IDENTITY(1,1) PRIMARY KEY,
        id_jenis    INT NOT NULL CONSTRAINT FK_Dokumen_Jenis REFERENCES dbo.jenis_dokumen (id_jenis),
        no_dokumen  NVARCHAR(100) NOT NULL,
        tanggal     DATE NOT NULL,
        perihal     NVARCHAR(255) NULL,
        created_by  INT NOT NULL CONSTRAINT FK_Dokumen_User REFERENCES dbo.users (id_user),
        created_at  DATETIME NOT NULL CONSTRAINT DF_Dokumen_Created DEFAULT (GETDATE())
    );
    CREATE INDEX IX_Dokumen_Jenis_No ON dbo.dokumen (id_jenis, no_dokumen);
END
GO

IF OBJECT_ID('dbo.dokumen_file', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.dokumen_file (
        id_file      INT IDENTITY(1,1) PRIMARY KEY,
        id_dokumen   INT NOT NULL CONSTRAINT FK_DokFile_Dokumen REFERENCES dbo.dokumen (id_dokumen),
        file_path    VARCHAR(255)  NOT NULL,          -- 'uploads/dokumen/...' (privat, dibuka lewat /berkas/)
        nama_asli    NVARCHAR(255) NULL,
        mime         VARCHAR(100)  NULL,
        ukuran_byte  INT NULL,
        sha256       CHAR(64) NULL,                   -- NULL hanya untuk file lama (sebelum migrasi 010)
        urutan       TINYINT NOT NULL CONSTRAINT DF_DokFile_Urutan DEFAULT (1),
        created_at   DATETIME NOT NULL CONSTRAINT DF_DokFile_Created DEFAULT (GETDATE())
    );
    CREATE INDEX IX_DokFile_Dokumen ON dbo.dokumen_file (id_dokumen, urutan);
END
GO

/* ---------- 2. Blacklist -> dokumen ---------- */
IF COL_LENGTH('dbo.blacklist', 'id_dokumen') IS NULL
    ALTER TABLE dbo.blacklist ADD id_dokumen INT NULL CONSTRAINT FK_Blacklist_Dokumen REFERENCES dbo.dokumen (id_dokumen);
GO

IF COL_LENGTH('dbo.blacklist', 'no_surat_blacklist') IS NOT NULL
EXEC(N'
DECLARE @id_blacklist INT, @no NVARCHAR(100), @tgl DATE, @file VARCHAR(255), @oleh INT, @dibuat DATETIME, @id_dok INT;
DECLARE @jenis INT = (SELECT id_jenis FROM dbo.jenis_dokumen WHERE kode = ''SURAT_BLACKLIST'');
DECLARE c CURSOR LOCAL FAST_FORWARD FOR
    SELECT id_blacklist, no_surat_blacklist, tgl_blacklist, file_surat_blacklist, created_by, created_at
    FROM dbo.blacklist WHERE id_dokumen IS NULL;
OPEN c;
FETCH NEXT FROM c INTO @id_blacklist, @no, @tgl, @file, @oleh, @dibuat;
WHILE @@FETCH_STATUS = 0
BEGIN
    INSERT INTO dbo.dokumen (id_jenis, no_dokumen, tanggal, perihal, created_by, created_at)
    VALUES (@jenis, @no, @tgl, N''Surat blacklist'', @oleh, @dibuat);
    SET @id_dok = SCOPE_IDENTITY();
    IF @file IS NOT NULL
        INSERT INTO dbo.dokumen_file (id_dokumen, file_path, mime, created_at)
        VALUES (@id_dok, @file, CASE WHEN @file LIKE ''%.pdf'' THEN ''application/pdf''
                                     WHEN @file LIKE ''%.png'' THEN ''image/png'' ELSE ''image/jpeg'' END, @dibuat);
    UPDATE dbo.blacklist SET id_dokumen = @id_dok WHERE id_blacklist = @id_blacklist;
    FETCH NEXT FROM c INTO @id_blacklist, @no, @tgl, @file, @oleh, @dibuat;
END
CLOSE c; DEALLOCATE c;');
GO

ALTER TABLE dbo.blacklist ALTER COLUMN id_dokumen INT NOT NULL;
GO
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Blacklist_Tgl' AND object_id = OBJECT_ID('dbo.blacklist'))
    DROP INDEX IX_Blacklist_Tgl ON dbo.blacklist;
IF COL_LENGTH('dbo.blacklist', 'no_surat_blacklist') IS NOT NULL ALTER TABLE dbo.blacklist DROP COLUMN no_surat_blacklist;
IF COL_LENGTH('dbo.blacklist', 'file_surat_blacklist') IS NOT NULL ALTER TABLE dbo.blacklist DROP COLUMN file_surat_blacklist;
IF COL_LENGTH('dbo.blacklist', 'tgl_blacklist') IS NOT NULL ALTER TABLE dbo.blacklist DROP COLUMN tgl_blacklist;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Blacklist_Dokumen' AND object_id = OBJECT_ID('dbo.blacklist'))
    CREATE INDEX IX_Blacklist_Dokumen ON dbo.blacklist (id_dokumen);
GO

/* ---------- 3. Pembatalan tiket (void oleh Admin, reject oleh Lab) ---------- */
IF OBJECT_ID('dbo.pembatalan_tiket', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pembatalan_tiket (
        no_tiket    VARCHAR(50)   NOT NULL PRIMARY KEY CONSTRAINT FK_Batal_Transaksi REFERENCES dbo.transaksi (no_tiket),
        jenis       VARCHAR(10)   NOT NULL CONSTRAINT CK_Batal_Jenis CHECK (jenis IN ('VOID', 'REJECT')),
        alasan      NVARCHAR(255) NOT NULL,
        id_dokumen  INT NULL CONSTRAINT FK_Batal_Dokumen REFERENCES dbo.dokumen (id_dokumen),   -- berita acara, boleh menyusul
        oleh        INT NULL CONSTRAINT FK_Batal_User REFERENCES dbo.users (id_user),           -- NULL hanya data lama
        waktu       DATETIME NOT NULL CONSTRAINT DF_Batal_Waktu DEFAULT (GETDATE())
    );
    CREATE INDEX IX_Batal_Waktu ON dbo.pembatalan_tiket (waktu DESC);
END
GO

IF COL_LENGTH('dbo.transaksi', 'alasan_void') IS NOT NULL
    EXEC(N'INSERT INTO dbo.pembatalan_tiket (no_tiket, jenis, alasan, oleh, waktu)
           SELECT t.no_tiket, ''VOID'', COALESCE(t.alasan_void, N''(tanpa alasan)''), t.void_by, COALESCE(t.void_at, t.created_at)
           FROM dbo.transaksi t
           WHERE t.status_alur = ''VOID'' AND NOT EXISTS (SELECT 1 FROM dbo.pembatalan_tiket p WHERE p.no_tiket = t.no_tiket);
           INSERT INTO dbo.pembatalan_tiket (no_tiket, jenis, alasan, oleh, waktu)
           SELECT t.no_tiket, ''REJECT'', COALESCE(t.alasan_reject, N''Ditolak''), t.rejected_by, t.created_at
           FROM dbo.transaksi t
           WHERE t.status_alur = ''REJECTED'' AND NOT EXISTS (SELECT 1 FROM dbo.pembatalan_tiket p WHERE p.no_tiket = t.no_tiket);');
GO

/* Hapus kolom lama dari transaksi (beserta FK / DEFAULT yang menempel) */
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += N'ALTER TABLE dbo.transaksi DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';'
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fc ON fc.constraint_object_id = fk.object_id
JOIN sys.columns col ON col.object_id = fc.parent_object_id AND col.column_id = fc.parent_column_id
WHERE fk.parent_object_id = OBJECT_ID('dbo.transaksi') AND col.name IN ('void_by', 'rejected_by');
SELECT @sql += N'ALTER TABLE dbo.transaksi DROP CONSTRAINT ' + QUOTENAME(d.name) + N';'
FROM sys.default_constraints d
JOIN sys.columns col ON col.object_id = d.parent_object_id AND col.column_id = d.parent_column_id
WHERE d.parent_object_id = OBJECT_ID('dbo.transaksi')
  AND col.name IN ('alasan_void', 'void_by', 'void_at', 'alasan_reject', 'rejected_by');
EXEC sp_executesql @sql;
GO
IF COL_LENGTH('dbo.transaksi', 'alasan_void') IS NOT NULL ALTER TABLE dbo.transaksi DROP COLUMN alasan_void;
IF COL_LENGTH('dbo.transaksi', 'void_by') IS NOT NULL ALTER TABLE dbo.transaksi DROP COLUMN void_by;
IF COL_LENGTH('dbo.transaksi', 'void_at') IS NOT NULL ALTER TABLE dbo.transaksi DROP COLUMN void_at;
IF COL_LENGTH('dbo.transaksi', 'alasan_reject') IS NOT NULL ALTER TABLE dbo.transaksi DROP COLUMN alasan_reject;
IF COL_LENGTH('dbo.transaksi', 'rejected_by') IS NOT NULL ALTER TABLE dbo.transaksi DROP COLUMN rejected_by;
GO
