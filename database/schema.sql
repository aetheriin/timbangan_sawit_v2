/* =====================================================================
   SCHEMA Sistem Timbangan Sawit (Weighbridge + Face Recognition) - ERD v3 final
   Membuat DATABASE BARU dari nol: semua tabel, view, prosedur, trigger, dan data awal
   (setara schema awal + migrasi 001-022). Diuji di SQL Server 2022; minimal SQL Server 2016 SP1
   (CREATE OR ALTER, JSON, HASHBYTES pada NVARCHAR(MAX)).

   ERD Ladder Desk (tahap 1: organisasi & hak akses berbahasa Inggris: Company, Mill, CompanyArea, Department(Details),
   Level(Details), Users, PasswordManager, Menu 3 level, ActionType, AccessMenu, UserCompany, UserSession).
   Tahap 2: orang & kendaraan: Users (= personel: karyawan, supir, tamu; UserName terisi = punya login), UserCategory,
   License + LicenseDetail (SIM), FaceRecog (wajah), VisitPurpose + Guest (kunjungan), FaceActivity (absensi),
   VehicleType, DetailVehicle, VehicleDriver, Blacklist, BlacklistDetection, view UserProfile.
   Tahap 3: mitra & kontrak: Currency, Bank, BankDetails, SupplierType (+ SupplierTypeDetails), SupplierGroup, Supplier
   (+ SupplierCompany), ProductType, Product (+ standar mutu), ProductPrice, DailyPrice, Contract, DeliveryOrder,
   DOTransport, VehicleContract, Invoice.
   Tahap 4: tiket & timbang: WeightBridgeType, Status, WeightBridge (tiket), Weighing, view WeighingSummary, Grading (sortasi),
   LabResult, TicketVoid, DOExcess (kelebihan DO), Log (+ view LogIntegrity).
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

-- Kategori orang (Users.CategoryCode): Driver, Security, Karyawan, Tamu, BHL
CREATE TABLE dbo.UserCategory (
    CategoryCode   VARCHAR(20)   NOT NULL PRIMARY KEY,
    CategoryName   NVARCHAR(50)  NOT NULL,
    RequireLicense BIT NOT NULL CONSTRAINT DF_UserCat_Sim DEFAULT (0),      -- wajib SIM
    CanLogin       BIT NOT NULL CONSTRAINT DF_UserCat_Login DEFAULT (0),    -- boleh dibuatkan akun login
    CodePrefix     VARCHAR(10)   NULL,                                      -- UserCode per kategori, mis. DRV-001
    Active         BIT NOT NULL CONSTRAINT DF_UserCat_Active DEFAULT (1)
);
GO

-- Users = SEMUA orang (karyawan, security, supir, tamu). UserID = YYMMDD + urutan 4 digit (mis. 2601010001), dibuat aplikasi.
-- Punya login bila UserName terisi (wajib ada peran UserLevelID). BlacklistID terisi = sedang diblacklist.
-- FaceEmbeddingData / UploadPath = salinan wajah utama dari FaceRecog (trigger TR_FaceRecog_Utama).
CREATE TABLE dbo.Users (
    UserID            BIGINT        NOT NULL PRIMARY KEY,
    CompAreaID        BIGINT        NULL CONSTRAINT FK_Users_Area REFERENCES dbo.CompanyArea (CompAreaID),
    UserCode          VARCHAR(20)   NULL,                                   -- kode orang, mis. DRV-001
    UserName          VARCHAR(50)   NULL,                                   -- username login; NULL = tanpa akun
    UserDeptID        BIGINT        NULL CONSTRAINT FK_Users_DeptDet REFERENCES dbo.DepartmentDetails (DeptDetailID),   -- NULL = admin sistem
    UserLevelID       INT           NULL CONSTRAINT FK_Users_LevelDet REFERENCES dbo.LevelDetails (LevelDetID),
    CategoryCode      VARCHAR(20)   NOT NULL CONSTRAINT DF_Users_Category DEFAULT ('DRIVER')
                      CONSTRAINT FK_Users_Category REFERENCES dbo.UserCategory (CategoryCode),
    NoKTP             VARCHAR(20)   NULL,                                   -- NIK 16 digit
    GuestID           BIGINT        NULL,
    Nama              NVARCHAR(100) NOT NULL,
    Email             NVARCHAR(100) NULL,
    FaceEmbeddingData VARBINARY(MAX) NULL,
    UploadPath        NVARCHAR(255) NULL,
    CurrentHash       VARCHAR(64)   NULL,
    CreateDate        DATETIME NOT NULL CONSTRAINT DF_Users_Create DEFAULT (GETDATE()),
    UpdateDate        DATETIME NOT NULL CONSTRAINT DF_Users_Update DEFAULT (GETDATE()),
    Active            BIT NOT NULL CONSTRAINT DF_Users_Active DEFAULT (1),
    IsUpload          BIT NOT NULL CONSTRAINT DF_Users_Upload DEFAULT (0),     -- data sudah dilengkapi / diperbarui
    BlacklistID       BIGINT        NULL,                                   -- FK ke Blacklist (dibuat setelah tabel Blacklist)
    Description       NVARCHAR(255) NULL,
    LastLogin         DATETIME      NULL,
    SessionVersion    INT NOT NULL CONSTRAINT DF_Users_SessVer DEFAULT (0),     -- naik = semua sesi user dicabut
    CONSTRAINT CK_Users_Login CHECK (UserName IS NULL OR UserLevelID IS NOT NULL)
);
CREATE UNIQUE INDEX UX_Users_UserName ON dbo.Users (UserName) WHERE UserName IS NOT NULL;
CREATE UNIQUE INDEX UX_Users_NoKTP ON dbo.Users (NoKTP) WHERE NoKTP IS NOT NULL;
CREATE UNIQUE INDEX UX_Users_UserCode ON dbo.Users (UserCode) WHERE UserCode IS NOT NULL;
CREATE INDEX IX_Users_Active_Category ON dbo.Users (Active, CategoryCode) INCLUDE (UserCode, Nama);
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

/* SIM (License + LicenseDetail), wajah (FaceRecog), kunjungan tamu (VisitPurpose + Guest) */
CREATE TABLE dbo.License (
    LicenseID    INT IDENTITY(1,1) PRIMARY KEY,
    LicenseCode  VARCHAR(20)   NOT NULL CONSTRAINT UX_License_Code UNIQUE,
    LicenseType  NVARCHAR(50)  NOT NULL,
    Description  NVARCHAR(255) NULL,
    Active       BIT NOT NULL CONSTRAINT DF_License_Active DEFAULT (1)
);
CREATE TABLE dbo.LicenseDetail (
    DetailLicenseID INT IDENTITY(1,1) PRIMARY KEY,
    UserID          BIGINT NOT NULL CONSTRAINT FK_LicDet_User REFERENCES dbo.Users (UserID),
    SIMType         INT NOT NULL CONSTRAINT FK_LicDet_License REFERENCES dbo.License (LicenseID),
    LicenseNumber   VARCHAR(30) NOT NULL,
    ExpiredSIM      DATE NULL,                 -- NULL hanya untuk data lama yang belum dilengkapi
    Active          BIT NOT NULL CONSTRAINT DF_LicDet_Active DEFAULT (1),
    CreateBy        BIGINT NULL CONSTRAINT FK_LicDet_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate      DATETIME NOT NULL CONSTRAINT DF_LicDet_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_LicDet_NumberActive ON dbo.LicenseDetail (LicenseNumber) WHERE Active = 1;
CREATE INDEX IX_LicDet_User ON dbo.LicenseDetail (UserID, Active);
CREATE TABLE dbo.FaceRecog (
    FaceID      INT IDENTITY(1,1) PRIMARY KEY,
    UserID      BIGINT NOT NULL CONSTRAINT FK_FaceRecog_User REFERENCES dbo.Users (UserID),
    FaceDet     VARBINARY(MAX) NOT NULL,                    -- embedding wajah
    PhotoPath   VARCHAR(255) NULL,
    Source      VARCHAR(10)  NULL CONSTRAINT CK_FaceRecog_Source CHECK (Source IN ('UPLOAD', 'KAMERA')),
    IsMain      BIT NOT NULL CONSTRAINT DF_FaceRecog_Main DEFAULT (1),
    Active      BIT NOT NULL CONSTRAINT DF_FaceRecog_Active DEFAULT (1),
    CreateBy    BIGINT NULL CONSTRAINT FK_FaceRecog_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate  DATETIME NOT NULL CONSTRAINT DF_FaceRecog_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_FaceRecog_Main ON dbo.FaceRecog (UserID) WHERE IsMain = 1 AND Active = 1;
CREATE INDEX IX_FaceRecog_Active ON dbo.FaceRecog (Active) INCLUDE (UserID);
CREATE TABLE dbo.VisitPurpose (
    PurposeID    INT IDENTITY(1,1) PRIMARY KEY,
    PurposeName  NVARCHAR(100) NOT NULL CONSTRAINT UX_VisitPurpose_Name UNIQUE,
    Active       BIT NOT NULL CONSTRAINT DF_VisitPurpose_Active DEFAULT (1)
);
CREATE TABLE dbo.Guest (
    GuestID       INT IDENTITY(1,1) PRIMARY KEY,
    UserID        BIGINT NOT NULL CONSTRAINT FK_Guest_User REFERENCES dbo.Users (UserID),          -- tamu
    VisitToID     BIGINT NOT NULL CONSTRAINT FK_Guest_VisitTo REFERENCES dbo.Users (UserID),       -- orang yang dituju
    PurposeID     INT NOT NULL CONSTRAINT FK_Guest_Purpose REFERENCES dbo.VisitPurpose (PurposeID),
    Description   NVARCHAR(255) NULL,
    CompanyFrom   NVARCHAR(100) NULL,
    NoVehicle     VARCHAR(15)   NULL,
    CompAreaID    BIGINT NOT NULL CONSTRAINT FK_Guest_Area REFERENCES dbo.CompanyArea (CompAreaID),
    PhotoPath     VARCHAR(255)  NULL,      -- snapshot wajah saat datang
    CheckInDate   DATETIME NOT NULL CONSTRAINT DF_Guest_CheckIn DEFAULT (GETDATE()),
    CheckOutDate  DATETIME NULL,           -- NULL = tamu masih di dalam
    CreateBy      BIGINT NOT NULL CONSTRAINT FK_Guest_CreateBy REFERENCES dbo.Users (UserID),
    CONSTRAINT CK_Guest_CheckOut CHECK (CheckOutDate IS NULL OR CheckOutDate >= CheckInDate)
);
CREATE INDEX IX_Guest_CheckIn ON dbo.Guest (CheckInDate DESC);
CREATE INDEX IX_Guest_Inside ON dbo.Guest (UserID) WHERE CheckOutDate IS NULL;
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
-- Profil orang + SIM aktif terbaru + wajah utama
CREATE OR ALTER VIEW dbo.UserProfile AS
SELECT u.UserID, u.UserCode, u.NoKTP, u.Nama, u.Email, u.CategoryCode, u.IsUpload, u.CurrentHash,
       CAST(CASE WHEN u.BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS IsBlacklisted, u.BlacklistID,
       u.Active, u.CreateDate, u.UpdateDate, u.UserName,
       s.LicenseNumber, s.LicenseID, s.LicenseCode, s.ExpiredSIM,
       w.FaceDet, w.PhotoPath, w.Source AS PhotoSource
FROM dbo.Users u
OUTER APPLY (SELECT TOP 1 ld.LicenseNumber, ld.SIMType AS LicenseID, l.LicenseCode, ld.ExpiredSIM
             FROM dbo.LicenseDetail ld JOIN dbo.License l ON l.LicenseID = ld.SIMType
             WHERE ld.UserID = u.UserID AND ld.Active = 1
             ORDER BY ld.ExpiredSIM DESC, ld.DetailLicenseID DESC) s
OUTER APPLY (SELECT TOP 1 f.FaceDet, f.PhotoPath, f.Source
             FROM dbo.FaceRecog f
             WHERE f.UserID = u.UserID AND f.Active = 1
             ORDER BY f.IsMain DESC, f.FaceID DESC) w;
GO

-- Customer (membeli / menjual) & pengangkutan pihak ketiga
-- Mata uang, bank & rekening (disiapkan untuk keuangan; belum ada layar)
CREATE TABLE dbo.Currency (
    CurrencyID    INT IDENTITY(1,1) PRIMARY KEY,
    CurrencyCode  VARCHAR(10)   NOT NULL CONSTRAINT UX_Currency_Code UNIQUE,
    CurrencyName  NVARCHAR(100) NOT NULL,
    CurrencyRate  DECIMAL(20, 4) NULL,                 -- kurs ke IDR
    Description   NVARCHAR(255) NULL,
    Active        BIT NOT NULL CONSTRAINT DF_Currency_Active DEFAULT (1)
);
CREATE TABLE dbo.Bank (
    BankAccountID  INT IDENTITY(1,1) PRIMARY KEY,
    BankName       NVARCHAR(300) NOT NULL,
    BankRegion     NVARCHAR(170) NULL,
    CurrencyID     INT NULL CONSTRAINT FK_Bank_Currency REFERENCES dbo.Currency (CurrencyID),
    CompAreaID     BIGINT NULL CONSTRAINT FK_Bank_Area REFERENCES dbo.CompanyArea (CompAreaID),
    Active         BIT NOT NULL CONSTRAINT DF_Bank_Active DEFAULT (1)
);
CREATE TABLE dbo.BankDetails (
    BankAccountDetailsID  BIGINT IDENTITY(1,1) PRIMARY KEY,
    BankAccountID         INT NOT NULL CONSTRAINT FK_BankDet_Bank REFERENCES dbo.Bank (BankAccountID),
    BankAccountCode       NVARCHAR(100) NOT NULL,          -- no. rekening
    BankName              NVARCHAR(300) NULL,              -- atas nama
    Balance               DECIMAL(20, 2) NULL,
    Active                BIT NOT NULL CONSTRAINT DF_BankDet_Active DEFAULT (1)
);
GO
-- Jenis mitra (Customer, Pengangkutan); satu supplier boleh lebih dari satu jenis (SupplierTypeDetails)
CREATE TABLE dbo.SupplierType (
    SupplierTypeID  INT IDENTITY(1,1) PRIMARY KEY,
    TypeCode        VARCHAR(20)   NOT NULL CONSTRAINT UX_SupplierType_Code UNIQUE,
    NameType        NVARCHAR(255) NOT NULL,
    Description     NVARCHAR(255) NULL,
    Active          BIT NOT NULL CONSTRAINT DF_SupplierType_Active DEFAULT (1)
);
CREATE TABLE dbo.SupplierGroup (
    SupplierGroupID  INT IDENTITY(1,1) PRIMARY KEY,
    NameGroup        NVARCHAR(255) NOT NULL,
    Description      NVARCHAR(255) NULL,
    Active           BIT NOT NULL CONSTRAINT DF_SupplierGroup_Active DEFAULT (1)
);
-- Supplier = mitra (customer / pengangkutan). BlacklistID: disiapkan untuk Supplier Blacklist
CREATE TABLE dbo.Supplier (
    SupplierID            INT IDENTITY(1,1) PRIMARY KEY,
    SupplierCode          VARCHAR(20)   NOT NULL CONSTRAINT UX_Supplier_Code UNIQUE,
    SupplierName          VARCHAR(100)  NOT NULL,
    SupplierAddress       NVARCHAR(255) NULL,
    SupplierGroupID       INT NULL CONSTRAINT FK_Supplier_Group REFERENCES dbo.SupplierGroup (SupplierGroupID),
    BankAccountDetailsID  BIGINT NULL CONSTRAINT FK_Supplier_BankDet REFERENCES dbo.BankDetails (BankAccountDetailsID),
    BlacklistID           BIGINT NULL,
    Description           NVARCHAR(255) NULL,
    Active                BIT NOT NULL CONSTRAINT DF_Supplier_Active DEFAULT (1),
    CreateDate            DATETIME NOT NULL CONSTRAINT DF_Supplier_Create DEFAULT (GETDATE())
);
-- Supplier hanya berlaku di PT tertentu; tanpa baris = semua PT
CREATE TABLE dbo.SupplierCompany (
    SupplierID  INT NOT NULL CONSTRAINT FK_SupplierComp_Supplier REFERENCES dbo.Supplier (SupplierID),
    CompID      VARCHAR(5) NOT NULL CONSTRAINT FK_SupplierComp_Company REFERENCES dbo.Company (CompID),
    CONSTRAINT PK_SupplierCompany PRIMARY KEY (SupplierID, CompID)
);
CREATE TABLE dbo.SupplierTypeDetails (
    SupplierID  INT NOT NULL CONSTRAINT FK_SupTypeDet_Supplier REFERENCES dbo.Supplier (SupplierID),
    TypeCode    VARCHAR(20) NOT NULL CONSTRAINT FK_SupTypeDet_Type REFERENCES dbo.SupplierType (TypeCode),
    CONSTRAINT PK_SupplierTypeDetails PRIMARY KEY (SupplierID, TypeCode)
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

CREATE TABLE dbo.ProductType (
    ProductTypeID    INT IDENTITY(1,1) PRIMARY KEY,
    ProductTypeCode  VARCHAR(20)   NOT NULL CONSTRAINT UX_ProductType_Code UNIQUE,     -- TBS, PRODUK_PKS
    ProductTypeName  NVARCHAR(50)  NOT NULL,
    Description      VARCHAR(150)  NULL,
    Active           BIT NOT NULL CONSTRAINT DF_ProductType_Active DEFAULT (1)
);
-- Produk + standar mutu (batas FFA / kadar air / kotoran, dipakai Lab)
CREATE TABLE dbo.Product (
    ProductID      INT IDENTITY(1,1) PRIMARY KEY,
    ProductName    VARCHAR(100) NOT NULL,
    Category       VARCHAR(20)  NOT NULL CONSTRAINT FK_Product_Type REFERENCES dbo.ProductType (ProductTypeCode),
    FlowID         INT NOT NULL CONSTRAINT FK_Product_Flow REFERENCES dbo.alur (id_alur),       -- alur tahap tiket
    StandardFFA    FLOAT NOT NULL CONSTRAINT DF_Product_FFA DEFAULT (5.0),
    StandardMoist  FLOAT NOT NULL CONSTRAINT DF_Product_Moist DEFAULT (0.5),
    StandardDirt   FLOAT NOT NULL CONSTRAINT DF_Product_Dirt DEFAULT (0.5),
    Active         BIT NOT NULL CONSTRAINT DF_Product_Active DEFAULT (1)
);
-- Harga per produk per tanggal (disiapkan untuk keuangan; belum ada layar). Void, bukan dihapus
CREATE TABLE dbo.ProductPrice (
    ProductPriceID  BIGINT IDENTITY(1,1) PRIMARY KEY,
    ProductID       INT NOT NULL CONSTRAINT FK_ProductPrice_Product REFERENCES dbo.Product (ProductID),
    PriceDate       DATE NOT NULL,
    Price           DECIMAL(14, 2) NOT NULL,
    CurrencyID      INT NULL CONSTRAINT FK_ProductPrice_Currency REFERENCES dbo.Currency (CurrencyID),
    CreateDate      DATETIME NOT NULL CONSTRAINT DF_ProductPrice_Create DEFAULT (GETDATE()),
    CreateBy        BIGINT NULL CONSTRAINT FK_ProductPrice_CreateBy REFERENCES dbo.Users (UserID),
    IsVoid          BIT NOT NULL CONSTRAINT DF_ProductPrice_Void DEFAULT (0),
    VoidDate        DATETIME NULL,
    VoidBy          BIGINT NULL CONSTRAINT FK_ProductPrice_VoidBy REFERENCES dbo.Users (UserID)
);
CREATE INDEX IX_ProductPrice_Product_Date ON dbo.ProductPrice (ProductID, PriceDate DESC) WHERE IsVoid = 0;
GO

-- Jenis kendaraan. Kapasitas: peringatan di timbangan; kosong = tidak dicek
CREATE TABLE dbo.VehicleType (
    VehicleTypeID    INT IDENTITY(1,1) PRIMARY KEY,
    VehicleTypeCode  VARCHAR(20)  NOT NULL CONSTRAINT UX_VehicleType_Code UNIQUE,
    NameType         NVARCHAR(50) NOT NULL,
    Active           BIT NOT NULL CONSTRAINT DF_VehicleType_Active DEFAULT (1),
    WeightCar        DECIMAL(10, 2) NULL,          -- berat kosong (kg)
    MaxLoad          DECIMAL(10, 2) NULL,          -- muatan maksimal (kg)
    Seat             INT NULL
);
GO
-- Kendaraan: plat & STNK unik. BlacklistID terisi = sedang diblacklist
CREATE TABLE dbo.DetailVehicle (
    IDVehicle    INT IDENTITY(1,1) PRIMARY KEY,
    NoVehicle    VARCHAR(15) NOT NULL CONSTRAINT UX_DetailVehicle_No UNIQUE,
    NoSTNK       VARCHAR(50) NOT NULL,
    VehicleType  INT NULL CONSTRAINT FK_DetailVehicle_Type REFERENCES dbo.VehicleType (VehicleTypeID),
    BlacklistID  BIGINT NULL,
    Active       BIT NOT NULL CONSTRAINT DF_DetailVehicle_Active DEFAULT (1),
    CreateDate   DATETIME NOT NULL CONSTRAINT DF_DetailVehicle_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_DetailVehicle_Stnk ON dbo.DetailVehicle (NoSTNK);
GO

-- Supir terdaftar per truk (supir utama disarankan saat Create Ticket)
CREATE TABLE dbo.VehicleDriver (
    VehicleDriverID INT IDENTITY(1,1) PRIMARY KEY,
    IDVehicle   INT NOT NULL CONSTRAINT FK_VD_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    UserID      BIGINT NOT NULL CONSTRAINT FK_VD_User REFERENCES dbo.Users (UserID),
    IsMain      BIT NOT NULL CONSTRAINT DF_VD_Main DEFAULT (0),
    Active      BIT NOT NULL CONSTRAINT DF_VD_Active DEFAULT (1),
    CreateBy    BIGINT NULL CONSTRAINT FK_VD_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate  DATETIME NOT NULL CONSTRAINT DF_VD_Create DEFAULT (GETDATE()),
    UpdateDate  DATETIME NOT NULL CONSTRAINT DF_VD_Update DEFAULT (GETDATE()),
    CONSTRAINT UQ_VD_Vehicle_User UNIQUE (IDVehicle, UserID)
);
CREATE INDEX IX_VD_User ON dbo.VehicleDriver (UserID) INCLUDE (IDVehicle, Active, IsMain);
GO

-- Kontrak per truk (modal Update > Kontrak Truk di Form Security)
CREATE TABLE dbo.VehicleContract (
    VehicleContractID  INT IDENTITY(1,1) PRIMARY KEY,
    ContractNumber     VARCHAR(50) NULL,
    IDVehicle          INT NOT NULL CONSTRAINT FK_VC_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    SupplierID         INT NOT NULL CONSTRAINT FK_VC_Supplier REFERENCES dbo.Supplier (SupplierID),
    ProductID          INT NULL CONSTRAINT FK_VC_Product REFERENCES dbo.Product (ProductID),
    TransactionType    VARCHAR(20) NULL,
    StartDate          DATE NOT NULL,
    EndDate            DATE NULL,
    Active             BIT NOT NULL CONSTRAINT DF_VC_Active DEFAULT (1),
    Description        VARCHAR(255) NULL,
    CreateBy           BIGINT NULL CONSTRAINT FK_VC_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate         DATETIME NOT NULL CONSTRAINT DF_VC_Create DEFAULT (GETDATE()),
    CONSTRAINT CK_VC_Type CHECK (TransactionType IS NULL OR TransactionType IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_VC_Period CHECK (EndDate IS NULL OR EndDate >= StartDate)
);
CREATE INDEX IX_VC_Vehicle ON dbo.VehicleContract (IDVehicle, Active);
CREATE INDEX IX_VC_Vehicle_Supplier ON dbo.VehicleContract (IDVehicle, SupplierID, Active);
GO

-- Kontrak & DO (migrasi 013, diisi HO): 1 kontrak = 1 produk = 1 DO; 1 DO boleh beberapa pengangkut
-- Jenis tiket (pembelian / penjualan / penimbangan saja); IsPayment disiapkan untuk keuangan
CREATE TABLE dbo.WeightBridgeType (
    WeightTypeID    INT IDENTITY(1,1) PRIMARY KEY,
    WeightTypeCode  VARCHAR(20)  NOT NULL CONSTRAINT UX_WBType_Code UNIQUE,
    WeightTypeName  NVARCHAR(50) NOT NULL,
    IsPayment       BIT NOT NULL CONSTRAINT DF_WBType_Payment DEFAULT (0),
    Active          BIT NOT NULL CONSTRAINT DF_WBType_Active DEFAULT (1)
);
ALTER TABLE dbo.VehicleContract ADD CONSTRAINT FK_VC_WBType FOREIGN KEY (TransactionType) REFERENCES dbo.WeightBridgeType (WeightTypeCode);
-- Status tiket: nama & warna diatur di Admin › Organisasi
CREATE TABLE dbo.Status (
    StatusID     INT IDENTITY(1,1) PRIMARY KEY,
    StatusCode   VARCHAR(30)   NOT NULL CONSTRAINT UX_Status_Code UNIQUE,
    StatusName   NVARCHAR(50)  NOT NULL,
    StatusColor  VARCHAR(10)   NOT NULL CONSTRAINT DF_Status_Color DEFAULT ('abu'),
    SortOrder    TINYINT NOT NULL CONSTRAINT DF_Status_Sort DEFAULT (0),
    Description  NVARCHAR(255) NULL
);
-- Kontrak (diisi HO): 1 kontrak = 1 produk = 1 DO
CREATE TABLE dbo.Contract (
    ContractID       INT IDENTITY(1,1) PRIMARY KEY,
    ContractNumber   VARCHAR(50) NOT NULL CONSTRAINT UX_Contract_No UNIQUE,
    TransactionType  VARCHAR(20) NOT NULL CONSTRAINT FK_Contract_WBType REFERENCES dbo.WeightBridgeType (WeightTypeCode),
    SupplierID       INT NOT NULL CONSTRAINT FK_Contract_Supplier REFERENCES dbo.Supplier (SupplierID),   -- customer
    ProductID        INT NOT NULL CONSTRAINT FK_Contract_Product REFERENCES dbo.Product (ProductID),
    ContractDate     DATE NOT NULL CONSTRAINT DF_Contract_Date DEFAULT (CAST(GETDATE() AS DATE)),
    ContractQty      DECIMAL(14, 2) NULL,
    Price            DECIMAL(14, 2) NULL,
    PPN              BIT NOT NULL CONSTRAINT DF_Contract_Ppn DEFAULT (0),
    IncludePPN       BIT NOT NULL CONSTRAINT DF_Contract_InclPpn DEFAULT (0),
    CurrencyID       INT NULL CONSTRAINT FK_Contract_Currency REFERENCES dbo.Currency (CurrencyID),
    CompID           VARCHAR(5) NULL CONSTRAINT FK_Contract_Company REFERENCES dbo.Company (CompID),
    Description      VARCHAR(200) NULL,
    Active           BIT NOT NULL CONSTRAINT DF_Contract_Active DEFAULT (1),
    CreateBy         BIGINT NULL CONSTRAINT FK_Contract_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate       DATETIME NOT NULL CONSTRAINT DF_Contract_Create DEFAULT (GETDATE()),
    CONSTRAINT CK_Contract_Type CHECK (TransactionType IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_Contract_Qty CHECK (ContractQty IS NULL OR ContractQty > 0)
);
GO
CREATE TABLE dbo.DeliveryOrder (
    DeliveryOrderID  INT IDENTITY(1,1) PRIMARY KEY,
    DONumber         VARCHAR(50) NOT NULL CONSTRAINT UX_DO_Number UNIQUE,
    ContractID       INT NOT NULL CONSTRAINT FK_DO_Contract REFERENCES dbo.Contract (ContractID),
    DODate           DATE NOT NULL CONSTRAINT DF_DO_Date DEFAULT (CAST(GETDATE() AS DATE)),
    ExpiredDate      DATE NULL,
    Description      VARCHAR(200) NULL,
    Active           BIT NOT NULL CONSTRAINT DF_DO_Active DEFAULT (1),
    CreateBy         BIGINT NULL CONSTRAINT FK_DO_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate       DATETIME NOT NULL CONSTRAINT DF_DO_Create DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_DO_Contract ON dbo.DeliveryOrder (ContractID);     -- 1 kontrak = 1 DO
GO
-- Pengangkutan per DO (boleh beberapa): PENGIRIM / PENERIMA / PIHAK_KETIGA (TransportID)
CREATE TABLE dbo.DOTransport (
    DOTransportID    INT IDENTITY(1,1) PRIMARY KEY,
    DeliveryOrderID  INT NOT NULL CONSTRAINT FK_DOTrans_DO REFERENCES dbo.DeliveryOrder (DeliveryOrderID),
    TransportMode    VARCHAR(15) NOT NULL,
    TransportID      INT NULL CONSTRAINT FK_DOTrans_Supplier REFERENCES dbo.Supplier (SupplierID),
    DOQty            DECIMAL(14, 2) NULL,               -- alokasi (opsional), total <= Contract.ContractQty
    PriceTransport   DECIMAL(14, 2) NULL,               -- ongkos angkut per kg
    CONSTRAINT CK_DOTrans_Mode CHECK (TransportMode IN ('PENGIRIM', 'PENERIMA', 'PIHAK_KETIGA')),
    CONSTRAINT CK_DOTrans_ThirdParty CHECK ((TransportMode = 'PIHAK_KETIGA' AND TransportID IS NOT NULL)
                                            OR (TransportMode <> 'PIHAK_KETIGA' AND TransportID IS NULL)),
    CONSTRAINT UX_DOTransport UNIQUE (DeliveryOrderID, TransportMode, TransportID)
);
GO
-- Tagihan per DO (disiapkan untuk keuangan; belum ada layar)
CREATE TABLE dbo.Invoice (
    InvoiceID        BIGINT IDENTITY(1,1) PRIMARY KEY,
    InvoiceNumber    VARCHAR(100) NOT NULL CONSTRAINT UX_Invoice_No UNIQUE,
    InvoiceDate      DATE NOT NULL,
    DeliveryOrderID  INT NOT NULL CONSTRAINT FK_Invoice_DO REFERENCES dbo.DeliveryOrder (DeliveryOrderID),
    SupplierID       INT NOT NULL CONSTRAINT FK_Invoice_Supplier REFERENCES dbo.Supplier (SupplierID),
    TransportID      INT NULL CONSTRAINT FK_Invoice_Transport REFERENCES dbo.Supplier (SupplierID),
    PriceTransport   DECIMAL(14, 2) NULL,
    DOQty            DECIMAL(14, 2) NULL,
    DOShipped        DECIMAL(14, 2) NULL,
    Amount           DECIMAL(20, 2) NULL,
    CurrencyID       INT NULL CONSTRAINT FK_Invoice_Currency REFERENCES dbo.Currency (CurrencyID),
    PaidDate         DATE NULL,
    Active           BIT NOT NULL CONSTRAINT DF_Invoice_Active DEFAULT (1),
    CreateBy         BIGINT NULL CONSTRAINT FK_Invoice_CreateBy REFERENCES dbo.Users (UserID),
    CreateDate       DATETIME NOT NULL CONSTRAINT DF_Invoice_Create DEFAULT (GETDATE())
);
GO

-- Dashboard: harga CPO & kernel, OER, biaya olah per tanggal (diisi HO)
CREATE TABLE dbo.DailyPrice (
    PriceDate       DATE PRIMARY KEY,
    CPOPrice        DECIMAL(12,2) NOT NULL,
    KernelPrice     DECIMAL(12,2) NOT NULL,
    OERCPO          DECIMAL(5,2)  NOT NULL,
    ProcessingCost  DECIMAL(12,2) NOT NULL,
    UpdateBy        BIGINT NULL CONSTRAINT FK_DailyPrice_UpdateBy REFERENCES dbo.Users (UserID),
    UpdateDate      DATETIME NOT NULL CONSTRAINT DF_DailyPrice_Update DEFAULT (GETDATE()),
    CONSTRAINT CK_DailyPrice_Oer CHECK (OERCPO BETWEEN 0 AND 100)
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
-- Tiket timbang (WeightBridge). Bruto / tara / netto dihitung dari Weighing (view WeighingSummary)
CREATE TABLE dbo.WeightBridge (
    WeightID            BIGINT IDENTITY(1,1) PRIMARY KEY,
    TicketNumber        VARCHAR(50) NOT NULL CONSTRAINT UX_WB_Ticket UNIQUE,
    TicketDate          DATETIME NOT NULL CONSTRAINT DF_WB_TicketDate DEFAULT (GETDATE()),
    WeightTypeCode      VARCHAR(20) NOT NULL CONSTRAINT FK_WB_Type REFERENCES dbo.WeightBridgeType (WeightTypeCode),
    SupplierID          INT NOT NULL CONSTRAINT FK_WB_Supplier REFERENCES dbo.Supplier (SupplierID),          -- customer (dari DO)
    ProductID           INT NOT NULL CONSTRAINT FK_WB_Product REFERENCES dbo.Product (ProductID),
    IDVehicle           INT NOT NULL CONSTRAINT FK_WB_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    DriverID            BIGINT NOT NULL CONSTRAINT FK_WB_Driver REFERENCES dbo.Users (UserID),
    TransportMode       VARCHAR(15) NOT NULL,                        -- PENGIRIM / PENERIMA / PIHAK_KETIGA (TransportID)
    TransportID         INT NULL CONSTRAINT FK_WB_Transport REFERENCES dbo.Supplier (SupplierID),
    VehicleContractID   INT NULL CONSTRAINT FK_WB_VehicleContract REFERENCES dbo.VehicleContract (VehicleContractID),
    DONumber            VARCHAR(50) NULL,
    DeliveryOrderID     INT NULL CONSTRAINT FK_WB_DO REFERENCES dbo.DeliveryOrder (DeliveryOrderID),
    StatusCode          VARCHAR(30) NOT NULL CONSTRAINT DF_WB_Status DEFAULT ('SECURITY_REGISTER')
                        CONSTRAINT FK_WB_Status REFERENCES dbo.Status (StatusCode),
    IsVoid              AS CAST(CASE WHEN StatusCode = 'VOID' THEN 1 ELSE 0 END AS BIT),
    IsQRActive          BIT NOT NULL CONSTRAINT DF_WB_QrActive DEFAULT (1),
    QRExpiredDate       DATETIME NOT NULL,
    QRReprintCount      INT NOT NULL CONSTRAINT DF_WB_Reprint DEFAULT (0),
    DriverPhotoPath     VARCHAR(255) NULL,
    ScaleID             INT NULL CONSTRAINT FK_WB_Scale REFERENCES dbo.jembatan_timbang (id_jembatan),     -- jembatan timbang masuk
    CompAreaID          BIGINT NOT NULL CONSTRAINT FK_WB_Area REFERENCES dbo.CompanyArea (CompAreaID),        -- area akun Security
    FlowID              INT NULL CONSTRAINT FK_WB_Flow REFERENCES dbo.alur (id_alur),                      -- alur tahap tiket (dari produk)
    ParentTicketNumber  VARCHAR(50) NULL CONSTRAINT FK_WB_Parent REFERENCES dbo.WeightBridge (TicketNumber),  -- tiket split kelebihan DO
    SplitWeight         DECIMAL(14, 2) NULL,                         -- netto tiket split (tanpa penimbangan sendiri)
    CreateBy            BIGINT NOT NULL CONSTRAINT FK_WB_CreateBy REFERENCES dbo.Users (UserID),             -- security
    CheckDate           DATETIME NULL,                               -- verifikasi tiket selesai
    CheckBy             BIGINT NULL CONSTRAINT FK_WB_CheckBy REFERENCES dbo.Users (UserID),
    IsCheck             AS CAST(CASE WHEN CheckDate IS NULL THEN 0 ELSE 1 END AS BIT),
    ExitDate            DATETIME NULL,                               -- jam keluar gerbang (Logbook)
    ExitBy              BIGINT NULL CONSTRAINT FK_WB_ExitBy REFERENCES dbo.Users (UserID),
    CONSTRAINT CK_WB_TransportMode CHECK ((TransportMode = 'PIHAK_KETIGA' AND TransportID IS NOT NULL)
                                          OR (TransportMode IN ('PENGIRIM', 'PENERIMA') AND TransportID IS NULL))
);
CREATE INDEX IX_WB_Status_Date ON dbo.WeightBridge (StatusCode, TicketDate DESC) INCLUDE (IDVehicle, SupplierID, DriverID);
CREATE INDEX IX_WB_Vehicle_Date ON dbo.WeightBridge (IDVehicle, TicketDate DESC);
CREATE INDEX IX_WB_Exit ON dbo.WeightBridge (ExitDate) INCLUDE (IDVehicle, CompAreaID, StatusCode);
CREATE INDEX IX_WB_Area_Date ON dbo.WeightBridge (CompAreaID, TicketDate DESC);
CREATE INDEX IX_WB_Supplier_Date ON dbo.WeightBridge (SupplierID, TicketDate DESC);
CREATE INDEX IX_WB_Driver_Date ON dbo.WeightBridge (DriverID, TicketDate DESC);
GO

-- Void (Admin) / reject (Lab), migrasi 010
CREATE TABLE dbo.TicketVoid (
    TicketNumber  VARCHAR(50)   NOT NULL PRIMARY KEY CONSTRAINT FK_TicketVoid_WB REFERENCES dbo.WeightBridge (TicketNumber),
    VoidType      VARCHAR(10)   NOT NULL CONSTRAINT CK_TicketVoid_Type CHECK (VoidType IN ('VOID', 'REJECT')),
    Reason        NVARCHAR(255) NOT NULL,
    DocumentID    INT NULL CONSTRAINT FK_TicketVoid_Doc REFERENCES dbo.dokumen (id_dokumen),   -- berita acara, boleh menyusul
    VoidBy        BIGINT NULL CONSTRAINT FK_TicketVoid_User REFERENCES dbo.Users (UserID),
    VoidDate      DATETIME NOT NULL CONSTRAINT DF_TicketVoid_Date DEFAULT (GETDATE())
);
CREATE INDEX IX_TicketVoid_Date ON dbo.TicketVoid (VoidDate DESC);
GO

-- Penimbangan: ke-1 masuk, ke-2 keluar di jembatan yang sama; bruto/tara/netto lewat view WeighingSummary
CREATE TABLE dbo.Weighing (
    TicketNumber  VARCHAR(50) NOT NULL CONSTRAINT FK_Weighing_WB REFERENCES dbo.WeightBridge (TicketNumber),
    WeighNo       TINYINT NOT NULL CONSTRAINT CK_Weighing_No CHECK (WeighNo IN (1, 2)),
    ScaleID       INT NOT NULL CONSTRAINT FK_Weighing_Scale REFERENCES dbo.jembatan_timbang (id_jembatan),
    Weight        DECIMAL(10, 2) NOT NULL,
    WeighDate     DATETIME NOT NULL CONSTRAINT DF_Weighing_Date DEFAULT (GETDATE()),
    OperatorID    BIGINT NULL CONSTRAINT FK_Weighing_Operator REFERENCES dbo.Users (UserID),
    Hash          CHAR(64) NULL,
    CONSTRAINT PK_Weighing PRIMARY KEY (TicketNumber, WeighNo)
);
CREATE INDEX IX_Weighing_Date ON dbo.Weighing (WeighDate DESC);
GO
CREATE OR ALTER TRIGGER dbo.TR_Weighing_SameScale ON dbo.Weighing AFTER INSERT, UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM inserted i
               JOIN dbo.Weighing w1 ON w1.TicketNumber = i.TicketNumber AND w1.WeighNo = 1
               WHERE i.WeighNo = 2 AND i.ScaleID <> w1.ScaleID)
    BEGIN
        RAISERROR('Timbang keluar harus di jembatan timbang yang sama dengan timbang masuk.', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END
    IF EXISTS (SELECT 1 FROM inserted i WHERE i.WeighNo = 2
               AND NOT EXISTS (SELECT 1 FROM dbo.Weighing w1 WHERE w1.TicketNumber = i.TicketNumber AND w1.WeighNo = 1))
    BEGIN
        RAISERROR('Timbang ke-2 hanya boleh setelah timbang ke-1.', 16, 1);
        ROLLBACK TRANSACTION;
        RETURN;
    END
    UPDATE t SET t.ScaleID = i.ScaleID
    FROM dbo.WeightBridge t JOIN inserted i ON i.TicketNumber = t.TicketNumber AND i.WeighNo = 1;
END
GO
-- Bruto / tara / netto per tiket (penjualan: masuk = tara, keluar = bruto; penimbangan saja: satu kali timbang)
CREATE OR ALTER VIEW dbo.WeighingSummary AS
SELECT t.TicketNumber, t.WeightTypeCode, t.ScaleID, j.kode AS ScaleCode,
       CAST(CASE WHEN t.WeightTypeCode = 'PENJUALAN' THEN w2.Weight ELSE w1.Weight END AS FLOAT) AS Bruto,
       CASE WHEN t.WeightTypeCode = 'PENJUALAN' THEN w2.WeighDate ELSE w1.WeighDate END AS BrutoDate,
       CAST(CASE WHEN t.WeightTypeCode = 'PENJUALAN' THEN w1.Weight
                 WHEN t.WeightTypeCode = 'PENIMBANGAN_SAJA' THEN NULL ELSE w2.Weight END AS FLOAT) AS Tara,
       CASE WHEN t.WeightTypeCode = 'PENJUALAN' THEN w1.WeighDate
            WHEN t.WeightTypeCode = 'PENIMBANGAN_SAJA' THEN NULL ELSE w2.WeighDate END AS TaraDate,
       CAST(CASE WHEN t.WeightTypeCode = 'PENIMBANGAN_SAJA' THEN w1.Weight
                 WHEN w2.Weight IS NOT NULL THEN ABS(w1.Weight - w2.Weight) END AS FLOAT) AS Netto,
       COALESCE(w2.Hash, w1.Hash) AS SecurityHash,
       COALESCE(w2.OperatorID, w1.OperatorID) AS OperatorID
FROM dbo.WeightBridge t
LEFT JOIN dbo.Weighing w1 ON w1.TicketNumber = t.TicketNumber AND w1.WeighNo = 1
LEFT JOIN dbo.Weighing w2 ON w2.TicketNumber = t.TicketNumber AND w2.WeighNo = 2
LEFT JOIN dbo.jembatan_timbang j ON j.id_jembatan = t.ScaleID;
GO

-- Kelebihan DO (migrasi 022): kelebihan netto di atas kuota kontrak -> tiket split + No. DO baru (Ascend)
CREATE TABLE dbo.DOExcess (
    ExcessID           INT IDENTITY(1,1) PRIMARY KEY,
    TicketNumber       VARCHAR(50)    NOT NULL CONSTRAINT FK_DOExcess_WB REFERENCES dbo.WeightBridge (TicketNumber),
    SplitTicketNumber  VARCHAR(50)    NOT NULL CONSTRAINT FK_DOExcess_Split REFERENCES dbo.WeightBridge (TicketNumber),
    DeliveryOrderID    INT            NOT NULL CONSTRAINT FK_DOExcess_DO REFERENCES dbo.DeliveryOrder (DeliveryOrderID),
    QuotaKg            DECIMAL(14, 2) NOT NULL,
    RealizedKg         DECIMAL(14, 2) NOT NULL,
    TicketNettoKg      DECIMAL(14, 2) NOT NULL,
    ExcessKg           DECIMAL(14, 2) NOT NULL,
    NewDONumber        VARCHAR(50)    NULL,
    Status             VARCHAR(15)    NOT NULL CONSTRAINT DF_DOExcess_Status DEFAULT ('MENUNGGU'),
    Notes              NVARCHAR(255)  NULL,
    SubmitBy           BIGINT NULL CONSTRAINT FK_DOExcess_SubmitBy REFERENCES dbo.Users (UserID),
    SubmitDate         DATETIME NULL,
    ConfirmBy          BIGINT NULL CONSTRAINT FK_DOExcess_ConfirmBy REFERENCES dbo.Users (UserID),
    ConfirmDate        DATETIME NULL,
    ReturnReason       NVARCHAR(255)  NULL,
    CompAreaID         BIGINT NULL CONSTRAINT FK_DOExcess_Area REFERENCES dbo.CompanyArea (CompAreaID),
    CreateDate         DATETIME NOT NULL CONSTRAINT DF_DOExcess_Create DEFAULT (GETDATE()),
    CONSTRAINT UX_DOExcess_Ticket UNIQUE (TicketNumber),
    CONSTRAINT CK_DOExcess_Status CHECK (Status IN ('MENUNGGU', 'DIAJUKAN', 'SELESAI', 'DIKEMBALIKAN')),
    CONSTRAINT CK_DOExcess_Kg CHECK (ExcessKg > 0)
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

-- Sortasi TBS (Grading): persen per kriteria + potongan kg
CREATE TABLE dbo.Grading (
    GradingID      INT IDENTITY(1,1) PRIMARY KEY,
    TicketNumber   VARCHAR(50) NOT NULL CONSTRAINT UX_Grading_Ticket UNIQUE
                   CONSTRAINT FK_Grading_WB REFERENCES dbo.WeightBridge (TicketNumber),
    UnripePct      FLOAT NULL,          -- buah mentah
    RottenPct      FLOAT NULL,          -- buah busuk
    LongStalkPct   FLOAT NULL,          -- tangkai panjang
    DirtPct        FLOAT NULL,          -- sampah / kotoran
    RipePct        FLOAT NULL,          -- buah matang
    LooseFruitPct  FLOAT NULL,          -- brondolan
    DeductionKg    FLOAT NULL,
    Notes          VARCHAR(500) NULL,
    GradedBy       BIGINT NULL CONSTRAINT FK_Grading_User REFERENCES dbo.Users (UserID),
    GradingDate    DATETIME NULL
);
GO

-- Hasil lab produk PKS; APPROVE wajib COA (COADocID)
CREATE TABLE dbo.LabResult (
    LabResultID    INT IDENTITY(1,1) PRIMARY KEY,
    TicketNumber   VARCHAR(50) NOT NULL CONSTRAINT UX_LabResult_Ticket UNIQUE
                   CONSTRAINT FK_LabResult_WB REFERENCES dbo.WeightBridge (TicketNumber),
    FFA            FLOAT NULL,
    Moisture       FLOAT NULL,          -- kadar air
    Dirt           FLOAT NULL,          -- kadar kotoran
    LovibondColor  VARCHAR(50) NULL,    -- warna (lovibond)
    Decision       VARCHAR(20) NULL,
    COADocID       INT NULL CONSTRAINT FK_LabResult_Doc REFERENCES dbo.dokumen (id_dokumen),
    TestedBy       BIGINT NULL CONSTRAINT FK_LabResult_User REFERENCES dbo.Users (UserID),
    TestDate       DATETIME NULL,
    CONSTRAINT CK_LabResult_Decision CHECK (Decision IS NULL OR Decision IN ('APPROVE', 'REJECT'))
);
GO

/* =========================== FACE RECOGNITION =========================== */

-- Blacklist orang (TableName 'Users') / kendaraan ('DetailVehicle'). Baris tidak pernah dihapus; dicabut lewat persetujuan.
-- AliasName, CategoryCode (kategori target saat itu; KENDARAAN untuk kendaraan), CompAreaID = area pengaju.
CREATE TABLE dbo.Blacklist (
    BlacklistID    BIGINT IDENTITY(1,1) PRIMARY KEY,
    CreateDate     DATETIME NOT NULL CONSTRAINT DF_Blacklist_Create DEFAULT (GETDATE()),
    BlacklistDoc   INT NULL CONSTRAINT FK_Blacklist_Doc REFERENCES dbo.dokumen (id_dokumen),   -- surat; NULL = menyusul
    LogActionType  VARCHAR(20)  NOT NULL CONSTRAINT DF_Blacklist_Action DEFAULT ('BLACKLIST'),
    TableName      VARCHAR(30)  NOT NULL CONSTRAINT CK_Blacklist_Table CHECK (TableName IN ('Users', 'DetailVehicle')),
    TargetType     AS CAST(CASE TableName WHEN 'Users' THEN 'PERSONEL' ELSE 'KENDARAAN' END AS VARCHAR(20)) PERSISTED,
    OldValue       NVARCHAR(MAX) NULL CONSTRAINT CK_Blacklist_Old CHECK (OldValue IS NULL OR ISJSON(OldValue) = 1),
    NewValue       NVARCHAR(MAX) NULL CONSTRAINT CK_Blacklist_New CHECK (NewValue IS NULL OR ISJSON(NewValue) = 1),
    UserID         BIGINT NULL CONSTRAINT FK_Blacklist_User REFERENCES dbo.Users (UserID),
    IDVehicle      INT NULL CONSTRAINT FK_Blacklist_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    Reason         VARCHAR(500) NOT NULL,
    CreateBy       BIGINT NOT NULL CONSTRAINT FK_Blacklist_CreateBy REFERENCES dbo.Users (UserID),
    NoVehicle      VARCHAR(15) NULL,                  -- plat saat itu (supir / tamu)
    CustomerID     INT NULL CONSTRAINT FK_Blacklist_Customer REFERENCES dbo.Supplier (SupplierID),
    TransportID    INT NULL CONSTRAINT FK_Blacklist_Transport REFERENCES dbo.Supplier (SupplierID),
    RevokeDate     DATETIME NULL,
    RevokeBy       BIGINT NULL CONSTRAINT FK_Blacklist_RevokeBy REFERENCES dbo.Users (UserID),
    RevokeReason   NVARCHAR(500) NULL,
    AliasName      NVARCHAR(100) NULL,
    CategoryCode   VARCHAR(20) NULL,
    CompAreaID     BIGINT NULL CONSTRAINT FK_Blacklist_Area REFERENCES dbo.CompanyArea (CompAreaID),
    CONSTRAINT CK_Blacklist_Target CHECK (
        (TableName = 'Users'         AND UserID IS NOT NULL AND IDVehicle IS NULL) OR
        (TableName = 'DetailVehicle' AND IDVehicle IS NOT NULL AND UserID IS NULL))
);
CREATE INDEX IX_Blacklist_User    ON dbo.Blacklist (UserID)    WHERE UserID IS NOT NULL;
CREATE INDEX IX_Blacklist_Vehicle ON dbo.Blacklist (IDVehicle) WHERE IDVehicle IS NOT NULL;
CREATE INDEX IX_Blacklist_Doc ON dbo.Blacklist (BlacklistDoc);
ALTER TABLE dbo.Users ADD CONSTRAINT FK_Users_Blacklist FOREIGN KEY (BlacklistID) REFERENCES dbo.Blacklist (BlacklistID);
ALTER TABLE dbo.DetailVehicle ADD CONSTRAINT FK_DetailVehicle_Blacklist FOREIGN KEY (BlacklistID) REFERENCES dbo.Blacklist (BlacklistID);
ALTER TABLE dbo.Supplier ADD CONSTRAINT FK_Supplier_Blacklist FOREIGN KEY (BlacklistID) REFERENCES dbo.Blacklist (BlacklistID);
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

-- Absensi wajah
CREATE TABLE dbo.FaceActivity (
    ActivityID         INT IDENTITY(1,1) PRIMARY KEY,
    UserID             BIGINT NULL CONSTRAINT FK_FaceAct_User REFERENCES dbo.Users (UserID),
    ActivityType       VARCHAR(10) NULL,
    Status             VARCHAR(20) NOT NULL,
    TimeStatus         VARCHAR(20) NULL,
    DiffMinutes        INT NULL,
    FaceDistance       FLOAT NULL,
    LivenessChallenge  VARCHAR(20) NULL,
    PhotoPath          VARCHAR(255) NULL,
    Device             VARCHAR(50) NULL,
    IPAddress          VARCHAR(45) NULL,
    LogDate            DATETIME NOT NULL CONSTRAINT DF_FaceAct_LogDate DEFAULT (GETDATE()),
    LogDay             AS CAST(LogDate AS DATE) PERSISTED,
    CONSTRAINT CK_FaceAct_Status CHECK (Status IN ('BERHASIL', 'TIDAK_DIKENALI', 'DITOLAK_BLACKLIST')),
    CONSTRAINT CK_FaceAct_Type CHECK (ActivityType IS NULL OR ActivityType IN ('MASUK', 'PULANG')),
    CONSTRAINT CK_FaceAct_Time CHECK (TimeStatus IS NULL OR TimeStatus IN ('TEPAT_WAKTU', 'TERLAMBAT', 'PULANG_AWAL', 'HARI_LIBUR')),
    CONSTRAINT CK_FaceAct_Success CHECK (Status <> 'BERHASIL' OR (UserID IS NOT NULL AND ActivityType IS NOT NULL))
);
CREATE INDEX IX_FaceAct_User_Day ON dbo.FaceActivity (UserID, LogDay);
CREATE INDEX IX_FaceAct_Day ON dbo.FaceActivity (LogDay);
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
CREATE TABLE dbo.Log (
    LogID          BIGINT IDENTITY(1,1) PRIMARY KEY,
    LogDate        DATETIME2(3) NOT NULL,
    CreateBy       BIGINT NULL CONSTRAINT FK_Log_User REFERENCES dbo.Users (UserID),     -- NULL = kiosk / sistem
    CompAreaID     BIGINT NULL CONSTRAINT FK_Log_Area REFERENCES dbo.CompanyArea (CompAreaID),
    Category       VARCHAR(20)  NOT NULL,      -- ADMIN, SECURITY, PERSONEL, STANDAR_MUTU, DATA, ...
    LogActionType  VARCHAR(40)  NOT NULL,
    TableName      VARCHAR(50)  NULL,
    RowID          VARCHAR(100) NULL,
    OldValue       NVARCHAR(MAX) NULL,
    NewValue       NVARCHAR(MAX) NULL,
    IPAddress      VARCHAR(45)  NULL,
    PrevHash       CHAR(64) NULL,              -- NULL hanya baris pertama
    RowHash        CHAR(64) NOT NULL,
    CONSTRAINT CK_Log_OldJson CHECK (OldValue IS NULL OR ISJSON(OldValue) = 1),
    CONSTRAINT CK_Log_NewJson CHECK (NewValue IS NULL OR ISJSON(NewValue) = 1)
);
CREATE INDEX IX_Log_Category_Date ON dbo.Log (Category, LogDate DESC);
CREATE INDEX IX_Log_Row ON dbo.Log (TableName, RowID);
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
    EXEC sp_getapplock @Resource = 'Log', @LockMode = 'Exclusive', @LockOwner = 'Transaction';
    DECLARE @prev CHAR(64) = (SELECT TOP 1 RowHash FROM dbo.Log ORDER BY LogID DESC);
    SET @waktu = COALESCE(@waktu, SYSDATETIME());
    IF @id_comp_area IS NULL AND @id_user IS NOT NULL
        SET @id_comp_area = (SELECT CompAreaID FROM dbo.Users WHERE UserID = @id_user);
    INSERT INTO dbo.Log (LogDate, CreateBy, CompAreaID, Category, LogActionType, TableName, RowID, OldValue, NewValue,
                         IPAddress, PrevHash, RowHash)
    VALUES (@waktu, @id_user, @id_comp_area, @kategori, @aksi, @tabel, @id_baris, @nilai_lama, @nilai_baru, @ip, @prev,
            dbo.fn_hash_log(@prev, @waktu, @id_user, @kategori, @aksi, @tabel, @id_baris, @nilai_lama, @nilai_baru, @ip));
    COMMIT TRANSACTION;
END
GO

CREATE OR ALTER TRIGGER dbo.TR_Log_AppendOnly ON dbo.Log INSTEAD OF UPDATE, DELETE AS
BEGIN
    RAISERROR('Log hanya boleh ditambah (tidak bisa diubah / dihapus).', 16, 1);
    ROLLBACK TRANSACTION;
END
GO

/* Baris pertama yang rantainya putus; kosong = utuh */
CREATE OR ALTER VIEW dbo.LogIntegrity AS
SELECT x.LogID, x.LogDate, x.Category, x.LogActionType,
       CASE WHEN x.RowHash <> x.CalcHash THEN 'ISI_BERUBAH' ELSE 'RANTAI_PUTUS' END AS Problem
FROM (SELECT l.LogID, l.LogDate, l.Category, l.LogActionType, l.PrevHash, l.RowHash,
             LAG(l.RowHash) OVER (ORDER BY l.LogID) AS ExpectedPrev,
             dbo.fn_hash_log(l.PrevHash, l.LogDate, l.CreateBy, l.Category, l.LogActionType, l.TableName, l.RowID,
                             l.OldValue, l.NewValue, l.IPAddress) AS CalcHash
      FROM dbo.Log l) x
WHERE x.RowHash <> x.CalcHash
   OR ISNULL(x.PrevHash, '') <> ISNULL(x.ExpectedPrev, '');
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
CREATE TABLE dbo.BlacklistDetection (
    DetectionID   BIGINT IDENTITY(1,1) PRIMARY KEY,
    DetectDate    DATETIME      NOT NULL CONSTRAINT DF_BlDetect_Date DEFAULT (GETDATE()),
    CompAreaID    BIGINT        NULL CONSTRAINT FK_BlDetect_Area REFERENCES dbo.CompanyArea (CompAreaID),
    UserID        BIGINT        NULL CONSTRAINT FK_BlDetect_User REFERENCES dbo.Users (UserID),
    IDVehicle     INT           NULL CONSTRAINT FK_BlDetect_Vehicle REFERENCES dbo.DetailVehicle (IDVehicle),
    NoVehicle     VARCHAR(15)   NULL,
    Source        VARCHAR(20)   NOT NULL,      -- SCAN_WAJAH, ABSENSI, TAMU, TAMU_MASUK, TIKET, TAMBAH_SUPIR, PENDAFTARAN, PLAT
    Action        VARCHAR(20)   NOT NULL CONSTRAINT CK_BlDetect_Action CHECK (Action IN ('DITOLAK', 'PERINGATAN', 'DILOLOSKAN')),
    FaceDistance  FLOAT         NULL,
    Description   NVARCHAR(300) NULL,
    TicketNumber  VARCHAR(50)   NULL,
    CreateBy      BIGINT        NULL CONSTRAINT FK_BlDetect_CreateBy REFERENCES dbo.Users (UserID),
    CONSTRAINT CK_BlDetect_Target CHECK (UserID IS NOT NULL OR IDVehicle IS NOT NULL)
);
CREATE INDEX IX_BlDetect_Area_Date ON dbo.BlacklistDetection (CompAreaID, DetectDate DESC);
CREATE INDEX IX_BlDetect_User ON dbo.BlacklistDetection (UserID, DetectDate) WHERE UserID IS NOT NULL;
CREATE INDEX IX_BlDetect_Vehicle ON dbo.BlacklistDetection (IDVehicle, DetectDate) WHERE IDVehicle IS NOT NULL;
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
CREATE OR ALTER TRIGGER dbo.TR_Users_BlacklistPermanen ON dbo.Users AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    -- Pencabutan (BlacklistID -> NULL) hanya dari jalur persetujuan (SESSION_CONTEXT cabut_blacklist = 1)
    IF UPDATE(BlacklistID) AND ISNULL(CAST(SESSION_CONTEXT(N'cabut_blacklist') AS INT), 0) <> 1
       AND EXISTS (SELECT 1 FROM inserted i JOIN deleted d ON d.UserID = i.UserID
                   WHERE d.BlacklistID IS NOT NULL AND i.BlacklistID IS NULL)
    BEGIN
        RAISERROR('Blacklist personel hanya bisa dicabut lewat persetujuan (menu Persetujuan).', 16, 1);
        ROLLBACK TRANSACTION;
    END
END
GO
CREATE OR ALTER TRIGGER dbo.TR_DetailVehicle_BlacklistPermanen ON dbo.DetailVehicle AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(BlacklistID) AND ISNULL(CAST(SESSION_CONTEXT(N'cabut_blacklist') AS INT), 0) <> 1
       AND EXISTS (SELECT 1 FROM inserted i JOIN deleted d ON d.IDVehicle = i.IDVehicle
                   WHERE d.BlacklistID IS NOT NULL AND i.BlacklistID IS NULL)
    BEGIN
        RAISERROR('Blacklist kendaraan hanya bisa dicabut lewat persetujuan (menu Persetujuan).', 16, 1);
        ROLLBACK TRANSACTION;
    END
END
GO
-- Salin wajah utama aktif ke Users.FaceEmbeddingData / UploadPath
CREATE OR ALTER TRIGGER dbo.TR_FaceRecog_Utama ON dbo.FaceRecog AFTER INSERT, UPDATE AS
BEGIN
    SET NOCOUNT ON;
    UPDATE u SET u.FaceEmbeddingData = f.FaceDet, u.UploadPath = f.PhotoPath
    FROM dbo.Users u
    JOIN (SELECT DISTINCT UserID FROM inserted) x ON x.UserID = u.UserID
    OUTER APPLY (SELECT TOP 1 FaceDet, PhotoPath FROM dbo.FaceRecog
                 WHERE UserID = u.UserID AND Active = 1 ORDER BY IsMain DESC, FaceID DESC) f;
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
INSERT INTO dbo.UserCategory (CategoryCode, CategoryName, RequireLicense, CanLogin, CodePrefix) VALUES
    ('DRIVER',   N'Driver',   1, 0, 'DRV'),
    ('SECURITY', N'Security', 0, 1, 'SEC'),
    ('EMPLOYEE', N'Karyawan', 0, 1, 'KRY'),
    ('TAMU',     N'Tamu',     0, 0, 'TMU'),
    ('BHL',      N'BHL',      0, 0, 'BHL');
INSERT INTO dbo.License (LicenseCode, LicenseType) VALUES
    ('A', N'SIM A'), ('B1', N'SIM B1'), ('B1_UMUM', N'SIM B1 Umum'), ('B2', N'SIM B2'), ('B2_UMUM', N'SIM B2 Umum');
INSERT INTO dbo.License (LicenseCode, LicenseType, Active) VALUES ('BELUM_DIISI', N'Belum dilengkapi', 0);
INSERT INTO dbo.VisitPurpose (PurposeName) VALUES
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
INSERT INTO dbo.WeightBridgeType (WeightTypeCode, WeightTypeName, IsPayment) VALUES
    ('PEMBELIAN', N'Pembelian', 1), ('PENJUALAN', N'Penjualan', 1), ('PENIMBANGAN_SAJA', N'Penimbangan Saja', 0);
INSERT INTO dbo.Status (StatusCode, StatusName, StatusColor, SortOrder) VALUES
    ('SECURITY_REGISTER', N'Registrasi Security', 'oranye', 1), ('SCAN_WAJAH', N'Scan Wajah', 'oranye', 2),
    ('TIMBANG_1', N'Timbang 1', 'biru', 3), ('INSPEKSI_PROSES', N'Inspeksi', 'ungu', 4),
    ('TIMBANG_2', N'Timbang 2', 'biru', 5), ('SELESAI', N'Selesai', 'hijau', 6),
    ('REJECTED', N'Ditolak', 'merah', 7), ('VOID', N'Dibatalkan', 'abu', 8);
INSERT INTO dbo.VehicleType (VehicleTypeCode, NameType) VALUES
    ('TRUK', N'Truk'), ('DUMP_TRUK', N'Dump Truk'), ('TANGKI', N'Truk Tangki'), ('PICKUP', N'Pick-up'), ('LAINNYA', N'Lainnya');
INSERT INTO dbo.Currency (CurrencyCode, CurrencyName, CurrencyRate) VALUES
    ('IDR', N'Rupiah Indonesia', 1), ('USD', N'U.S. Dollar', NULL), ('MYR', N'Ringgit Malaysia', NULL), ('EUR', N'Euro', NULL);
INSERT INTO dbo.SupplierType (TypeCode, NameType) VALUES ('CUSTOMER', N'Customer / Supplier'), ('PENGANGKUTAN', N'Pengangkutan');
INSERT INTO dbo.ProductType (ProductTypeCode, ProductTypeName) VALUES ('TBS', N'TBS'), ('PRODUK_PKS', N'Produk PKS');
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
INSERT INTO dbo.Users (UserID, UserName, Nama, CategoryCode, UserLevelID, UserDeptID, CompAreaID)
SELECT CAST(FORMAT(GETDATE(), 'yyMMdd') AS BIGINT) * 10000 + 1, 'admin', 'Super Admin', 'EMPLOYEE',
       (SELECT LevelDetID FROM dbo.LevelDetails WHERE LevelDetCode = 'ADMIN'), NULL,
       (SELECT MIN(CompAreaID) FROM dbo.CompanyArea);
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
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
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
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
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
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
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
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
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
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
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
CREATE OR ALTER TRIGGER dbo.TR_LogData_Supplier ON dbo.Supplier AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.SupplierID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.SupplierID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.SupplierID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.SupplierID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'Supplier', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_Product ON dbo.Product AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.ProductID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.ProductID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.ProductID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.ProductID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'Product', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_DetailVehicle ON dbo.DetailVehicle AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.IDVehicle AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.IDVehicle AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.IDVehicle AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.IDVehicle AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'DetailVehicle', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_VehicleType ON dbo.VehicleType AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.VehicleTypeID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.VehicleTypeID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.VehicleTypeID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.VehicleTypeID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'VehicleType', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_Contract ON dbo.Contract AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.ContractID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.ContractID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.ContractID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.ContractID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'Contract', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_DeliveryOrder ON dbo.DeliveryOrder AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.DeliveryOrderID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.DeliveryOrderID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.DeliveryOrderID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.DeliveryOrderID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'DeliveryOrder', @id_baris = @k,
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
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
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
CREATE OR ALTER TRIGGER dbo.TR_LogData_DailyPrice ON dbo.DailyPrice AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(CONVERT(VARCHAR(10), d.PriceDate, 23) AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(CONVERT(VARCHAR(10), i.PriceDate, 23) AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(CONVERT(VARCHAR(10), d.PriceDate, 23) AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(CONVERT(VARCHAR(10), i.PriceDate, 23) AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'DailyPrice', @id_baris = @k,
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
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
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
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
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
CREATE OR ALTER TRIGGER dbo.TR_LogData_Status ON dbo.Status AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.StatusCode AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.StatusCode AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.StatusCode AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.StatusCode AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'Status', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_UserCategory ON dbo.UserCategory AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.CategoryCode AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.CategoryCode AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.CategoryCode AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.CategoryCode AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'UserCategory', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_License ON dbo.License AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.LicenseID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.LicenseID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.LicenseID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.LicenseID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'License', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
CREATE OR ALTER TRIGGER dbo.TR_LogData_VisitPurpose ON dbo.VisitPurpose AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM inserted) AND NOT EXISTS (SELECT 1 FROM deleted) RETURN;
    DECLARE @kunci TABLE (k NVARCHAR(100) PRIMARY KEY);
    INSERT INTO @kunci (k) SELECT CAST(d.PurposeID AS NVARCHAR(100)) FROM deleted d UNION SELECT CAST(i.PurposeID AS NVARCHAR(100)) FROM inserted i;
    DECLARE @k NVARCHAR(100), @lama NVARCHAR(MAX), @baru NVARCHAR(MAX), @aksi VARCHAR(40),
            @id_user BIGINT = TRY_CAST(SESSION_CONTEXT(N'id_user') AS BIGINT), @ip VARCHAR(45) = CAST(SESSION_CONTEXT(N'ip') AS VARCHAR(45));
    DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT k FROM @kunci;
    OPEN c; FETCH NEXT FROM c INTO @k;
    WHILE @@FETCH_STATUS = 0
    BEGIN
        SET @lama = (SELECT * FROM deleted d WHERE CAST(d.PurposeID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @baru = (SELECT * FROM inserted i WHERE CAST(i.PurposeID AS NVARCHAR(100)) = @k FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES);
        SET @lama = JSON_MODIFY(@lama, '$.FaceEmbeddingData', NULL); SET @baru = JSON_MODIFY(@baru, '$.FaceEmbeddingData', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.LastLogin', NULL); SET @baru = JSON_MODIFY(@baru, '$.LastLogin', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.SessionVersion', NULL); SET @baru = JSON_MODIFY(@baru, '$.SessionVersion', NULL);
        SET @lama = JSON_MODIFY(@lama, '$.UpdateDate', NULL); SET @baru = JSON_MODIFY(@baru, '$.UpdateDate', NULL);
        IF ISNULL(@lama, N'') <> ISNULL(@baru, N'')
        BEGIN
            SET @aksi = CASE WHEN @lama IS NULL THEN 'DATA_TAMBAH' WHEN @baru IS NULL THEN 'DATA_HAPUS' ELSE 'DATA_UBAH' END;
            EXEC dbo.sp_catat_log @kategori = 'DATA', @aksi = @aksi, @tabel = 'VisitPurpose', @id_baris = @k,
                 @nilai_lama = @lama, @nilai_baru = @baru, @id_user = @id_user, @ip = @ip;
        END
        FETCH NEXT FROM c INTO @k;
    END
    CLOSE c; DEALLOCATE c;
END
GO
