/* =====================================================================
   SCHEMA Sistem Timbangan Sawit (Weighbridge + Face Recognition) - ERD v3 final
   Membuat DATABASE BARU dari nol: semua tabel, view, prosedur, trigger, dan data awal
   (setara schema awal + migrasi 001-022). Diuji di SQL Server 2022; minimal SQL Server 2016 SP1
   (CREATE OR ALTER, JSON, HASHBYTES pada NVARCHAR(MAX)).

   Database yang SUDAH berjalan TIDAK memakai file ini: cukup jalankan migrasi yang belum
   (database/migrations/), atau pindahkan dengan backup / restore (docs/DOKUMENTASI.md).

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

/* =========================== ORGANISASI & HAK AKSES (migrasi 008) =========================== */
CREATE TABLE dbo.company (
    id_company  INT IDENTITY(1,1) PRIMARY KEY,
    kode        VARCHAR(10)   NOT NULL CONSTRAINT UX_Company_Kode UNIQUE,
    nama        NVARCHAR(100) NOT NULL,
    is_active   BIT NOT NULL CONSTRAINT DF_Company_Aktif DEFAULT (1),
    created_at  DATETIME NOT NULL CONSTRAINT DF_Company_Created DEFAULT (GETDATE())
);
CREATE TABLE dbo.comp_area (
    id_comp_area INT IDENTITY(1,1) PRIMARY KEY,
    id_company   INT NOT NULL CONSTRAINT FK_Area_Company REFERENCES dbo.company (id_company),
    kode         VARCHAR(10)   NOT NULL CONSTRAINT UX_Area_Kode UNIQUE,
    nama         NVARCHAR(100) NOT NULL,
    alamat       NVARCHAR(255) NULL,
    is_active    BIT NOT NULL CONSTRAINT DF_Area_Aktif DEFAULT (1),
    created_at   DATETIME NOT NULL CONSTRAINT DF_Area_Created DEFAULT (GETDATE())
);
CREATE TABLE dbo.department (
    id_department INT IDENTITY(1,1) PRIMARY KEY,
    nama          NVARCHAR(100) NOT NULL CONSTRAINT UX_Department_Nama UNIQUE,
    keterangan    NVARCHAR(255) NULL,
    is_active     BIT NOT NULL CONSTRAINT DF_Department_Aktif DEFAULT (1)
);
CREATE TABLE dbo.level (
    id_level      INT IDENTITY(1,1) PRIMARY KEY,
    kode          VARCHAR(30)   NOT NULL CONSTRAINT UX_Level_Kode UNIQUE,
    nama          NVARCHAR(100) NOT NULL,
    is_admin      BIT NOT NULL CONSTRAINT DF_Level_Admin DEFAULT (0),
    halaman_awal  VARCHAR(100)  NOT NULL CONSTRAINT DF_Level_Awal DEFAULT ('/weighbridge'),
    keterangan    NVARCHAR(255) NULL,
    is_active     BIT NOT NULL CONSTRAINT DF_Level_Aktif DEFAULT (1)
);
CREATE TABLE dbo.menu (
    id_menu    INT IDENTITY(1,1) PRIMARY KEY,
    kode       VARCHAR(40)   NOT NULL CONSTRAINT UX_Menu_Kode UNIQUE,
    nama       NVARCHAR(100) NOT NULL,
    url        VARCHAR(200)  NULL,
    ikon       VARCHAR(40)   NULL,
    id_parent  INT NULL CONSTRAINT FK_Menu_Parent REFERENCES dbo.menu (id_menu),
    urutan     INT NOT NULL CONSTRAINT DF_Menu_Urutan DEFAULT (0),
    is_active  BIT NOT NULL CONSTRAINT DF_Menu_Aktif DEFAULT (1)
);
CREATE TABLE dbo.level_akses (
    id_level     INT NOT NULL CONSTRAINT FK_LevelAkses_Level REFERENCES dbo.level (id_level),
    id_menu      INT NOT NULL CONSTRAINT FK_LevelAkses_Menu REFERENCES dbo.menu (id_menu),
    bisa_tambah  BIT NOT NULL CONSTRAINT DF_LevelAkses_Tambah DEFAULT (0),
    bisa_ubah    BIT NOT NULL CONSTRAINT DF_LevelAkses_Ubah DEFAULT (0),
    bisa_hapus   BIT NOT NULL CONSTRAINT DF_LevelAkses_Hapus DEFAULT (0),
    CONSTRAINT PK_LevelAkses PRIMARY KEY (id_level, id_menu)
);
GO
/* Isi awal company, area, department, level, menu, level_akses ada di bagian DATA AWAL (paling bawah). */

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
    nik                  VARCHAR(20)  NOT NULL CONSTRAINT UX_Personel_Nik UNIQUE,
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
CREATE UNIQUE INDEX UX_Personel_Kode ON dbo.personel (kode_personel) WHERE kode_personel IS NOT NULL;
CREATE INDEX IX_Personel_Aktif_Kategori ON dbo.personel (is_active, kategori) INCLUDE (kode_personel, nama_personel);
GO

