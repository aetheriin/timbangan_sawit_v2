SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 4a: jembatan timbang & penimbangan.
   - jembatan_timbang: beberapa timbangan per area (JT-1, JT-2, ...), masing-masing port serial sendiri
   - penimbangan: 1 baris per timbang (ke 1 = masuk, ke 2 = keluar). Keluar WAJIB di jembatan yang sama (trigger)
   - tabel timbangan lama dipindah ke penimbangan lalu DIHAPUS; dibaca lewat view v_timbangan (bentuk lama)
   Wajib setelah migrasi 010.
   ===================================================================================== */

/* ---------- 1. Jembatan timbang ---------- */
IF OBJECT_ID('dbo.jembatan_timbang', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.jembatan_timbang (
        id_jembatan   INT IDENTITY(1,1) PRIMARY KEY,
        id_comp_area  INT NOT NULL CONSTRAINT FK_Jembatan_Area REFERENCES dbo.comp_area (id_comp_area),
        kode          VARCHAR(10)   NOT NULL,
        nama          NVARCHAR(100) NOT NULL,
        port          VARCHAR(30)   NOT NULL,                 -- COM3 (Windows) / /dev/ttyUSB0
        baudrate      INT NOT NULL CONSTRAINT DF_Jembatan_Baud DEFAULT (9600),
        is_active     BIT NOT NULL CONSTRAINT DF_Jembatan_Aktif DEFAULT (1),
        created_at    DATETIME NOT NULL CONSTRAINT DF_Jembatan_Created DEFAULT (GETDATE()),
        CONSTRAINT UX_Jembatan_AreaKode UNIQUE (id_comp_area, kode)
    );
    INSERT INTO dbo.jembatan_timbang (id_comp_area, kode, nama, port)
    SELECT MIN(id_comp_area), 'JT-1', N'Jembatan Timbang 1', 'COM3' FROM dbo.comp_area;
END
GO

IF COL_LENGTH('dbo.transaksi', 'id_jembatan') IS NULL
    ALTER TABLE dbo.transaksi ADD id_jembatan INT NULL CONSTRAINT FK_Trx_Jembatan REFERENCES dbo.jembatan_timbang (id_jembatan);
GO

/* ---------- 2. Penimbangan ---------- */
IF OBJECT_ID('dbo.penimbangan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.penimbangan (
        no_tiket     VARCHAR(50) NOT NULL CONSTRAINT FK_Penimbangan_Trx REFERENCES dbo.transaksi (no_tiket),
        ke           TINYINT NOT NULL CONSTRAINT CK_Penimbangan_Ke CHECK (ke IN (1, 2)),
        id_jembatan  INT NOT NULL CONSTRAINT FK_Penimbangan_Jembatan REFERENCES dbo.jembatan_timbang (id_jembatan),
        berat_kg     DECIMAL(10, 2) NOT NULL,
        waktu        DATETIME NOT NULL CONSTRAINT DF_Penimbangan_Waktu DEFAULT (GETDATE()),
        operator     INT NULL CONSTRAINT FK_Penimbangan_Operator REFERENCES dbo.users (id_user),   -- NULL hanya data lama
        hash         CHAR(64) NULL,
        CONSTRAINT PK_Penimbangan PRIMARY KEY (no_tiket, ke)
    );
    CREATE INDEX IX_Penimbangan_Waktu ON dbo.penimbangan (waktu DESC);
END
GO

/* Data lama: PEMBELIAN / PENIMBANGAN_SAJA -> bruto = timbang ke-1, tara = ke-2; PENJUALAN sebaliknya */
IF OBJECT_ID('dbo.timbangan', 'U') IS NOT NULL
    EXEC(N'
    DECLARE @jt INT = (SELECT MIN(id_jembatan) FROM dbo.jembatan_timbang);
    INSERT INTO dbo.penimbangan (no_tiket, ke, id_jembatan, berat_kg, waktu, operator, hash)
    SELECT tb.no_tiket, 1, @jt,
           CASE WHEN t.jenis_transaksi = ''PENJUALAN'' THEN tb.berat_tara ELSE tb.berat_bruto END,
           COALESCE(CASE WHEN t.jenis_transaksi = ''PENJUALAN'' THEN tb.waktu_tara ELSE tb.waktu_bruto END, t.created_at),
           tb.operator_timbang_id, CASE WHEN t.jenis_transaksi = ''PENIMBANGAN_SAJA'' THEN tb.hash_keamanan END
    FROM dbo.timbangan tb JOIN dbo.transaksi t ON t.no_tiket = tb.no_tiket
    WHERE (CASE WHEN t.jenis_transaksi = ''PENJUALAN'' THEN tb.berat_tara ELSE tb.berat_bruto END) IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM dbo.penimbangan p WHERE p.no_tiket = tb.no_tiket AND p.ke = 1);

    INSERT INTO dbo.penimbangan (no_tiket, ke, id_jembatan, berat_kg, waktu, operator, hash)
    SELECT tb.no_tiket, 2, @jt,
           CASE WHEN t.jenis_transaksi = ''PENJUALAN'' THEN tb.berat_bruto ELSE tb.berat_tara END,
           COALESCE(CASE WHEN t.jenis_transaksi = ''PENJUALAN'' THEN tb.waktu_bruto ELSE tb.waktu_tara END, t.created_at),
           tb.operator_timbang_id, tb.hash_keamanan
    FROM dbo.timbangan tb JOIN dbo.transaksi t ON t.no_tiket = tb.no_tiket
    WHERE t.jenis_transaksi <> ''PENIMBANGAN_SAJA''
      AND tb.berat_bruto IS NOT NULL AND tb.berat_tara IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM dbo.penimbangan p WHERE p.no_tiket = tb.no_tiket AND p.ke = 2);

    UPDATE t SET t.id_jembatan = p.id_jembatan
    FROM dbo.transaksi t JOIN dbo.penimbangan p ON p.no_tiket = t.no_tiket AND p.ke = 1
    WHERE t.id_jembatan IS NULL;');
