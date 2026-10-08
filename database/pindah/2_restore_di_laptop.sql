/* =====================================================================
   PINDAH LAPTOP langkah 2: restore database di laptop (docs/DOKUMENTASI.md).
   1. Taruh file .bak di folder yang bisa dibaca SQL Server, mis. folder Backup bawaan:
      C:\Program Files\Microsoft SQL Server\MSSQL16.SQLEXPRESS\MSSQL\Backup\
   2. Isi @file (lokasi .bak) dan @db (nama database, samakan dengan DB_NAME di .env), lalu Execute.
   File data & log otomatis ditaruh di folder data bawaan SQL Server laptop.
   Versi SQL Server laptop harus SAMA atau LEBIH BARU dari PC lama (lihat hasil langkah 1).
   ===================================================================== */
DECLARE @file NVARCHAR(400) = N'C:\Program Files\Microsoft SQL Server\MSSQL16.SQLEXPRESS\MSSQL\Backup\DbSistemTimbangan_Test_pindah_20261005.bak';
DECLARE @db   SYSNAME       = N'DbSistemTimbangan_Test';
DECLARE @timpa BIT          = 0;               -- 1 = timpa database @db yang sudah ada di laptop

IF DB_ID(@db) IS NOT NULL AND @timpa = 0
BEGIN
    RAISERROR(N'Database %s sudah ada di laptop. Ganti @db atau isi @timpa = 1.', 16, 1, @db);
    RETURN;
END

DECLARE @isi TABLE (LogicalName NVARCHAR(128), PhysicalName NVARCHAR(260), [Type] CHAR(1), FileGroupName NVARCHAR(128),
                    Size NUMERIC(20, 0), MaxSize NUMERIC(20, 0), FileId BIGINT, CreateLSN NUMERIC(25, 0), DropLSN NUMERIC(25, 0),
                    UniqueId UNIQUEIDENTIFIER, ReadOnlyLSN NUMERIC(25, 0), ReadWriteLSN NUMERIC(25, 0),
                    BackupSizeInBytes BIGINT, SourceBlockSize INT, FileGroupId INT, LogGroupGUID UNIQUEIDENTIFIER,
                    DifferentialBaseLSN NUMERIC(25, 0), DifferentialBaseGUID UNIQUEIDENTIFIER, IsReadOnly BIT, IsPresent BIT,
                    TDEThumbprint VARBINARY(32), SnapshotURL NVARCHAR(360));
INSERT INTO @isi EXEC (N'RESTORE FILELISTONLY FROM DISK = N''' + @file + N'''');

DECLARE @data NVARCHAR(260) = CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS NVARCHAR(260));
DECLARE @log  NVARCHAR(260) = CAST(SERVERPROPERTY('InstanceDefaultLogPath') AS NVARCHAR(260));
DECLARE @move NVARCHAR(MAX) = N'';
SELECT @move += N', MOVE N''' + LogicalName + N''' TO N''' + CASE WHEN [Type] = 'L' THEN @log ELSE @data END
              + @db + CASE WHEN [Type] = 'L' THEN N'_log' + CAST(FileId AS NVARCHAR(10)) + N'.ldf'
                           ELSE N'_' + CAST(FileId AS NVARCHAR(10)) + N'.mdf' END + N''''
FROM @isi;

DECLARE @sql NVARCHAR(MAX) = N'RESTORE DATABASE ' + QUOTENAME(@db) + N' FROM DISK = N''' + @file + N''' WITH RECOVERY, STATS = 10'
                           + CASE WHEN @timpa = 1 THEN N', REPLACE' ELSE N'' END + @move + N';';
PRINT @sql;
EXEC (@sql);
GO

/* Cek cepat */
SELECT name, state_desc, compatibility_level FROM sys.databases WHERE name LIKE N'DbSistemTimbangan%';
GO
