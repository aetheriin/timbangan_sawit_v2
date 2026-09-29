/* =====================================================================
   Migrasi 002: driver -> personel, blacklist, audit security
   (versi face recognition, lihat docs/PERANCANGAN_FACE_RECOGNITION.md)

   Perubahan:
   - driver               -> personel (+ kode_personel, kategori, is_blacklisted)
   - driver_audit_logs    -> personel_audit_logs (+ kode_personel_lama/baru)
   - kendaraan            + is_blacklisted
   - users                + id_personel, role aktif hanya HO / SECURITY
   - transaksi            + is_driver_changed, prev_driver_id, driver_photo_path, hash_keamanan
                          no_do -> no_do_manual, status_alur disederhanakan
   - Tabel baru: blacklist, security_audit_logs
   - Trigger: blacklist permanen (is_blacklisted tidak bisa 1 -> 0)

   Jalankan di SSMS pada SALINAN database (ganti nama di baris USE).
   Aman dijalankan ulang: setiap objek dicek dulu sebelum dibuat/diubah.
   Tabel timbangan, sortasi, lab_hasil, standar_mutu, timeline_monitoring TIDAK dihapus.
   ===================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbFaceRecognition]
GO

/* ---------- 1. driver -> personel ---------- */
IF OBJECT_ID('dbo.driver', 'U') IS NOT NULL AND OBJECT_ID('dbo.personel', 'U') IS NULL
    EXEC sp_rename 'dbo.driver', 'personel';
GO
IF COL_LENGTH('dbo.personel', 'id_driver') IS NOT NULL
    EXEC sp_rename 'dbo.personel.id_driver', 'id_personel', 'COLUMN';
IF COL_LENGTH('dbo.personel', 'nama_driver') IS NOT NULL
    EXEC sp_rename 'dbo.personel.nama_driver', 'nama_personel', 'COLUMN';
GO

IF COL_LENGTH('dbo.personel', 'kode_personel') IS NULL
    ALTER TABLE dbo.personel ADD kode_personel VARCHAR(20) NULL;
IF COL_LENGTH('dbo.personel', 'kategori') IS NULL
    ALTER TABLE dbo.personel ADD kategori VARCHAR(20) NOT NULL
        CONSTRAINT DF_Personel_Kategori DEFAULT ('DRIVER');
IF COL_LENGTH('dbo.personel', 'is_blacklisted') IS NULL
    ALTER TABLE dbo.personel ADD is_blacklisted BIT NOT NULL
        CONSTRAINT DF_Personel_Blacklist DEFAULT (0);
GO

-- SECURITY / EMPLOYEE tidak selalu punya SIM; DRIVER tetap wajib
ALTER TABLE dbo.personel ALTER COLUMN no_sim VARCHAR(30) NULL;
GO
IF OBJECT_ID('CK_Personel_Kategori', 'C') IS NULL
    ALTER TABLE dbo.personel ADD CONSTRAINT CK_Personel_Kategori
        CHECK (kategori IN ('DRIVER', 'SECURITY', 'EMPLOYEE'));
IF OBJECT_ID('CK_Personel_SimDriver', 'C') IS NULL
    ALTER TABLE dbo.personel ADD CONSTRAINT CK_Personel_SimDriver
        CHECK (kategori <> 'DRIVER' OR no_sim IS NOT NULL);
-- kode_personel unik, tapi boleh kosong sampai HO mengisi
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Personel_Kode' AND object_id = OBJECT_ID('dbo.personel'))
    CREATE UNIQUE INDEX UX_Personel_Kode ON dbo.personel (kode_personel) WHERE kode_personel IS NOT NULL;
GO

/* ---------- 2. driver_audit_logs -> personel_audit_logs ---------- */
IF OBJECT_ID('dbo.driver_audit_logs', 'U') IS NOT NULL AND OBJECT_ID('dbo.personel_audit_logs', 'U') IS NULL
    EXEC sp_rename 'dbo.driver_audit_logs', 'personel_audit_logs';
GO
IF COL_LENGTH('dbo.personel_audit_logs', 'id_driver') IS NOT NULL
    EXEC sp_rename 'dbo.personel_audit_logs.id_driver', 'id_personel', 'COLUMN';
GO
IF COL_LENGTH('dbo.personel_audit_logs', 'kode_personel_lama') IS NULL
    ALTER TABLE dbo.personel_audit_logs ADD kode_personel_lama VARCHAR(20) NULL,
                                           kode_personel_baru VARCHAR(20) NULL;
GO

/* ---------- 3. kendaraan + is_blacklisted ---------- */
IF COL_LENGTH('dbo.kendaraan', 'is_blacklisted') IS NULL
    ALTER TABLE dbo.kendaraan ADD is_blacklisted BIT NOT NULL
        CONSTRAINT DF_Kendaraan_Blacklist DEFAULT (0);
