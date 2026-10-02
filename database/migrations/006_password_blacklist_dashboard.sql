/* =====================================================================
   Migrasi 006: password kedaluwarsa, info terkait blacklist, riwayat standar mutu, dashboard harga
   - users.password_changed_at  (NULL = wajib ganti saat login; user lama diisi tanggal sekarang)
   - blacklist + no_plat_terkait, id_customer_terkait, id_pengangkutan_terkait
   - standar_mutu_log           riwayat perubahan standar mutu (tab Laboratorium, 2 hari terakhir)
   - harga_harian               harga CPO, kernel, OER CPO, biaya olah per tanggal (Dashboard)

   Jalankan SETELAH 001-005, di SSMS (ganti nama di baris USE). Aman dijalankan ulang.
   ===================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* ---------- 1. users.password_changed_at ---------- */
IF COL_LENGTH('dbo.users', 'password_changed_at') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD password_changed_at DATETIME NULL;
    EXEC('UPDATE dbo.users SET password_changed_at = GETDATE()');   -- user lama tidak langsung dipaksa ganti
END
GO

/* ---------- 2. blacklist: info saat ditetapkan ---------- */
IF COL_LENGTH('dbo.blacklist', 'no_plat_terkait') IS NULL
    ALTER TABLE dbo.blacklist ADD
        no_plat_terkait          VARCHAR(15) NULL,
        id_customer_terkait      INT NULL CONSTRAINT FK_Blacklist_Customer REFERENCES dbo.supplier (id_supplier),
        id_pengangkutan_terkait  INT NULL CONSTRAINT FK_Blacklist_Angkut REFERENCES dbo.supplier (id_supplier);
GO

/* ---------- 3. standar_mutu_log ---------- */
IF OBJECT_ID('dbo.standar_mutu_log', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.standar_mutu_log (
        id_log        INT IDENTITY(1,1) PRIMARY KEY,
        id_produk     INT NOT NULL CONSTRAINT FK_StdLog_Produk REFERENCES dbo.produk (id_produk),
        maks_ffa      FLOAT NOT NULL,
        maks_air      FLOAT NOT NULL,
        maks_kotoran  FLOAT NOT NULL,
        updated_by    INT NULL CONSTRAINT FK_StdLog_User REFERENCES dbo.users (id_user),
        updated_at    DATETIME NOT NULL CONSTRAINT DF_StdLog_Waktu DEFAULT (GETDATE())
    );
    CREATE INDEX IX_StdLog_Waktu ON dbo.standar_mutu_log (updated_at DESC);
END
GO

/* ---------- 4. harga_harian ---------- */
IF OBJECT_ID('dbo.harga_harian', 'U') IS NULL
    CREATE TABLE dbo.harga_harian (
        tanggal       DATE PRIMARY KEY,
        harga_cpo     DECIMAL(12,2) NOT NULL,     -- Rp/kg
        harga_kernel  DECIMAL(12,2) NOT NULL,     -- Rp/kg
        oer_cpo       DECIMAL(5,2)  NOT NULL,     -- %
        biaya_olah    DECIMAL(12,2) NOT NULL,     -- Rp/kg TBS
        updated_by    INT NULL CONSTRAINT FK_Harga_User REFERENCES dbo.users (id_user),
        updated_at    DATETIME NOT NULL CONSTRAINT DF_Harga_Updated DEFAULT (GETDATE()),
        CONSTRAINT CK_Harga_Oer CHECK (oer_cpo BETWEEN 0 AND 100)
    );
GO
