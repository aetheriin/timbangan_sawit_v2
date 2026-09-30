/* =====================================================================
   Backup database harian (docs/KEAMANAN_WEB.md #22).
   Jadwalkan lewat SQL Server Agent (Job, harian 23:00) atau Windows Task Scheduler:
       sqlcmd -S <server> -E -i "C:\path\database\keamanan\02_backup_harian.sql"
   Simpan salinan folder backup juga di komputer / disk lain.
   Uji restore minimal 1x sebulan ke database salinan.
   ===================================================================== */
DECLARE @folder NVARCHAR(200) = N'D:\Backup\Timbangan\';          -- ganti sesuai server
DECLARE @db     SYSNAME       = N'DbSistemTimbangan';
DECLARE @file   NVARCHAR(400) = @folder + @db + N'_' + CONVERT(CHAR(8), GETDATE(), 112) + N'.bak';

BACKUP DATABASE @db TO DISK = @file WITH INIT, CHECKSUM, COMPRESSION, STATS = 10;
RESTORE VERIFYONLY FROM DISK = @file WITH CHECKSUM;
GO
