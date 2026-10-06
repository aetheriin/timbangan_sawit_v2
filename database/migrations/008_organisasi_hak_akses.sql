SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 1: organisasi & hak akses dinamis.
   - company -> comp_area, department, level, menu, level_akses
   - users mendapat id_level, id_department, id_comp_area; kolom role DIHAPUS (diganti level)
   - perangkat_kiosk mendapat id_comp_area
   Aplikasi versi Fase 1 WAJIB memakai migrasi ini (login membaca level).
   Tabel users belum di-rename ke akun (dilakukan di fase bersih-bersih supaya FK lama tetap utuh).
   ===================================================================================== */

/* ---------- 1. Organisasi ---------- */
IF OBJECT_ID('dbo.company', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.company (
        id_company  INT IDENTITY(1,1) PRIMARY KEY,
        kode        VARCHAR(10)   NOT NULL CONSTRAINT UX_Company_Kode UNIQUE,
        nama        NVARCHAR(100) NOT NULL,
        is_active   BIT NOT NULL CONSTRAINT DF_Company_Aktif DEFAULT (1),
        created_at  DATETIME NOT NULL CONSTRAINT DF_Company_Created DEFAULT (GETDATE())
    );
    INSERT INTO dbo.company (kode, nama) VALUES ('PT', N'Perusahaan (ubah di Admin › Organisasi)');
END
GO

IF OBJECT_ID('dbo.comp_area', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.comp_area (
        id_comp_area INT IDENTITY(1,1) PRIMARY KEY,
        id_company   INT NOT NULL CONSTRAINT FK_Area_Company REFERENCES dbo.company (id_company),
        kode         VARCHAR(10)   NOT NULL CONSTRAINT UX_Area_Kode UNIQUE,
        nama         NVARCHAR(100) NOT NULL,
        alamat       NVARCHAR(255) NULL,
        is_active    BIT NOT NULL CONSTRAINT DF_Area_Aktif DEFAULT (1),
        created_at   DATETIME NOT NULL CONSTRAINT DF_Area_Created DEFAULT (GETDATE())
    );
    INSERT INTO dbo.comp_area (id_company, kode, nama)
    SELECT id_company, 'SITE1', N'Site Utama (ubah di Admin › Organisasi)' FROM dbo.company WHERE kode = 'PT';
END
GO

IF OBJECT_ID('dbo.department', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.department (
        id_department INT IDENTITY(1,1) PRIMARY KEY,
        nama          NVARCHAR(100) NOT NULL CONSTRAINT UX_Department_Nama UNIQUE,
        keterangan    NVARCHAR(255) NULL,
        is_active     BIT NOT NULL CONSTRAINT DF_Department_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.department (nama) VALUES (N'Umum'), (N'Security'), (N'Timbangan'), (N'QC / Lab'), (N'Head Office');
END
GO

/* ---------- 2. Level (pengganti role) ---------- */
IF OBJECT_ID('dbo.level', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.level (
        id_level      INT IDENTITY(1,1) PRIMARY KEY,
        kode          VARCHAR(30)   NOT NULL CONSTRAINT UX_Level_Kode UNIQUE,
        nama          NVARCHAR(100) NOT NULL,
        is_admin      BIT NOT NULL CONSTRAINT DF_Level_Admin DEFAULT (0),   -- 1 = hanya area Admin
        halaman_awal  VARCHAR(100)  NOT NULL CONSTRAINT DF_Level_Awal DEFAULT ('/weighbridge'),
        keterangan    NVARCHAR(255) NULL,
        is_active     BIT NOT NULL CONSTRAINT DF_Level_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.level (kode, nama, is_admin, halaman_awal) VALUES
        ('ADMIN',            N'Super Admin',      1, '/admin'),
        ('HO',               N'Head Office',      0, '/dashboard'),
        ('SECURITY',         N'Security',         0, '/weighbridge?tab=security'),
        ('OPERATOR_TIMBANG', N'Operator Timbang', 0, '/weighbridge?tab=timbangan'),
        ('SORTASI',          N'Sortasi',          0, '/weighbridge?tab=sortasi'),
        ('LAB',              N'Laboratorium',     0, '/weighbridge?tab=lab');
END
GO

/* ---------- 3. Menu & hak akses ---------- */
IF OBJECT_ID('dbo.menu', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.menu (
        id_menu    INT IDENTITY(1,1) PRIMARY KEY,
        kode       VARCHAR(40)   NOT NULL CONSTRAINT UX_Menu_Kode UNIQUE,
        nama       NVARCHAR(100) NOT NULL,
        url        VARCHAR(200)  NULL,          -- NULL = bagian di dalam halaman (tab), hanya untuk hak akses
        ikon       VARCHAR(40)   NULL,
        id_parent  INT NULL CONSTRAINT FK_Menu_Parent REFERENCES dbo.menu (id_menu),
        urutan     INT NOT NULL CONSTRAINT DF_Menu_Urutan DEFAULT (0),
        is_active  BIT NOT NULL CONSTRAINT DF_Menu_Aktif DEFAULT (1)
    );

    INSERT INTO dbo.menu (kode, nama, url, ikon, urutan) VALUES
        ('DASHBOARD',        N'Dashboard',        '/dashboard',            'fa-chart-line',    10),
        ('LIST',             N'List',             '/weighbridge?view=list', 'fa-list',         20),
        ('FORM',             N'Form',             '/weighbridge?view=form', 'fa-file-pen',     30),
        ('FACE_RECOGNITION', N'Face Recognition', '/face-recognition',     'fa-face-smile',    40),
        ('KONTRAK_DO',       N'Kontrak & DO',     '/kontrak',              'fa-file-contract', 50),
        ('MASTER',           N'Data Master',      '/master',               'fa-database',      60);

    INSERT INTO dbo.menu (kode, nama, id_parent, urutan)
    SELECT v.kode, v.nama, p.id_menu, v.urutan
    FROM (VALUES ('FORM_SECURITY',    N'Form › Security',          'FORM', 1),
                 ('FORM_TIMBANGAN',   N'Form › Timbangan',         'FORM', 2),
                 ('FORM_SORTASI',     N'Form › Sortasi',           'FORM', 3),
                 ('FORM_LAB',         N'Form › Laboratorium',      'FORM', 4),
                 ('ABSENSI',          N'Face Recognition › Absensi', 'FACE_RECOGNITION', 1),
                 ('PERSONEL',         N'Face Recognition › Personel', 'FACE_RECOGNITION', 2),
                 ('BLACKLIST',        N'Face Recognition › Blacklist', 'FACE_RECOGNITION', 3),
                 ('AUDIT_LOG',        N'Face Recognition › Audit Log', 'FACE_RECOGNITION', 4),
                 ('MASTER_DRIVER',    N'Data Master › Driver',     'MASTER', 1),
                 ('MASTER_KENDARAAN', N'Data Master › Kendaraan',  'MASTER', 2)) v (kode, nama, induk, urutan)
    JOIN dbo.menu p ON p.kode = v.induk;
END
GO

IF OBJECT_ID('dbo.level_akses', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.level_akses (
        id_level     INT NOT NULL CONSTRAINT FK_LevelAkses_Level REFERENCES dbo.level (id_level),
        id_menu      INT NOT NULL CONSTRAINT FK_LevelAkses_Menu REFERENCES dbo.menu (id_menu),
        bisa_tambah  BIT NOT NULL CONSTRAINT DF_LevelAkses_Tambah DEFAULT (0),
        bisa_ubah    BIT NOT NULL CONSTRAINT DF_LevelAkses_Ubah DEFAULT (0),
        bisa_hapus   BIT NOT NULL CONSTRAINT DF_LevelAkses_Hapus DEFAULT (0),
        CONSTRAINT PK_LevelAkses PRIMARY KEY (id_level, id_menu)
    );

    /* Sama dengan hak akses sebelum Fase 1 (docs/DOKUMENTASI.md). Semua level non-admin melihat semua menu. */
    INSERT INTO dbo.level_akses (id_level, id_menu, bisa_tambah, bisa_ubah, bisa_hapus)
    SELECT l.id_level, m.id_menu, v.t, v.u, v.h
    FROM (VALUES ('HO',               'DASHBOARD',        0, 1, 0),
                 ('HO',               'PERSONEL',         1, 1, 1),
                 ('HO',               'BLACKLIST',        1, 0, 0),
                 ('HO',               'KONTRAK_DO',       1, 1, 1),
                 ('HO',               'MASTER_DRIVER',    1, 1, 1),
                 ('HO',               'MASTER_KENDARAAN', 1, 1, 0),
                 ('SECURITY',         'FORM_SECURITY',    1, 1, 0),
                 ('SECURITY',         'MASTER_DRIVER',    1, 1, 1),
                 ('SECURITY',         'MASTER_KENDARAAN', 1, 1, 0),
                 ('OPERATOR_TIMBANG', 'FORM_TIMBANGAN',   1, 0, 0),
                 ('SORTASI',          'FORM_SORTASI',     1, 0, 0),
                 ('LAB',              'FORM_LAB',         1, 1, 0)) v (lv, mn, t, u, h)
    JOIN dbo.level l ON l.kode = v.lv
    JOIN dbo.menu m ON m.kode = v.mn;
END
GO

/* ---------- 4. users: level, department, area (role dihapus) ---------- */
-- users sudah di-rename menjadi akun (migrasi 016) -> bagian ini dilewati, aman dijalankan ulang
IF OBJECT_ID('dbo.users', 'U') IS NOT NULL AND COL_LENGTH('dbo.users', 'id_level') IS NULL
    ALTER TABLE dbo.users ADD
        id_level      INT NULL CONSTRAINT FK_Users_Level REFERENCES dbo.level (id_level),
        id_department INT NULL CONSTRAINT FK_Users_Department REFERENCES dbo.department (id_department),
        id_comp_area  INT NULL CONSTRAINT FK_Users_Area REFERENCES dbo.comp_area (id_comp_area);
GO

IF COL_LENGTH('dbo.users', 'role') IS NOT NULL
BEGIN
    EXEC('UPDATE u SET u.id_level = l.id_level FROM dbo.users u JOIN dbo.level l ON l.kode = u.role WHERE u.id_level IS NULL');
    EXEC(N'UPDATE u SET u.id_department = d.id_department
           FROM dbo.users u JOIN dbo.department d ON d.nama = CASE u.role
                WHEN ''HO'' THEN N''Head Office'' WHEN ''SECURITY'' THEN N''Security''
                WHEN ''OPERATOR_TIMBANG'' THEN N''Timbangan'' WHEN ''LAB'' THEN N''QC / Lab'' ELSE N''Umum'' END
           WHERE u.id_department IS NULL');
END
IF OBJECT_ID('dbo.users', 'U') IS NOT NULL
BEGIN
    EXEC('UPDATE dbo.users SET id_comp_area = (SELECT MIN(id_comp_area) FROM dbo.comp_area) WHERE id_comp_area IS NULL');
    EXEC('UPDATE dbo.users SET id_department = (SELECT id_department FROM dbo.department WHERE nama = N''Umum'') WHERE id_department IS NULL');
END
GO

IF COLUMNPROPERTY(OBJECT_ID('dbo.users'), 'id_level', 'AllowsNull') = 1
BEGIN
    ALTER TABLE dbo.users ALTER COLUMN id_level INT NOT NULL;
    ALTER TABLE dbo.users ALTER COLUMN id_department INT NOT NULL;
    ALTER TABLE dbo.users ALTER COLUMN id_comp_area INT NOT NULL;
END
GO

/* Kolom role diganti level: hapus CHECK / DEFAULT yang menempel, lalu kolomnya */
IF COL_LENGTH('dbo.users', 'role') IS NOT NULL
BEGIN
    DECLARE @sql NVARCHAR(MAX) = N'';
    SELECT @sql += N'ALTER TABLE dbo.users DROP CONSTRAINT ' + QUOTENAME(c.name) + N';'
    FROM sys.check_constraints c
    WHERE c.parent_object_id = OBJECT_ID('dbo.users') AND c.definition LIKE '%role%';
    SELECT @sql += N'ALTER TABLE dbo.users DROP CONSTRAINT ' + QUOTENAME(d.name) + N';'
    FROM sys.default_constraints d
    JOIN sys.columns col ON col.object_id = d.parent_object_id AND col.column_id = d.parent_column_id
    WHERE d.parent_object_id = OBJECT_ID('dbo.users') AND col.name = 'role';
    EXEC sp_executesql @sql;
    ALTER TABLE dbo.users DROP COLUMN role;
END
GO

/* ---------- 5. Kiosk per area ---------- */
IF COL_LENGTH('dbo.perangkat_kiosk', 'id_comp_area') IS NULL
    ALTER TABLE dbo.perangkat_kiosk ADD id_comp_area INT NULL CONSTRAINT FK_Kiosk_Area REFERENCES dbo.comp_area (id_comp_area);
GO
EXEC('UPDATE dbo.perangkat_kiosk SET id_comp_area = (SELECT MIN(id_comp_area) FROM dbo.comp_area) WHERE id_comp_area IS NULL');
GO
ALTER TABLE dbo.perangkat_kiosk ALTER COLUMN id_comp_area INT NOT NULL;
GO