GO

IF OBJECT_ID('dbo.timbangan', 'U') IS NOT NULL
    DROP TABLE dbo.timbangan;
GO

/* ---------- 3. Aturan: keluar di jembatan yang sama dengan masuk ---------- */
CREATE OR ALTER TRIGGER dbo.TR_Penimbangan_JembatanSama ON dbo.penimbangan AFTER INSERT, UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted i
               JOIN dbo.penimbangan p1 ON p1.no_tiket = i.no_tiket AND p1.ke = 1
               WHERE i.ke = 2 AND i.id_jembatan <> p1.id_jembatan)
    BEGIN
        RAISERROR('Timbang keluar harus di jembatan timbang yang sama dengan timbang masuk.', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END
    IF EXISTS (SELECT 1 FROM inserted i WHERE i.ke = 2
               AND NOT EXISTS (SELECT 1 FROM dbo.penimbangan p1 WHERE p1.no_tiket = i.no_tiket AND p1.ke = 1))
    BEGIN
        RAISERROR('Timbang ke-2 hanya boleh setelah timbang ke-1.', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END
    UPDATE t SET t.id_jembatan = i.id_jembatan
    FROM dbo.transaksi t JOIN inserted i ON i.no_tiket = t.no_tiket AND i.ke = 1;
END
GO

/* ---------- 4. View bentuk lama (bruto / tara / netto) ---------- */
CREATE OR ALTER VIEW dbo.v_timbangan AS
SELECT t.no_tiket, t.jenis_transaksi, t.id_jembatan, j.kode AS kode_jembatan,
       CAST(CASE WHEN t.jenis_transaksi = 'PENJUALAN' THEN p2.berat_kg ELSE p1.berat_kg END AS FLOAT) AS berat_bruto,
       CASE WHEN t.jenis_transaksi = 'PENJUALAN' THEN p2.waktu ELSE p1.waktu END AS waktu_bruto,
       CAST(CASE WHEN t.jenis_transaksi = 'PENJUALAN' THEN p1.berat_kg
                 WHEN t.jenis_transaksi = 'PENIMBANGAN_SAJA' THEN NULL ELSE p2.berat_kg END AS FLOAT) AS berat_tara,
       CASE WHEN t.jenis_transaksi = 'PENJUALAN' THEN p1.waktu
            WHEN t.jenis_transaksi = 'PENIMBANGAN_SAJA' THEN NULL ELSE p2.waktu END AS waktu_tara,
       CAST(CASE WHEN t.jenis_transaksi = 'PENIMBANGAN_SAJA' THEN p1.berat_kg
                 WHEN p2.berat_kg IS NOT NULL THEN ABS(p1.berat_kg - p2.berat_kg) END AS FLOAT) AS berat_netto,
       COALESCE(p2.hash, p1.hash) AS hash_keamanan,
       COALESCE(p2.operator, p1.operator) AS operator_timbang_id
FROM dbo.transaksi t
LEFT JOIN dbo.penimbangan p1 ON p1.no_tiket = t.no_tiket AND p1.ke = 1
LEFT JOIN dbo.penimbangan p2 ON p2.no_tiket = t.no_tiket AND p2.ke = 2
LEFT JOIN dbo.jembatan_timbang j ON j.id_jembatan = t.id_jembatan;
GO
