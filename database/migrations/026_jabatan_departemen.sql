SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Departemen & jabatan (Admin › Level & Hak Akses).
   - level.id_department : jabatan (dulu "level") milik satu departemen. Departemen user ikut jabatannya.
   - level_akses.bisa_lihat : halaman yang boleh dibuka. Agar tidak ada yang tiba-tiba kehilangan akses,
     semua jabatan non-admin yang sudah ada diberi Lihat ke semua menu (perilaku lama: semua menu terlihat).
   - akun_company : PT yang dikelola user kantor pusat. Kosong = semua PT.
   Aman dijalankan ulang.
   ===================================================================================== */
IF COL_LENGTH('dbo.level', 'id_department') IS NULL
    ALTER TABLE dbo.level ADD id_department INT NULL CONSTRAINT FK_Level_Department REFERENCES dbo.department (id_department);
GO

-- Departemen jabatan lama = departemen yang paling banyak dipakai penggunanya; tanpa pengguna -> departemen pertama
UPDATE l SET id_department = COALESCE(
    (SELECT TOP 1 u.id_department FROM dbo.akun u WHERE u.id_level = l.id_level
     GROUP BY u.id_department ORDER BY COUNT(*) DESC, u.id_department),
    (SELECT MIN(d.id_department) FROM dbo.department d WHERE d.is_active = 1))
FROM dbo.level l
WHERE l.id_department IS NULL;
GO

IF COL_LENGTH('dbo.level_akses', 'bisa_lihat') IS NULL
BEGIN
    ALTER TABLE dbo.level_akses ADD bisa_lihat BIT NOT NULL CONSTRAINT DF_LevelAkses_Lihat DEFAULT (1);
    EXEC (N'
    INSERT INTO dbo.level_akses (id_level, id_menu, bisa_lihat, bisa_tambah, bisa_ubah, bisa_hapus)
    SELECT l.id_level, m.id_menu, 1, 0, 0, 0
    FROM dbo.level l CROSS JOIN dbo.menu m
    WHERE l.is_admin = 0 AND m.is_active = 1
      AND NOT EXISTS (SELECT 1 FROM dbo.level_akses a WHERE a.id_level = l.id_level AND a.id_menu = m.id_menu);');
END
GO

-- Departemen user disamakan dengan departemen jabatannya
UPDATE u SET id_department = l.id_department
FROM dbo.akun u JOIN dbo.level l ON l.id_level = u.id_level
WHERE l.id_department IS NOT NULL AND u.id_department <> l.id_department;
GO

IF OBJECT_ID('dbo.akun_company', 'U') IS NULL
CREATE TABLE dbo.akun_company (
    id_user     INT NOT NULL CONSTRAINT FK_AkunCompany_Akun REFERENCES dbo.akun (id_user),
    id_company  INT NOT NULL CONSTRAINT FK_AkunCompany_Company REFERENCES dbo.company (id_company),
    CONSTRAINT PK_AkunCompany PRIMARY KEY (id_user, id_company)
);
GO
