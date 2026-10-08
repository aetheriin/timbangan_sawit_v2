SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 5b: nama tabel sesuai ERD & bersih-bersih.
   - users -> akun, supplier -> mitra, supplier_peran -> mitra_peran (nama KOLOM tetap: id_user, id_supplier, ...
     supaya FK & kode yang sudah stabil tidak berubah). akun.id_personel tetap opsional: akun dan personel terpisah.
   - transaksi.is_driver_changed / prev_driver_id -> log_aktivitas (SECURITY / OVERRIDE_DRIVER, bila belum ada), kolom dihapus
   - 5 tabel log lama dihapus bila isinya sudah lengkap di log_aktivitas (migrasi 015)
   Wajib setelah migrasi 015. Hentikan aplikasi (serve.py) saat menjalankan migrasi ini.
   ===================================================================================== */

/* ---------- 1. Rename tabel ---------- */
IF OBJECT_ID('dbo.users', 'U') IS NOT NULL AND OBJECT_ID('dbo.akun', 'U') IS NULL
    EXEC sp_rename 'dbo.users', 'akun';
GO
IF OBJECT_ID('dbo.supplier', 'U') IS NOT NULL AND OBJECT_ID('dbo.mitra', 'U') IS NULL
    EXEC sp_rename 'dbo.supplier', 'mitra';
GO
IF OBJECT_ID('dbo.supplier_peran', 'U') IS NOT NULL AND OBJECT_ID('dbo.mitra_peran', 'U') IS NULL
    EXEC sp_rename 'dbo.supplier_peran', 'mitra_peran';
GO

/* Prosedur log membaca area dari akun (sp_rename tidak mengubah isi prosedur) */
CREATE OR ALTER PROCEDURE dbo.sp_catat_log
    @kategori VARCHAR(20), @aksi VARCHAR(40), @tabel VARCHAR(50) = NULL, @id_baris VARCHAR(100) = NULL,
    @nilai_lama NVARCHAR(MAX) = NULL, @nilai_baru NVARCHAR(MAX) = NULL, @id_user INT = NULL,
    @id_comp_area INT = NULL, @ip VARCHAR(45) = NULL, @waktu DATETIME2(3) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRANSACTION;
    EXEC sp_getapplock @Resource = 'log_aktivitas', @LockMode = 'Exclusive', @LockOwner = 'Transaction';
    DECLARE @prev CHAR(64) = (SELECT TOP 1 hash_baris FROM dbo.log_aktivitas ORDER BY id_log DESC);
    SET @waktu = COALESCE(@waktu, SYSDATETIME());
    IF @id_comp_area IS NULL AND @id_user IS NOT NULL
    BEGIN
        -- tabel akun bernama users sebelum migrasi 016: pilih yang ada, supaya urutan menjalankan 015 / 016 bebas
        DECLARE @q NVARCHAR(200) = N'SELECT @a = id_comp_area FROM dbo.'
            + CASE WHEN OBJECT_ID('dbo.akun', 'U') IS NOT NULL THEN N'akun' ELSE N'users' END + N' WHERE id_user = @u';
        EXEC sp_executesql @q, N'@u INT, @a INT OUTPUT', @u = @id_user, @a = @id_comp_area OUTPUT;
    END
    INSERT INTO dbo.log_aktivitas (waktu, id_user, id_comp_area, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru,
                                   ip, hash_sebelum, hash_baris)
    VALUES (@waktu, @id_user, @id_comp_area, @kategori, @aksi, @tabel, @id_baris, @nilai_lama, @nilai_baru, @ip, @prev,
            dbo.fn_hash_log(@prev, @waktu, @id_user, @kategori, @aksi, @tabel, @id_baris, @nilai_lama, @nilai_baru, @ip));
    COMMIT TRANSACTION;
END
GO