-- Akun login (migrasi 016: dulu users). id_personel = tautan opsional ke data personel / wajah petugas
CREATE TABLE dbo.akun (
    id_user      INT IDENTITY(1,1) PRIMARY KEY,
    nama         VARCHAR(100) NOT NULL,
    username     VARCHAR(50)  NOT NULL CONSTRAINT UX_Users_Username UNIQUE,
    password     VARCHAR(255) NOT NULL,                         -- hash pbkdf2
    id_level      INT NOT NULL CONSTRAINT FK_Users_Level REFERENCES dbo.level (id_level),
    id_department INT NOT NULL CONSTRAINT FK_Users_Department REFERENCES dbo.department (id_department),
    id_comp_area  INT NOT NULL CONSTRAINT FK_Users_Area REFERENCES dbo.comp_area (id_comp_area),
    id_personel  INT NULL CONSTRAINT FK_Users_Personel REFERENCES dbo.personel (id_personel),
    is_active    BIT NOT NULL CONSTRAINT DF_Users_Aktif DEFAULT (1),
    last_login   DATETIME NULL,
    sesi_versi   INT NOT NULL CONSTRAINT DF_Users_SesiVersi DEFAULT (0),   -- naik = semua sesi user dicabut
    password_changed_at DATETIME NULL,                          -- NULL = wajib ganti password saat login
    created_at   DATETIME NOT NULL CONSTRAINT DF_Users_Created DEFAULT (GETDATE()),
    updated_at   DATETIME NOT NULL CONSTRAINT DF_Users_Modified DEFAULT (GETDATE())
);
CREATE UNIQUE INDEX UX_Users_Personel ON dbo.akun (id_personel) WHERE id_personel IS NOT NULL;
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
    created_by      INT NULL CONSTRAINT FK_PersonelSim_User REFERENCES dbo.akun (id_user),
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
    created_by   INT NULL CONSTRAINT FK_PersonelWajah_User REFERENCES dbo.akun (id_user),
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
    id_comp_area     INT NOT NULL CONSTRAINT FK_Kunjungan_Area REFERENCES dbo.comp_area (id_comp_area),
    foto_masuk_path  VARCHAR(255)  NULL,      -- snapshot wajah saat datang
    waktu_masuk      DATETIME NOT NULL CONSTRAINT DF_Kunjungan_Masuk DEFAULT (GETDATE()),
    waktu_keluar     DATETIME NULL,           -- NULL = tamu masih di dalam
    dicatat_oleh     INT NOT NULL CONSTRAINT FK_Kunjungan_User REFERENCES dbo.akun (id_user),
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
    created_by  INT NOT NULL CONSTRAINT FK_Dokumen_User REFERENCES dbo.akun (id_user),
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
    created_at     DATETIME NOT NULL CONSTRAINT DF_Supplier_Created DEFAULT (GETDATE())
);
GO
-- Peran mitra (migrasi 013, nama tabel migrasi 016): satu mitra boleh customer sekaligus pengangkutan
CREATE TABLE dbo.mitra_peran (
    id_supplier  INT NOT NULL CONSTRAINT FK_SupPeran_Supplier REFERENCES dbo.mitra (id_supplier),
    peran        VARCHAR(20) NOT NULL CONSTRAINT CK_SupPeran_Peran CHECK (peran IN ('CUSTOMER', 'PENGANGKUTAN')),
    CONSTRAINT PK_SupplierPeran PRIMARY KEY (id_supplier, peran)
);
GO

