SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Jabatan umum (ERD Level): Admin, Manager, Supervisor, Staff, Magang (bisa ditambah di Admin › Organisasi).
   Tabel level sekarang = PERAN: gabungan departemen + jabatan (mis. Security · Staff). Hak menu & halaman awal
   menempel di peran (Admin › Level & Hak Akses). Kode & nama peran dibuat otomatis.
   Jabatan lama (Security, Operator Timbang, KTU, ...) dibuatkan jabatan bernama sama supaya tidak ada yang bentrok;
   rapikan sesudahnya lewat Kelola Pengguna. Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.jabatan') IS NULL
    CREATE TABLE dbo.jabatan (
        id_jabatan  INT IDENTITY(1,1) PRIMARY KEY,
        nama        NVARCHAR(100) NOT NULL CONSTRAINT UX_Jabatan_Nama UNIQUE,
        keterangan  NVARCHAR(255) NULL,
        is_admin    BIT NOT NULL CONSTRAINT DF_Jabatan_Admin DEFAULT (0),   -- admin sistem: hanya menu Admin, tanpa departemen
        urutan      INT NOT NULL CONSTRAINT DF_Jabatan_Urutan DEFAULT (100),
        is_active   BIT NOT NULL CONSTRAINT DF_Jabatan_Aktif DEFAULT (1)
    );
GO
INSERT INTO dbo.jabatan (nama, is_admin, urutan)
SELECT v.nama, v.adm, v.urut FROM (VALUES (N'Admin', 1, 1), (N'Manager', 0, 2), (N'Supervisor', 0, 3),
                                          (N'Staff', 0, 4), (N'Magang', 0, 5)) v (nama, adm, urut)
WHERE NOT EXISTS (SELECT 1 FROM dbo.jabatan j WHERE j.nama = v.nama);
GO

IF COL_LENGTH('dbo.level', 'id_jabatan') IS NULL
    ALTER TABLE dbo.level ADD id_jabatan INT NULL CONSTRAINT FK_Level_Jabatan REFERENCES dbo.jabatan (id_jabatan);
GO
-- Jabatan admin sistem
UPDATE dbo.level SET id_jabatan = (SELECT id_jabatan FROM dbo.jabatan WHERE nama = N'Admin')
WHERE is_admin = 1 AND id_jabatan IS NULL;
-- Jabatan bawaan -> jabatan umum (HO = Manager; Security / Operator Timbang / Sortasi / Lab = Staff), selama
-- departemennya belum punya jabatan umum itu (mis. Sortasi & Lab di departemen yang sama: Lab tetap bernama Laboratorium)
GO
DECLARE @peta TABLE (urut INT, kode VARCHAR(30), jabatan NVARCHAR(100));
INSERT INTO @peta VALUES (1, 'HO', N'Manager'), (2, 'SECURITY', N'Staff'), (3, 'OPERATOR_TIMBANG', N'Staff'),
                         (4, 'SORTASI', N'Staff'), (5, 'LAB', N'Staff');
DECLARE @urut INT = 1, @kode VARCHAR(30), @jab NVARCHAR(100);
WHILE @urut <= 5
BEGIN
    SELECT @kode = kode, @jab = jabatan FROM @peta WHERE urut = @urut;
    UPDATE l SET id_jabatan = j.id_jabatan
    FROM dbo.level l JOIN dbo.jabatan j ON j.nama = @jab
    WHERE l.kode = @kode AND l.is_admin = 0 AND l.id_jabatan IS NULL
      AND NOT EXISTS (SELECT 1 FROM dbo.level x WHERE x.id_jabatan = j.id_jabatan AND x.id_department = l.id_department);
    SET @urut += 1;
END
GO
-- Jabatan lama lainnya -> jabatan bernama sama (nama lama bisa sudah berformat "Departemen · Jabatan" bila diulang)
INSERT INTO dbo.jabatan (nama)
SELECT DISTINCT l.nama FROM dbo.level l
WHERE l.is_admin = 0 AND l.id_jabatan IS NULL AND NOT EXISTS (SELECT 1 FROM dbo.jabatan j WHERE j.nama = l.nama);
UPDATE l SET id_jabatan = j.id_jabatan FROM dbo.level l JOIN dbo.jabatan j ON j.nama = l.nama
WHERE l.is_admin = 0 AND l.id_jabatan IS NULL;
-- Nama peran = "Departemen · Jabatan"
UPDATE l SET nama = LEFT(d.nama + N' · ' + j.nama, 100)
FROM dbo.level l JOIN dbo.department d ON d.id_department = l.id_department JOIN dbo.jabatan j ON j.id_jabatan = l.id_jabatan
WHERE l.is_admin = 0;
GO
-- Satu peran per gabungan departemen + jabatan
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Level_Peran' AND object_id = OBJECT_ID('dbo.level'))
   AND NOT EXISTS (SELECT id_department, id_jabatan FROM dbo.level WHERE id_department IS NOT NULL AND id_jabatan IS NOT NULL
                   GROUP BY id_department, id_jabatan HAVING COUNT(*) > 1)
    CREATE UNIQUE INDEX UX_Level_Peran ON dbo.level (id_department, id_jabatan)
        WHERE id_department IS NOT NULL AND id_jabatan IS NOT NULL;
GO
