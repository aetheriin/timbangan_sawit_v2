SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Unit timbang (tabel mill) dihapus. Setiap transaksi langsung menyimpan:
   - id_comp_area : area tempat transaksi (area akun security yang mencatat)
   - id_alur      : alur tahap (alur produk; Penimbangan saja = TIMBANG_SAJA; Pos Security = POS_SAJA)
   Isi lama diambil dari unit timbang; tiket tanpa unit timbang memakai area security & alur produk.
   Aman dijalankan ulang.
   ===================================================================================== */
IF COL_LENGTH('dbo.transaksi', 'id_comp_area') IS NULL
    ALTER TABLE dbo.transaksi ADD id_comp_area INT NULL CONSTRAINT FK_Trx_Area REFERENCES dbo.comp_area (id_comp_area);
IF COL_LENGTH('dbo.transaksi', 'id_alur') IS NULL
    ALTER TABLE dbo.transaksi ADD id_alur INT NULL CONSTRAINT FK_Trx_Alur REFERENCES dbo.alur (id_alur);
GO

IF OBJECT_ID('dbo.mill') IS NOT NULL AND COL_LENGTH('dbo.transaksi', 'id_mill') IS NOT NULL
    EXEC('UPDATE t SET id_comp_area = COALESCE(t.id_comp_area, m.id_comp_area), id_alur = COALESCE(t.id_alur, m.id_alur)
          FROM dbo.transaksi t JOIN dbo.mill m ON m.id_mill = t.id_mill');
GO
UPDATE t SET id_comp_area = u.id_comp_area FROM dbo.transaksi t JOIN dbo.akun u ON u.id_user = t.security_id
WHERE t.id_comp_area IS NULL;
UPDATE t SET id_alur = CASE WHEN t.jenis_transaksi = 'PENIMBANGAN_SAJA'
                            THEN (SELECT id_alur FROM dbo.alur WHERE kode = 'TIMBANG_SAJA') ELSE p.id_alur END
FROM dbo.transaksi t JOIN dbo.produk p ON p.id_produk = t.id_produk
WHERE t.id_alur IS NULL;
GO
ALTER TABLE dbo.transaksi ALTER COLUMN id_comp_area INT NOT NULL;
GO

-- Lepas id_mill dari transaksi (indeks, FK apa pun namanya), lalu hapus tabel mill
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Trx_Keluar' AND object_id = OBJECT_ID('dbo.transaksi'))
    DROP INDEX IX_Trx_Keluar ON dbo.transaksi;
GO
IF COL_LENGTH('dbo.transaksi', 'id_mill') IS NOT NULL
BEGIN
    DECLARE @sql NVARCHAR(MAX) = N'';
    SELECT @sql += N'ALTER TABLE dbo.transaksi DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';'
    FROM sys.foreign_keys fk JOIN sys.foreign_key_columns fc ON fc.constraint_object_id = fk.object_id
    JOIN sys.columns c ON c.object_id = fc.parent_object_id AND c.column_id = fc.parent_column_id
    WHERE fk.parent_object_id = OBJECT_ID('dbo.transaksi') AND c.name = 'id_mill';
    SELECT @sql += N'DROP INDEX ' + QUOTENAME(i.name) + N' ON dbo.transaksi;'
    FROM sys.indexes i JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    WHERE i.object_id = OBJECT_ID('dbo.transaksi') AND c.name = 'id_mill' AND i.is_primary_key = 0;
    EXEC sp_executesql @sql;
    ALTER TABLE dbo.transaksi DROP COLUMN id_mill;
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Trx_Keluar' AND object_id = OBJECT_ID('dbo.transaksi'))
    CREATE INDEX IX_Trx_Keluar ON dbo.transaksi (waktu_keluar) INCLUDE (id_kendaraan, id_comp_area, status_alur);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Trx_Area_Created' AND object_id = OBJECT_ID('dbo.transaksi'))
    CREATE INDEX IX_Trx_Area_Created ON dbo.transaksi (id_comp_area, created_at DESC);
GO
IF OBJECT_ID('dbo.TR_LogData_mill') IS NOT NULL DROP TRIGGER dbo.TR_LogData_mill;
IF OBJECT_ID('dbo.mill') IS NOT NULL DROP TABLE dbo.mill;
GO
