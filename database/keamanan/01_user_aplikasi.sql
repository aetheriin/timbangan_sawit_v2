/* =====================================================================
   Akun SQL khusus aplikasi dengan hak minimal (docs/DOKUMENTASI.md bagian 8).
   Aplikasi hanya perlu SELECT / INSERT / UPDATE, DELETE untuk beberapa tabel relasi, EXECUTE sp_WriteLog.
   Jalankan setelah database dibuat dari database/schema.sql.

   1. Ganti password di bawah (minimal 16 karakter), jalankan di SSMS sebagai sysadmin.
   2. Isi .env:  DB_USER=weighbridge_app  DB_PASSWORD=<password yang sama>
   3. SQL Server harus mengizinkan "SQL Server and Windows Authentication mode"
      (SSMS > klik kanan server > Properties > Security).
   ===================================================================== */
USE [master]
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'weighbridge_app')
    CREATE LOGIN [weighbridge_app] WITH PASSWORD = 'GANTI_PASSWORD_KUAT_DI_SINI_16+', CHECK_POLICY = ON;
GO

USE [DbSistemTimbangan]
GO
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'weighbridge_app')
    CREATE USER [weighbridge_app] FOR LOGIN [weighbridge_app];
GO
-- Baca & tulis data saja (DELETE tidak diberikan untuk schema, hanya tabel di bawah)
GRANT SELECT, INSERT, UPDATE ON SCHEMA::dbo TO [weighbridge_app];
-- Tidak boleh ubah struktur
DENY ALTER ON SCHEMA::dbo TO [weighbridge_app];
-- Tabel relasi / pengaturan yang memang diganti ulang oleh aplikasi
GRANT DELETE ON dbo.AccessMenu TO [weighbridge_app];
GRANT DELETE ON dbo.UserCompany TO [weighbridge_app];
GRANT DELETE ON dbo.SupplierTypeDetails TO [weighbridge_app];
GRANT DELETE ON dbo.SupplierCompany TO [weighbridge_app];
GRANT DELETE ON dbo.DOTransport TO [weighbridge_app];
GRANT DELETE ON dbo.Setting TO [weighbridge_app];
GRANT DELETE ON dbo.SettingArea TO [weighbridge_app];
GRANT DELETE ON dbo.RequiredDataField TO [weighbridge_app];
GRANT DELETE ON dbo.TicketVoid TO [weighbridge_app];
GRANT DELETE ON dbo.ApprovalFlow TO [weighbridge_app];
GRANT DELETE ON dbo.ApprovalFlowStep TO [weighbridge_app];
-- Log hanya lewat prosedur (rantai hash); tabelnya tidak boleh ditulis langsung
GRANT EXECUTE ON dbo.sp_WriteLog TO [weighbridge_app];
DENY INSERT, UPDATE, DELETE ON dbo.Log TO [weighbridge_app];
-- Blacklist tidak pernah dihapus (dicabut = RevokeDate diisi lewat persetujuan)
DENY DELETE ON dbo.Blacklist TO [weighbridge_app];
GO
