/* =====================================================================
   Migrasi 004: halaman Admin (super admin)
   - users            + last_login (Kelola User), + sesi_versi (paksa keluar semua sesi user)
   - pengaturan       pengaturan site yang bisa diubah admin tanpa restart (fallback ke .env)
   - perangkat_kiosk  pos kamera kiosk + token per pos (hash SHA-256, token asli tidak disimpan)
   - admin_audit_logs jejak semua aksi admin

   Jalankan SETELAH 001-003, di SSMS (ganti nama di baris USE).
   Aman dijalankan ulang: setiap objek dicek dulu sebelum dibuat.
   ===================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* ---------- 1. users ---------- */
IF COL_LENGTH('dbo.users', 'last_login') IS NULL
    ALTER TABLE dbo.users ADD last_login DATETIME NULL;
IF COL_LENGTH('dbo.users', 'sesi_versi') IS NULL
    ALTER TABLE dbo.users ADD sesi_versi INT NOT NULL CONSTRAINT DF_Users_SesiVersi DEFAULT (0);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Users_Username' AND object_id = OBJECT_ID('dbo.users'))
   AND NOT EXISTS (SELECT username FROM dbo.users GROUP BY username HAVING COUNT(*) > 1)
    CREATE UNIQUE INDEX UX_Users_Username ON dbo.users (username);
GO

/* ---------- 2. pengaturan (kunci -> nilai) ---------- */
IF OBJECT_ID('dbo.pengaturan', 'U') IS NULL
    CREATE TABLE dbo.pengaturan (
        kunci       VARCHAR(50)  NOT NULL PRIMARY KEY,
        nilai       VARCHAR(200) NOT NULL,
        updated_by  INT NULL CONSTRAINT FK_Pengaturan_User REFERENCES dbo.users (id_user),
        updated_at  DATETIME NOT NULL CONSTRAINT DF_Pengaturan_Updated DEFAULT (GETDATE())
    );
GO

/* ---------- 3. perangkat_kiosk ---------- */
IF OBJECT_ID('dbo.perangkat_kiosk', 'U') IS NULL
    CREATE TABLE dbo.perangkat_kiosk (
        id_pos      VARCHAR(30)  NOT NULL PRIMARY KEY,          -- dikirim kiosk di header X-Kiosk-Id
        nama        VARCHAR(100) NOT NULL,
        lokasi      VARCHAR(100) NULL,
        token_hash  CHAR(64)     NOT NULL,                      -- SHA-256 dari token
        is_active   BIT NOT NULL CONSTRAINT DF_Kiosk_Aktif DEFAULT (1),
        created_at  DATETIME NOT NULL CONSTRAINT DF_Kiosk_Created DEFAULT (GETDATE()),
        CONSTRAINT CK_Kiosk_Id CHECK (id_pos NOT LIKE '%[^A-Z0-9_-]%')
    );
GO

/* ---------- 4. admin_audit_logs ---------- */
IF OBJECT_ID('dbo.admin_audit_logs', 'U') IS NULL
    CREATE TABLE dbo.admin_audit_logs (
        id_log      BIGINT IDENTITY(1,1) PRIMARY KEY,
        user_id     INT NOT NULL CONSTRAINT FK_AdminAudit_User REFERENCES dbo.users (id_user),
        aksi        VARCHAR(40)   NOT NULL,
        target      VARCHAR(100)  NULL,
        detail      NVARCHAR(500) NULL,
        ip_address  VARCHAR(45)   NULL,
        created_at  DATETIME NOT NULL CONSTRAINT DF_AdminAudit_Created DEFAULT (GETDATE())
    );
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_AdminAudit_Created' AND object_id = OBJECT_ID('dbo.admin_audit_logs'))
    CREATE INDEX IX_AdminAudit_Created ON dbo.admin_audit_logs (created_at DESC);
GO
