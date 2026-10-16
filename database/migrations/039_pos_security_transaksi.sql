SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Tahap 1 Security memakai tabel transaksi (= WeightBridge di ERD), tanpa tabel baru:
   - transaksi.waktu_keluar / keluar_oleh: jam keluar gerbang (Logbook). Jam masuk = created_at, petugas = security_id.
   - Alur POS_SAJA (tahap SECURITY saja) + unit timbang "POS" per area: kendaraan dari Pos Security tercatat sebagai
     transaksi biasa (jenis, customer, produk, supir, pengangkutan) dan selesai saat dicatat keluar.
     Tahap 2 (tiket penuh) cukup mematikan menu Pos Security; Logbook tetap dipakai untuk tiket biasa.
   - Tiket lama yang sudah selesai / ditolak / batal diberi jam keluar (timbang terakhir, atau jam dibuat)
     supaya tidak muncul sebagai "masih di dalam".
   Aman dijalankan ulang.
   ===================================================================================== */
IF COL_LENGTH('dbo.transaksi', 'waktu_keluar') IS NULL
    ALTER TABLE dbo.transaksi ADD waktu_keluar DATETIME NULL;
IF COL_LENGTH('dbo.transaksi', 'keluar_oleh') IS NULL
    ALTER TABLE dbo.transaksi ADD keluar_oleh INT NULL CONSTRAINT FK_Trx_Keluar REFERENCES dbo.akun (id_user);
GO

UPDATE t SET waktu_keluar = COALESCE((SELECT MAX(p.waktu) FROM dbo.penimbangan p WHERE p.no_tiket = t.no_tiket), t.created_at)
FROM dbo.transaksi t
WHERE t.waktu_keluar IS NULL AND t.status_alur IN ('SELESAI', 'REJECTED', 'VOID');
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Trx_Keluar' AND object_id = OBJECT_ID('dbo.transaksi'))
    CREATE INDEX IX_Trx_Keluar ON dbo.transaksi (waktu_keluar) INCLUDE (id_kendaraan, id_mill, status_alur);
GO

IF NOT EXISTS (SELECT 1 FROM dbo.alur WHERE kode = 'POS_SAJA')
    INSERT INTO dbo.alur (kode, nama) VALUES ('POS_SAJA', N'Pos Security saja (catat masuk / keluar, tanpa timbang)');
INSERT INTO dbo.alur_tahap (id_alur, urutan, kode_tahap)
SELECT a.id_alur, 1, 'SECURITY' FROM dbo.alur a
WHERE a.kode = 'POS_SAJA' AND NOT EXISTS (SELECT 1 FROM dbo.alur_tahap x WHERE x.id_alur = a.id_alur);
GO

-- Unit timbang POS di setiap area yang sudah punya unit timbang (area lain: tambah di Admin › Organisasi)
INSERT INTO dbo.mill (id_comp_area, kode, nama, id_alur)
SELECT ar.id_comp_area, 'POS', N'Pos Security', a.id_alur
FROM dbo.comp_area ar CROSS JOIN dbo.alur a
WHERE a.kode = 'POS_SAJA'
  AND EXISTS (SELECT 1 FROM dbo.mill m WHERE m.id_comp_area = ar.id_comp_area)
  AND NOT EXISTS (SELECT 1 FROM dbo.mill m WHERE m.id_comp_area = ar.id_comp_area AND (m.kode = 'POS' OR m.id_alur = a.id_alur));
GO
