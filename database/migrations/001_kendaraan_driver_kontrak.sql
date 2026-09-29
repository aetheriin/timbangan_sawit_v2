/* =====================================================================
   Migrasi 001: relasi Truk <-> Supir dan Truk <-> Supplier (kontrak)

   Kasus yang ditangani:
   - Truk sama, supir beda      -> kendaraan_driver (1 truk bisa banyak supir, 1 supir utama)
   - Truk sama, supplier beda   -> kontrak_kendaraan (truk terikat kontrak dgn supplier/buyer, ada periode)
   - Tiket mencatat kontrak yang dipakai -> transaksi.id_kontrak

   Jalankan di SSMS pada database yang dipakai aplikasi (ganti nama di baris USE).
   Aman dijalankan ulang: setiap objek dicek dulu sebelum dibuat.
   ===================================================================== */
USE [DbSistemTimbangan_Test]
GO

IF OBJECT_ID('dbo.kendaraan_driver', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.kendaraan_driver (
        id_kendaraan_driver INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        id_kendaraan  INT NOT NULL,
        id_driver     INT NOT NULL,
        is_utama      BIT NOT NULL CONSTRAINT DF_KD_Utama DEFAULT (0),   -- supir utama truk ini (disarankan saat Create Ticket)
        is_active     BIT NOT NULL CONSTRAINT DF_KD_Active DEFAULT (1),
        created_by    INT NULL,
        created_at    DATETIME NOT NULL CONSTRAINT DF_KD_Created DEFAULT (GETDATE()),
        updated_at    DATETIME NOT NULL CONSTRAINT DF_KD_Updated DEFAULT (GETDATE()),
        CONSTRAINT UQ_KD_Kendaraan_Driver UNIQUE (id_kendaraan, id_driver),
        CONSTRAINT FK_KD_Kendaraan FOREIGN KEY (id_kendaraan) REFERENCES dbo.kendaraan (id_kendaraan),
        CONSTRAINT FK_KD_Driver    FOREIGN KEY (id_driver)    REFERENCES dbo.driver (id_driver),
        CONSTRAINT FK_KD_User      FOREIGN KEY (created_by)   REFERENCES dbo.users (id_user)
    );
END
GO

IF OBJECT_ID('dbo.kontrak_kendaraan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.kontrak_kendaraan (
        id_kontrak       INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        no_kontrak       VARCHAR(50) NULL,
        id_kendaraan     INT NOT NULL,
        id_supplier      INT NOT NULL,
        id_produk        INT NULL,            -- produk default kontrak (opsional)
        jenis_transaksi  VARCHAR(20) NULL,    -- jenis default kontrak (opsional)
        tanggal_mulai    DATE NOT NULL,
        tanggal_selesai  DATE NULL,           -- NULL = tanpa batas waktu
        is_active        BIT NOT NULL CONSTRAINT DF_KK_Active DEFAULT (1),
        keterangan       VARCHAR(255) NULL,
        created_by       INT NULL,
        created_at       DATETIME NOT NULL CONSTRAINT DF_KK_Created DEFAULT (GETDATE()),
        CONSTRAINT CK_KK_Jenis CHECK (jenis_transaksi IS NULL OR jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
        CONSTRAINT CK_KK_Periode CHECK (tanggal_selesai IS NULL OR tanggal_selesai >= tanggal_mulai),
        CONSTRAINT FK_KK_Kendaraan FOREIGN KEY (id_kendaraan) REFERENCES dbo.kendaraan (id_kendaraan),
        CONSTRAINT FK_KK_Supplier  FOREIGN KEY (id_supplier)  REFERENCES dbo.supplier (id_supplier),
        CONSTRAINT FK_KK_Produk    FOREIGN KEY (id_produk)    REFERENCES dbo.produk (id_produk),
        CONSTRAINT FK_KK_User      FOREIGN KEY (created_by)   REFERENCES dbo.users (id_user)
    );
    CREATE INDEX IX_KK_Kendaraan ON dbo.kontrak_kendaraan (id_kendaraan, is_active);
END
GO

IF COL_LENGTH('dbo.transaksi', 'id_kontrak') IS NULL
BEGIN
    ALTER TABLE dbo.transaksi ADD id_kontrak INT NULL;
END
GO

IF OBJECT_ID('FK_Trx_Kontrak', 'F') IS NULL
BEGIN
    ALTER TABLE dbo.transaksi ADD CONSTRAINT FK_Trx_Kontrak
        FOREIGN KEY (id_kontrak) REFERENCES dbo.kontrak_kendaraan (id_kontrak);
END
GO