/* ---------- 2. Ganti supir: kolom transaksi -> log ---------- */
IF COL_LENGTH('dbo.transaksi', 'prev_driver_id') IS NOT NULL
BEGIN
    EXEC(N'
    DECLARE @w DATETIME2(3), @u INT, @b VARCHAR(100), @nb NVARCHAR(MAX);
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR
        SELECT t.created_at, t.security_id, t.no_tiket,
               (SELECT N''Supir diganti (data lama transaksi.prev_driver_id)'' AS keterangan,
                       t.prev_driver_id AS prev_driver_id, t.id_driver AS id_driver FOR JSON PATH, WITHOUT_ARRAY_WRAPPER)
        FROM dbo.transaksi t
        WHERE t.prev_driver_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM dbo.log_aktivitas l
                          WHERE l.kategori = ''SECURITY'' AND l.aksi = ''OVERRIDE_DRIVER'' AND l.id_baris = t.no_tiket)
        ORDER BY t.created_at;
    OPEN c;
    FETCH NEXT FROM c INTO @w, @u, @b, @nb;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        EXEC dbo.sp_catat_log @kategori = ''SECURITY'', @aksi = ''OVERRIDE_DRIVER'', @tabel = ''transaksi'', @id_baris = @b,
                              @nilai_baru = @nb, @id_user = @u, @waktu = @w;
        FETCH NEXT FROM c INTO @w, @u, @b, @nb;
    END
    CLOSE c;
    DEALLOCATE c;');

    DECLARE @sql NVARCHAR(MAX) = N'';
    SELECT @sql += N'ALTER TABLE dbo.transaksi DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';'
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fc ON fc.constraint_object_id = fk.object_id
    JOIN sys.columns c ON c.object_id = fc.parent_object_id AND c.column_id = fc.parent_column_id
    WHERE fk.parent_object_id = OBJECT_ID('dbo.transaksi') AND c.name IN ('prev_driver_id', 'is_driver_changed');
    SELECT @sql += N'ALTER TABLE dbo.transaksi DROP CONSTRAINT ' + QUOTENAME(d.name) + N';'
    FROM sys.default_constraints d
    JOIN sys.columns c ON c.object_id = d.parent_object_id AND c.column_id = d.parent_column_id
    WHERE d.parent_object_id = OBJECT_ID('dbo.transaksi') AND c.name IN ('prev_driver_id', 'is_driver_changed');
    SELECT @sql += N'ALTER TABLE dbo.transaksi DROP CONSTRAINT ' + QUOTENAME(k.name) + N';'
    FROM sys.check_constraints k
    WHERE k.parent_object_id = OBJECT_ID('dbo.transaksi')
      AND (k.definition LIKE '%prev_driver_id%' OR k.definition LIKE '%is_driver_changed%');
    EXEC (@sql);
    ALTER TABLE dbo.transaksi DROP COLUMN prev_driver_id, is_driver_changed;
END
GO

/* ---------- 3. Hapus tabel log lama bila isinya sudah ada di log_aktivitas ---------- */
DECLARE @lama TABLE (tabel SYSNAME, kategori VARCHAR(20));
INSERT INTO @lama VALUES ('admin_audit_logs', 'ADMIN'), ('security_audit_logs', 'SECURITY'),
                         ('personel_audit_logs', 'PERSONEL'), ('standar_mutu_log', 'STANDAR_MUTU'),
                         ('timeline_monitoring', 'TIMELINE');
DECLARE @t SYSNAME, @k VARCHAR(20), @n_lama INT, @n_log INT, @q NVARCHAR(400);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT tabel, kategori FROM @lama;
OPEN c;
FETCH NEXT FROM c INTO @t, @k;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF OBJECT_ID('dbo.' + @t, 'U') IS NOT NULL
    BEGIN
        SET @q = N'SELECT @n = COUNT(*) FROM dbo.' + QUOTENAME(@t);
        EXEC sp_executesql @q, N'@n INT OUTPUT', @n = @n_lama OUTPUT;
        SET @n_log = (SELECT COUNT(*) FROM dbo.log_aktivitas WHERE kategori = @k);
        IF @n_log >= @n_lama
        BEGIN
            SET @q = N'DROP TABLE dbo.' + QUOTENAME(@t);
            EXEC (@q);
            PRINT 'Tabel ' + @t + ' dihapus (' + CAST(@n_lama AS VARCHAR(12)) + ' baris sudah di log_aktivitas).';
        END
        ELSE
            PRINT 'PERHATIAN: ' + @t + ' punya ' + CAST(@n_lama AS VARCHAR(12)) + ' baris, log_aktivitas ' + @k + ' hanya '
                  + CAST(@n_log AS VARCHAR(12)) + '. Tabel TIDAK dihapus; periksa migrasi 015.';
    END
    FETCH NEXT FROM c INTO @t, @k;
END
CLOSE c;
DEALLOCATE c;
GO

SELECT OBJECT_ID('dbo.akun') AS akun, OBJECT_ID('dbo.mitra') AS mitra, OBJECT_ID('dbo.mitra_peran') AS mitra_peran,
       COL_LENGTH('dbo.transaksi', 'prev_driver_id') AS prev_driver_id_harus_null;
GO
