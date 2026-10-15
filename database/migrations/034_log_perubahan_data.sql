SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Log perubahan data (ERD Log: TableName, OldValue, NewValue).
   Trigger di tabel master / organisasi / akun / kontrak mencatat setiap tambah / ubah / hapus ke log_aktivitas
   (kategori DATA): isi baris lama & baru dalam JSON, lewat sp_catat_log (rantai hash). Pengguna & IP diambil dari
   SESSION_CONTEXT yang diisi aplikasi; perubahan langsung di database tercatat tanpa pengguna.
   Kolom password, last_login, sesi_versi, updated_at tidak dicatat. Dilihat di Admin › Audit › Perubahan Data.
   Aman dijalankan ulang.
   ===================================================================================== */
CREATE OR ALTER TRIGGER dbo.TR_LogData_company ON dbo.company AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_company AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_company AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_company AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_company AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'company', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_comp_area ON dbo.comp_area AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_comp_area AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_comp_area AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_comp_area AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_comp_area AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'comp_area', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_lokasi ON dbo.lokasi AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_lokasi AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_lokasi AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_lokasi AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_lokasi AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'lokasi', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_department ON dbo.department AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_department AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_department AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_department AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_department AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'department', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_level ON dbo.level AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_level AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_level AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_level AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_level AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'level', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_akun ON dbo.akun AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_user AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_user AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_user AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_user AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'akun', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_mitra ON dbo.mitra AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_supplier AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_supplier AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_supplier AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_supplier AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'mitra', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_produk ON dbo.produk AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_produk AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_produk AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_produk AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_produk AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'produk', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_standar_mutu ON dbo.standar_mutu AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_produk AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_produk AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_produk AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_produk AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'standar_mutu', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_kendaraan ON dbo.kendaraan AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_kendaraan AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_kendaraan AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_kendaraan AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_kendaraan AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'kendaraan', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_jenis_kendaraan ON dbo.jenis_kendaraan AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_jenis_kendaraan AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_jenis_kendaraan AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_jenis_kendaraan AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_jenis_kendaraan AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'jenis_kendaraan', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_kontrak ON dbo.kontrak AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_kontrak AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_kontrak AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_kontrak AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_kontrak AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'kontrak', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_delivery_order ON dbo.delivery_order AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_do AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_do AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_do AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_do AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'delivery_order', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_jembatan_timbang ON dbo.jembatan_timbang AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_jembatan AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_jembatan AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_jembatan AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_jembatan AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'jembatan_timbang', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_mill ON dbo.mill AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_mill AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_mill AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_mill AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_mill AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'mill', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_harga_harian ON dbo.harga_harian AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(CONVERT(VARCHAR(10), d.tanggal, 23) AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(CONVERT(VARCHAR(10), i.tanggal, 23) AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(CONVERT(VARCHAR(10), d.tanggal, 23) AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(CONVERT(VARCHAR(10), i.tanggal, 23) AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'harga_harian', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_pengaturan ON dbo.pengaturan AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.kunci AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.kunci AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.kunci AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.kunci AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'pengaturan', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_pengaturan_area ON dbo.pengaturan_area AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(CONCAT(d.id_comp_area, '|', d.kunci) AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(CONCAT(i.id_comp_area, '|', i.kunci) AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(CONCAT(d.id_comp_area, '|', d.kunci) AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(CONCAT(i.id_comp_area, '|', i.kunci) AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'pengaturan_area', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_status_tiket ON dbo.status_tiket AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.kode AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.kode AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.kode AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.kode AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'status_tiket', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_kategori_personel ON dbo.kategori_personel AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.kode AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.kode AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.kode AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.kode AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'kategori_personel', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_jenis_sim ON dbo.jenis_sim AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_jenis_sim AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_jenis_sim AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_jenis_sim AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_jenis_sim AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'jenis_sim', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_keperluan_kunjungan ON dbo.keperluan_kunjungan AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.id_keperluan AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.id_keperluan AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user INT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS INT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.id_keperluan AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.id_keperluan AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'keperluan_kunjungan', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
