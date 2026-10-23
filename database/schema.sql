/* =====================================================================
   SCHEMA Sistem Timbangan Sawit (Weighbridge + Face Recognition) - ERD v3 final
   Membuat DATABASE BARU dari nol: semua tabel, view, prosedur, trigger, dan data awal
   (setara schema awal + migrasi 001-022). Diuji di SQL Server 2022; minimal SQL Server 2016 SP1
   (CREATE OR ALTER, JSON, HASHBYTES pada NVARCHAR(MAX)).

   ERD Ladder Desk (tahap 1: organisasi & hak akses berbahasa Inggris: Company, Mill, CompanyArea, Department(Details),
   Level(Details), Users, PasswordManager, Menu 3 level, ActionType, AccessMenu, UserCompany, UserSession).
   Mulai versi ini database DIBUAT BARU dari file ini; migrasi lama (database/migrations/ 001-043) hanya untuk
   database versi sebelumnya dan tidak dipakai lagi.

   Cara pakai (SSMS / VS Code mssql): ganti nama database di 2 baris di bawah bila perlu, lalu Execute.
   Login awal: admin / admin12345 (wajib ganti password saat login pertama).
   Diagram: docs/DOKUMENTASI.md
   ===================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
IF DB_ID('DbSistemTimbangan') IS NULL CREATE DATABASE DbSistemTimbangan;
GO
/* Baca data tidak menunggu kunci tulis (migrasi 018) */
ALTER DATABASE DbSistemTimbangan SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO
USE [DbSistemTimbangan]
GO

/* =========================== ORGANISASI & HAK AKSES (ERD Ladder Desk, tahap 1) ===========================
   Company (kode VARCHAR(5) sbg ID) -> CompanyArea (area milik perusahaan, bertipe Mill).
   Department + DepartmentDetails (departemen yang ada di sebuah area, Location SITE/HO).
   Level (jabatan umum) + LevelDetails (= PERAN: Departemen + Level; CompAreaID NULL = berlaku di semua area).
   Menu 3 level (ParentMenuID) + ActionType + AccessMenu (hak per peran = LevelDetID, atau per pengguna = UserID). */
