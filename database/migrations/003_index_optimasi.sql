/* =====================================================================
   Migrasi 003: index untuk query yang paling sering dipakai aplikasi
   (lihat docs/OPTIMASI_WEB.md poin 8). Tidak mengubah data / struktur tabel.

   Jalankan SETELAH 001 & 002, di SSMS (ganti nama di baris USE).
   Aman dijalankan ulang: setiap index dicek dulu sebelum dibuat.
   ===================================================================== */
USE [DbSistemTimbangan_Test]
GO

-- List Ticket Aktif & lookup tiket aktif per plat: WHERE status_alur NOT IN (...) ORDER BY created_at
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Trx_Status_Created' AND object_id = OBJECT_ID('dbo.transaksi'))
    CREATE INDEX IX_Trx_Status_Created ON dbo.transaksi (status_alur, created_at DESC)
        INCLUDE (id_kendaraan, id_supplier, id_driver);
GO
-- Lookup plat (tiket aktif, riwayat supir terakhir truk)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Trx_Kendaraan_Created' AND object_id = OBJECT_ID('dbo.transaksi'))
    CREATE INDEX IX_Trx_Kendaraan_Created ON dbo.transaksi (id_kendaraan, created_at DESC);
GO
-- History Timbangan per supplier 7 hari
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Trx_Supplier_Created' AND object_id = OBJECT_ID('dbo.transaksi'))
    CREATE INDEX IX_Trx_Supplier_Created ON dbo.transaksi (id_supplier, created_at DESC);
GO
-- History Driver, truk terakhir personel (menu Blacklist)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Trx_Driver_Created' AND object_id = OBJECT_ID('dbo.transaksi'))
    CREATE INDEX IX_Trx_Driver_Created ON dbo.transaksi (id_driver, created_at DESC);
GO
-- Jejak tahap per tiket
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Timeline_Tiket' AND object_id = OBJECT_ID('dbo.timeline_monitoring'))
    CREATE INDEX IX_Timeline_Tiket ON dbo.timeline_monitoring (no_tiket);
GO
-- Supir terdaftar per truk & truk per supir
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_KD_Driver' AND object_id = OBJECT_ID('dbo.kendaraan_driver'))
    CREATE INDEX IX_KD_Driver ON dbo.kendaraan_driver (id_driver) INCLUDE (id_kendaraan, is_active, is_utama);
GO
-- Kontrak berlaku per truk + supplier
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_KK_Kendaraan_Supplier' AND object_id = OBJECT_ID('dbo.kontrak_kendaraan'))
    CREATE INDEX IX_KK_Kendaraan_Supplier ON dbo.kontrak_kendaraan (id_kendaraan, id_supplier, is_active);
GO
-- Daftar personel aktif (filter kategori)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Personel_Aktif_Kategori' AND object_id = OBJECT_ID('dbo.personel'))
    CREATE INDEX IX_Personel_Aktif_Kategori ON dbo.personel (is_active, kategori) INCLUDE (kode_personel, nama_personel);
GO
-- Audit Log (rentang hari ini / 7 / 30 hari)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_SecAudit_Created' AND object_id = OBJECT_ID('dbo.security_audit_logs'))
    CREATE INDEX IX_SecAudit_Created ON dbo.security_audit_logs (created_at DESC);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_PersonelAudit_Updated' AND object_id = OBJECT_ID('dbo.personel_audit_logs'))
    CREATE INDEX IX_PersonelAudit_Updated ON dbo.personel_audit_logs (updated_at DESC);
GO
-- Riwayat blacklist
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Blacklist_Tgl' AND object_id = OBJECT_ID('dbo.blacklist'))
    CREATE INDEX IX_Blacklist_Tgl ON dbo.blacklist (tgl_blacklist DESC);
GO
