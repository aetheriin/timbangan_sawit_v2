/* =====================================================================
   Akun SQL khusus aplikasi dengan hak minimal (docs/KEAMANAN_WEB.md #19).
   Aplikasi hanya perlu SELECT / INSERT / UPDATE (tidak DELETE, DROP, ALTER).

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
-- Baca & tulis data saja
GRANT SELECT, INSERT, UPDATE ON SCHEMA::dbo TO [weighbridge_app];
-- Tidak boleh hapus data / ubah struktur
DENY DELETE ON SCHEMA::dbo TO [weighbridge_app];
DENY ALTER ON SCHEMA::dbo TO [weighbridge_app];
-- Log audit & blacklist hanya boleh ditambah, tidak boleh diubah
DENY UPDATE ON dbo.security_audit_logs TO [weighbridge_app];
DENY UPDATE ON dbo.personel_audit_logs TO [weighbridge_app];
DENY UPDATE ON dbo.blacklist TO [weighbridge_app];
GO