-- Alur tahap tiket (migrasi 012): urutan tahap per alur, dipakai produk & mill
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
-- Mill per area: tiket baru memakai mill aktif di area akun Security sesuai alur produk
CREATE TABLE dbo.mill (
    id_mill       INT IDENTITY(1,1) PRIMARY KEY,
    id_comp_area  INT NOT NULL CONSTRAINT FK_Mill_Area REFERENCES dbo.comp_area (id_comp_area),
    kode          VARCHAR(10)   NOT NULL,
    nama          NVARCHAR(100) NOT NULL,
    id_alur       INT NOT NULL CONSTRAINT FK_Mill_Alur REFERENCES dbo.alur (id_alur),
    is_active     BIT NOT NULL CONSTRAINT DF_Mill_Aktif DEFAULT (1),
    CONSTRAINT UX_Mill_AreaKode UNIQUE (id_comp_area, kode)
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
    is_active           BIT NOT NULL CONSTRAINT DF_JenisKendaraan_Aktif DEFAULT (1)
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
    created_by    INT NULL CONSTRAINT FK_KD_User REFERENCES dbo.akun (id_user),
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
    created_by       INT NULL CONSTRAINT FK_KK_User REFERENCES dbo.akun (id_user),
    created_at       DATETIME NOT NULL CONSTRAINT DF_KK_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_KK_Jenis CHECK (jenis_transaksi IS NULL OR jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_KK_Periode CHECK (tanggal_selesai IS NULL OR tanggal_selesai >= tanggal_mulai)
);
CREATE INDEX IX_KK_Kendaraan ON dbo.kontrak_kendaraan (id_kendaraan, is_active);
CREATE INDEX IX_KK_Kendaraan_Supplier ON dbo.kontrak_kendaraan (id_kendaraan, id_supplier, is_active);
GO

-- Kontrak & DO (migrasi 013, diisi HO): 1 kontrak = 1 produk = 1 DO; 1 DO boleh beberapa pengangkut
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
    created_by       INT NULL CONSTRAINT FK_Kontrak_User REFERENCES dbo.akun (id_user),
    created_at       DATETIME NOT NULL CONSTRAINT DF_Kontrak_Created DEFAULT (GETDATE()),
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
    created_by      INT NULL CONSTRAINT FK_DO_User REFERENCES dbo.akun (id_user),
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
    updated_by    INT NULL CONSTRAINT FK_Harga_User REFERENCES dbo.akun (id_user),
    updated_at    DATETIME NOT NULL CONSTRAINT DF_Harga_Updated DEFAULT (GETDATE()),
    CONSTRAINT CK_Harga_Oer CHECK (oer_cpo BETWEEN 0 AND 100)
);
GO

/* =========================== TRANSAKSI =========================== */

