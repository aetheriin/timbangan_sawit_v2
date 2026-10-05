SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 4b: alur tahap dinamis.
   - tahap (SECURITY, TIMBANG_1, SORTASI, LAB, TIMBANG_2), alur + alur_tahap (urutan tahap per alur)
   - produk.id_alur: produk menentukan alurnya (TBS -> sortasi, produk PKS -> lab)
   - mill per area menunjuk alur; transaksi.id_mill (tiket mengikuti tahap alur mill-nya)
   Wajib setelah migrasi 011.
   ===================================================================================== */

IF OBJECT_ID('dbo.tahap', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.tahap (
        kode    VARCHAR(20)  NOT NULL PRIMARY KEY,
        nama    NVARCHAR(50) NOT NULL,
        urutan  TINYINT NOT NULL
    );
    INSERT INTO dbo.tahap (kode, nama, urutan) VALUES
        ('SECURITY', N'Security', 1), ('TIMBANG_1', N'Timbang Masuk', 2), ('SORTASI', N'Sortasi', 3),
        ('LAB', N'Laboratorium', 4), ('TIMBANG_2', N'Timbang Keluar', 5);
END
GO

IF OBJECT_ID('dbo.alur', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.alur (
        id_alur    INT IDENTITY(1,1) PRIMARY KEY,
        kode       VARCHAR(20)   NOT NULL CONSTRAINT UX_Alur_Kode UNIQUE,
        nama       NVARCHAR(100) NOT NULL,
        is_active  BIT NOT NULL CONSTRAINT DF_Alur_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.alur (kode, nama) VALUES
        ('TBS', N'TBS: timbang - sortasi - timbang'),
        ('PKS', N'Produk PKS: timbang - lab - timbang'),
        ('TIMBANG_SAJA', N'Penimbangan saja (sekali timbang)');
END
GO

IF OBJECT_ID('dbo.alur_tahap', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.alur_tahap (
        id_alur     INT NOT NULL CONSTRAINT FK_AlurTahap_Alur REFERENCES dbo.alur (id_alur),
        urutan      TINYINT NOT NULL,
        kode_tahap  VARCHAR(20) NOT NULL CONSTRAINT FK_AlurTahap_Tahap REFERENCES dbo.tahap (kode),
        CONSTRAINT PK_AlurTahap PRIMARY KEY (id_alur, urutan),
        CONSTRAINT UX_AlurTahap_Tahap UNIQUE (id_alur, kode_tahap)
    );
    INSERT INTO dbo.alur_tahap (id_alur, urutan, kode_tahap)
    SELECT a.id_alur, v.urutan, v.tahap
    FROM (VALUES ('TBS', 1, 'SECURITY'), ('TBS', 2, 'TIMBANG_1'), ('TBS', 3, 'SORTASI'), ('TBS', 4, 'TIMBANG_2'),
                 ('PKS', 1, 'SECURITY'), ('PKS', 2, 'TIMBANG_1'), ('PKS', 3, 'LAB'), ('PKS', 4, 'TIMBANG_2'),
                 ('TIMBANG_SAJA', 1, 'SECURITY'), ('TIMBANG_SAJA', 2, 'TIMBANG_1')) v (alur, urutan, tahap)
    JOIN dbo.alur a ON a.kode = v.alur;
END
GO

/* ---------- Mill per area ---------- */
IF OBJECT_ID('dbo.mill', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.mill (
        id_mill       INT IDENTITY(1,1) PRIMARY KEY,
        id_comp_area  INT NOT NULL CONSTRAINT FK_Mill_Area REFERENCES dbo.comp_area (id_comp_area),
        kode          VARCHAR(10)   NOT NULL,
        nama          NVARCHAR(100) NOT NULL,
        id_alur       INT NOT NULL CONSTRAINT FK_Mill_Alur REFERENCES dbo.alur (id_alur),
        is_active     BIT NOT NULL CONSTRAINT DF_Mill_Aktif DEFAULT (1),
        CONSTRAINT UX_Mill_AreaKode UNIQUE (id_comp_area, kode)
    );
    INSERT INTO dbo.mill (id_comp_area, kode, nama, id_alur)
    SELECT ar.id_comp_area, v.kode, v.nama, al.id_alur
    FROM dbo.comp_area ar
    CROSS JOIN (VALUES ('TBS', N'Penerimaan TBS', 'TBS'), ('PKS', N'Produk PKS', 'PKS'),
                       ('TS', N'Penimbangan Saja', 'TIMBANG_SAJA')) v (kode, nama, alur)
    JOIN dbo.alur al ON al.kode = v.alur;
END
GO

/* ---------- Produk menentukan alur ---------- */
IF COL_LENGTH('dbo.produk', 'id_alur') IS NULL
    ALTER TABLE dbo.produk ADD id_alur INT NULL CONSTRAINT FK_Produk_Alur REFERENCES dbo.alur (id_alur);
GO
EXEC(N'UPDATE p SET p.id_alur = a.id_alur
       FROM dbo.produk p JOIN dbo.alur a ON a.kode = CASE WHEN p.kategori = ''TBS'' THEN ''TBS'' ELSE ''PKS'' END
       WHERE p.id_alur IS NULL');
GO
ALTER TABLE dbo.produk ALTER COLUMN id_alur INT NOT NULL;
GO

/* ---------- Tiket mengikuti mill ---------- */
IF COL_LENGTH('dbo.transaksi', 'id_mill') IS NULL
    ALTER TABLE dbo.transaksi ADD id_mill INT NULL CONSTRAINT FK_Trx_Mill REFERENCES dbo.mill (id_mill);
GO
/* Tiket lama: mill area pertama sesuai alur produk (penimbangan saja -> mill TIMBANG_SAJA) */
EXEC(N'UPDATE t SET t.id_mill = m.id_mill
       FROM dbo.transaksi t
       JOIN dbo.produk p ON p.id_produk = t.id_produk
       JOIN dbo.alur a ON a.id_alur = CASE WHEN t.jenis_transaksi = ''PENIMBANGAN_SAJA''
                                          THEN (SELECT id_alur FROM dbo.alur WHERE kode = ''TIMBANG_SAJA'') ELSE p.id_alur END
       JOIN dbo.mill m ON m.id_alur = a.id_alur
                      AND m.id_comp_area = (SELECT MIN(id_comp_area) FROM dbo.comp_area)
       WHERE t.id_mill IS NULL');
GO