GO

/* ---------- 4. users: role HO / SECURITY + tautan ke personel ---------- */
DECLARE @ck SYSNAME, @sql NVARCHAR(400);
WHILE 1 = 1
BEGIN
    SET @ck = NULL;
    SELECT TOP 1 @ck = name FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.users') AND definition LIKE '%role%'
      AND name <> 'CK_Users_Role';
    IF @ck IS NULL BREAK;
    SET @sql = N'ALTER TABLE dbo.users DROP CONSTRAINT ' + QUOTENAME(@ck);
    EXEC sp_executesql @sql;
END
GO
UPDATE dbo.users SET role = 'HO' WHERE role = 'ADMIN';
-- akun tahap timbang/sortasi/lab dinonaktifkan, role lamanya tetap disimpan
UPDATE dbo.users SET is_active = 0 WHERE role NOT IN ('HO', 'SECURITY');
GO
IF OBJECT_ID('CK_Users_Role', 'C') IS NULL
    ALTER TABLE dbo.users ADD CONSTRAINT CK_Users_Role CHECK (
        role IN ('HO', 'SECURITY')
        OR (is_active = 0 AND role IN ('LAB', 'SORTASI', 'OPERATOR_TIMBANG'))
    );
IF COL_LENGTH('dbo.users', 'id_personel') IS NULL
    ALTER TABLE dbo.users ADD id_personel INT NULL;
GO
IF OBJECT_ID('FK_Users_Personel', 'F') IS NULL
    ALTER TABLE dbo.users ADD CONSTRAINT FK_Users_Personel
        FOREIGN KEY (id_personel) REFERENCES dbo.personel (id_personel);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Users_Personel' AND object_id = OBJECT_ID('dbo.users'))
    CREATE UNIQUE INDEX UX_Users_Personel ON dbo.users (id_personel) WHERE id_personel IS NOT NULL;
GO

/* ---------- 5. transaksi ---------- */
IF COL_LENGTH('dbo.transaksi', 'no_do') IS NOT NULL AND COL_LENGTH('dbo.transaksi', 'no_do_manual') IS NULL
    EXEC sp_rename 'dbo.transaksi.no_do', 'no_do_manual', 'COLUMN';
GO
IF COL_LENGTH('dbo.transaksi', 'is_driver_changed') IS NULL
    ALTER TABLE dbo.transaksi ADD is_driver_changed BIT NOT NULL
        CONSTRAINT DF_Trx_DriverChanged DEFAULT (0);
IF COL_LENGTH('dbo.transaksi', 'prev_driver_id') IS NULL
    ALTER TABLE dbo.transaksi ADD prev_driver_id INT NULL;
IF COL_LENGTH('dbo.transaksi', 'driver_photo_path') IS NULL
    ALTER TABLE dbo.transaksi ADD driver_photo_path VARCHAR(255) NULL;
IF COL_LENGTH('dbo.transaksi', 'hash_keamanan') IS NULL
    ALTER TABLE dbo.transaksi ADD hash_keamanan VARCHAR(64) NULL;
GO
IF OBJECT_ID('FK_Trx_PrevDriver', 'F') IS NULL
    ALTER TABLE dbo.transaksi ADD CONSTRAINT FK_Trx_PrevDriver
        FOREIGN KEY (prev_driver_id) REFERENCES dbo.personel (id_personel);
GO

-- status_alur: tahap timbang/sortasi/lab tidak ada lagi
DECLARE @ck SYSNAME, @sql NVARCHAR(400);
WHILE 1 = 1
BEGIN
    SET @ck = NULL;
    SELECT TOP 1 @ck = name FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.transaksi') AND definition LIKE '%status_alur%'
      AND name <> 'CK_Trx_StatusAlur';
    IF @ck IS NULL BREAK;
    SET @sql = N'ALTER TABLE dbo.transaksi DROP CONSTRAINT ' + QUOTENAME(@ck);
    EXEC sp_executesql @sql;
END
GO
UPDATE dbo.transaksi SET status_alur = 'TERVERIFIKASI'
WHERE status_alur IN ('TIMBANG_1', 'INSPEKSI_PROSES', 'TIMBANG_2');
GO
IF OBJECT_ID('CK_Trx_StatusAlur', 'C') IS NULL
    ALTER TABLE dbo.transaksi ADD CONSTRAINT CK_Trx_StatusAlur CHECK (
        status_alur IN ('SECURITY_REGISTER', 'SCAN_WAJAH', 'TERVERIFIKASI', 'SELESAI', 'REJECTED')
    );