-- Jembatan timbang per area (migrasi 011)
CREATE TABLE dbo.jembatan_timbang (
    id_jembatan   INT IDENTITY(1,1) PRIMARY KEY,
    id_comp_area  INT NOT NULL CONSTRAINT FK_Jembatan_Area REFERENCES dbo.comp_area (id_comp_area),
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
    security_id        INT NOT NULL CONSTRAINT FK_Trx_Security REFERENCES dbo.akun (id_user),
    id_jembatan        INT NULL CONSTRAINT FK_Trx_Jembatan REFERENCES dbo.jembatan_timbang (id_jembatan),   -- jembatan timbang masuk
    id_mill            INT NULL CONSTRAINT FK_Trx_Mill REFERENCES dbo.mill (id_mill),                       -- alur tahap tiket
    id_do              INT NULL CONSTRAINT FK_Trx_DO REFERENCES dbo.delivery_order (id_do),
    cara_angkut        VARCHAR(15) NOT NULL,                        -- PENGIRIM / PENERIMA / PIHAK_KETIGA (id_pengangkutan)
    no_tiket_induk     VARCHAR(50) NULL CONSTRAINT FK_Trx_Induk REFERENCES dbo.transaksi (no_tiket),   -- tiket split kelebihan DO (migrasi 022)
    berat_split_kg     DECIMAL(14, 2) NULL,                         -- netto tiket split (tanpa penimbangan sendiri)
    created_at         DATETIME NOT NULL CONSTRAINT DF_Trx_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_Trx_Jenis CHECK (jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_Trx_CaraAngkut CHECK ((cara_angkut = 'PIHAK_KETIGA' AND id_pengangkutan IS NOT NULL)
                                        OR (cara_angkut IN ('PENGIRIM', 'PENERIMA') AND id_pengangkutan IS NULL)),
    CONSTRAINT CK_Trx_Status CHECK (status_alur IN ('SECURITY_REGISTER', 'SCAN_WAJAH', 'TIMBANG_1', 'INSPEKSI_PROSES',
                                                    'TIMBANG_2', 'SELESAI', 'REJECTED', 'VOID'))
);
CREATE INDEX IX_Trx_Status_Created ON dbo.transaksi (status_alur, created_at DESC) INCLUDE (id_kendaraan, id_supplier, id_driver);
CREATE INDEX IX_Trx_Kendaraan_Created ON dbo.transaksi (id_kendaraan, created_at DESC);
CREATE INDEX IX_Trx_Supplier_Created ON dbo.transaksi (id_supplier, created_at DESC);
CREATE INDEX IX_Trx_Driver_Created ON dbo.transaksi (id_driver, created_at DESC);
GO

-- Void (Admin) / reject (Lab), migrasi 010
CREATE TABLE dbo.pembatalan_tiket (
    no_tiket    VARCHAR(50)   NOT NULL PRIMARY KEY CONSTRAINT FK_Batal_Transaksi REFERENCES dbo.transaksi (no_tiket),
    jenis       VARCHAR(10)   NOT NULL CONSTRAINT CK_Batal_Jenis CHECK (jenis IN ('VOID', 'REJECT')),
    alasan      NVARCHAR(255) NOT NULL,
    id_dokumen  INT NULL CONSTRAINT FK_Batal_Dokumen REFERENCES dbo.dokumen (id_dokumen),   -- berita acara, boleh menyusul
    oleh        INT NULL CONSTRAINT FK_Batal_User REFERENCES dbo.akun (id_user),           -- NULL hanya data lama
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
    operator     INT NULL CONSTRAINT FK_Penimbangan_Operator REFERENCES dbo.akun (id_user),   -- NULL hanya data lama
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
    diajukan_oleh    INT NULL CONSTRAINT FK_Lebih_Aju REFERENCES dbo.akun (id_user),
    diajukan_at      DATETIME NULL,
    ditetapkan_oleh  INT NULL CONSTRAINT FK_Lebih_Tetap REFERENCES dbo.akun (id_user),
    ditetapkan_at    DATETIME NULL,
    alasan_kembali   NVARCHAR(255)  NULL,
    id_comp_area     INT NULL CONSTRAINT FK_Lebih_Area REFERENCES dbo.comp_area (id_comp_area),
    created_at       DATETIME NOT NULL CONSTRAINT DF_Lebih_Created DEFAULT (GETDATE()),
    CONSTRAINT UX_Lebih_Tiket UNIQUE (no_tiket),
    CONSTRAINT CK_Lebih_Status CHECK (status IN ('MENUNGGU', 'DIAJUKAN', 'SELESAI', 'DIKEMBALIKAN')),
    CONSTRAINT CK_Lebih_Kg CHECK (kelebihan_kg > 0)
);
-- Notifikasi lonceng (migrasi 022): sasaran = level yang punya hak menu kode_menu
CREATE TABLE dbo.notifikasi (
    id_notifikasi  INT IDENTITY(1,1) PRIMARY KEY,
    kode_menu      VARCHAR(40)    NOT NULL,
    id_comp_area   INT NULL CONSTRAINT FK_Notif_Area REFERENCES dbo.comp_area (id_comp_area),
    judul          NVARCHAR(150)  NOT NULL,
    isi            NVARCHAR(500)  NULL,
    tautan         VARCHAR(200)   NULL,
    waktu          DATETIME NOT NULL CONSTRAINT DF_Notif_Waktu DEFAULT (GETDATE())
);
CREATE INDEX IX_Notif_Waktu ON dbo.notifikasi (waktu DESC);
CREATE TABLE dbo.notifikasi_baca (
    id_notifikasi  INT NOT NULL CONSTRAINT FK_NotifBaca_Notif REFERENCES dbo.notifikasi (id_notifikasi),
    id_user        INT NOT NULL CONSTRAINT FK_NotifBaca_User REFERENCES dbo.akun (id_user),
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
    operator_sortasi_id     INT NULL CONSTRAINT FK_Sortasi_Operator REFERENCES dbo.akun (id_user),
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
    operator_lab_id    INT NULL CONSTRAINT FK_Lab_Operator REFERENCES dbo.akun (id_user),
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
    created_by            INT NOT NULL CONSTRAINT FK_Blacklist_User REFERENCES dbo.akun (id_user),
    created_at            DATETIME NOT NULL CONSTRAINT DF_Blacklist_Created DEFAULT (GETDATE()),
    no_plat_terkait          VARCHAR(15) NULL,                  -- plat saat itu (supir / tamu)
    id_customer_terkait      INT NULL CONSTRAINT FK_Blacklist_Customer REFERENCES dbo.mitra (id_supplier),
    id_pengangkutan_terkait  INT NULL CONSTRAINT FK_Blacklist_Angkut REFERENCES dbo.mitra (id_supplier),
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
    id_comp_area     INT NOT NULL CONSTRAINT FK_Jadwal_Area REFERENCES dbo.comp_area (id_comp_area),
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

CREATE TABLE dbo.pengaturan (
    kunci       VARCHAR(50)  PRIMARY KEY,
    nilai       VARCHAR(200) NOT NULL,
    updated_by  INT NULL CONSTRAINT FK_Pengaturan_User REFERENCES dbo.akun (id_user),
    updated_at  DATETIME NOT NULL CONSTRAINT DF_Pengaturan_Updated DEFAULT (GETDATE())
);
GO

-- Pengaturan operasional per area (migrasi 014), menimpa nilai global di tabel pengaturan
CREATE TABLE dbo.pengaturan_area (
    id_comp_area  INT NOT NULL CONSTRAINT FK_PengArea_Area REFERENCES dbo.comp_area (id_comp_area),
    kunci         VARCHAR(50)  NOT NULL,
    nilai         VARCHAR(200) NOT NULL,
    updated_by    INT NULL CONSTRAINT FK_PengArea_User REFERENCES dbo.akun (id_user),
    updated_at    DATETIME NOT NULL CONSTRAINT DF_PengArea_Updated DEFAULT (GETDATE()),
    CONSTRAINT PK_PengaturanArea PRIMARY KEY (id_comp_area, kunci)
);
GO

CREATE TABLE dbo.perangkat_kiosk (
    id_pos      VARCHAR(30)  PRIMARY KEY,
    nama        VARCHAR(100) NOT NULL,
    lokasi      VARCHAR(100) NULL,
    token_hash  CHAR(64)     NOT NULL,
    id_comp_area INT NOT NULL CONSTRAINT FK_Kiosk_Area REFERENCES dbo.comp_area (id_comp_area),
    is_active   BIT NOT NULL CONSTRAINT DF_Kiosk_Aktif DEFAULT (1),
    created_at  DATETIME NOT NULL CONSTRAINT DF_Kiosk_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_Kiosk_Id CHECK (id_pos NOT LIKE '%[^A-Z0-9_-]%')
);
GO

/* Satu log untuk semua aktivitas (migrasi 015): JSON + rantai hash, hanya INSERT lewat sp_catat_log */
CREATE TABLE dbo.log_aktivitas (
    id_log         BIGINT IDENTITY(1,1) PRIMARY KEY,
    waktu          DATETIME2(3) NOT NULL,
    id_user        INT NULL CONSTRAINT FK_Log_User REFERENCES dbo.akun (id_user),     -- NULL = kiosk / sistem
    id_comp_area   INT NULL CONSTRAINT FK_Log_Area REFERENCES dbo.comp_area (id_comp_area),
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
    @hash_sebelum CHAR(64), @waktu DATETIME2(3), @id_user INT, @kategori VARCHAR(20), @aksi VARCHAR(40),
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
    @nilai_lama NVARCHAR(MAX) = NULL, @nilai_baru NVARCHAR(MAX) = NULL, @id_user INT = NULL,
    @id_comp_area INT = NULL, @ip VARCHAR(45) = NULL, @waktu DATETIME2(3) = NULL
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
        SET @id_comp_area = (SELECT id_comp_area FROM dbo.akun WHERE id_user = @id_user);
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


/* Sesi login dari semua PC (Admin > Sesi Aktif, paksa keluar, 1 user 1 perangkat) - migrasi 007 */
CREATE TABLE dbo.sesi_login (
    sid             VARCHAR(24)  NOT NULL PRIMARY KEY,
    user_id         INT          NOT NULL CONSTRAINT FK_SesiLogin_User REFERENCES dbo.akun (id_user),
    ip              VARCHAR(45)  NULL,
    agen            VARCHAR(200) NULL,
    login_at        DATETIME     NOT NULL DEFAULT GETDATE(),
    terakhir_aktif  DATETIME     NOT NULL DEFAULT GETDATE(),
    berakhir_at     DATETIME     NULL,
    alasan          VARCHAR(20)  NULL
);
CREATE INDEX IX_SesiLogin_User ON dbo.sesi_login (user_id, berakhir_at);
CREATE INDEX IX_SesiLogin_Aktif ON dbo.sesi_login (berakhir_at, terakhir_aktif);
GO

/* =========================== TRIGGER: blacklist permanen =========================== */
CREATE OR ALTER TRIGGER dbo.TR_Personel_BlacklistPermanen ON dbo.personel AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(is_blacklisted) AND EXISTS (SELECT 1 FROM inserted i JOIN deleted d ON d.id_personel = i.id_personel
                                          WHERE d.is_blacklisted = 1 AND i.is_blacklisted = 0)
    BEGIN
        RAISERROR('Blacklist personel bersifat permanen dan tidak bisa dicabut.', 16, 1);
        ROLLBACK TRANSACTION;
    END
END
GO
CREATE OR ALTER TRIGGER dbo.TR_Kendaraan_BlacklistPermanen ON dbo.kendaraan AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE(is_blacklisted) AND EXISTS (SELECT 1 FROM inserted i JOIN deleted d ON d.id_kendaraan = i.id_kendaraan
                                          WHERE d.is_blacklisted = 1 AND i.is_blacklisted = 0)
    BEGIN
        RAISERROR('Blacklist kendaraan bersifat permanen dan tidak bisa dicabut.', 16, 1);
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
    ('TAMU',     N'Tamu',     0, 0, 'TMU');
INSERT INTO dbo.jenis_sim (kode, nama) VALUES
    ('A', N'SIM A'), ('B1', N'SIM B1'), ('B1_UMUM', N'SIM B1 Umum'), ('B2', N'SIM B2'), ('B2_UMUM', N'SIM B2 Umum');
INSERT INTO dbo.jenis_sim (kode, nama, is_active) VALUES ('BELUM_DIISI', N'Belum dilengkapi', 0);
INSERT INTO dbo.keperluan_kunjungan (nama) VALUES
    (N'Rapat / Bertemu'), (N'Pengiriman Barang'), (N'Perbaikan / Servis'), (N'Audit / Inspeksi'), (N'Lainnya');
GO
-- Organisasi, level (pengganti role), menu, dan hak akses awal (sama dengan migrasi 008)
INSERT INTO dbo.company (kode, nama) VALUES ('PT', N'Perusahaan (ubah di Admin › Organisasi)');
INSERT INTO dbo.comp_area (id_company, kode, nama)
SELECT id_company, 'SITE1', N'Site Utama (ubah di Admin › Organisasi)' FROM dbo.company WHERE kode = 'PT';
INSERT INTO dbo.department (nama) VALUES (N'Umum'), (N'Security'), (N'Timbangan'), (N'QC / Lab'), (N'Head Office');
INSERT INTO dbo.level (kode, nama, is_admin, halaman_awal) VALUES
    ('ADMIN',            N'Super Admin',      1, '/admin'),
    ('HO',               N'Head Office',      0, '/dashboard'),
    ('SECURITY',         N'Security',         0, '/weighbridge?tab=security'),
    ('OPERATOR_TIMBANG', N'Operator Timbang', 0, '/weighbridge?tab=timbangan'),
    ('SORTASI',          N'Sortasi',          0, '/weighbridge?tab=sortasi'),
    ('LAB',              N'Laboratorium',     0, '/weighbridge?tab=lab');
INSERT INTO dbo.menu (kode, nama, url, ikon, urutan) VALUES
    ('DASHBOARD',        N'Dashboard',        '/dashboard',            'fa-chart-line',    10),
    ('LIST',             N'List',             '/weighbridge?view=list', 'fa-list',         20),
    ('FORM',             N'Form',             '/weighbridge?view=form', 'fa-file-pen',     30),
    ('FACE_RECOGNITION', N'Face Recognition', '/face-recognition',     'fa-face-smile',    40),
    ('KONTRAK_DO',       N'Kontrak & DO',     '/kontrak',              'fa-file-contract', 50),
    ('BLACKLIST',        N'Blacklist',        '/blacklist',            'fa-ban',           45),
    ('KUNJUNGAN',        N'Tamu',             '/tamu',                 'fa-id-card',       46),
    ('KELEBIHAN_DO',     N'Kelebihan DO',     '/kelebihan-do',         'fa-scale-unbalanced', 55),
    ('MASTER',           N'Data Master',      '/master',               'fa-database',      60);
INSERT INTO dbo.menu (kode, nama, id_parent, urutan)
SELECT v.kode, v.nama, p.id_menu, v.urutan
FROM (VALUES ('FORM_SECURITY',    N'Form › Security',          'FORM', 1),
             ('FORM_TIMBANGAN',   N'Form › Timbangan',         'FORM', 2),
             ('FORM_SORTASI',     N'Form › Sortasi',           'FORM', 3),
             ('FORM_LAB',         N'Form › Laboratorium',      'FORM', 4),
             ('ABSENSI',          N'Face Recognition › Absensi', 'FACE_RECOGNITION', 1),
             ('PERSONEL',         N'Face Recognition › Personel', 'FACE_RECOGNITION', 2),
             ('AUDIT_LOG',        N'Face Recognition › Audit Log', 'FACE_RECOGNITION', 4),
             ('MASTER_DRIVER',    N'Data Master › Driver',     'MASTER', 1),
             ('MASTER_KENDARAAN', N'Data Master › Kendaraan',  'MASTER', 2),
             ('MASTER_MITRA',     N'Data Master › Mitra',      'MASTER', 3),
             ('MASTER_PRODUK',    N'Data Master › Produk',     'MASTER', 4)) v (kode, nama, induk, urutan)
JOIN dbo.menu p ON p.kode = v.induk;
INSERT INTO dbo.level_akses (id_level, id_menu, bisa_tambah, bisa_ubah, bisa_hapus)
SELECT l.id_level, m.id_menu, v.t, v.u, v.h
FROM (VALUES ('HO',               'DASHBOARD',        0, 1, 0),
             ('HO',               'PERSONEL',         1, 1, 1),
             ('HO',               'BLACKLIST',        1, 0, 0),
             ('HO',               'KONTRAK_DO',       1, 1, 1),
             ('HO',               'MASTER_DRIVER',    1, 1, 1),
             ('HO',               'MASTER_KENDARAAN', 1, 1, 0),
             ('HO',               'KELEBIHAN_DO',     0, 1, 0),
             ('OPERATOR_TIMBANG', 'KELEBIHAN_DO',     1, 0, 0),
             ('HO',               'MASTER_MITRA',     1, 1, 0),
             ('HO',               'MASTER_PRODUK',    1, 1, 0),
             ('SECURITY',         'FORM_SECURITY',    1, 1, 0),
             ('SECURITY',         'MASTER_DRIVER',    1, 1, 1),
             ('SECURITY',         'MASTER_KENDARAAN', 1, 1, 0),
             ('OPERATOR_TIMBANG', 'FORM_TIMBANGAN',   1, 0, 0),
             ('SORTASI',          'FORM_SORTASI',     1, 0, 0),
             ('LAB',              'FORM_LAB',         1, 1, 0)) v (lv, mn, t, u, h)
JOIN dbo.level l ON l.kode = v.lv
JOIN dbo.menu m ON m.kode = v.mn;
-- Jembatan timbang awal (migrasi 011)
INSERT INTO dbo.jembatan_timbang (id_comp_area, kode, nama, port)
SELECT MIN(id_comp_area), 'JT-1', N'Jembatan Timbang 1', 'COM3' FROM dbo.comp_area;
-- Jadwal kerja awal per area (migrasi 014)
INSERT INTO dbo.jadwal_kerja (id_comp_area, hari, nama_hari, jam_masuk, jam_pulang, is_libur)
SELECT a.id_comp_area, v.hari, v.nama, v.masuk, v.pulang, v.libur
FROM dbo.comp_area a
CROSS JOIN (VALUES (1, 'Senin', '08:00', '17:00', 0), (2, 'Selasa', '08:00', '17:00', 0), (3, 'Rabu', '08:00', '17:00', 0),
                   (4, 'Kamis', '08:00', '17:00', 0), (5, 'Jumat', '08:00', '17:00', 0), (6, 'Sabtu', '08:00', '12:00', 0),
                   (7, 'Minggu', NULL, NULL, 1)) v (hari, nama, masuk, pulang, libur);
-- Jenis kendaraan (migrasi 014)
INSERT INTO dbo.jenis_kendaraan (kode, nama) VALUES
    ('TRUK', N'Truk'), ('DUMP_TRUK', N'Dump Truk'), ('TANGKI', N'Truk Tangki'), ('PICKUP', N'Pick-up'), ('LAINNYA', N'Lainnya');
-- Alur tahap & mill per area (migrasi 012)
INSERT INTO dbo.tahap (kode, nama, urutan) VALUES
    ('SECURITY', N'Security', 1), ('TIMBANG_1', N'Timbang Masuk', 2), ('SORTASI', N'Sortasi', 3),
    ('LAB', N'Laboratorium', 4), ('TIMBANG_2', N'Timbang Keluar', 5);
INSERT INTO dbo.alur (kode, nama) VALUES
    ('TBS', N'TBS: timbang - sortasi - timbang'),
    ('PKS', N'Produk PKS: timbang - lab - timbang'),
    ('TIMBANG_SAJA', N'Penimbangan saja (sekali timbang)');
INSERT INTO dbo.alur_tahap (id_alur, urutan, kode_tahap)
SELECT a.id_alur, v.urutan, v.tahap
FROM (VALUES ('TBS', 1, 'SECURITY'), ('TBS', 2, 'TIMBANG_1'), ('TBS', 3, 'SORTASI'), ('TBS', 4, 'TIMBANG_2'),
             ('PKS', 1, 'SECURITY'), ('PKS', 2, 'TIMBANG_1'), ('PKS', 3, 'LAB'), ('PKS', 4, 'TIMBANG_2'),
             ('TIMBANG_SAJA', 1, 'SECURITY'), ('TIMBANG_SAJA', 2, 'TIMBANG_1')) v (alur, urutan, tahap)
JOIN dbo.alur a ON a.kode = v.alur;
INSERT INTO dbo.mill (id_comp_area, kode, nama, id_alur)
SELECT ar.id_comp_area, v.kode, v.nama, al.id_alur
FROM dbo.comp_area ar
CROSS JOIN (VALUES ('TBS', N'Penerimaan TBS', 'TBS'), ('PKS', N'Produk PKS', 'PKS'),
                   ('TS', N'Penimbangan Saja', 'TIMBANG_SAJA')) v (kode, nama, alur)
JOIN dbo.alur al ON al.kode = v.alur;
-- Hak menu Tamu (KUNJUNGAN) untuk Security
INSERT INTO dbo.level_akses (id_level, id_menu, bisa_tambah, bisa_ubah, bisa_hapus)
SELECT l.id_level, m.id_menu, 1, 1, 0
FROM dbo.level l CROSS JOIN dbo.menu m
WHERE l.kode = 'SECURITY' AND m.kode = 'KUNJUNGAN';
GO
-- Akun super admin pertama: admin / admin12345. password_changed_at NULL -> wajib buat password baru saat login pertama
INSERT INTO dbo.akun (nama, username, password, id_level, id_department, id_comp_area)
SELECT 'Super Admin', 'admin',
       'pbkdf2:sha256:1000000$zkbmkQ6HN9jaUBF5$c6b4177f0ac7789efa50b5d512d6b1ae6bd86963b81d2ba9b9208d3349801419',
       (SELECT id_level FROM dbo.level WHERE kode = 'ADMIN'), (SELECT id_department FROM dbo.department WHERE nama = N'Umum'),
       (SELECT MIN(id_comp_area) FROM dbo.comp_area);
GO
