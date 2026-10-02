/* =====================================================================
   Migrasi 005: Kontrak & DO (diisi HO) dan Void tiket (Admin)
   - supplier.tipe     -> CUSTOMER (perusahaan yang membeli / menjual) | PENGANGKUTAN (angkutan pihak ketiga)
   - delivery_order    No DO -> No Kontrak, jenis transaksi, customer, produk, pengangkutan
   - transaksi         + id_pengangkutan, + kolom void (status_alur = 'VOID')

   Jalankan SETELAH 001-004, di SSMS (ganti nama di baris USE). Aman dijalankan ulang.
   ===================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* ---------- 1. supplier.tipe ---------- */
DECLARE @ck SYSNAME, @sql NVARCHAR(400);
WHILE 1 = 1
BEGIN
    SET @ck = NULL;
    SELECT TOP 1 @ck = name FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.supplier') AND definition LIKE '%tipe%' AND name <> 'CK_Supplier_Tipe';
    IF @ck IS NULL BREAK;
    SET @sql = N'ALTER TABLE dbo.supplier DROP CONSTRAINT ' + QUOTENAME(@ck);
    EXEC sp_executesql @sql;
END
GO
UPDATE dbo.supplier SET tipe = 'CUSTOMER' WHERE tipe IN ('SUPPLIER_PEMBELIAN', 'BUYER_PENJUALAN');
IF OBJECT_ID('CK_Supplier_Tipe', 'C') IS NULL
    ALTER TABLE dbo.supplier ADD CONSTRAINT CK_Supplier_Tipe CHECK (tipe IN ('CUSTOMER', 'PENGANGKUTAN'));
GO

/* ---------- 2. delivery_order ---------- */
IF OBJECT_ID('dbo.delivery_order', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.delivery_order (
        id_do           INT IDENTITY(1,1) PRIMARY KEY,
        no_do           VARCHAR(50)  NOT NULL CONSTRAINT UX_DO_No UNIQUE,
        no_kontrak      VARCHAR(50)  NOT NULL,
        jenis_transaksi VARCHAR(20)  NOT NULL CONSTRAINT CK_DO_Jenis CHECK (jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
        id_customer     INT NOT NULL CONSTRAINT FK_DO_Customer REFERENCES dbo.supplier (id_supplier),
        id_produk       INT NOT NULL CONSTRAINT FK_DO_Produk REFERENCES dbo.produk (id_produk),
        id_pengangkutan INT NULL     CONSTRAINT FK_DO_Angkut REFERENCES dbo.supplier (id_supplier),   -- NULL = kendaraan sendiri
        tanggal_do      DATE NOT NULL CONSTRAINT DF_DO_Tanggal DEFAULT (CAST(GETDATE() AS DATE)),
        berlaku_sampai  DATE NULL,
        keterangan      VARCHAR(200) NULL,
        is_active       BIT NOT NULL CONSTRAINT DF_DO_Aktif DEFAULT (1),
        created_by      INT NULL CONSTRAINT FK_DO_User REFERENCES dbo.users (id_user),
        created_at      DATETIME NOT NULL CONSTRAINT DF_DO_Created DEFAULT (GETDATE())
    );
    CREATE INDEX IX_DO_Kontrak ON dbo.delivery_order (no_kontrak);
END
GO

/* ---------- 3. transaksi: pengangkutan & void ---------- */
IF COL_LENGTH('dbo.transaksi', 'id_pengangkutan') IS NULL
    ALTER TABLE dbo.transaksi ADD id_pengangkutan INT NULL
        CONSTRAINT FK_Trx_Angkut REFERENCES dbo.supplier (id_supplier);
IF COL_LENGTH('dbo.transaksi', 'alasan_void') IS NULL
    ALTER TABLE dbo.transaksi ADD alasan_void VARCHAR(255) NULL, void_by INT NULL
        CONSTRAINT FK_Trx_VoidBy REFERENCES dbo.users (id_user), void_at DATETIME NULL;
GO