GO

/* ---------- 6. blacklist ---------- */
IF OBJECT_ID('dbo.blacklist', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.blacklist (
        id_blacklist         INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        tipe_entitas         VARCHAR(20)  NOT NULL,
        id_personel          INT          NULL,
        id_kendaraan         INT          NULL,
        no_surat_blacklist   VARCHAR(50)  NOT NULL,   -- nomor surat penetapan dari HO
        alasan_blacklist     VARCHAR(500) NOT NULL,   -- indisipliner / fraud / dll
        file_surat_blacklist VARCHAR(255) NULL,       -- path upload surat (PDF/JPG)
        tgl_blacklist        DATE         NOT NULL,
        created_by           INT          NOT NULL,   -- user HO
        created_at           DATETIME     NOT NULL CONSTRAINT DF_Blacklist_Created DEFAULT (GETDATE()),
        CONSTRAINT CK_Blacklist_Tipe CHECK (tipe_entitas IN ('PERSONEL', 'KENDARAAN')),
        CONSTRAINT CK_Blacklist_Target CHECK (
            (tipe_entitas = 'PERSONEL'  AND id_personel IS NOT NULL AND id_kendaraan IS NULL) OR
            (tipe_entitas = 'KENDARAAN' AND id_kendaraan IS NOT NULL AND id_personel IS NULL)
        ),
        CONSTRAINT FK_Blacklist_Personel  FOREIGN KEY (id_personel)  REFERENCES dbo.personel (id_personel),
        CONSTRAINT FK_Blacklist_Kendaraan FOREIGN KEY (id_kendaraan) REFERENCES dbo.kendaraan (id_kendaraan),
        CONSTRAINT FK_Blacklist_User      FOREIGN KEY (created_by)   REFERENCES dbo.users (id_user)
    );
    CREATE INDEX IX_Blacklist_Personel  ON dbo.blacklist (id_personel)  WHERE id_personel IS NOT NULL;
    CREATE INDEX IX_Blacklist_Kendaraan ON dbo.blacklist (id_kendaraan) WHERE id_kendaraan IS NOT NULL;
END
GO

/* ---------- 7. security_audit_logs ---------- */
IF OBJECT_ID('dbo.security_audit_logs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.security_audit_logs (
        id_log      INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        user_id     INT           NOT NULL,
        action_type VARCHAR(30)   NOT NULL,
        no_tiket    VARCHAR(50)   NULL,   -- diisi bila aktivitas terkait tiket
        details     NVARCHAR(MAX) NULL,   -- JSON detail aktivitas
        ip_address  VARCHAR(45)   NULL,   -- cukup untuk IPv6
        created_at  DATETIME      NOT NULL CONSTRAINT DF_SecAudit_Created DEFAULT (GETDATE()),
        CONSTRAINT CK_SecAudit_Action CHECK (action_type IN ('TRY_SCAN_BLACKLIST', 'OVERRIDE_DRIVER', 'MANUAL_INPUT')),
        CONSTRAINT CK_SecAudit_Json CHECK (details IS NULL OR ISJSON(details) = 1),
        CONSTRAINT FK_SecAudit_User FOREIGN KEY (user_id)  REFERENCES dbo.users (id_user),
        CONSTRAINT FK_SecAudit_Trx  FOREIGN KEY (no_tiket) REFERENCES dbo.transaksi (no_tiket)
    );
    CREATE INDEX IX_SecAudit_User_Waktu ON dbo.security_audit_logs (user_id, created_at);
END
GO

/* ---------- 8. Blacklist permanen ---------- */
CREATE OR ALTER TRIGGER dbo.TR_Personel_BlacklistPermanen ON dbo.personel
AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(is_blacklisted) AND EXISTS (
        SELECT 1 FROM inserted i JOIN deleted d ON d.id_personel = i.id_personel
        WHERE d.is_blacklisted = 1 AND i.is_blacklisted = 0)
    BEGIN
        RAISERROR('Blacklist personel bersifat permanen dan tidak bisa dicabut.', 16, 1);
        ROLLBACK TRANSACTION;
    END
END
GO
CREATE OR ALTER TRIGGER dbo.TR_Kendaraan_BlacklistPermanen ON dbo.kendaraan
AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(is_blacklisted) AND EXISTS (
        SELECT 1 FROM inserted i JOIN deleted d ON d.id_kendaraan = i.id_kendaraan
        WHERE d.is_blacklisted = 1 AND i.is_blacklisted = 0)
    BEGIN
        RAISERROR('Blacklist kendaraan bersifat permanen dan tidak bisa dicabut.', 16, 1);
        ROLLBACK TRANSACTION;
    END
END
GO
