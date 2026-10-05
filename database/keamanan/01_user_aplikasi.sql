/* =====================================================================
   Akun SQL khusus aplikasi dengan hak minimal (docs/KEAMANAN_WEB.md #19).
   Aplikasi hanya perlu SELECT / INSERT / UPDATE, DELETE untuk beberapa tabel relasi, EXECUTE sp_catat_log.
   Jalankan ulang setelah migrasi 016 (nama tabel akun / mitra).

   1. Ganti password di bawah (minimal 16 karakter), jalankan di SSMS sebagai sysadmin.
   2. Isi .env:  DB_USER=weighbridge_app  DB_PASSWORD=<password yang sama>
   3. SQL Server harus mengizinkan "SQL Server and Windows Authentication mode"
      (SSMS > klik kanan server > Properties > Security).
   Jalankan dulu di DbSistemTimbangan_Test.
   ===================================================================== */
USE [master]
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'weighbridge_app')
    CREATE LOGIN [weighbridge_app] WITH PASSWORD = 'GANTI_PASSWORD_KUAT_DI_SINI_16+', CHECK_POLICY = ON;
GO

USE [DbSistemTimbangan_Test]
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'weighbridge_app')
    CREATE USER [weighbridge_app] FOR LOGIN [weighbridge_app];
GO
-- Baca & tulis data saja (DELETE tidak diberikan untuk schema, hanya tabel di bawah)
GRANT SELECT, INSERT, UPDATE ON SCHEMA::dbo TO [weighbridge_app];
-- Tidak boleh ubah struktur
DENY ALTER ON SCHEMA::dbo TO [weighbridge_app];
-- Tabel pengaturan / relasi yang memang diganti ulang oleh aplikasi
GRANT DELETE ON dbo.mitra_peran TO [weighbridge_app];
GRANT DELETE ON dbo.do_pengangkutan TO [weighbridge_app];
GRANT DELETE ON dbo.level_akses TO [weighbridge_app];
GRANT DELETE ON dbo.pengaturan TO [weighbridge_app];
GRANT DELETE ON dbo.pengaturan_area TO [weighbridge_app];
GRANT DELETE ON dbo.pembatalan_tiket TO [weighbridge_app];
-- Log hanya lewat prosedur (rantai hash); tabelnya tidak boleh ditulis langsung
GRANT EXECUTE ON dbo.sp_catat_log TO [weighbridge_app];
DENY INSERT, UPDATE, DELETE ON dbo.log_aktivitas TO [weighbridge_app];
-- Blacklist hanya boleh ditambah, tidak boleh diubah
DENY UPDATE ON dbo.blacklist TO [weighbridge_app];
GO