CREATE TABLE dbo.Company (
    CompID       VARCHAR(5)       NOT NULL PRIMARY KEY,           -- kode perusahaan, mis. YBS, SUN
    CompName     NVARCHAR(100) NOT NULL,
    CompAddress  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_Company_Active DEFAULT (1),
    Description  NVARCHAR(255) NULL,
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_Company_Create DEFAULT (GETDATE())
);
-- Mill = tipe area, sama untuk semua perusahaan (HO, PKS, REFINERY, ...). IsHeadOffice = kantor pusat
CREATE TABLE dbo.Mill (
    MillID       BIGINT IDENTITY(1,1) PRIMARY KEY,
    MillCode     VARCHAR(10)   NOT NULL CONSTRAINT UX_Mill_Code UNIQUE,
    MillName     NVARCHAR(50)  NOT NULL,
    IsHeadOffice BIT NOT NULL CONSTRAINT DF_Mill_HO DEFAULT (0),
    Active       BIT NOT NULL CONSTRAINT DF_Mill_Active DEFAULT (1),
    Description  NVARCHAR(255) NULL,
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_Mill_Create DEFAULT (GETDATE())
);
-- Area milik perusahaan (YBS · OFFICE, YBS · REFINERY). AreaCode ikut MillCode.
CREATE TABLE dbo.CompanyArea (
    CompAreaID   BIGINT IDENTITY(1,1) PRIMARY KEY,
    CompID       VARCHAR(5)       NOT NULL CONSTRAINT FK_CompArea_Company REFERENCES dbo.Company (CompID),
    MillID       BIGINT        NULL CONSTRAINT FK_CompArea_Mill REFERENCES dbo.Mill (MillID),
    AreaCode     VARCHAR(10)   NOT NULL,
    AreaName     NVARCHAR(100) NOT NULL,
    AreaDesc     NVARCHAR(255) NULL,
    AreaAddress  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_CompArea_Active DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_CompArea_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_CompArea_CompName ON dbo.CompanyArea (CompID, AreaName);
CREATE TABLE dbo.Department (
    DeptID       VARCHAR(5)       NOT NULL PRIMARY KEY,           -- kode departemen, mis. TBG, HRD
    DeptName     NVARCHAR(120) NOT NULL CONSTRAINT UX_Department_Name UNIQUE,
    Description  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_Department_Active DEFAULT (1)
);
-- Departemen yang ada di sebuah area; akun memakai baris ini (Users.UserDeptID)
CREATE TABLE dbo.DepartmentDetails (
    DeptDetailID BIGINT IDENTITY(1,1) PRIMARY KEY,
    CompAreaID   BIGINT        NOT NULL CONSTRAINT FK_DeptDet_Area REFERENCES dbo.CompanyArea (CompAreaID),
    DeptID       VARCHAR(5)       NOT NULL CONSTRAINT FK_DeptDet_Dept REFERENCES dbo.Department (DeptID),
    Location     NVARCHAR(120) NOT NULL CONSTRAINT DF_DeptDet_Location DEFAULT ('SITE'),   -- SITE / HO
    Description  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_DeptDet_Active DEFAULT (1),
    CONSTRAINT UX_DeptDet_AreaDept UNIQUE (CompAreaID, DeptID)
);
-- Jabatan umum: Admin, Manager, Supervisor, Staff, Magang (ditambah di Admin › Organisasi)
CREATE TABLE dbo.Level (
    LevelID      INT IDENTITY(1,1) PRIMARY KEY,
    LevelName    NVARCHAR(120) NOT NULL CONSTRAINT UX_Level_Name UNIQUE,
    Description  NVARCHAR(255) NULL,
    IsAdmin      BIT NOT NULL CONSTRAINT DF_Level_Admin DEFAULT (0),     -- admin sistem: hanya menu Admin
    SortOrder    INT NOT NULL CONSTRAINT DF_Level_Sort DEFAULT (100),
    Active       BIT NOT NULL CONSTRAINT DF_Level_Active DEFAULT (1)
);
-- Peran = Departemen + Level (mis. "Security · Staff"); hak menu (AccessMenu) & halaman awal menempel di sini.
-- CompAreaID NULL = berlaku di semua area. Dibuat otomatis saat hak akses / akun pertama memakai gabungan ini.
CREATE TABLE dbo.LevelDetails (
    LevelDetID   INT IDENTITY(1,1) PRIMARY KEY,
    CompAreaID   BIGINT        NULL CONSTRAINT FK_LevelDet_Area REFERENCES dbo.CompanyArea (CompAreaID),
    LevelID      INT           NOT NULL CONSTRAINT FK_LevelDet_Level REFERENCES dbo.Level (LevelID),
    DeptID       VARCHAR(5)       NULL CONSTRAINT FK_LevelDet_Dept REFERENCES dbo.Department (DeptID),   -- NULL = admin sistem
    LevelDetCode VARCHAR(30)   NOT NULL CONSTRAINT UX_LevelDet_Code UNIQUE,
    LevelDetName NVARCHAR(120) NOT NULL,
    HomeUrl      VARCHAR(100)  NOT NULL CONSTRAINT DF_LevelDet_Home DEFAULT ('/weighbridge?view=list'),
    Description  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_LevelDet_Active DEFAULT (1)
);
CREATE UNIQUE INDEX UX_LevelDet_Role ON dbo.LevelDetails (DeptID, LevelID) WHERE CompAreaID IS NULL AND DeptID IS NOT NULL;
-- Menu 3 level (flowchart navbar): Lv1 grup, Lv2 halaman, Lv3 bagian / sub-halaman. Url NULL = belum ada (tautan '#').
CREATE TABLE dbo.Menu (
    MenuID       INT IDENTITY(1,1) PRIMARY KEY,
    MenuCode     VARCHAR(40)   NOT NULL CONSTRAINT UX_Menu_Code UNIQUE,
    MenuName     NVARCHAR(100) NOT NULL,
    Description  NVARCHAR(255) NULL,
    ParentMenuID INT           NULL CONSTRAINT FK_Menu_Parent REFERENCES dbo.Menu (MenuID),
    MenuLevel    TINYINT       NOT NULL CONSTRAINT DF_Menu_Level DEFAULT (2) CONSTRAINT CK_Menu_Level CHECK (MenuLevel BETWEEN 1 AND 3),
    Url          VARCHAR(200)  NULL,
    Icon         VARCHAR(40)   NULL,
    AppCode      VARCHAR(20)   NOT NULL CONSTRAINT DF_Menu_App DEFAULT ('CPOS'),   -- CPOS / ANALYTICS / REKAPIN
    SortOrder    INT NOT NULL CONSTRAINT DF_Menu_Sort DEFAULT (0),
    CompAreaID   BIGINT        NULL CONSTRAINT FK_Menu_Area REFERENCES dbo.CompanyArea (CompAreaID),   -- NULL = semua area
    Active       BIT NOT NULL CONSTRAINT DF_Menu_Active DEFAULT (1)
);
CREATE TABLE dbo.ActionType (
    ActionID     INT           NOT NULL PRIMARY KEY,
    TypeName     VARCHAR(100)  NOT NULL CONSTRAINT UX_ActionType_Name UNIQUE,
    Description  VARCHAR(255)  NULL,
    Active       BIT NOT NULL CONSTRAINT DF_ActionType_Active DEFAULT (1)
);
-- Hak menu: satu baris per menu x aksi, untuk peran (LevelDetID) ATAU pengguna (UserID, hak khusus).
-- Pengguna yang punya baris untuk sebuah menu memakai barisnya sendiri untuk menu itu (Active 0 = dicabut).
CREATE TABLE dbo.AccessMenu (
    AccessMenuID INT IDENTITY(1,1) PRIMARY KEY,
    MenuID       INT    NOT NULL CONSTRAINT FK_AccessMenu_Menu REFERENCES dbo.Menu (MenuID),
    ActionID     INT    NOT NULL CONSTRAINT FK_AccessMenu_Action REFERENCES dbo.ActionType (ActionID),
    LevelDetID   INT    NULL CONSTRAINT FK_AccessMenu_LevelDet REFERENCES dbo.LevelDetails (LevelDetID),
    UserID       BIGINT NULL,                       -- FK ke Users ditambahkan setelah tabel Users dibuat
    Active       BIT NOT NULL CONSTRAINT DF_AccessMenu_Active DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_AccessMenu_Create DEFAULT (GETDATE()),
    CONSTRAINT CK_AccessMenu_Target CHECK ((LevelDetID IS NULL AND UserID IS NOT NULL) OR (LevelDetID IS NOT NULL AND UserID IS NULL))
);
CREATE UNIQUE INDEX UX_AccessMenu_Level ON dbo.AccessMenu (LevelDetID, MenuID, ActionID) WHERE LevelDetID IS NOT NULL;
CREATE UNIQUE INDEX UX_AccessMenu_User ON dbo.AccessMenu (UserID, MenuID, ActionID) WHERE UserID IS NOT NULL;
GO
/* Isi awal ada di bagian DATA AWAL (paling bawah). */

/* =========================== MASTER =========================== */

-- Personel: supir, security, karyawan HO, tamu. SIM & wajah di tabel sendiri (migrasi 009), lihat v_personel
CREATE TABLE dbo.kategori_personel (
    kode        VARCHAR(20)   NOT NULL PRIMARY KEY,
    nama        NVARCHAR(50)  NOT NULL,
    wajib_sim   BIT NOT NULL CONSTRAINT DF_KatPersonel_Sim DEFAULT (0),
    boleh_akun  BIT NOT NULL CONSTRAINT DF_KatPersonel_Akun DEFAULT (0),
    prefix_kode VARCHAR(10)   NULL,                 -- kode personel per kategori, mis. DRV-001 (migrasi 020)
    is_active   BIT NOT NULL CONSTRAINT DF_KatPersonel_Aktif DEFAULT (1)
);
CREATE TABLE dbo.personel (
    id_personel          INT IDENTITY(1,1) PRIMARY KEY,
    kode_personel        VARCHAR(20)  NULL,                     -- diisi HO, mis. PRGBS-001
    nik                  VARCHAR(20)  NULL,                     -- 16 digit; boleh kosong untuk akun lama (migrasi 031)
    email                NVARCHAR(100) NULL,                    -- migrasi 031
    nama_personel        VARCHAR(100) NOT NULL,
    kategori             VARCHAR(20)  NOT NULL CONSTRAINT DF_Personel_Kategori DEFAULT ('DRIVER')
                         CONSTRAINT FK_Personel_Kategori REFERENCES dbo.kategori_personel (kode),
    is_updated           BIT NOT NULL CONSTRAINT DF_Personel_Updated DEFAULT (0),
    current_hash         VARCHAR(64)  NULL,
    is_blacklisted       BIT NOT NULL CONSTRAINT DF_Personel_Blacklist DEFAULT (0),
    is_active            BIT NOT NULL CONSTRAINT DF_Personel_Aktif DEFAULT (1),
    created_at           DATETIME NOT NULL CONSTRAINT DF_Personel_Created DEFAULT (GETDATE()),
    updated_at           DATETIME NOT NULL CONSTRAINT DF_Personel_Modified DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_Personel_Nik ON dbo.personel (nik) WHERE nik IS NOT NULL;
CREATE UNIQUE INDEX UX_Personel_Kode ON dbo.personel (kode_personel) WHERE kode_personel IS NOT NULL;
CREATE INDEX IX_Personel_Aktif_Kategori ON dbo.personel (is_active, kategori) INCLUDE (kode_personel, nama_personel);
GO

-- Pengguna (ERD Users). UserID = YYMMDD + urutan 4 digit (mis. 2601010001), dibuat aplikasi.
-- PersonnelID = tautan ke data personel / wajah (sementara, digabung ke Users di tahap 2).
CREATE TABLE dbo.Users (
    UserID            BIGINT        NOT NULL PRIMARY KEY,
    CompAreaID        BIGINT        NOT NULL CONSTRAINT FK_Users_Area REFERENCES dbo.CompanyArea (CompAreaID),
    UserCode          VARCHAR(20)   NULL,
    UserName          VARCHAR(50)   NOT NULL CONSTRAINT UX_Users_UserName UNIQUE,     -- username login
    UserDeptID        BIGINT        NULL CONSTRAINT FK_Users_DeptDet REFERENCES dbo.DepartmentDetails (DeptDetailID),   -- NULL = admin sistem
    UserLevelID       INT           NOT NULL CONSTRAINT FK_Users_LevelDet REFERENCES dbo.LevelDetails (LevelDetID),
    NoKTP             CHAR(16)      NULL,
    GuestID           BIGINT        NULL,
    Nama              NVARCHAR(100) NOT NULL,
    Email             NVARCHAR(100) NULL,
    FaceEmbeddingData VARBINARY(MAX) NULL,
    UploadPath        NVARCHAR(200) NULL,
    CurrentHash       NVARCHAR(64)  NULL,
    CreateDate        DATETIME NOT NULL CONSTRAINT DF_Users_Create DEFAULT (GETDATE()),
    UpdateDate        DATETIME NOT NULL CONSTRAINT DF_Users_Update DEFAULT (GETDATE()),
    Active            BIT NOT NULL CONSTRAINT DF_Users_Active DEFAULT (1),
    IsUpload          BIT NOT NULL CONSTRAINT DF_Users_Upload DEFAULT (0),
    BlacklistID       BIGINT        NULL,
    Description       NVARCHAR(255) NULL,
    PersonnelID       INT           NOT NULL CONSTRAINT FK_Users_Personel REFERENCES dbo.personel (id_personel),
    LastLogin         DATETIME      NULL,
    SessionVersion    INT NOT NULL CONSTRAINT DF_Users_SessVer DEFAULT (0)       -- naik = semua sesi user dicabut
);
CREATE UNIQUE INDEX UX_Users_Personnel ON dbo.Users (PersonnelID);
-- Password (hash) + riwayat (History JSON: hash terakhir, terbaru dulu) untuk menolak pemakaian ulang.
-- MustChange = 1 -> wajib buat password baru saat login.
CREATE TABLE dbo.PasswordManager (
    UserID      BIGINT        NOT NULL PRIMARY KEY CONSTRAINT FK_PwMgr_User REFERENCES dbo.Users (UserID),
    UserPasswd  VARCHAR(255)  NOT NULL,
    CreateDate  DATETIME NOT NULL CONSTRAINT DF_PwMgr_Create DEFAULT (GETDATE()),
    MustChange  BIT NOT NULL CONSTRAINT DF_PwMgr_Must DEFAULT (1),
    History     NVARCHAR(MAX) NOT NULL CONSTRAINT DF_PwMgr_History DEFAULT (N'[]')
                CONSTRAINT CK_PwMgr_History CHECK (ISJSON(History) = 1),
    Term        INT           NULL,
    Description NVARCHAR(255) NULL
);
ALTER TABLE dbo.AccessMenu ADD CONSTRAINT FK_AccessMenu_User FOREIGN KEY (UserID) REFERENCES dbo.Users (UserID);
-- Perusahaan yang dikelola user kantor pusat. Kosong = semua perusahaan
CREATE TABLE dbo.UserCompany (
    UserID  BIGINT  NOT NULL CONSTRAINT FK_UserComp_User REFERENCES dbo.Users (UserID),
    CompID  VARCHAR(5) NOT NULL CONSTRAINT FK_UserComp_Company REFERENCES dbo.Company (CompID),
    CONSTRAINT PK_UserCompany PRIMARY KEY (UserID, CompID)
);
GO

/* SIM, wajah, kunjungan tamu (migrasi 009) */
CREATE TABLE dbo.jenis_sim (
    id_jenis_sim INT IDENTITY(1,1) PRIMARY KEY,
    kode         VARCHAR(20)  NOT NULL CONSTRAINT UX_JenisSim_Kode UNIQUE,
    nama         NVARCHAR(50) NOT NULL,
    is_active    BIT NOT NULL CONSTRAINT DF_JenisSim_Aktif DEFAULT (1)
);
CREATE TABLE dbo.personel_sim (
    id_sim          INT IDENTITY(1,1) PRIMARY KEY,
    id_personel     INT NOT NULL CONSTRAINT FK_PersonelSim_Personel REFERENCES dbo.personel (id_personel),
    id_jenis_sim    INT NOT NULL CONSTRAINT FK_PersonelSim_Jenis REFERENCES dbo.jenis_sim (id_jenis_sim),
    no_sim          VARCHAR(30) NOT NULL,
    berlaku_sampai  DATE NULL,                 -- NULL hanya untuk data lama yang belum dilengkapi
    is_active       BIT NOT NULL CONSTRAINT DF_PersonelSim_Aktif DEFAULT (1),
    created_by      BIGINT NULL CONSTRAINT FK_PersonelSim_User REFERENCES dbo.Users (UserID),
    created_at      DATETIME NOT NULL CONSTRAINT DF_PersonelSim_Created DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_PersonelSim_NoAktif ON dbo.personel_sim (no_sim) WHERE is_active = 1;
CREATE INDEX IX_PersonelSim_Personel ON dbo.personel_sim (id_personel, is_active);
CREATE TABLE dbo.personel_wajah (
    id_wajah     INT IDENTITY(1,1) PRIMARY KEY,
    id_personel  INT NOT NULL CONSTRAINT FK_PersonelWajah_Personel REFERENCES dbo.personel (id_personel),
    embedding    VARBINARY(MAX) NOT NULL,
    foto_path    VARCHAR(255) NULL,
    sumber       VARCHAR(10)  NULL CONSTRAINT CK_PersonelWajah_Sumber CHECK (sumber IN ('UPLOAD', 'KAMERA')),
    is_utama     BIT NOT NULL CONSTRAINT DF_PersonelWajah_Utama DEFAULT (1),
    is_active    BIT NOT NULL CONSTRAINT DF_PersonelWajah_Aktif DEFAULT (1),
    created_by   BIGINT NULL CONSTRAINT FK_PersonelWajah_User REFERENCES dbo.Users (UserID),
    created_at   DATETIME NOT NULL CONSTRAINT DF_PersonelWajah_Created DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_PersonelWajah_Utama ON dbo.personel_wajah (id_personel) WHERE is_utama = 1 AND is_active = 1;
CREATE INDEX IX_PersonelWajah_Aktif ON dbo.personel_wajah (is_active) INCLUDE (id_personel);
CREATE TABLE dbo.keperluan_kunjungan (
    id_keperluan INT IDENTITY(1,1) PRIMARY KEY,
    nama         NVARCHAR(100) NOT NULL CONSTRAINT UX_Keperluan_Nama UNIQUE,
    is_active    BIT NOT NULL CONSTRAINT DF_Keperluan_Aktif DEFAULT (1)
);
CREATE TABLE dbo.kunjungan (
    id_kunjungan     INT IDENTITY(1,1) PRIMARY KEY,
    id_personel      INT NOT NULL CONSTRAINT FK_Kunjungan_Tamu REFERENCES dbo.personel (id_personel),
    id_dituju        INT NOT NULL CONSTRAINT FK_Kunjungan_Dituju REFERENCES dbo.personel (id_personel),
    id_keperluan     INT NOT NULL CONSTRAINT FK_Kunjungan_Keperluan REFERENCES dbo.keperluan_kunjungan (id_keperluan),
    keterangan       NVARCHAR(255) NULL,
    asal_perusahaan  NVARCHAR(100) NULL,
    no_plat          VARCHAR(15)   NULL,
    id_comp_area     BIGINT NOT NULL CONSTRAINT FK_Kunjungan_Area REFERENCES dbo.CompanyArea (CompAreaID),
    foto_masuk_path  VARCHAR(255)  NULL,      -- snapshot wajah saat datang
    waktu_masuk      DATETIME NOT NULL CONSTRAINT DF_Kunjungan_Masuk DEFAULT (GETDATE()),
    waktu_keluar     DATETIME NULL,           -- NULL = tamu masih di dalam
    dicatat_oleh     BIGINT NOT NULL CONSTRAINT FK_Kunjungan_User REFERENCES dbo.Users (UserID),
    CONSTRAINT CK_Kunjungan_Keluar CHECK (waktu_keluar IS NULL OR waktu_keluar >= waktu_masuk)
);
CREATE INDEX IX_Kunjungan_Masuk ON dbo.kunjungan (waktu_masuk DESC);
CREATE INDEX IX_Kunjungan_Didalam ON dbo.kunjungan (id_personel) WHERE waktu_keluar IS NULL;
GO
/* Dokumen umum (migrasi 010) */
CREATE TABLE dbo.jenis_dokumen (
    id_jenis    INT IDENTITY(1,1) PRIMARY KEY,
    kode        VARCHAR(30)   NOT NULL CONSTRAINT UX_JenisDok_Kode UNIQUE,
    nama        NVARCHAR(100) NOT NULL,
    wajib_file  BIT NOT NULL CONSTRAINT DF_JenisDok_WajibFile DEFAULT (1),
    is_active   BIT NOT NULL CONSTRAINT DF_JenisDok_Aktif DEFAULT (1)
);
CREATE TABLE dbo.dokumen (
    id_dokumen  INT IDENTITY(1,1) PRIMARY KEY,
    id_jenis    INT NOT NULL CONSTRAINT FK_Dokumen_Jenis REFERENCES dbo.jenis_dokumen (id_jenis),
    no_dokumen  NVARCHAR(100) NOT NULL,
    tanggal     DATE NOT NULL,
    perihal     NVARCHAR(255) NULL,
    created_by  BIGINT NOT NULL CONSTRAINT FK_Dokumen_User REFERENCES dbo.Users (UserID),
    created_at  DATETIME NOT NULL CONSTRAINT DF_Dokumen_Created DEFAULT (GETDATE())
);
CREATE INDEX IX_Dokumen_Jenis_No ON dbo.dokumen (id_jenis, no_dokumen);
CREATE TABLE dbo.dokumen_file (
    id_file      INT IDENTITY(1,1) PRIMARY KEY,
    id_dokumen   INT NOT NULL CONSTRAINT FK_DokFile_Dokumen REFERENCES dbo.dokumen (id_dokumen),
    file_path    VARCHAR(255)  NOT NULL,          -- 'uploads/dokumen/...' (privat, dibuka lewat /berkas/)
    nama_asli    NVARCHAR(255) NULL,
    mime         VARCHAR(100)  NULL,
    ukuran_byte  INT NULL,
    sha256       CHAR(64) NULL,                   -- NULL hanya untuk file lama (sebelum migrasi 010)
    urutan       TINYINT NOT NULL CONSTRAINT DF_DokFile_Urutan DEFAULT (1),
    created_at   DATETIME NOT NULL CONSTRAINT DF_DokFile_Created DEFAULT (GETDATE())
);
CREATE INDEX IX_DokFile_Dokumen ON dbo.dokumen_file (id_dokumen, urutan);
GO
CREATE OR ALTER VIEW dbo.v_personel AS
SELECT p.id_personel, p.kode_personel, p.nik, p.nama_personel, p.kategori, p.is_updated, p.current_hash,
       p.is_blacklisted, p.is_active, p.created_at, p.updated_at,
       s.no_sim, s.id_jenis_sim, s.kode_jenis_sim, s.berlaku_sampai AS sim_berlaku_sampai,
       w.embedding AS face_embedding_data, w.foto_path, w.sumber AS foto_sumber
FROM dbo.personel p
OUTER APPLY (SELECT TOP 1 ps.no_sim, ps.id_jenis_sim, j.kode AS kode_jenis_sim, ps.berlaku_sampai
             FROM dbo.personel_sim ps JOIN dbo.jenis_sim j ON j.id_jenis_sim = ps.id_jenis_sim
             WHERE ps.id_personel = p.id_personel AND ps.is_active = 1
             ORDER BY ps.berlaku_sampai DESC, ps.id_sim DESC) s
OUTER APPLY (SELECT TOP 1 pw.embedding, pw.foto_path, pw.sumber
             FROM dbo.personel_wajah pw
             WHERE pw.id_personel = p.id_personel AND pw.is_active = 1
             ORDER BY pw.is_utama DESC, pw.id_wajah DESC) w;
GO

-- Customer (membeli / menjual) & pengangkutan pihak ketiga
CREATE TABLE dbo.mitra (
    id_supplier    INT IDENTITY(1,1) PRIMARY KEY,
    kode_supplier  VARCHAR(20)  NOT NULL CONSTRAINT UX_Supplier_Kode UNIQUE,
    nama_supplier  VARCHAR(100) NOT NULL,
    is_active      BIT NOT NULL CONSTRAINT DF_Supplier_Aktif DEFAULT (1),
    created_at     DATETIME NOT NULL CONSTRAINT DF_Supplier_Created DEFAULT (GETDATE()),
    alamat         NVARCHAR(255) NULL                                  -- migrasi 032
);
-- Supplier hanya berlaku di PT tertentu (migrasi 032); tanpa baris = semua PT
CREATE TABLE dbo.mitra_company (
    id_supplier INT NOT NULL CONSTRAINT FK_MitraCompany_Mitra REFERENCES dbo.mitra (id_supplier),
    id_company  VARCHAR(5) NOT NULL CONSTRAINT FK_MitraCompany_Company REFERENCES dbo.Company (CompID),
    CONSTRAINT PK_MitraCompany PRIMARY KEY (id_supplier, id_company)
);
GO
-- Peran mitra (migrasi 013, nama tabel migrasi 016): satu mitra boleh customer sekaligus pengangkutan
CREATE TABLE dbo.mitra_peran (
    id_supplier  INT NOT NULL CONSTRAINT FK_SupPeran_Supplier REFERENCES dbo.mitra (id_supplier),
    peran        VARCHAR(20) NOT NULL CONSTRAINT CK_SupPeran_Peran CHECK (peran IN ('CUSTOMER', 'PENGANGKUTAN')),
    CONSTRAINT PK_SupplierPeran PRIMARY KEY (id_supplier, peran)
);
GO

-- Alur tahap tiket (migrasi 012): urutan tahap per alur, dipakai produk & transaksi
CREATE TABLE dbo.tahap (
    kode    VARCHAR(20)  NOT NULL PRIMARY KEY,
    nama    NVARCHAR(50) NOT NULL,
    urutan  TINYINT NOT NULL
);
GO
CREATE TABLE dbo.alur (
    id_alur    INT IDENTITY(1,1) PRIMARY KEY,
    kode       VARCHAR(20)   NOT NULL CONSTRAINT UX_Alur_Kode UNIQUE,
    nama       NVARCHAR(100) NOT NULL,
    is_active  BIT NOT NULL CONSTRAINT DF_Alur_Aktif DEFAULT (1)
);
GO
CREATE TABLE dbo.alur_tahap (
    id_alur     INT NOT NULL CONSTRAINT FK_AlurTahap_Alur REFERENCES dbo.alur (id_alur),
    urutan      TINYINT NOT NULL,
    kode_tahap  VARCHAR(20) NOT NULL CONSTRAINT FK_AlurTahap_Tahap REFERENCES dbo.tahap (kode),
    CONSTRAINT PK_AlurTahap PRIMARY KEY (id_alur, urutan),
    CONSTRAINT UX_AlurTahap_Tahap UNIQUE (id_alur, kode_tahap)
);
GO

CREATE TABLE dbo.produk (
    id_produk    INT IDENTITY(1,1) PRIMARY KEY,
    nama_produk  VARCHAR(100) NOT NULL,
    kategori     VARCHAR(20)  NOT NULL,
    id_alur      INT NOT NULL CONSTRAINT FK_Produk_Alur REFERENCES dbo.alur (id_alur),
    is_active    BIT NOT NULL CONSTRAINT DF_Produk_Aktif DEFAULT (1),
    CONSTRAINT CK_Produk_Kategori CHECK (kategori IN ('TBS', 'PRODUK_PKS'))
);
GO

CREATE TABLE dbo.standar_mutu (
    id_produk     INT PRIMARY KEY CONSTRAINT FK_Standar_Produk REFERENCES dbo.produk (id_produk),
    maks_ffa      FLOAT NOT NULL CONSTRAINT DF_Standar_Ffa DEFAULT (5.0),
    maks_air      FLOAT NOT NULL CONSTRAINT DF_Standar_Air DEFAULT (0.5),
    maks_kotoran  FLOAT NOT NULL CONSTRAINT DF_Standar_Kotoran DEFAULT (0.5)
);
GO

-- Jenis kendaraan (migrasi 014)
CREATE TABLE dbo.jenis_kendaraan (
    id_jenis_kendaraan  INT IDENTITY(1,1) PRIMARY KEY,
    kode                VARCHAR(20)  NOT NULL CONSTRAINT UX_JenisKendaraan_Kode UNIQUE,
    nama                NVARCHAR(50) NOT NULL,
    is_active           BIT NOT NULL CONSTRAINT DF_JenisKendaraan_Aktif DEFAULT (1),
    -- Kapasitas (migrasi 032): peringatan di timbangan; kosong = tidak dicek
    berat_kosong_kg     DECIMAL(10, 2) NULL,
    muatan_maks_kg      DECIMAL(10, 2) NULL,
    kursi               INT NULL
);
GO
-- STNK wajib & unik (migrasi 014)
CREATE TABLE dbo.kendaraan (
    id_kendaraan    INT IDENTITY(1,1) PRIMARY KEY,
    no_plat         VARCHAR(15) NOT NULL CONSTRAINT UX_Kendaraan_Plat UNIQUE,
    no_stnk         VARCHAR(50) NOT NULL,
    id_jenis_kendaraan INT NULL CONSTRAINT FK_Kendaraan_Jenis REFERENCES dbo.jenis_kendaraan (id_jenis_kendaraan),
    is_blacklisted  BIT NOT NULL CONSTRAINT DF_Kendaraan_Blacklist DEFAULT (0),
    is_active       BIT NOT NULL CONSTRAINT DF_Kendaraan_Aktif DEFAULT (1),
    created_at      DATETIME NOT NULL CONSTRAINT DF_Kendaraan_Created DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_Kendaraan_Stnk ON dbo.kendaraan (no_stnk) WHERE no_stnk IS NOT NULL;
GO

-- Supir terdaftar per truk (supir utama disarankan saat Create Ticket)
CREATE TABLE dbo.kendaraan_driver (
    id_kendaraan_driver INT IDENTITY(1,1) PRIMARY KEY,
    id_kendaraan  INT NOT NULL CONSTRAINT FK_KD_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    id_driver     INT NOT NULL CONSTRAINT FK_KD_Driver REFERENCES dbo.personel (id_personel),
    is_utama      BIT NOT NULL CONSTRAINT DF_KD_Utama DEFAULT (0),
    is_active     BIT NOT NULL CONSTRAINT DF_KD_Active DEFAULT (1),
    created_by    BIGINT NULL CONSTRAINT FK_KD_User REFERENCES dbo.Users (UserID),
    created_at    DATETIME NOT NULL CONSTRAINT DF_KD_Created DEFAULT (GETDATE()),
    updated_at    DATETIME NOT NULL CONSTRAINT DF_KD_Updated DEFAULT (GETDATE()),
    CONSTRAINT UQ_KD_Kendaraan_Driver UNIQUE (id_kendaraan, id_driver)
);
CREATE INDEX IX_KD_Driver ON dbo.kendaraan_driver (id_driver) INCLUDE (id_kendaraan, is_active, is_utama);
GO

-- Kontrak per truk (modal Update > Kontrak Truk di Form Security)
CREATE TABLE dbo.kontrak_kendaraan (
    id_kontrak       INT IDENTITY(1,1) PRIMARY KEY,
    no_kontrak       VARCHAR(50) NULL,
    id_kendaraan     INT NOT NULL CONSTRAINT FK_KK_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    id_supplier      INT NOT NULL CONSTRAINT FK_KK_Supplier REFERENCES dbo.mitra (id_supplier),
    id_produk        INT NULL CONSTRAINT FK_KK_Produk REFERENCES dbo.produk (id_produk),
    jenis_transaksi  VARCHAR(20) NULL,
    tanggal_mulai    DATE NOT NULL,
    tanggal_selesai  DATE NULL,
    is_active        BIT NOT NULL CONSTRAINT DF_KK_Active DEFAULT (1),
    keterangan       VARCHAR(255) NULL,
    created_by       BIGINT NULL CONSTRAINT FK_KK_User REFERENCES dbo.Users (UserID),
    created_at       DATETIME NOT NULL CONSTRAINT DF_KK_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_KK_Jenis CHECK (jenis_transaksi IS NULL OR jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_KK_Periode CHECK (tanggal_selesai IS NULL OR tanggal_selesai >= tanggal_mulai)
);
CREATE INDEX IX_KK_Kendaraan ON dbo.kontrak_kendaraan (id_kendaraan, is_active);
CREATE INDEX IX_KK_Kendaraan_Supplier ON dbo.kontrak_kendaraan (id_kendaraan, id_supplier, is_active);
GO

-- Kontrak & DO (migrasi 013, diisi HO): 1 kontrak = 1 produk = 1 DO; 1 DO boleh beberapa pengangkut
-- Jenis tiket + is_bayar (WeightBridgeType.isPayment, migrasi 033): disiapkan untuk tahap keuangan, belum ditampilkan
CREATE TABLE dbo.jenis_transaksi (
    kode      VARCHAR(20)  NOT NULL PRIMARY KEY,
    nama      NVARCHAR(50) NOT NULL,
    is_bayar  BIT NOT NULL CONSTRAINT DF_JenisTrx_Bayar DEFAULT (0),
    is_active BIT NOT NULL CONSTRAINT DF_JenisTrx_Aktif DEFAULT (1)
);
-- Nama & warna status tiket (Status: StatusName, StatusColor, migrasi 033), diatur di Admin › Organisasi
CREATE TABLE dbo.status_tiket (
    kode   VARCHAR(30)  NOT NULL PRIMARY KEY,
    nama   NVARCHAR(50) NOT NULL,
    warna  VARCHAR(10)  NOT NULL CONSTRAINT DF_StatusTiket_Warna DEFAULT ('abu'),
    urutan TINYINT NOT NULL CONSTRAINT DF_StatusTiket_Urutan DEFAULT (0)
);
CREATE TABLE dbo.kontrak (
    id_kontrak       INT IDENTITY(1,1) PRIMARY KEY,
    no_kontrak       VARCHAR(50) NOT NULL CONSTRAINT UX_Kontrak_No UNIQUE,
    jenis_transaksi  VARCHAR(20) NOT NULL,
    id_customer      INT NOT NULL CONSTRAINT FK_Kontrak_Customer REFERENCES dbo.mitra (id_supplier),
    id_produk        INT NOT NULL CONSTRAINT FK_Kontrak_Produk REFERENCES dbo.produk (id_produk),
    tanggal          DATE NOT NULL CONSTRAINT DF_Kontrak_Tanggal DEFAULT (CAST(GETDATE() AS DATE)),
    qty_kg           DECIMAL(14, 2) NULL,
    harga_per_kg     DECIMAL(14, 2) NULL,
    keterangan       VARCHAR(200) NULL,
    is_active        BIT NOT NULL CONSTRAINT DF_Kontrak_Aktif DEFAULT (1),
    created_by       BIGINT NULL CONSTRAINT FK_Kontrak_User REFERENCES dbo.Users (UserID),
    created_at       DATETIME NOT NULL CONSTRAINT DF_Kontrak_Created DEFAULT (GETDATE()),
    -- migrasi 033: PPN & PT pemilik kontrak
    ppn                BIT NOT NULL CONSTRAINT DF_Kontrak_Ppn DEFAULT (0),
    harga_termasuk_ppn BIT NOT NULL CONSTRAINT DF_Kontrak_InclPpn DEFAULT (0),
    id_company         VARCHAR(5) NULL CONSTRAINT FK_Kontrak_Company REFERENCES dbo.Company (CompID),
    CONSTRAINT CK_Kontrak_Jenis CHECK (jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_Kontrak_Qty CHECK (qty_kg IS NULL OR qty_kg > 0)
);
GO
CREATE TABLE dbo.delivery_order (
    id_do           INT IDENTITY(1,1) PRIMARY KEY,
    no_do           VARCHAR(50) NOT NULL CONSTRAINT UX_DO_No UNIQUE,
    id_kontrak      INT NOT NULL CONSTRAINT FK_DO_Kontrak REFERENCES dbo.kontrak (id_kontrak),
    tanggal_do      DATE NOT NULL CONSTRAINT DF_DO_Tanggal DEFAULT (CAST(GETDATE() AS DATE)),
    berlaku_sampai  DATE NULL,
    keterangan      VARCHAR(200) NULL,
    is_active       BIT NOT NULL CONSTRAINT DF_DO_Aktif DEFAULT (1),
    created_by      BIGINT NULL CONSTRAINT FK_DO_User REFERENCES dbo.Users (UserID),
    created_at      DATETIME NOT NULL CONSTRAINT DF_DO_Created DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_DO_Kontrak ON dbo.delivery_order (id_kontrak);     -- 1 kontrak = 1 DO
GO
CREATE TABLE dbo.do_pengangkutan (
    id_do_angkut     INT IDENTITY(1,1) PRIMARY KEY,
    id_do            INT NOT NULL CONSTRAINT FK_DoAngkut_DO REFERENCES dbo.delivery_order (id_do),
    cara_angkut      VARCHAR(15) NOT NULL,
    id_pengangkutan  INT NULL CONSTRAINT FK_DoAngkut_Supplier REFERENCES dbo.mitra (id_supplier),
    qty_kg           DECIMAL(14, 2) NULL,               -- alokasi (opsional), total <= kontrak.qty_kg
    ongkos_per_kg    DECIMAL(14, 2) NULL,               -- ongkos angkut (migrasi 033)
    CONSTRAINT CK_DoAngkut_Cara CHECK (cara_angkut IN ('PENGIRIM', 'PENERIMA', 'PIHAK_KETIGA')),
    CONSTRAINT CK_DoAngkut_PihakKetiga CHECK ((cara_angkut = 'PIHAK_KETIGA' AND id_pengangkutan IS NOT NULL)
                                              OR (cara_angkut <> 'PIHAK_KETIGA' AND id_pengangkutan IS NULL)),
    CONSTRAINT UX_DoAngkut UNIQUE (id_do, cara_angkut, id_pengangkutan)
);
GO

-- Dashboard: harga per tanggal (diisi HO)
CREATE TABLE dbo.harga_harian (
    tanggal       DATE PRIMARY KEY,
    harga_cpo     DECIMAL(12,2) NOT NULL,
    harga_kernel  DECIMAL(12,2) NOT NULL,
    oer_cpo       DECIMAL(5,2)  NOT NULL,
    biaya_olah    DECIMAL(12,2) NOT NULL,
    updated_by    BIGINT NULL CONSTRAINT FK_Harga_User REFERENCES dbo.Users (UserID),
    updated_at    DATETIME NOT NULL CONSTRAINT DF_Harga_Updated DEFAULT (GETDATE()),
    CONSTRAINT CK_Harga_Oer CHECK (oer_cpo BETWEEN 0 AND 100)
);
GO

/* =========================== TRANSAKSI =========================== */

-- Jembatan timbang per area (migrasi 011)
CREATE TABLE dbo.jembatan_timbang (
    id_jembatan   INT IDENTITY(1,1) PRIMARY KEY,
    id_comp_area  BIGINT NOT NULL CONSTRAINT FK_Jembatan_Area REFERENCES dbo.CompanyArea (CompAreaID),
    kode          VARCHAR(10)   NOT NULL,
    nama          NVARCHAR(100) NOT NULL,
    port          VARCHAR(100)  NOT NULL,                 -- COM3 / /dev/ttyUSB0 / socket://IP:PORT (alat serial-to-LAN)
    baudrate      INT NOT NULL CONSTRAINT DF_Jembatan_Baud DEFAULT (9600),
    is_active     BIT NOT NULL CONSTRAINT DF_Jembatan_Aktif DEFAULT (1),
    created_at    DATETIME NOT NULL CONSTRAINT DF_Jembatan_Created DEFAULT (GETDATE()),
    -- Profil indikator (migrasi 017): LOKAL = dibaca server, AGEN = dibaca agen_timbang.py di PC jembatan
    mode           VARCHAR(10)   NOT NULL CONSTRAINT DF_Jembatan_Mode DEFAULT ('LOKAL'),
    data_bits      TINYINT       NOT NULL CONSTRAINT DF_Jembatan_DataBits DEFAULT (7),
    parity         CHAR(1)       NOT NULL CONSTRAINT DF_Jembatan_Parity DEFAULT ('E'),
    stop_bits      DECIMAL(2, 1) NOT NULL CONSTRAINT DF_Jembatan_StopBits DEFAULT (1),
    format_data    VARCHAR(20)   NOT NULL CONSTRAINT DF_Jembatan_Format DEFAULT ('ST_GS'),
    pola           VARCHAR(200)  NULL,
    faktor         DECIMAL(10, 4) NOT NULL CONSTRAINT DF_Jembatan_Faktor DEFAULT (1),
    toleransi_kg   DECIMAL(9, 2) NOT NULL CONSTRAINT DF_Jembatan_Toleransi DEFAULT (5),
    durasi_stabil  DECIMAL(4, 1) NOT NULL CONSTRAINT DF_Jembatan_Durasi DEFAULT (3),
    berat_min_kg   DECIMAL(10, 2) NOT NULL CONSTRAINT DF_Jembatan_BeratMin DEFAULT (100),
    wajib_st       BIT           NOT NULL CONSTRAINT DF_Jembatan_WajibSt DEFAULT (0),
    CONSTRAINT UX_Jembatan_AreaKode UNIQUE (id_comp_area, kode),
    CONSTRAINT CK_Jembatan_Profil CHECK (
        mode IN ('LOKAL', 'AGEN') AND data_bits IN (5, 6, 7, 8) AND parity IN ('N', 'E', 'O', 'M', 'S')
        AND stop_bits IN (1, 1.5, 2) AND format_data IN ('ST_GS', 'ANGKA', 'TERBALIK', 'POLA')
        AND faktor > 0 AND toleransi_kg >= 0 AND durasi_stabil >= 0.5 AND berat_min_kg >= 0)
);
GO
CREATE TABLE dbo.transaksi (
    no_tiket           VARCHAR(50) PRIMARY KEY,
    jenis_transaksi    VARCHAR(20) NOT NULL,
    id_supplier        INT NOT NULL CONSTRAINT FK_Trx_Supplier REFERENCES dbo.mitra (id_supplier),     -- customer (dari DO)
    id_produk          INT NOT NULL CONSTRAINT FK_Trx_Produk REFERENCES dbo.produk (id_produk),
    id_kendaraan       INT NOT NULL CONSTRAINT FK_Trx_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    id_driver          INT NOT NULL CONSTRAINT FK_Trx_Driver REFERENCES dbo.personel (id_personel),
    id_pengangkutan    INT NULL CONSTRAINT FK_Trx_Angkut REFERENCES dbo.mitra (id_supplier),
    id_kontrak         INT NULL CONSTRAINT FK_Trx_Kontrak REFERENCES dbo.kontrak_kendaraan (id_kontrak),
    no_do              VARCHAR(50) NULL,
    status_alur        VARCHAR(30) NOT NULL CONSTRAINT DF_Trx_Status DEFAULT ('SECURITY_REGISTER'),
    is_qr_active       BIT NOT NULL CONSTRAINT DF_Trx_QrAktif DEFAULT (1),
    qr_expired_at      DATETIME NOT NULL,
    qr_reprint_count   INT NOT NULL CONSTRAINT DF_Trx_Reprint DEFAULT (0),
    driver_photo_path  VARCHAR(255) NULL,
    security_id        BIGINT NOT NULL CONSTRAINT FK_Trx_Security REFERENCES dbo.Users (UserID),
    id_jembatan        INT NULL CONSTRAINT FK_Trx_Jembatan REFERENCES dbo.jembatan_timbang (id_jembatan),   -- jembatan timbang masuk
    id_comp_area       BIGINT NOT NULL CONSTRAINT FK_Trx_Area REFERENCES dbo.CompanyArea (CompAreaID),          -- area akun Security (migrasi 041)
    id_alur            INT NULL CONSTRAINT FK_Trx_Alur REFERENCES dbo.alur (id_alur),                       -- alur tahap tiket (dari produk)
    id_do              INT NULL CONSTRAINT FK_Trx_DO REFERENCES dbo.delivery_order (id_do),
    cara_angkut        VARCHAR(15) NOT NULL,                        -- PENGIRIM / PENERIMA / PIHAK_KETIGA (id_pengangkutan)
    no_tiket_induk     VARCHAR(50) NULL CONSTRAINT FK_Trx_Induk REFERENCES dbo.transaksi (no_tiket),   -- tiket split kelebihan DO (migrasi 022)
    berat_split_kg     DECIMAL(14, 2) NULL,                         -- netto tiket split (tanpa penimbangan sendiri)
    created_at         DATETIME NOT NULL CONSTRAINT DF_Trx_Created DEFAULT (GETDATE()),
    diperiksa_pada     DATETIME NULL,                               -- verifikasi tiket selesai (migrasi 033)
    diperiksa_oleh     BIGINT NULL CONSTRAINT FK_Trx_Pemeriksa REFERENCES dbo.Users (UserID),
    waktu_keluar       DATETIME NULL,                               -- jam keluar gerbang, Logbook (migrasi 039)
    keluar_oleh        BIGINT NULL CONSTRAINT FK_Trx_Keluar REFERENCES dbo.Users (UserID),
    CONSTRAINT CK_Trx_Jenis CHECK (jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_Trx_CaraAngkut CHECK ((cara_angkut = 'PIHAK_KETIGA' AND id_pengangkutan IS NOT NULL)
                                        OR (cara_angkut IN ('PENGIRIM', 'PENERIMA') AND id_pengangkutan IS NULL)),
    CONSTRAINT CK_Trx_Status CHECK (status_alur IN ('SECURITY_REGISTER', 'SCAN_WAJAH', 'TIMBANG_1', 'INSPEKSI_PROSES',
                                                    'TIMBANG_2', 'SELESAI', 'REJECTED', 'VOID'))
);
CREATE INDEX IX_Trx_Status_Created ON dbo.transaksi (status_alur, created_at DESC) INCLUDE (id_kendaraan, id_supplier, id_driver);
CREATE INDEX IX_Trx_Kendaraan_Created ON dbo.transaksi (id_kendaraan, created_at DESC);
CREATE INDEX IX_Trx_Keluar ON dbo.transaksi (waktu_keluar) INCLUDE (id_kendaraan, id_comp_area, status_alur);
CREATE INDEX IX_Trx_Area_Created ON dbo.transaksi (id_comp_area, created_at DESC);
CREATE INDEX IX_Trx_Supplier_Created ON dbo.transaksi (id_supplier, created_at DESC);
CREATE INDEX IX_Trx_Driver_Created ON dbo.transaksi (id_driver, created_at DESC);
GO

-- Void (Admin) / reject (Lab), migrasi 010
CREATE TABLE dbo.pembatalan_tiket (
    no_tiket    VARCHAR(50)   NOT NULL PRIMARY KEY CONSTRAINT FK_Batal_Transaksi REFERENCES dbo.transaksi (no_tiket),
    jenis       VARCHAR(10)   NOT NULL CONSTRAINT CK_Batal_Jenis CHECK (jenis IN ('VOID', 'REJECT')),
    alasan      NVARCHAR(255) NOT NULL,
    id_dokumen  INT NULL CONSTRAINT FK_Batal_Dokumen REFERENCES dbo.dokumen (id_dokumen),   -- berita acara, boleh menyusul
    oleh        BIGINT NULL CONSTRAINT FK_Batal_User REFERENCES dbo.Users (UserID),           -- NULL hanya data lama
    waktu       DATETIME NOT NULL CONSTRAINT DF_Batal_Waktu DEFAULT (GETDATE())
);
CREATE INDEX IX_Batal_Waktu ON dbo.pembatalan_tiket (waktu DESC);
GO

-- Penimbangan (migrasi 011): ke-1 masuk, ke-2 keluar di jembatan yang sama; bruto/tara/netto lewat v_timbangan
CREATE TABLE dbo.penimbangan (
    no_tiket     VARCHAR(50) NOT NULL CONSTRAINT FK_Penimbangan_Trx REFERENCES dbo.transaksi (no_tiket),
    ke           TINYINT NOT NULL CONSTRAINT CK_Penimbangan_Ke CHECK (ke IN (1, 2)),
    id_jembatan  INT NOT NULL CONSTRAINT FK_Penimbangan_Jembatan REFERENCES dbo.jembatan_timbang (id_jembatan),
    berat_kg     DECIMAL(10, 2) NOT NULL,
    waktu        DATETIME NOT NULL CONSTRAINT DF_Penimbangan_Waktu DEFAULT (GETDATE()),
    operator     BIGINT NULL CONSTRAINT FK_Penimbangan_Operator REFERENCES dbo.Users (UserID),   -- NULL hanya data lama
    hash         CHAR(64) NULL,
    CONSTRAINT PK_Penimbangan PRIMARY KEY (no_tiket, ke)
);
CREATE INDEX IX_Penimbangan_Waktu ON dbo.penimbangan (waktu DESC);
GO
CREATE OR ALTER TRIGGER dbo.TR_Penimbangan_JembatanSama ON dbo.penimbangan AFTER INSERT, UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted i
               JOIN dbo.penimbangan p1 ON p1.no_tiket = i.no_tiket AND p1.ke = 1
               WHERE i.ke = 2 AND i.id_jembatan <> p1.id_jembatan)
    BEGIN
        RAISERROR('Timbang keluar harus di jembatan timbang yang sama dengan timbang masuk.', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END
    IF EXISTS (SELECT 1 FROM inserted i WHERE i.ke = 2
               AND NOT EXISTS (SELECT 1 FROM dbo.penimbangan p1 WHERE p1.no_tiket = i.no_tiket AND p1.ke = 1))
    BEGIN
        RAISERROR('Timbang ke-2 hanya boleh setelah timbang ke-1.', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END
    UPDATE t SET t.id_jembatan = i.id_jembatan
    FROM dbo.transaksi t JOIN inserted i ON i.no_tiket = t.no_tiket AND i.ke = 1;
END
GO
CREATE OR ALTER VIEW dbo.v_timbangan AS
SELECT t.no_tiket, t.jenis_transaksi, t.id_jembatan, j.kode AS kode_jembatan,
       CAST(CASE WHEN t.jenis_transaksi = 'PENJUALAN' THEN p2.berat_kg ELSE p1.berat_kg END AS FLOAT) AS berat_bruto,
       CASE WHEN t.jenis_transaksi = 'PENJUALAN' THEN p2.waktu ELSE p1.waktu END AS waktu_bruto,
       CAST(CASE WHEN t.jenis_transaksi = 'PENJUALAN' THEN p1.berat_kg
                 WHEN t.jenis_transaksi = 'PENIMBANGAN_SAJA' THEN NULL ELSE p2.berat_kg END AS FLOAT) AS berat_tara,
       CASE WHEN t.jenis_transaksi = 'PENJUALAN' THEN p1.waktu
            WHEN t.jenis_transaksi = 'PENIMBANGAN_SAJA' THEN NULL ELSE p2.waktu END AS waktu_tara,
       CAST(CASE WHEN t.jenis_transaksi = 'PENIMBANGAN_SAJA' THEN p1.berat_kg
                 WHEN p2.berat_kg IS NOT NULL THEN ABS(p1.berat_kg - p2.berat_kg) END AS FLOAT) AS berat_netto,
       COALESCE(p2.hash, p1.hash) AS hash_keamanan,
       COALESCE(p2.operator, p1.operator) AS operator_timbang_id
FROM dbo.transaksi t
LEFT JOIN dbo.penimbangan p1 ON p1.no_tiket = t.no_tiket AND p1.ke = 1
LEFT JOIN dbo.penimbangan p2 ON p2.no_tiket = t.no_tiket AND p2.ke = 2
LEFT JOIN dbo.jembatan_timbang j ON j.id_jembatan = t.id_jembatan;
GO

-- Kelebihan DO (migrasi 022): kelebihan netto di atas kuota kontrak -> tiket split + No. DO baru (Ascend)
CREATE TABLE dbo.kelebihan_do (
    id_kelebihan     INT IDENTITY(1,1) PRIMARY KEY,
    no_tiket         VARCHAR(50)    NOT NULL CONSTRAINT FK_Lebih_Tiket REFERENCES dbo.transaksi (no_tiket),
    no_tiket_split   VARCHAR(50)    NOT NULL CONSTRAINT FK_Lebih_Split REFERENCES dbo.transaksi (no_tiket),
    id_do            INT            NOT NULL CONSTRAINT FK_Lebih_DO REFERENCES dbo.delivery_order (id_do),
    kuota_kg         DECIMAL(14, 2) NOT NULL,
    realisasi_kg     DECIMAL(14, 2) NOT NULL,
    netto_tiket_kg   DECIMAL(14, 2) NOT NULL,
    kelebihan_kg     DECIMAL(14, 2) NOT NULL,
    no_do_baru       VARCHAR(50)    NULL,
    status           VARCHAR(15)    NOT NULL CONSTRAINT DF_Lebih_Status DEFAULT ('MENUNGGU'),
    catatan          NVARCHAR(255)  NULL,
    diajukan_oleh    BIGINT NULL CONSTRAINT FK_Lebih_Aju REFERENCES dbo.Users (UserID),
    diajukan_at      DATETIME NULL,
    ditetapkan_oleh  BIGINT NULL CONSTRAINT FK_Lebih_Tetap REFERENCES dbo.Users (UserID),
    ditetapkan_at    DATETIME NULL,
    alasan_kembali   NVARCHAR(255)  NULL,
    id_comp_area     BIGINT NULL CONSTRAINT FK_Lebih_Area REFERENCES dbo.CompanyArea (CompAreaID),
    created_at       DATETIME NOT NULL CONSTRAINT DF_Lebih_Created DEFAULT (GETDATE()),
    CONSTRAINT UX_Lebih_Tiket UNIQUE (no_tiket),
    CONSTRAINT CK_Lebih_Status CHECK (status IN ('MENUNGGU', 'DIAJUKAN', 'SELESAI', 'DIKEMBALIKAN')),
    CONSTRAINT CK_Lebih_Kg CHECK (kelebihan_kg > 0)
);
-- Notifikasi lonceng (migrasi 022): sasaran = level yang punya hak menu kode_menu
CREATE TABLE dbo.notifikasi (
    id_notifikasi  INT IDENTITY(1,1) PRIMARY KEY,
    kode_menu      VARCHAR(40)    NOT NULL,
    id_comp_area   BIGINT NULL CONSTRAINT FK_Notif_Area REFERENCES dbo.CompanyArea (CompAreaID),
    judul          NVARCHAR(150)  NOT NULL,
    isi            NVARCHAR(500)  NULL,
    tautan         VARCHAR(200)   NULL,
    waktu          DATETIME NOT NULL CONSTRAINT DF_Notif_Waktu DEFAULT (GETDATE()),
    -- Sasaran (migrasi 027): jabatan di PT tertentu, atau satu user. Keduanya NULL = per menu (kode_menu)
    id_level       INT NULL CONSTRAINT FK_Notif_Level REFERENCES dbo.LevelDetails (LevelDetID),
    id_company     VARCHAR(5) NULL CONSTRAINT FK_Notif_Company REFERENCES dbo.Company (CompID),
    id_user        BIGINT NULL CONSTRAINT FK_Notif_User REFERENCES dbo.Users (UserID)
);
CREATE INDEX IX_Notif_Waktu ON dbo.notifikasi (waktu DESC);
CREATE TABLE dbo.notifikasi_baca (
    id_notifikasi  INT NOT NULL CONSTRAINT FK_NotifBaca_Notif REFERENCES dbo.notifikasi (id_notifikasi),
    id_user        BIGINT NOT NULL CONSTRAINT FK_NotifBaca_User REFERENCES dbo.Users (UserID),
    dibaca_at      DATETIME NOT NULL CONSTRAINT DF_NotifBaca_Waktu DEFAULT (GETDATE()),
    CONSTRAINT PK_NotifBaca PRIMARY KEY (id_notifikasi, id_user)
);
GO

CREATE TABLE dbo.sortasi (
    id_sortasi              INT IDENTITY(1,1) PRIMARY KEY,
    no_tiket                VARCHAR(50) NOT NULL CONSTRAINT UX_Sortasi_Tiket UNIQUE
                            CONSTRAINT FK_Sortasi_Trx REFERENCES dbo.transaksi (no_tiket),
    persen_buah_mentah      FLOAT NULL,
    persen_buah_busuk       FLOAT NULL,
    persen_tangkai_panjang  FLOAT NULL,
    persen_sampah_kotoran   FLOAT NULL,
    persen_buah_matang      FLOAT NULL,
    persen_brondolan        FLOAT NULL,
    total_potongan_kg       FLOAT NULL,
    catatan                 VARCHAR(500) NULL,
    operator_sortasi_id     BIGINT NULL CONSTRAINT FK_Sortasi_Operator REFERENCES dbo.Users (UserID),
    waktu_sortasi           DATETIME NULL
);
GO

CREATE TABLE dbo.lab_hasil (
    id_lab             INT IDENTITY(1,1) PRIMARY KEY,
    no_tiket           VARCHAR(50) NOT NULL CONSTRAINT UX_Lab_Tiket UNIQUE
                       CONSTRAINT FK_Lab_Trx REFERENCES dbo.transaksi (no_tiket),
    ffa                FLOAT NULL,
    kadar_air          FLOAT NULL,
    kadar_kotoran      FLOAT NULL,
    warna_locis        VARCHAR(50) NULL,
    keputusan          VARCHAR(20) NULL,
    id_dokumen         INT NULL CONSTRAINT FK_Lab_Dokumen REFERENCES dbo.dokumen (id_dokumen),   -- COA (APPROVE), migrasi 014
    operator_lab_id    BIGINT NULL CONSTRAINT FK_Lab_Operator REFERENCES dbo.Users (UserID),
    waktu_pemeriksaan  DATETIME NULL,
    CONSTRAINT CK_Lab_Keputusan CHECK (keputusan IS NULL OR keputusan IN ('APPROVE', 'REJECT'))
);
GO

/* =========================== FACE RECOGNITION =========================== */

CREATE TABLE dbo.blacklist (
    id_blacklist          INT IDENTITY(1,1) PRIMARY KEY,
    tipe_entitas          VARCHAR(20)  NOT NULL,
    id_personel           INT NULL CONSTRAINT FK_Blacklist_Personel REFERENCES dbo.personel (id_personel),
    id_kendaraan          INT NULL CONSTRAINT FK_Blacklist_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    alasan_blacklist      VARCHAR(500) NOT NULL,
    id_dokumen            INT NULL CONSTRAINT FK_Blacklist_Dokumen REFERENCES dbo.dokumen (id_dokumen),       -- surat; NULL = menyusul (migrasi 021)
    created_by            BIGINT NOT NULL CONSTRAINT FK_Blacklist_User REFERENCES dbo.Users (UserID),
    created_at            DATETIME NOT NULL CONSTRAINT DF_Blacklist_Created DEFAULT (GETDATE()),
    no_plat_terkait          VARCHAR(15) NULL,                  -- plat saat itu (supir / tamu)
    id_customer_terkait      INT NULL CONSTRAINT FK_Blacklist_Customer REFERENCES dbo.mitra (id_supplier),
    id_pengangkutan_terkait  INT NULL CONSTRAINT FK_Blacklist_Angkut REFERENCES dbo.mitra (id_supplier),
    -- Dicabut lewat persetujuan (migrasi 027); baris tidak pernah dihapus
    dicabut_at               DATETIME NULL,
    dicabut_oleh             BIGINT NULL CONSTRAINT FK_Blacklist_Pencabut REFERENCES dbo.Users (UserID),
    alasan_cabut             NVARCHAR(500) NULL,
    -- Blacklist berjenjang (migrasi 043): alias, kategori target saat itu (KENDARAAN untuk kendaraan), lokasi = area pengaju
    nama_alias               NVARCHAR(100) NULL,
    kategori                 VARCHAR(20) NULL,
    id_comp_area             BIGINT NULL CONSTRAINT FK_Blacklist_Area REFERENCES dbo.CompanyArea (CompAreaID),
    CONSTRAINT CK_Blacklist_Tipe CHECK (tipe_entitas IN ('PERSONEL', 'KENDARAAN')),
    CONSTRAINT CK_Blacklist_Target CHECK (
        (tipe_entitas = 'PERSONEL'  AND id_personel IS NOT NULL AND id_kendaraan IS NULL) OR
        (tipe_entitas = 'KENDARAAN' AND id_kendaraan IS NOT NULL AND id_personel IS NULL))
);
CREATE INDEX IX_Blacklist_Personel  ON dbo.blacklist (id_personel)  WHERE id_personel IS NOT NULL;
CREATE INDEX IX_Blacklist_Kendaraan ON dbo.blacklist (id_kendaraan) WHERE id_kendaraan IS NOT NULL;
CREATE INDEX IX_Blacklist_Dokumen ON dbo.blacklist (id_dokumen);
GO

-- Jadwal kerja per area (migrasi 014): absensi memakai jadwal area akun yang men-scan
CREATE TABLE dbo.jadwal_kerja (
    id_comp_area     BIGINT NOT NULL CONSTRAINT FK_Jadwal_Area REFERENCES dbo.CompanyArea (CompAreaID),
    hari             TINYINT NOT NULL,                          -- 1 = Senin ... 7 = Minggu
    nama_hari        VARCHAR(10) NOT NULL,
    jam_masuk        TIME(0) NULL,
    jam_pulang       TIME(0) NULL,
    is_libur         BIT NOT NULL CONSTRAINT DF_Jadwal_Libur DEFAULT (0),
    toleransi_menit  INT NOT NULL CONSTRAINT DF_Jadwal_Toleransi DEFAULT (0),
    CONSTRAINT CK_Jadwal_Hari CHECK (hari BETWEEN 1 AND 7),
    CONSTRAINT CK_Jadwal_Jam CHECK (is_libur = 1 OR (jam_masuk IS NOT NULL AND jam_pulang IS NOT NULL AND jam_pulang > jam_masuk)),
    CONSTRAINT PK_JadwalKerja PRIMARY KEY (id_comp_area, hari)
);
GO

CREATE TABLE dbo.absensi (
    id_absensi          INT IDENTITY(1,1) PRIMARY KEY,
    id_personel         INT NULL CONSTRAINT FK_Absensi_Personel REFERENCES dbo.personel (id_personel),
    jenis               VARCHAR(10) NULL,
    status              VARCHAR(20) NOT NULL,
    status_waktu        VARCHAR(20) NULL,
    selisih_menit       INT NULL,
    jarak_wajah         FLOAT NULL,
    tantangan_liveness  VARCHAR(20) NULL,
    foto_path           VARCHAR(255) NULL,
    perangkat           VARCHAR(50) NULL,
    ip_address          VARCHAR(45) NULL,
    waktu               DATETIME NOT NULL CONSTRAINT DF_Absensi_Waktu DEFAULT (GETDATE()),
    tanggal             AS CAST(waktu AS DATE) PERSISTED,
    CONSTRAINT CK_Absensi_Status CHECK (status IN ('BERHASIL', 'TIDAK_DIKENALI', 'DITOLAK_BLACKLIST')),
    CONSTRAINT CK_Absensi_Jenis CHECK (jenis IS NULL OR jenis IN ('MASUK', 'PULANG')),
    CONSTRAINT CK_Absensi_Waktu CHECK (status_waktu IS NULL OR status_waktu IN ('TEPAT_WAKTU', 'TERLAMBAT', 'PULANG_AWAL', 'HARI_LIBUR')),
    CONSTRAINT CK_Absensi_Berhasil CHECK (status <> 'BERHASIL' OR (id_personel IS NOT NULL AND jenis IS NOT NULL))
);
CREATE INDEX IX_Absensi_Personel_Tanggal ON dbo.absensi (id_personel, tanggal);
CREATE INDEX IX_Absensi_Tanggal ON dbo.absensi (tanggal);
GO

/* =========================== ADMIN =========================== */

-- Kolom wajib dinamis (RequiredDataField, migrasi 035): kolom opsional yang diwajibkan per formulir
CREATE TABLE dbo.kolom_wajib (
    form   VARCHAR(30) NOT NULL,
    kolom  VARCHAR(50) NOT NULL,
    CONSTRAINT PK_KolomWajib PRIMARY KEY (form, kolom)
);
CREATE TABLE dbo.pengaturan (
    kunci       VARCHAR(50)  PRIMARY KEY,
    nilai       VARCHAR(200) NOT NULL,
    updated_by  BIGINT NULL CONSTRAINT FK_Pengaturan_User REFERENCES dbo.Users (UserID),
    updated_at  DATETIME NOT NULL CONSTRAINT DF_Pengaturan_Updated DEFAULT (GETDATE())
);
GO

-- Pengaturan operasional per area (migrasi 014), menimpa nilai global di tabel pengaturan
CREATE TABLE dbo.pengaturan_area (
    id_comp_area  BIGINT NOT NULL CONSTRAINT FK_PengArea_Area REFERENCES dbo.CompanyArea (CompAreaID),
    kunci         VARCHAR(50)  NOT NULL,
    nilai         VARCHAR(200) NOT NULL,
    updated_by    BIGINT NULL CONSTRAINT FK_PengArea_User REFERENCES dbo.Users (UserID),
    updated_at    DATETIME NOT NULL CONSTRAINT DF_PengArea_Updated DEFAULT (GETDATE()),
    CONSTRAINT PK_PengaturanArea PRIMARY KEY (id_comp_area, kunci)
);
GO

CREATE TABLE dbo.perangkat_kiosk (
    id_pos      VARCHAR(30)  PRIMARY KEY,
    nama        VARCHAR(100) NOT NULL,
    lokasi      VARCHAR(100) NULL,
    token_hash  CHAR(64)     NOT NULL,
    id_comp_area BIGINT NOT NULL CONSTRAINT FK_Kiosk_Area REFERENCES dbo.CompanyArea (CompAreaID),
    is_active   BIT NOT NULL CONSTRAINT DF_Kiosk_Aktif DEFAULT (1),
    created_at  DATETIME NOT NULL CONSTRAINT DF_Kiosk_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_Kiosk_Id CHECK (id_pos NOT LIKE '%[^A-Z0-9_-]%')
);
GO

/* Satu log untuk semua aktivitas (migrasi 015): JSON + rantai hash, hanya INSERT lewat sp_catat_log */
CREATE TABLE dbo.log_aktivitas (
    id_log         BIGINT IDENTITY(1,1) PRIMARY KEY,
    waktu          DATETIME2(3) NOT NULL,
    id_user        BIGINT NULL CONSTRAINT FK_Log_User REFERENCES dbo.Users (UserID),     -- NULL = kiosk / sistem
    id_comp_area   BIGINT NULL CONSTRAINT FK_Log_Area REFERENCES dbo.CompanyArea (CompAreaID),
    kategori       VARCHAR(20)  NOT NULL,      -- ADMIN, SECURITY, PERSONEL, STANDAR_MUTU, TIMELINE, ...
    aksi           VARCHAR(40)  NOT NULL,
    tabel          VARCHAR(50)  NULL,
    id_baris       VARCHAR(100) NULL,
    nilai_lama     NVARCHAR(MAX) NULL,
    nilai_baru     NVARCHAR(MAX) NULL,
    ip             VARCHAR(45)  NULL,
    hash_sebelum   CHAR(64) NULL,              -- NULL hanya baris pertama
    hash_baris     CHAR(64) NOT NULL,
    CONSTRAINT CK_Log_JsonLama CHECK (nilai_lama IS NULL OR ISJSON(nilai_lama) = 1),
    CONSTRAINT CK_Log_JsonBaru CHECK (nilai_baru IS NULL OR ISJSON(nilai_baru) = 1)
);
CREATE INDEX IX_Log_Kategori_Waktu ON dbo.log_aktivitas (kategori, waktu DESC);
CREATE INDEX IX_Log_Baris ON dbo.log_aktivitas (tabel, id_baris);
GO

/* Isi yang di-hash (dipakai juga untuk verifikasi) */
CREATE OR ALTER FUNCTION dbo.fn_hash_log (
    @hash_sebelum CHAR(64), @waktu DATETIME2(3), @id_user BIGINT, @kategori VARCHAR(20), @aksi VARCHAR(40),
    @tabel VARCHAR(50), @id_baris VARCHAR(100), @nilai_lama NVARCHAR(MAX), @nilai_baru NVARCHAR(MAX), @ip VARCHAR(45))
RETURNS CHAR(64)
AS
BEGIN
    RETURN CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT(
        ISNULL(@hash_sebelum, REPLICATE('0', 64)), N'|', CONVERT(VARCHAR(30), @waktu, 121), N'|', @id_user, N'|',
        @kategori, N'|', @aksi, N'|', @tabel, N'|', @id_baris, N'|', @nilai_lama, N'|', @nilai_baru, N'|', @ip)), 2);
END
GO

CREATE OR ALTER PROCEDURE dbo.sp_catat_log
    @kategori VARCHAR(20), @aksi VARCHAR(40), @tabel VARCHAR(50) = NULL, @id_baris VARCHAR(100) = NULL,
    @nilai_lama NVARCHAR(MAX) = NULL, @nilai_baru NVARCHAR(MAX) = NULL, @id_user BIGINT = NULL,
    @id_comp_area BIGINT = NULL, @ip VARCHAR(45) = NULL, @waktu DATETIME2(3) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRANSACTION;
    -- satu penulis pada satu waktu supaya rantai tidak bercabang
    EXEC sp_getapplock @Resource = 'log_aktivitas', @LockMode = 'Exclusive', @LockOwner = 'Transaction';
    DECLARE @prev CHAR(64) = (SELECT TOP 1 hash_baris FROM dbo.log_aktivitas ORDER BY id_log DESC);
    SET @waktu = COALESCE(@waktu, SYSDATETIME());
    IF @id_comp_area IS NULL AND @id_user IS NOT NULL
        SET @id_comp_area = (SELECT CompAreaID FROM dbo.Users WHERE UserID = @id_user);
    INSERT INTO dbo.log_aktivitas (waktu, id_user, id_comp_area, kategori, aksi, tabel, id_baris, nilai_lama, nilai_baru,
                                   ip, hash_sebelum, hash_baris)
    VALUES (@waktu, @id_user, @id_comp_area, @kategori, @aksi, @tabel, @id_baris, @nilai_lama, @nilai_baru, @ip, @prev,
            dbo.fn_hash_log(@prev, @waktu, @id_user, @kategori, @aksi, @tabel, @id_baris, @nilai_lama, @nilai_baru, @ip));
    COMMIT TRANSACTION;
END
GO

CREATE OR ALTER TRIGGER dbo.TR_Log_HanyaTambah ON dbo.log_aktivitas INSTEAD OF UPDATE, DELETE AS
BEGIN
    RAISERROR('log_aktivitas hanya boleh ditambah (tidak bisa diubah / dihapus).', 16, 1);
    ROLLBACK TRANSACTION;
END
GO

/* Baris pertama yang rantainya putus; kosong = utuh */
CREATE OR ALTER VIEW dbo.v_log_rusak AS
SELECT x.id_log, x.waktu, x.kategori, x.aksi,
       CASE WHEN x.hash_baris <> x.hash_hitung THEN 'ISI_BERUBAH' ELSE 'RANTAI_PUTUS' END AS masalah
FROM (SELECT l.id_log, l.waktu, l.kategori, l.aksi, l.hash_sebelum, l.hash_baris,
             LAG(l.hash_baris) OVER (ORDER BY l.id_log) AS hash_seharusnya,
             dbo.fn_hash_log(l.hash_sebelum, l.waktu, l.id_user, l.kategori, l.aksi, l.tabel, l.id_baris,
                             l.nilai_lama, l.nilai_baru, l.ip) AS hash_hitung
      FROM dbo.log_aktivitas l) x
WHERE x.hash_baris <> x.hash_hitung
   OR ISNULL(x.hash_sebelum, '') <> ISNULL(x.hash_seharusnya, '');
GO


/* Sesi login dari semua PC (Admin > Sesi Aktif, paksa keluar, 1 user 1 perangkat) */
CREATE TABLE dbo.UserSession (
    SessionID   VARCHAR(24)  NOT NULL PRIMARY KEY,
    UserID      BIGINT       NOT NULL CONSTRAINT FK_UserSession_User REFERENCES dbo.Users (UserID),
    IPAddress   VARCHAR(45)  NULL,
    UserAgent   VARCHAR(200) NULL,
    LoginDate   DATETIME     NOT NULL CONSTRAINT DF_UserSession_Login DEFAULT (GETDATE()),
    LastActive  DATETIME     NOT NULL CONSTRAINT DF_UserSession_Active DEFAULT (GETDATE()),
    EndDate     DATETIME     NULL,
    EndReason   VARCHAR(20)  NULL
);
CREATE INDEX IX_UserSession_User ON dbo.UserSession (UserID, EndDate);
CREATE INDEX IX_UserSession_Active ON dbo.UserSession (EndDate, LastActive);
GO


/* =========================== LOG VALIDASI BLACKLIST (migrasi 028) =========================== */
CREATE TABLE dbo.blacklist_deteksi (
    id_deteksi    BIGINT IDENTITY(1,1) PRIMARY KEY,
    waktu         DATETIME      NOT NULL CONSTRAINT DF_BlDeteksi_Waktu DEFAULT (GETDATE()),
    id_comp_area  BIGINT           NULL CONSTRAINT FK_BlDeteksi_Area REFERENCES dbo.CompanyArea (CompAreaID),
    id_personel   INT           NULL CONSTRAINT FK_BlDeteksi_Personel REFERENCES dbo.personel (id_personel),
    id_kendaraan  INT           NULL CONSTRAINT FK_BlDeteksi_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    no_plat       VARCHAR(15)   NULL,
    sumber        VARCHAR(20)   NOT NULL,      -- SCAN_WAJAH, ABSENSI, TAMU, TAMU_MASUK, TIKET, TAMBAH_SUPIR, PENDAFTARAN, PLAT
    tindakan      VARCHAR(20)   NOT NULL CONSTRAINT CK_BlDeteksi_Tindakan CHECK (tindakan IN ('DITOLAK', 'PERINGATAN', 'DILOLOSKAN')),
    jarak_wajah   FLOAT         NULL,
    keterangan    NVARCHAR(300) NULL,
    no_tiket      VARCHAR(50)   NULL,
    id_user       BIGINT           NULL CONSTRAINT FK_BlDeteksi_User REFERENCES dbo.Users (UserID),
    CONSTRAINT CK_BlDeteksi_Target CHECK (id_personel IS NOT NULL OR id_kendaraan IS NOT NULL)
);
CREATE INDEX IX_BlDeteksi_Area_Waktu ON dbo.blacklist_deteksi (id_comp_area, waktu DESC);
CREATE INDEX IX_BlDeteksi_Personel ON dbo.blacklist_deteksi (id_personel, waktu) WHERE id_personel IS NOT NULL;
CREATE INDEX IX_BlDeteksi_Kendaraan ON dbo.blacklist_deteksi (id_kendaraan, waktu) WHERE id_kendaraan IS NOT NULL;
GO

/* =========================== PERSETUJUAN (migrasi 027; penyetuju = hak Setujui, migrasi 029) =========================== */
CREATE TABLE dbo.pengajuan (
    id_pengajuan   INT IDENTITY(1,1) PRIMARY KEY,
    jenis          VARCHAR(40)    NOT NULL,
    status         VARCHAR(20)    NOT NULL CONSTRAINT DF_Pengajuan_Status DEFAULT ('MENUNGGU')
                   CONSTRAINT CK_Pengajuan_Status CHECK (status IN ('MENUNGGU', 'DISETUJUI', 'DITOLAK', 'DIBATALKAN')),
    langkah        TINYINT        NOT NULL CONSTRAINT DF_Pengajuan_Langkah DEFAULT (1),
    total_langkah  TINYINT        NOT NULL,
    id_company     VARCHAR(5)            NOT NULL CONSTRAINT FK_Pengajuan_Company REFERENCES dbo.Company (CompID),
    id_comp_area   BIGINT            NOT NULL CONSTRAINT FK_Pengajuan_Area REFERENCES dbo.CompanyArea (CompAreaID),
    target         VARCHAR(50)    NOT NULL,
    judul          NVARCHAR(200)  NOT NULL,
    alasan         NVARCHAR(500)  NULL,
    data           NVARCHAR(MAX)  NULL CONSTRAINT CK_Pengajuan_Json CHECK (data IS NULL OR ISJSON(data) = 1),
    diajukan_oleh  BIGINT            NOT NULL CONSTRAINT FK_Pengajuan_User REFERENCES dbo.Users (UserID),
    created_at     DATETIME       NOT NULL CONSTRAINT DF_Pengajuan_Dibuat DEFAULT (GETDATE()),
    selesai_at     DATETIME       NULL,
    kategori       VARCHAR(20)    NULL                -- kategori target (memilih alur persetujuan, migrasi 043)
);
CREATE INDEX IX_Pengajuan_Status ON dbo.pengajuan (status, jenis, id_company);
CREATE TABLE dbo.pengajuan_riwayat (
    id_riwayat    INT IDENTITY(1,1) PRIMARY KEY,
    id_pengajuan  INT           NOT NULL CONSTRAINT FK_PengRiwayat_Pengajuan REFERENCES dbo.pengajuan (id_pengajuan),
    langkah       TINYINT       NOT NULL,
    aksi          VARCHAR(20)   NOT NULL CONSTRAINT CK_PengRiwayat_Aksi CHECK (aksi IN ('DIAJUKAN', 'DISETUJUI', 'DITOLAK', 'DIBATALKAN', 'DILEWATI')),
    id_level      INT           NULL CONSTRAINT FK_PengRiwayat_Level REFERENCES dbo.LevelDetails (LevelDetID),
    id_user       BIGINT           NOT NULL CONSTRAINT FK_PengRiwayat_User REFERENCES dbo.Users (UserID),
    catatan       NVARCHAR(500) NULL,
    waktu         DATETIME      NOT NULL CONSTRAINT DF_PengRiwayat_Waktu DEFAULT (GETDATE())
);
-- Alur persetujuan berjenjang (migrasi 043): per jenis + kategori target (NULL = semua); tiap tahap = satu peran.
-- Penyetuju tahap = pengguna aktif dengan peran itu di PT pengajuan (kantor pusat: PT yang dikelolanya).
CREATE TABLE dbo.alur_persetujuan (
    id_alur_persetujuan INT IDENTITY(1,1) PRIMARY KEY,
    jenis       VARCHAR(40)   NOT NULL,
    kategori    VARCHAR(20)   NULL,
    keterangan  NVARCHAR(255) NULL,
    is_active   BIT NOT NULL CONSTRAINT DF_AlurSetuju_Aktif DEFAULT (1),
    created_at  DATETIME NOT NULL CONSTRAINT DF_AlurSetuju_Dibuat DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_AlurSetuju_Jenis ON dbo.alur_persetujuan (jenis, kategori);
CREATE TABLE dbo.alur_persetujuan_tahap (
    id_tahap            INT IDENTITY(1,1) PRIMARY KEY,
    id_alur_persetujuan INT NOT NULL CONSTRAINT FK_AlurSetujuTahap_Alur REFERENCES dbo.alur_persetujuan (id_alur_persetujuan),
    urutan              TINYINT NOT NULL,
    id_level            INT NOT NULL CONSTRAINT FK_AlurSetujuTahap_Level REFERENCES dbo.LevelDetails (LevelDetID),
    CONSTRAINT UX_AlurSetujuTahap_Urutan UNIQUE (id_alur_persetujuan, urutan)
);
-- Salinan tahap saat diajukan (perubahan alur tidak mengganggu pengajuan yang berjalan)
CREATE TABLE dbo.pengajuan_tahap (
    id_pengajuan INT NOT NULL CONSTRAINT FK_PengTahap_Pengajuan REFERENCES dbo.pengajuan (id_pengajuan),
    urutan       TINYINT NOT NULL,
    id_level     INT NOT NULL CONSTRAINT FK_PengTahap_Level REFERENCES dbo.LevelDetails (LevelDetID),
    CONSTRAINT PK_PengTahap PRIMARY KEY (id_pengajuan, urutan)
);
GO

/* =========================== TRIGGER: blacklist permanen =========================== */
CREATE OR ALTER TRIGGER dbo.TR_Personel_BlacklistPermanen ON dbo.personel AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    -- Pencabutan hanya dari jalur persetujuan (SESSION_CONTEXT cabut_blacklist = 1, migrasi 027)
    IF UPDATE(is_blacklisted) AND ISNULL(CAST(SESSION_CONTEXT(N'cabut_blacklist') AS INT), 0) <> 1
       AND EXISTS (SELECT 1 FROM inserted i JOIN deleted d ON d.id_personel = i.id_personel
                   WHERE d.is_blacklisted = 1 AND i.is_blacklisted = 0)
    BEGIN
        RAISERROR('Blacklist personel hanya bisa dicabut lewat persetujuan (menu Persetujuan).', 16, 1);
        ROLLBACK TRANSACTION;
    END
END
GO
CREATE OR ALTER TRIGGER dbo.TR_Kendaraan_BlacklistPermanen ON dbo.kendaraan AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    -- Pencabutan hanya dari jalur persetujuan (SESSION_CONTEXT cabut_blacklist = 1, migrasi 027)
    IF UPDATE(is_blacklisted) AND ISNULL(CAST(SESSION_CONTEXT(N'cabut_blacklist') AS INT), 0) <> 1
       AND EXISTS (SELECT 1 FROM inserted i JOIN deleted d ON d.id_kendaraan = i.id_kendaraan
                   WHERE d.is_blacklisted = 1 AND i.is_blacklisted = 0)
    BEGIN
        RAISERROR('Blacklist kendaraan hanya bisa dicabut lewat persetujuan (menu Persetujuan).', 16, 1);
        ROLLBACK TRANSACTION;
    END
END
GO

/* =========================== DATA AWAL =========================== */
-- Jenis dokumen (migrasi 010)
INSERT INTO dbo.jenis_dokumen (kode, nama, wajib_file) VALUES
    ('SURAT_BLACKLIST', N'Surat Blacklist', 1),
    ('BA_VOID',         N'Berita Acara Void Tiket', 1),
    ('COA',             N'Certificate of Analysis (Lab)', 0),
    ('SIM',             N'Scan SIM', 1),
    ('STNK',            N'Scan STNK', 1),
    ('KONTRAK',         N'Dokumen Kontrak', 0);
-- Kategori personel, jenis SIM, keperluan kunjungan (migrasi 009)
INSERT INTO dbo.kategori_personel (kode, nama, wajib_sim, boleh_akun, prefix_kode) VALUES
    ('DRIVER',   N'Driver',   1, 0, 'DRV'),
    ('SECURITY', N'Security', 0, 1, 'SEC'),
    ('EMPLOYEE', N'Karyawan', 0, 1, 'KRY'),
    ('TAMU',     N'Tamu',     0, 0, 'TMU'),
    ('BHL',      N'BHL',      0, 0, 'BHL');
INSERT INTO dbo.jenis_sim (kode, nama) VALUES
    ('A', N'SIM A'), ('B1', N'SIM B1'), ('B1_UMUM', N'SIM B1 Umum'), ('B2', N'SIM B2'), ('B2_UMUM', N'SIM B2 Umum');
INSERT INTO dbo.jenis_sim (kode, nama, is_active) VALUES ('BELUM_DIISI', N'Belum dilengkapi', 0);
INSERT INTO dbo.keperluan_kunjungan (nama) VALUES
    (N'Rapat / Bertemu'), (N'Pengiriman Barang'), (N'Perbaikan / Servis'), (N'Audit / Inspeksi'), (N'Lainnya');
GO
-- Organisasi, peran, menu (sidebar master page, 3 level), dan hak akses awal (ERD Ladder Desk)
INSERT INTO dbo.Company (CompID, CompName) VALUES ('PT', N'Perusahaan (ubah di Admin › Organisasi)'), ('HO', N'HEAD OFFICE');
INSERT INTO dbo.Mill (MillCode, MillName, Description, IsHeadOffice) VALUES ('300', N'HO', N'Kantor pusat', 1),
    ('400', N'OFFICE', N'Kantor cabang di site', 0), ('600', N'PKS', NULL, 0);
INSERT INTO dbo.CompanyArea (CompID, MillID, AreaCode, AreaName)
SELECT v.comp, m.MillID, m.MillCode, v.nama
FROM (VALUES ('PT', '600', N'PKS'), ('HO', '300', N'HEAD OFFICE')) v (comp, mill, nama)
JOIN dbo.Mill m ON m.MillCode = v.mill;
INSERT INTO dbo.Department (DeptID, DeptName) VALUES
    ('UMUM', N'Umum'), ('SEC', N'Security'), ('TBG', N'Timbangan'), ('SRT', N'Sortasi'), ('LAB', N'Laboratorium'), ('HO', N'Head Office');
INSERT INTO dbo.DepartmentDetails (CompAreaID, DeptID, Location)
SELECT a.CompAreaID, d.DeptID, CASE WHEN m.IsHeadOffice = 1 THEN 'HO' ELSE 'SITE' END
FROM dbo.CompanyArea a JOIN dbo.Mill m ON m.MillID = a.MillID JOIN dbo.Department d
  ON (m.IsHeadOffice = 0 AND d.DeptID IN ('UMUM', 'SEC', 'TBG', 'SRT', 'LAB')) OR (m.IsHeadOffice = 1 AND d.DeptID IN ('UMUM', 'HO'));
INSERT INTO dbo.Level (LevelName, IsAdmin, SortOrder) VALUES
    (N'Admin', 1, 1), (N'Manager', 0, 2), (N'Supervisor', 0, 3), (N'Staff', 0, 4), (N'Magang', 0, 5);
-- Peran awal (Departemen · Level); kode dipakai data awal hak akses di bawah
INSERT INTO dbo.LevelDetails (LevelDetCode, LevelDetName, LevelID, DeptID, HomeUrl)
SELECT v.kode, CASE WHEN d.DeptName IS NULL THEN l.LevelName ELSE d.DeptName + N' · ' + l.LevelName END, l.LevelID, d.DeptID, v.awal
FROM (VALUES ('ADMIN',            N'Admin',   NULL,   '/admin'),
             ('HO',               N'Manager', 'HO',   '/dashboard'),
             ('SECURITY',         N'Staff',   'SEC',  '/pos-security'),
             ('OPERATOR_TIMBANG', N'Staff',   'TBG',  '/weighbridge?tab=timbangan'),
             ('SORTASI',          N'Staff',   'SRT',  '/weighbridge?tab=sortasi'),
             ('LAB',              N'Staff',   'LAB',  '/weighbridge?tab=lab')) v (kode, lvl, dept, awal)
JOIN dbo.Level l ON l.LevelName = v.lvl
LEFT JOIN dbo.Department d ON d.DeptID = v.dept;
INSERT INTO dbo.ActionType (ActionID, TypeName, Description) VALUES
    (0, 'Delete', N'Hapus'), (1, 'View', N'Lihat halaman / bagian'), (2, 'Create', N'Tambah'), (3, 'Edit', N'Ubah'),
    (4, 'Void', N'Batalkan'), (5, 'Approve', N'Setujui pengajuan');
-- Menu Lv1 (grup sidebar master page)
INSERT INTO dbo.Menu (MenuCode, MenuName, MenuLevel, Icon, SortOrder) VALUES
    ('G_DASHBOARD',  N'Dashboard',            1, 'fa-gauge',       10),
    ('G_ANALYTICAL', N'Analytical Dashboard', 1, 'fa-chart-column', 20),
    ('G_MILLS',      N'Mills Operation',      1, 'fa-industry',    30),
    ('G_FORMS',      N'Forms',                1, 'fa-file-lines',  40),
    ('G_REPORTS',    N'Reports',              1, 'fa-chart-pie',   50),
    ('G_MASTER',     N'Master',               1, 'fa-database',    60);
-- Menu Lv2 (halaman). Url NULL = halaman belum ada (tahap berikutnya / web lain)
INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
SELECT v.kode, v.nama, p.MenuID, 2, v.url, v.ikon, v.app, v.urut
FROM (VALUES ('DASHBOARD',       N'Dashboard',                  'G_DASHBOARD',  '/dashboard',             'fa-chart-line',       'CPOS', 10),
             ('AN_PR_PO',        N'PR & PO Outstanding',        'G_ANALYTICAL', NULL, 'fa-chart-bar', 'ANALYTICS', 10),
             ('AN_PO_PI',        N'PO & PI Outstanding',        'G_ANALYTICAL', NULL, 'fa-chart-bar', 'ANALYTICS', 20),
             ('AN_PVR_KPI',      N'PVR KPI',                    'G_ANALYTICAL', NULL, 'fa-chart-bar', 'ANALYTICS', 30),
             ('AN_PV_KPI',       N'PV KPI',                     'G_ANALYTICAL', NULL, 'fa-chart-bar', 'ANALYTICS', 40),
             ('AN_WB_FRAUD',     N'Weighbridge Fraud Analyst',  'G_ANALYTICAL', NULL, 'fa-chart-bar', 'ANALYTICS', 50),
             ('AN_TBS',          N'TBS Transaction Analyst',    'G_ANALYTICAL', NULL, 'fa-chart-bar', 'ANALYTICS', 60),
             ('AN_COST',         N'Transaction Cost Analyst',   'G_ANALYTICAL', NULL, 'fa-chart-bar', 'ANALYTICS', 70),
             ('LIST',            N'Tickets',                    'G_MILLS',      '/weighbridge?view=list', 'fa-list',             'CPOS', 10),
             ('FORM',            N'Stasiun Timbang',            'G_MILLS',      '/weighbridge?view=form', 'fa-file-pen',         'CPOS', 20),
             ('POS_SECURITY',    N'Pos Security',               'G_MILLS',      '/pos-security',          'fa-shield-halved',    'CPOS', 30),
             ('LOGBOOK',         N'Logbook Kendaraan',          'G_MILLS',      '/logbook',               'fa-book',             'CPOS', 40),
             ('KELEBIHAN_DO',    N'Kelebihan DO',               'G_MILLS',      '/kelebihan-do',          'fa-scale-unbalanced', 'CPOS', 50),
             ('KUNJUNGAN',       N'Visitor & Staff Logs',       'G_FORMS',      '/tamu',                  'fa-id-card',          'CPOS', 10),
             ('FM_IT_HELPDESK',  N'IT Helpdesk',                'G_FORMS',      NULL, 'fa-headset',    'CPOS', 20),
             ('FM_NEW_ITEM',     N'New Item Request',           'G_FORMS',      NULL, 'fa-box-open',   'CPOS', 30),
             ('RP_PR',           N'Purchase Request',           'G_REPORTS',    NULL, 'fa-file-invoice', 'ANALYTICS', 10),
             ('RP_PO',           N'Purchase Orders',            'G_REPORTS',    NULL, 'fa-file-invoice', 'ANALYTICS', 20),
             ('RP_PI',           N'Purchase Invoice',           'G_REPORTS',    NULL, 'fa-file-invoice', 'ANALYTICS', 30),
             ('RP_GT',           N'Goods Transfer',             'G_REPORTS',    NULL, 'fa-file-invoice', 'ANALYTICS', 40),
             ('RP_ITEM',         N'Item Transaction Reports',   'G_REPORTS',    NULL, 'fa-file-invoice', 'ANALYTICS', 50),
             ('BLACKLIST',       N'Blacklist',                  'G_MASTER',     '/blacklist',             'fa-ban',              'CPOS', 10),
             ('MASTER',          N'Data Master',                'G_MASTER',     '/master',                'fa-database',         'CPOS', 20),
             ('KONTRAK_DO',      N'Kontrak & DO',               'G_MASTER',     '/kontrak',               'fa-file-contract',    'CPOS', 30),
             ('FACE_RECOGNITION', N'Pengenalan Wajah',          'G_MASTER',     '/face-recognition',      'fa-face-smile',       'CPOS', 40)
     ) v (kode, nama, induk, url, ikon, app, urut)
JOIN dbo.Menu p ON p.MenuCode = v.induk;
-- Menu Lv3 (bagian halaman / sub-halaman)
INSERT INTO dbo.Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, SortOrder)
SELECT v.kode, v.nama, p.MenuID, 3, v.url, v.urut
FROM (VALUES ('FORM_SECURITY',    N'Security',                  'FORM',  '/weighbridge?view=form&tab=security',  1),
             ('FORM_TIMBANGAN',   N'Timbangan',                 'FORM',  '/weighbridge?view=form&tab=timbangan', 2),
             ('FORM_SORTASI',     N'Sortasi',                   'FORM',  '/weighbridge?view=form&tab=sortasi',   3),
             ('FORM_LAB',         N'Laboratorium',              'FORM',  '/weighbridge?view=form&tab=lab',       4),
             ('BL_PERSONEL',      N'Visitor & Staff Blacklist', 'BLACKLIST', '/blacklist?tipe=PERSONEL',        1),
             ('BL_SUPPLIER',      N'Supplier Blacklist',        'BLACKLIST', NULL,                              2),
             ('BL_KENDARAAN',     N'Vehicle Blacklist',         'BLACKLIST', '/blacklist?tipe=KENDARAAN',       3),
             ('MASTER_DRIVER',    N'Supir',                     'MASTER', '/master?tab=personel',  1),
             ('MASTER_KENDARAAN', N'Kendaraan',                 'MASTER', '/master?tab=kendaraan', 2),
             ('MASTER_MITRA',     N'Supplier',                  'MASTER', '/master?tab=mitra',     3),
             ('MASTER_PRODUK',    N'Produk',                    'MASTER', '/master?tab=produk',    4),
             ('ABSENSI',          N'Absensi',                   'FACE_RECOGNITION', '/face-recognition?tab=absensi',  1),
             ('PERSONEL',         N'Personel',                  'FACE_RECOGNITION', '/face-recognition?tab=personel', 2),
             ('AUDIT_LOG',        N'Log Audit',                 'FACE_RECOGNITION', '/face-recognition?tab=audit',    4)
     ) v (kode, nama, induk, url, urut)
JOIN dbo.Menu p ON p.MenuCode = v.induk;
-- Hak akses awal: (peran, menu, tambah, ubah, hapus, setujui). Lihat ikut diberikan.
DECLARE @hak TABLE (peran VARCHAR(30), menu VARCHAR(40), t BIT, u BIT, h BIT, s BIT);
INSERT INTO @hak VALUES
    ('HO', 'DASHBOARD', 0, 1, 0, 0), ('HO', 'PERSONEL', 1, 1, 1, 0), ('HO', 'BLACKLIST', 1, 0, 0, 1),
    ('HO', 'KONTRAK_DO', 1, 1, 1, 0), ('HO', 'MASTER_DRIVER', 1, 1, 1, 0), ('HO', 'MASTER_KENDARAAN', 1, 1, 0, 0),
    ('HO', 'KELEBIHAN_DO', 0, 1, 0, 0), ('OPERATOR_TIMBANG', 'KELEBIHAN_DO', 1, 0, 0, 0),
    ('HO', 'MASTER_MITRA', 1, 1, 0, 0), ('HO', 'MASTER_PRODUK', 1, 1, 0, 0),
    ('SECURITY', 'FORM_SECURITY', 1, 1, 0, 0), ('SECURITY', 'MASTER_DRIVER', 1, 1, 1, 0), ('SECURITY', 'MASTER_KENDARAAN', 1, 1, 0, 0),
    ('OPERATOR_TIMBANG', 'FORM_TIMBANGAN', 1, 0, 0, 0), ('SORTASI', 'FORM_SORTASI', 1, 0, 0, 0), ('LAB', 'FORM_LAB', 1, 1, 0, 0),
    ('SECURITY', 'POS_SECURITY', 1, 1, 0, 0), ('SECURITY', 'LOGBOOK', 0, 1, 0, 0), ('SECURITY', 'KUNJUNGAN', 1, 1, 0, 0),
    ('HO', 'POS_SECURITY', 0, 0, 0, 0), ('HO', 'LOGBOOK', 0, 0, 0, 0);
-- Semua peran non-admin awalnya boleh melihat semua halaman CPOS yang sudah ada (kecuali menu pos: hanya yang diberi di atas)
INSERT INTO @hak (peran, menu, t, u, h, s)
SELECT ld.LevelDetCode, m.MenuCode, 0, 0, 0, 0
FROM dbo.LevelDetails ld JOIN dbo.Level l ON l.LevelID = ld.LevelID CROSS JOIN dbo.Menu m
WHERE l.IsAdmin = 0 AND m.AppCode = 'CPOS' AND m.Url IS NOT NULL AND m.MenuCode NOT IN ('POS_SECURITY', 'LOGBOOK')
  AND NOT EXISTS (SELECT 1 FROM @hak x WHERE x.peran = ld.LevelDetCode AND x.menu = m.MenuCode);
INSERT INTO dbo.AccessMenu (MenuID, ActionID, LevelDetID)
SELECT m.MenuID, a.ActionID, ld.LevelDetID
FROM @hak h JOIN dbo.LevelDetails ld ON ld.LevelDetCode = h.peran JOIN dbo.Menu m ON m.MenuCode = h.menu
CROSS APPLY (VALUES (1, 1), (2, h.t), (3, h.u), (0, h.h), (5, h.s)) a (ActionID, ada)
WHERE a.ada = 1;
-- Induk (Lv2 / Lv1) ikut terlihat bila ada anak yang terlihat (flowchart: menu ditampilkan per level)
INSERT INTO dbo.AccessMenu (MenuID, ActionID, LevelDetID)
SELECT DISTINCT p.MenuID, 1, x.LevelDetID
FROM dbo.AccessMenu x JOIN dbo.Menu m ON m.MenuID = x.MenuID JOIN dbo.Menu p ON p.MenuID = m.ParentMenuID
WHERE x.ActionID = 1 AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu y WHERE y.LevelDetID = x.LevelDetID AND y.MenuID = p.MenuID AND y.ActionID = 1);
INSERT INTO dbo.AccessMenu (MenuID, ActionID, LevelDetID)
SELECT DISTINCT p.MenuID, 1, x.LevelDetID
FROM dbo.AccessMenu x JOIN dbo.Menu m ON m.MenuID = x.MenuID JOIN dbo.Menu p ON p.MenuID = m.ParentMenuID
WHERE x.ActionID = 1 AND NOT EXISTS (SELECT 1 FROM dbo.AccessMenu y WHERE y.LevelDetID = x.LevelDetID AND y.MenuID = p.MenuID AND y.ActionID = 1);
GO
-- Jembatan timbang awal (migrasi 011)
INSERT INTO dbo.jembatan_timbang (id_comp_area, kode, nama, port)
SELECT MIN(CompAreaID), 'JT-1', N'Jembatan Timbang 1', 'COM3' FROM dbo.CompanyArea;
-- Jadwal kerja awal per area (migrasi 014)
INSERT INTO dbo.jadwal_kerja (id_comp_area, hari, nama_hari, jam_masuk, jam_pulang, is_libur)
SELECT a.CompAreaID, v.hari, v.nama, v.masuk, v.pulang, v.libur
FROM dbo.CompanyArea a
CROSS JOIN (VALUES (1, 'Senin', '08:00', '17:00', 0), (2, 'Selasa', '08:00', '17:00', 0), (3, 'Rabu', '08:00', '17:00', 0),
                   (4, 'Kamis', '08:00', '17:00', 0), (5, 'Jumat', '08:00', '17:00', 0), (6, 'Sabtu', '08:00', '12:00', 0),
                   (7, 'Minggu', NULL, NULL, 1)) v (hari, nama, masuk, pulang, libur);
-- Jenis kendaraan (migrasi 014)
INSERT INTO dbo.jenis_transaksi (kode, nama, is_bayar) VALUES
    ('PEMBELIAN', N'Pembelian', 1), ('PENJUALAN', N'Penjualan', 1), ('PENIMBANGAN_SAJA', N'Penimbangan Saja', 0);
INSERT INTO dbo.status_tiket (kode, nama, warna, urutan) VALUES
    ('SECURITY_REGISTER', N'Registrasi Security', 'oranye', 1), ('SCAN_WAJAH', N'Scan Wajah', 'oranye', 2),
    ('TIMBANG_1', N'Timbang 1', 'biru', 3), ('INSPEKSI_PROSES', N'Inspeksi', 'ungu', 4),
    ('TIMBANG_2', N'Timbang 2', 'biru', 5), ('SELESAI', N'Selesai', 'hijau', 6),
    ('REJECTED', N'Ditolak', 'merah', 7), ('VOID', N'Dibatalkan', 'abu', 8);
INSERT INTO dbo.jenis_kendaraan (kode, nama) VALUES
    ('TRUK', N'Truk'), ('DUMP_TRUK', N'Dump Truk'), ('TANGKI', N'Truk Tangki'), ('PICKUP', N'Pick-up'), ('LAINNYA', N'Lainnya');
-- Alur tahap (migrasi 012; unit timbang dihapus di migrasi 041)
INSERT INTO dbo.tahap (kode, nama, urutan) VALUES
    ('SECURITY', N'Security', 1), ('TIMBANG_1', N'Timbang Masuk', 2), ('SORTASI', N'Sortasi', 3),
    ('LAB', N'Laboratorium', 4), ('TIMBANG_2', N'Timbang Keluar', 5);
INSERT INTO dbo.alur (kode, nama) VALUES
    ('TBS', N'TBS: timbang - sortasi - timbang'),
    ('PKS', N'Produk PKS: timbang - lab - timbang'),
    ('TIMBANG_SAJA', N'Penimbangan saja (sekali timbang)'),
    ('POS_SAJA', N'Pos Security saja (catat masuk / keluar, tanpa timbang)');      -- migrasi 039
INSERT INTO dbo.alur_tahap (id_alur, urutan, kode_tahap)
SELECT a.id_alur, v.urutan, v.tahap
FROM (VALUES ('TBS', 1, 'SECURITY'), ('TBS', 2, 'TIMBANG_1'), ('TBS', 3, 'SORTASI'), ('TBS', 4, 'TIMBANG_2'),
             ('PKS', 1, 'SECURITY'), ('PKS', 2, 'TIMBANG_1'), ('PKS', 3, 'LAB'), ('PKS', 4, 'TIMBANG_2'),
             ('TIMBANG_SAJA', 1, 'SECURITY'), ('TIMBANG_SAJA', 2, 'TIMBANG_1'),
             ('POS_SAJA', 1, 'SECURITY')) v (alur, urutan, tahap)
JOIN dbo.alur a ON a.kode = v.alur;
-- Akun super admin pertama: admin / admin12345. MustChange = 1 -> wajib buat password baru saat login pertama
INSERT INTO dbo.personel (nik, nama_personel, kategori) VALUES (NULL, 'Super Admin', 'EMPLOYEE');
INSERT INTO dbo.Users (UserID, UserName, Nama, UserLevelID, UserDeptID, CompAreaID, PersonnelID)
SELECT CAST(FORMAT(GETDATE(), 'yyMMdd') AS BIGINT) * 10000 + 1, 'admin', 'Super Admin',
       (SELECT LevelDetID FROM dbo.LevelDetails WHERE LevelDetCode = 'ADMIN'), NULL,
       (SELECT MIN(CompAreaID) FROM dbo.CompanyArea), SCOPE_IDENTITY();
INSERT INTO dbo.PasswordManager (UserID, UserPasswd, MustChange, History)
SELECT UserID, 'pbkdf2:sha256:1000000$zkbmkQ6HN9jaUBF5$c6b4177f0ac7789efa50b5d512d6b1ae6bd86963b81d2ba9b9208d3349801419', 1,
       N'["pbkdf2:sha256:1000000$zkbmkQ6HN9jaUBF5$c6b4177f0ac7789efa50b5d512d6b1ae6bd86963b81d2ba9b9208d3349801419"]'
FROM dbo.Users;
GO

/* Log perubahan data (migrasi 034): isi lama & baru tiap baris ke log_aktivitas kategori DATA */
CREATE OR ALTER TRIGGER dbo.TR_LogData_Company ON dbo.Company AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.CompID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.CompID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.CompID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.CompID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'Company', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_CompanyArea ON dbo.CompanyArea AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.CompAreaID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.CompAreaID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.CompAreaID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.CompAreaID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'CompanyArea', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_Mill ON dbo.Mill AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.MillID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.MillID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.MillID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.MillID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'Mill', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_Department ON dbo.Department AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.DeptID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.DeptID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.DeptID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.DeptID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'Department', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_LevelDetails ON dbo.LevelDetails AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.LevelDetID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.LevelDetID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.LevelDetID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.LevelDetID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.password', NULL); SET @baru = JSON_MODIFY(@baru, '$.password', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.last_login', NULL); SET @baru = JSON_MODIFY(@baru, '$.last_login', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.sesi_versi', NULL); SET @baru = JSON_MODIFY(@baru, '$.sesi_versi', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.updated_at', NULL); SET @baru = JSON_MODIFY(@baru, '$.updated_at', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'LevelDetails', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_Users ON dbo.Users AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.UserID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.UserID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.UserID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.UserID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'Users', @id_baris = @k,
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
CREATE OR ALTER TRIGGER dbo.TR_LogData_harga_harian ON dbo.harga_harian AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(CONVERT(VARCHAR(10), d.tanggal, 23) AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(CONVERT(VARCHAR(10), i.tanggal, 23) AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
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
