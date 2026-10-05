/* =====================================================================
   PINDAH LAPTOP langkah 1: backup database di PC lama (docs/PINDAH_LAPTOP.md).
   1. Hentikan aplikasi (tutup jendela serve.py) supaya tidak ada transaksi yang sedang berjalan.
   2. Ganti @db (lihat DB_NAME di .env) dan @folder bila perlu, lalu Execute.
   3. Salin file .bak yang terbentuk ke laptop (flashdisk / jaringan).
   Folder harus bisa ditulis oleh layanan SQL Server: paling aman memakai folder Backup bawaan SQL Server
   (dibiarkan kosong = otomatis).
   ===================================================================== */
DECLARE @db     SYSNAME       = N'DbSistemTimbangan_Test';
DECLARE @folder NVARCHAR(260) = N'';            -- kosong = folder Backup bawaan SQL Server

IF @folder = N''
    SET @folder = CAST(SERVERPROPERTY('InstanceDefaultBackupPath') AS NVARCHAR(260));
IF RIGHT(@folder, 1) NOT IN (N'\', N'/')
    SET @folder += N'\';
DECLARE @file NVARCHAR(400) = @folder + @db + N'_pindah_' + CONVERT(CHAR(8), GETDATE(), 112) + N'.bak';

-- COPY_ONLY: tidak mengganggu jadwal backup rutin. Tanpa COMPRESSION supaya jalan juga di SQL Server Express.
BACKUP DATABASE @db TO DISK = @file WITH COPY_ONLY, INIT, CHECKSUM, STATS = 10;
RESTORE VERIFYONLY FROM DISK = @file WITH CHECKSUM;
SELECT @file AS file_backup_salin_ke_laptop, CAST(SERVERPROPERTY('ProductVersion') AS VARCHAR(30)) AS versi_sql_server_pc_lama;
GO
