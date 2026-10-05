USE DbSistemTimbangan_Test;

DECLARE @t TABLE (tabel SYSNAME);
INSERT INTO @t VALUES ('admin_audit_logs'), ('security_audit_logs'), ('personel_audit_logs'),
                      ('standar_mutu_log'), ('timeline_monitoring'), ('log_aktivitas');
DECLARE @nama SYSNAME, @n INT, @q NVARCHAR(200);
DECLARE @hasil TABLE (tabel SYSNAME, jumlah INT);
DECLARE c CURSOR LOCAL FOR SELECT tabel FROM @t;
OPEN c; FETCH NEXT FROM c INTO @nama;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF OBJECT_ID('dbo.' + @nama, 'U') IS NULL
        INSERT INTO @hasil VALUES (@nama, NULL);           -- NULL = tabel sudah dihapus
    ELSE
    BEGIN
        SET @q = N'SELECT @n = COUNT(*) FROM dbo.' + QUOTENAME(@nama);
        EXEC sp_executesql @q, N'@n INT OUTPUT', @n = @n OUTPUT;
        INSERT INTO @hasil VALUES (@nama, @n);
    END
    FETCH NEXT FROM c INTO @nama;
END
CLOSE c; DEALLOCATE c;
SELECT * FROM @hasil;