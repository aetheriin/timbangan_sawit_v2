SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 4c: kontrak -> DO -> pengangkutan.
   - supplier_peran: satu mitra (tabel supplier) boleh berperan CUSTOMER sekaligus PENGANGKUTAN (kolom tipe dihapus)
   - kontrak: 1 kontrak = 1 produk = 1 customer; delivery_order menunjuk kontrak (1 kontrak = 1 DO)
   - do_pengangkutan: 1 DO boleh beberapa pengangkut: PENGIRIM / PENERIMA (kendaraan sendiri) / PIHAK_KETIGA
   - transaksi.id_do + cara_angkut (id_pengangkutan hanya untuk PIHAK_KETIGA)
   Wajib setelah migrasi 012.
   ===================================================================================== */

/* ---------- 1. Peran mitra ---------- */
-- sudah di-rename menjadi mitra_peran oleh migrasi 016 -> lewati (aman dijalankan ulang)
IF OBJECT_ID('dbo.supplier_peran', 'U') IS NULL AND OBJECT_ID('dbo.mitra_peran', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.supplier_peran (
        id_supplier  INT NOT NULL CONSTRAINT FK_SupPeran_Supplier REFERENCES dbo.supplier (id_supplier),
        peran        VARCHAR(20) NOT NULL CONSTRAINT CK_SupPeran_Peran CHECK (peran IN ('CUSTOMER', 'PENGANGKUTAN')),
        CONSTRAINT PK_SupplierPeran PRIMARY KEY (id_supplier, peran)
    );
END
GO
IF COL_LENGTH('dbo.supplier', 'tipe') IS NOT NULL
BEGIN
    EXEC(N'INSERT INTO dbo.supplier_peran (id_supplier, peran)
           SELECT s.id_supplier, s.tipe FROM dbo.supplier s
           WHERE s.tipe IN (''CUSTOMER'', ''PENGANGKUTAN'')
             AND NOT EXISTS (SELECT 1 FROM dbo.supplier_peran p WHERE p.id_supplier = s.id_supplier AND p.peran = s.tipe)');
    DECLARE @sql NVARCHAR(MAX) = N'';
    SELECT @sql += N'ALTER TABLE dbo.supplier DROP CONSTRAINT ' + QUOTENAME(c.name) + N';'
    FROM sys.check_constraints c WHERE c.parent_object_id = OBJECT_ID('dbo.supplier')
      AND c.definition LIKE '%tipe%';
    SELECT @sql += N'ALTER TABLE dbo.supplier DROP CONSTRAINT ' + QUOTENAME(d.name) + N';'
    FROM sys.default_constraints d
    JOIN sys.columns col ON col.object_id = d.parent_object_id AND col.column_id = d.parent_column_id
    WHERE d.parent_object_id = OBJECT_ID('dbo.supplier') AND col.name = 'tipe';
    EXEC (@sql);
    ALTER TABLE dbo.supplier DROP COLUMN tipe;
END
GO

/* ---------- 2. Kontrak ---------- */
IF OBJECT_ID('dbo.kontrak', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.kontrak (
        id_kontrak       INT IDENTITY(1,1) PRIMARY KEY,
        no_kontrak       VARCHAR(50) NOT NULL CONSTRAINT UX_Kontrak_No UNIQUE,
        jenis_transaksi  VARCHAR(20) NOT NULL,
        id_customer      INT NOT NULL CONSTRAINT FK_Kontrak_Customer REFERENCES dbo.supplier (id_supplier),
        id_produk        INT NOT NULL CONSTRAINT FK_Kontrak_Produk REFERENCES dbo.produk (id_produk),
        tanggal          DATE NOT NULL CONSTRAINT DF_Kontrak_Tanggal DEFAULT (CAST(GETDATE() AS DATE)),
        qty_kg           DECIMAL(14, 2) NULL,
        harga_per_kg     DECIMAL(14, 2) NULL,
        keterangan       VARCHAR(200) NULL,
        is_active        BIT NOT NULL CONSTRAINT DF_Kontrak_Aktif DEFAULT (1),
        created_by       INT NULL CONSTRAINT FK_Kontrak_User REFERENCES dbo.users (id_user),
        created_at       DATETIME NOT NULL CONSTRAINT DF_Kontrak_Created DEFAULT (GETDATE()),
        CONSTRAINT CK_Kontrak_Jenis CHECK (jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
        CONSTRAINT CK_Kontrak_Qty CHECK (qty_kg IS NULL OR qty_kg > 0)
    );
END
GO

/* ---------- 3. DO menunjuk kontrak ---------- */
IF COL_LENGTH('dbo.delivery_order', 'id_kontrak') IS NULL
    ALTER TABLE dbo.delivery_order ADD id_kontrak INT NULL CONSTRAINT FK_DO_Kontrak REFERENCES dbo.kontrak (id_kontrak);
GO

IF OBJECT_ID('dbo.do_pengangkutan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.do_pengangkutan (
        id_do_angkut     INT IDENTITY(1,1) PRIMARY KEY,
        id_do            INT NOT NULL CONSTRAINT FK_DoAngkut_DO REFERENCES dbo.delivery_order (id_do),
        cara_angkut      VARCHAR(15) NOT NULL,
        id_pengangkutan  INT NULL CONSTRAINT FK_DoAngkut_Supplier REFERENCES dbo.supplier (id_supplier),
        qty_kg           DECIMAL(14, 2) NULL,               -- alokasi (opsional), total <= kontrak.qty_kg
        CONSTRAINT CK_DoAngkut_Cara CHECK (cara_angkut IN ('PENGIRIM', 'PENERIMA', 'PIHAK_KETIGA')),
        CONSTRAINT CK_DoAngkut_PihakKetiga CHECK ((cara_angkut = 'PIHAK_KETIGA' AND id_pengangkutan IS NOT NULL)
                                                  OR (cara_angkut <> 'PIHAK_KETIGA' AND id_pengangkutan IS NULL)),
        CONSTRAINT UX_DoAngkut UNIQUE (id_do, cara_angkut, id_pengangkutan)
    );
END
GO

/* Data lama: 1 kontrak per No Kontrak teks. No Kontrak yang dipakai beberapa DO -> DO berikutnya
   mendapat kontrak sendiri (No Kontrak + '/' + No DO), karena 1 kontrak = 1 DO. */
IF COL_LENGTH('dbo.delivery_order', 'no_kontrak') IS NOT NULL
BEGIN
    EXEC(N'
    ;WITH d AS (
        SELECT id_do, no_do, no_kontrak, jenis_transaksi, id_customer, id_produk, tanggal_do, keterangan, is_active,
               created_by, created_at, ROW_NUMBER() OVER (PARTITION BY no_kontrak ORDER BY created_at, id_do) AS rn
        FROM dbo.delivery_order WHERE id_kontrak IS NULL)
    INSERT INTO dbo.kontrak (no_kontrak, jenis_transaksi, id_customer, id_produk, tanggal, keterangan, is_active, created_by, created_at)
    SELECT LEFT(CASE WHEN rn = 1 THEN no_kontrak ELSE no_kontrak + ''/'' + no_do END, 50),
           jenis_transaksi, id_customer, id_produk, tanggal_do, keterangan, is_active, created_by, created_at
    FROM d
    WHERE NOT EXISTS (SELECT 1 FROM dbo.kontrak k
                      WHERE k.no_kontrak = LEFT(CASE WHEN d.rn = 1 THEN d.no_kontrak ELSE d.no_kontrak + ''/'' + d.no_do END, 50));

    ;WITH d AS (
        SELECT id_do, no_do, no_kontrak, ROW_NUMBER() OVER (PARTITION BY no_kontrak ORDER BY created_at, id_do) AS rn
        FROM dbo.delivery_order WHERE id_kontrak IS NULL)
    UPDATE o SET o.id_kontrak = k.id_kontrak
    FROM dbo.delivery_order o JOIN d ON d.id_do = o.id_do
    JOIN dbo.kontrak k ON k.no_kontrak = LEFT(CASE WHEN d.rn = 1 THEN d.no_kontrak ELSE d.no_kontrak + ''/'' + d.no_do END, 50);

    /* Pengangkutan: id_pengangkutan -> PIHAK_KETIGA; NULL (kendaraan customer sendiri) -> PENGIRIM pada pembelian,
       PENERIMA pada penjualan */
    INSERT INTO dbo.do_pengangkutan (id_do, cara_angkut, id_pengangkutan)
    SELECT o.id_do,
           CASE WHEN o.id_pengangkutan IS NOT NULL THEN ''PIHAK_KETIGA''
                WHEN o.jenis_transaksi = ''PENJUALAN'' THEN ''PENERIMA'' ELSE ''PENGIRIM'' END,
           o.id_pengangkutan
    FROM dbo.delivery_order o
    WHERE NOT EXISTS (SELECT 1 FROM dbo.do_pengangkutan a WHERE a.id_do = o.id_do);');
END
GO

/* Kolom lama DO pindah ke kontrak / do_pengangkutan: hapus constraint, index, lalu kolomnya */
IF COL_LENGTH('dbo.delivery_order', 'no_kontrak') IS NOT NULL
BEGIN
    DECLARE @sql NVARCHAR(MAX) = N'';
    SELECT @sql += N'ALTER TABLE dbo.delivery_order DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';'
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fc ON fc.constraint_object_id = fk.object_id
    JOIN sys.columns c ON c.object_id = fc.parent_object_id AND c.column_id = fc.parent_column_id
    WHERE fk.parent_object_id = OBJECT_ID('dbo.delivery_order') AND c.name IN ('id_customer', 'id_produk', 'id_pengangkutan');
    SELECT @sql += N'ALTER TABLE dbo.delivery_order DROP CONSTRAINT ' + QUOTENAME(cc.name) + N';'
    FROM sys.check_constraints cc WHERE cc.parent_object_id = OBJECT_ID('dbo.delivery_order')
      AND cc.definition LIKE '%jenis_transaksi%';
    SELECT @sql += N'DROP INDEX ' + QUOTENAME(i.name) + N' ON dbo.delivery_order;'
    FROM sys.indexes i
    WHERE i.object_id = OBJECT_ID('dbo.delivery_order') AND i.is_primary_key = 0 AND i.is_unique_constraint = 0
      AND EXISTS (SELECT 1 FROM sys.index_columns ic JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
                  WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id
                    AND c.name IN ('no_kontrak', 'jenis_transaksi', 'id_customer', 'id_produk', 'id_pengangkutan'));
    EXEC (@sql);
    ALTER TABLE dbo.delivery_order DROP COLUMN no_kontrak, jenis_transaksi, id_customer, id_produk, id_pengangkutan;
END
GO
IF COLUMNPROPERTY(OBJECT_ID('dbo.delivery_order'), 'id_kontrak', 'AllowsNull') = 1
    ALTER TABLE dbo.delivery_order ALTER COLUMN id_kontrak INT NOT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_DO_Kontrak' AND object_id = OBJECT_ID('dbo.delivery_order'))
    CREATE UNIQUE INDEX UX_DO_Kontrak ON dbo.delivery_order (id_kontrak);     -- 1 kontrak = 1 DO
GO

/* ---------- 4. Transaksi: DO + cara angkut ---------- */
IF COL_LENGTH('dbo.transaksi', 'id_do') IS NULL
    ALTER TABLE dbo.transaksi ADD id_do INT NULL CONSTRAINT FK_Trx_DO REFERENCES dbo.delivery_order (id_do);
GO
IF COL_LENGTH('dbo.transaksi', 'cara_angkut') IS NULL
    ALTER TABLE dbo.transaksi ADD cara_angkut VARCHAR(15) NULL;
GO
EXEC(N'UPDATE t SET t.id_do = o.id_do FROM dbo.transaksi t JOIN dbo.delivery_order o ON o.no_do = t.no_do
       WHERE t.id_do IS NULL AND t.no_do IS NOT NULL;
       UPDATE dbo.transaksi SET cara_angkut = CASE WHEN id_pengangkutan IS NOT NULL THEN ''PIHAK_KETIGA''
                                                   WHEN jenis_transaksi = ''PENJUALAN'' THEN ''PENERIMA'' ELSE ''PENGIRIM'' END
       WHERE cara_angkut IS NULL;');
GO
IF COLUMNPROPERTY(OBJECT_ID('dbo.transaksi'), 'cara_angkut', 'AllowsNull') = 1
    ALTER TABLE dbo.transaksi ALTER COLUMN cara_angkut VARCHAR(15) NOT NULL;
GO
IF OBJECT_ID('dbo.CK_Trx_CaraAngkut', 'C') IS NULL
    ALTER TABLE dbo.transaksi ADD CONSTRAINT CK_Trx_CaraAngkut CHECK (
        (cara_angkut = 'PIHAK_KETIGA' AND id_pengangkutan IS NOT NULL)
        OR (cara_angkut IN ('PENGIRIM', 'PENERIMA') AND id_pengangkutan IS NULL));
GO
