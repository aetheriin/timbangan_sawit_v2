/* =====================================================================
   SCHEMA LENGKAP Sistem Timbangan Sawit (Weighbridge + Face Recognition)
   Untuk membuat DATABASE BARU dari nol = schema.sql (main) + migrasi 001-006 dalam satu file.
   Database yang SUDAH ada cukup menjalankan migrasi 001-006 berurutan.

   Cara pakai (SSMS): ganti nama database di 2 baris di bawah, lalu Execute (F5).
   Urutan tabel mengikuti ketergantungan foreign key. Diagram: docs/ERD.md
   ===================================================================== */
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
IF DB_ID('DbSistemTimbangan') IS NULL CREATE DATABASE DbSistemTimbangan;
GO
USE [DbSistemTimbangan]
GO

/* =========================== MASTER =========================== */

-- Personel: supir, security, karyawan HO (wajah untuk face recognition)
CREATE TABLE dbo.personel (
    id_personel          INT IDENTITY(1,1) PRIMARY KEY,
    kode_personel        VARCHAR(20)  NULL,                     -- diisi HO, mis. PRGBS-001
    nik                  VARCHAR(20)  NOT NULL CONSTRAINT UX_Personel_Nik UNIQUE,
    nama_personel        VARCHAR(100) NOT NULL,
    no_sim               VARCHAR(30)  NULL,
    kategori             VARCHAR(20)  NOT NULL CONSTRAINT DF_Personel_Kategori DEFAULT ('DRIVER'),
    face_embedding_data  VARBINARY(MAX) NULL,
    foto_path            VARCHAR(255) NULL,
    foto_sumber          VARCHAR(10)  NULL,
    is_updated           BIT NOT NULL CONSTRAINT DF_Personel_Updated DEFAULT (0),
    current_hash         VARCHAR(64)  NULL,
    is_blacklisted       BIT NOT NULL CONSTRAINT DF_Personel_Blacklist DEFAULT (0),
    is_active            BIT NOT NULL CONSTRAINT DF_Personel_Aktif DEFAULT (1),
    created_at           DATETIME NOT NULL CONSTRAINT DF_Personel_Created DEFAULT (GETDATE()),
    updated_at           DATETIME NOT NULL CONSTRAINT DF_Personel_Modified DEFAULT (GETDATE()),
    CONSTRAINT CK_Personel_Kategori   CHECK (kategori IN ('DRIVER', 'SECURITY', 'EMPLOYEE')),
    CONSTRAINT CK_Personel_SimDriver  CHECK (kategori <> 'DRIVER' OR no_sim IS NOT NULL),
    CONSTRAINT CK_Personel_FotoSumber CHECK (foto_sumber IS NULL OR foto_sumber IN ('UPLOAD', 'KAMERA'))
);
CREATE UNIQUE INDEX UX_Personel_Kode ON dbo.personel (kode_personel) WHERE kode_personel IS NOT NULL;
CREATE INDEX IX_Personel_Aktif_Kategori ON dbo.personel (is_active, kategori) INCLUDE (kode_personel, nama_personel);
GO

-- User aplikasi (login). id_personel = tautan opsional ke data wajah petugas
CREATE TABLE dbo.users (
    id_user      INT IDENTITY(1,1) PRIMARY KEY,
    nama         VARCHAR(100) NOT NULL,
    username     VARCHAR(50)  NOT NULL CONSTRAINT UX_Users_Username UNIQUE,
    password     VARCHAR(255) NOT NULL,                         -- hash pbkdf2
    role         VARCHAR(30)  NOT NULL,
    id_personel  INT NULL CONSTRAINT FK_Users_Personel REFERENCES dbo.personel (id_personel),
    is_active    BIT NOT NULL CONSTRAINT DF_Users_Aktif DEFAULT (1),
    last_login   DATETIME NULL,
    sesi_versi   INT NOT NULL CONSTRAINT DF_Users_SesiVersi DEFAULT (0),   -- naik = semua sesi user dicabut
    password_changed_at DATETIME NULL,                          -- NULL = wajib ganti password saat login
    created_at   DATETIME NOT NULL CONSTRAINT DF_Users_Created DEFAULT (GETDATE()),
    updated_at   DATETIME NOT NULL CONSTRAINT DF_Users_Modified DEFAULT (GETDATE()),
    CONSTRAINT CK_Users_Role CHECK (role IN ('ADMIN', 'HO', 'SECURITY', 'OPERATOR_TIMBANG', 'SORTASI', 'LAB'))
);
CREATE UNIQUE INDEX UX_Users_Personel ON dbo.users (id_personel) WHERE id_personel IS NOT NULL;
GO

-- Customer (membeli / menjual) & pengangkutan pihak ketiga
CREATE TABLE dbo.supplier (
    id_supplier    INT IDENTITY(1,1) PRIMARY KEY,
    kode_supplier  VARCHAR(20)  NOT NULL CONSTRAINT UX_Supplier_Kode UNIQUE,
    nama_supplier  VARCHAR(100) NOT NULL,
    tipe           VARCHAR(30)  NOT NULL,
    is_active      BIT NOT NULL CONSTRAINT DF_Supplier_Aktif DEFAULT (1),
    created_at     DATETIME NOT NULL CONSTRAINT DF_Supplier_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_Supplier_Tipe CHECK (tipe IN ('CUSTOMER', 'PENGANGKUTAN'))
);
GO

CREATE TABLE dbo.produk (
    id_produk    INT IDENTITY(1,1) PRIMARY KEY,
    nama_produk  VARCHAR(100) NOT NULL,
    kategori     VARCHAR(20)  NOT NULL,
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

CREATE TABLE dbo.kendaraan (
    id_kendaraan    INT IDENTITY(1,1) PRIMARY KEY,
    no_plat         VARCHAR(15) NOT NULL CONSTRAINT UX_Kendaraan_Plat UNIQUE,
    no_stnk         VARCHAR(50) NULL,
    is_blacklisted  BIT NOT NULL CONSTRAINT DF_Kendaraan_Blacklist DEFAULT (0),
    is_active       BIT NOT NULL CONSTRAINT DF_Kendaraan_Aktif DEFAULT (1),
    created_at      DATETIME NOT NULL CONSTRAINT DF_Kendaraan_Created DEFAULT (GETDATE())
);
GO

-- Supir terdaftar per truk (supir utama disarankan saat Create Ticket)
CREATE TABLE dbo.kendaraan_driver (
    id_kendaraan_driver INT IDENTITY(1,1) PRIMARY KEY,
    id_kendaraan  INT NOT NULL CONSTRAINT FK_KD_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    id_driver     INT NOT NULL CONSTRAINT FK_KD_Driver REFERENCES dbo.personel (id_personel),
    is_utama      BIT NOT NULL CONSTRAINT DF_KD_Utama DEFAULT (0),
    is_active     BIT NOT NULL CONSTRAINT DF_KD_Active DEFAULT (1),
    created_by    INT NULL CONSTRAINT FK_KD_User REFERENCES dbo.users (id_user),
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
    id_supplier      INT NOT NULL CONSTRAINT FK_KK_Supplier REFERENCES dbo.supplier (id_supplier),
    id_produk        INT NULL CONSTRAINT FK_KK_Produk REFERENCES dbo.produk (id_produk),
    jenis_transaksi  VARCHAR(20) NULL,
    tanggal_mulai    DATE NOT NULL,
    tanggal_selesai  DATE NULL,
    is_active        BIT NOT NULL CONSTRAINT DF_KK_Active DEFAULT (1),
    keterangan       VARCHAR(255) NULL,
    created_by       INT NULL CONSTRAINT FK_KK_User REFERENCES dbo.users (id_user),
    created_at       DATETIME NOT NULL CONSTRAINT DF_KK_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_KK_Jenis CHECK (jenis_transaksi IS NULL OR jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_KK_Periode CHECK (tanggal_selesai IS NULL OR tanggal_selesai >= tanggal_mulai)
);
CREATE INDEX IX_KK_Kendaraan ON dbo.kontrak_kendaraan (id_kendaraan, is_active);
CREATE INDEX IX_KK_Kendaraan_Supplier ON dbo.kontrak_kendaraan (id_kendaraan, id_supplier, is_active);
GO

-- DO (diisi HO, menu Kontrak & DO). Form Security: ketik No DO -> data transaksi terisi
CREATE TABLE dbo.delivery_order (
    id_do           INT IDENTITY(1,1) PRIMARY KEY,
    no_do           VARCHAR(50) NOT NULL CONSTRAINT UX_DO_No UNIQUE,
    no_kontrak      VARCHAR(50) NOT NULL,
    jenis_transaksi VARCHAR(20) NOT NULL,
    id_customer     INT NOT NULL CONSTRAINT FK_DO_Customer REFERENCES dbo.supplier (id_supplier),
    id_produk       INT NOT NULL CONSTRAINT FK_DO_Produk REFERENCES dbo.produk (id_produk),
    id_pengangkutan INT NULL CONSTRAINT FK_DO_Angkut REFERENCES dbo.supplier (id_supplier),   -- NULL = kendaraan customer sendiri
    tanggal_do      DATE NOT NULL CONSTRAINT DF_DO_Tanggal DEFAULT (CAST(GETDATE() AS DATE)),
    berlaku_sampai  DATE NULL,
    keterangan      VARCHAR(200) NULL,
    is_active       BIT NOT NULL CONSTRAINT DF_DO_Aktif DEFAULT (1),
    created_by      INT NULL CONSTRAINT FK_DO_User REFERENCES dbo.users (id_user),
    created_at      DATETIME NOT NULL CONSTRAINT DF_DO_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_DO_Jenis CHECK (jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA'))
);
CREATE INDEX IX_DO_Kontrak ON dbo.delivery_order (no_kontrak);
GO

CREATE TABLE dbo.standar_mutu_log (
    id_log        INT IDENTITY(1,1) PRIMARY KEY,
    id_produk     INT NOT NULL CONSTRAINT FK_StdLog_Produk REFERENCES dbo.produk (id_produk),
    maks_ffa      FLOAT NOT NULL,
    maks_air      FLOAT NOT NULL,
    maks_kotoran  FLOAT NOT NULL,
    updated_by    INT NULL CONSTRAINT FK_StdLog_User REFERENCES dbo.users (id_user),
    updated_at    DATETIME NOT NULL CONSTRAINT DF_StdLog_Waktu DEFAULT (GETDATE())
);
CREATE INDEX IX_StdLog_Waktu ON dbo.standar_mutu_log (updated_at DESC);
GO

-- Dashboard: harga per tanggal (diisi HO)
CREATE TABLE dbo.harga_harian (
    tanggal       DATE PRIMARY KEY,
    harga_cpo     DECIMAL(12,2) NOT NULL,
    harga_kernel  DECIMAL(12,2) NOT NULL,
    oer_cpo       DECIMAL(5,2)  NOT NULL,
    biaya_olah    DECIMAL(12,2) NOT NULL,
    updated_by    INT NULL CONSTRAINT FK_Harga_User REFERENCES dbo.users (id_user),
    updated_at    DATETIME NOT NULL CONSTRAINT DF_Harga_Updated DEFAULT (GETDATE()),
    CONSTRAINT CK_Harga_Oer CHECK (oer_cpo BETWEEN 0 AND 100)
);
GO

/* =========================== TRANSAKSI =========================== */

CREATE TABLE dbo.transaksi (
    no_tiket           VARCHAR(50) PRIMARY KEY,
    jenis_transaksi    VARCHAR(20) NOT NULL,
    id_supplier        INT NOT NULL CONSTRAINT FK_Trx_Supplier REFERENCES dbo.supplier (id_supplier),     -- customer (dari DO)
    id_produk          INT NOT NULL CONSTRAINT FK_Trx_Produk REFERENCES dbo.produk (id_produk),
    id_kendaraan       INT NOT NULL CONSTRAINT FK_Trx_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    id_driver          INT NOT NULL CONSTRAINT FK_Trx_Driver REFERENCES dbo.personel (id_personel),
    id_pengangkutan    INT NULL CONSTRAINT FK_Trx_Angkut REFERENCES dbo.supplier (id_supplier),
    id_kontrak         INT NULL CONSTRAINT FK_Trx_Kontrak REFERENCES dbo.kontrak_kendaraan (id_kontrak),
    no_do              VARCHAR(50) NULL,
    status_alur        VARCHAR(30) NOT NULL CONSTRAINT DF_Trx_Status DEFAULT ('SECURITY_REGISTER'),
    is_qr_active       BIT NOT NULL CONSTRAINT DF_Trx_QrAktif DEFAULT (1),
    qr_expired_at      DATETIME NOT NULL,
    qr_reprint_count   INT NOT NULL CONSTRAINT DF_Trx_Reprint DEFAULT (0),
    alasan_reject      VARCHAR(255) NULL,
    rejected_by        INT NULL CONSTRAINT FK_Trx_RejectBy REFERENCES dbo.users (id_user),
    alasan_void        VARCHAR(255) NULL,
    void_by            INT NULL CONSTRAINT FK_Trx_VoidBy REFERENCES dbo.users (id_user),
    void_at            DATETIME NULL,
    is_driver_changed  BIT NOT NULL CONSTRAINT DF_Trx_DriverChanged DEFAULT (0),
    prev_driver_id     INT NULL CONSTRAINT FK_Trx_PrevDriver REFERENCES dbo.personel (id_personel),
    driver_photo_path  VARCHAR(255) NULL,
    security_id        INT NOT NULL CONSTRAINT FK_Trx_Security REFERENCES dbo.users (id_user),
    created_at         DATETIME NOT NULL CONSTRAINT DF_Trx_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_Trx_Jenis CHECK (jenis_transaksi IN ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')),
    CONSTRAINT CK_Trx_Status CHECK (status_alur IN ('SECURITY_REGISTER', 'SCAN_WAJAH', 'TIMBANG_1', 'INSPEKSI_PROSES',
                                                    'TIMBANG_2', 'SELESAI', 'REJECTED', 'VOID'))
);
CREATE INDEX IX_Trx_Status_Created ON dbo.transaksi (status_alur, created_at DESC) INCLUDE (id_kendaraan, id_supplier, id_driver);
CREATE INDEX IX_Trx_Kendaraan_Created ON dbo.transaksi (id_kendaraan, created_at DESC);
CREATE INDEX IX_Trx_Supplier_Created ON dbo.transaksi (id_supplier, created_at DESC);
CREATE INDEX IX_Trx_Driver_Created ON dbo.transaksi (id_driver, created_at DESC);
GO

CREATE TABLE dbo.timbangan (
    id_timbangan            INT IDENTITY(1,1) PRIMARY KEY,
    no_tiket                VARCHAR(50) NOT NULL CONSTRAINT UX_Timbangan_Tiket UNIQUE
                            CONSTRAINT FK_Timbangan_Trx REFERENCES dbo.transaksi (no_tiket),
    berat_bruto             FLOAT NULL,
    waktu_bruto             DATETIME NULL,
    berat_tara              FLOAT NULL,
    waktu_tara              DATETIME NULL,
    berat_netto             FLOAT NULL,
    hash_keamanan           VARCHAR(64) NULL,
    operator_timbang_id     INT NULL CONSTRAINT FK_Timbangan_Operator REFERENCES dbo.users (id_user),
    is_checklist_validated  BIT NOT NULL CONSTRAINT DF_Timbangan_Checklist DEFAULT (0)
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
    operator_sortasi_id     INT NULL CONSTRAINT FK_Sortasi_Operator REFERENCES dbo.users (id_user),
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
    no_dokumen_coa     VARCHAR(50) NULL,
    operator_lab_id    INT NULL CONSTRAINT FK_Lab_Operator REFERENCES dbo.users (id_user),
    waktu_pemeriksaan  DATETIME NULL,
    CONSTRAINT CK_Lab_Keputusan CHECK (keputusan IS NULL OR keputusan IN ('APPROVE', 'REJECT'))
);
GO

CREATE TABLE dbo.timeline_monitoring (
    id_timeline   INT IDENTITY(1,1) PRIMARY KEY,
    no_tiket      VARCHAR(50) NOT NULL CONSTRAINT FK_Timeline_Trx REFERENCES dbo.transaksi (no_tiket),
    stage         VARCHAR(30) NOT NULL,
    [timestamp]   DATETIME NOT NULL CONSTRAINT DF_Timeline_Waktu DEFAULT (GETDATE()),
    processed_by  INT NOT NULL CONSTRAINT FK_Timeline_User REFERENCES dbo.users (id_user)
);
CREATE INDEX IX_Timeline_Tiket ON dbo.timeline_monitoring (no_tiket);
GO

/* =========================== FACE RECOGNITION =========================== */

CREATE TABLE dbo.personel_audit_logs (
    id_log              INT IDENTITY(1,1) PRIMARY KEY,
    id_personel         INT NOT NULL CONSTRAINT FK_PersonelAudit_Personel REFERENCES dbo.personel (id_personel),
    aksi                VARCHAR(10) NOT NULL CONSTRAINT DF_PersonelAudit_Aksi DEFAULT ('UPDATE'),
    kode_personel_lama  VARCHAR(20) NULL,
    kode_personel_baru  VARCHAR(20) NULL,
    nik_lama            VARCHAR(20) NULL,
    nik_baru            VARCHAR(20) NULL,
    nama_lama           VARCHAR(100) NULL,
    nama_baru           VARCHAR(100) NULL,
    no_sim_lama         VARCHAR(30) NULL,
    no_sim_baru         VARCHAR(30) NULL,
    hash_audit          VARCHAR(64) NOT NULL,
    updated_by          INT NOT NULL CONSTRAINT FK_PersonelAudit_User REFERENCES dbo.users (id_user),
    updated_at          DATETIME NOT NULL CONSTRAINT DF_PersonelAudit_Waktu DEFAULT (GETDATE()),
    CONSTRAINT CK_PersonelAudit_Aksi CHECK (aksi IN ('TAMBAH', 'UPDATE', 'HAPUS'))
);
CREATE INDEX IX_PersonelAudit_Updated ON dbo.personel_audit_logs (updated_at DESC);
GO

CREATE TABLE dbo.blacklist (
    id_blacklist          INT IDENTITY(1,1) PRIMARY KEY,
    tipe_entitas          VARCHAR(20)  NOT NULL,
    id_personel           INT NULL CONSTRAINT FK_Blacklist_Personel REFERENCES dbo.personel (id_personel),
    id_kendaraan          INT NULL CONSTRAINT FK_Blacklist_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    no_surat_blacklist    VARCHAR(50)  NOT NULL,
    alasan_blacklist      VARCHAR(500) NOT NULL,
    file_surat_blacklist  VARCHAR(255) NULL,
    tgl_blacklist         DATE NOT NULL,
    created_by            INT NOT NULL CONSTRAINT FK_Blacklist_User REFERENCES dbo.users (id_user),
    created_at            DATETIME NOT NULL CONSTRAINT DF_Blacklist_Created DEFAULT (GETDATE()),
    no_plat_terkait          VARCHAR(15) NULL,                  -- plat saat itu (supir / tamu)
    id_customer_terkait      INT NULL CONSTRAINT FK_Blacklist_Customer REFERENCES dbo.supplier (id_supplier),
    id_pengangkutan_terkait  INT NULL CONSTRAINT FK_Blacklist_Angkut REFERENCES dbo.supplier (id_supplier),
    CONSTRAINT CK_Blacklist_Tipe CHECK (tipe_entitas IN ('PERSONEL', 'KENDARAAN')),
    CONSTRAINT CK_Blacklist_Target CHECK (
        (tipe_entitas = 'PERSONEL'  AND id_personel IS NOT NULL AND id_kendaraan IS NULL) OR
        (tipe_entitas = 'KENDARAAN' AND id_kendaraan IS NOT NULL AND id_personel IS NULL))
);
CREATE INDEX IX_Blacklist_Personel  ON dbo.blacklist (id_personel)  WHERE id_personel IS NOT NULL;
CREATE INDEX IX_Blacklist_Kendaraan ON dbo.blacklist (id_kendaraan) WHERE id_kendaraan IS NOT NULL;
CREATE INDEX IX_Blacklist_Tgl ON dbo.blacklist (tgl_blacklist DESC);
GO

CREATE TABLE dbo.security_audit_logs (
    id_log       INT IDENTITY(1,1) PRIMARY KEY,
    user_id      INT NOT NULL CONSTRAINT FK_SecAudit_User REFERENCES dbo.users (id_user),
    action_type  VARCHAR(30) NOT NULL,
    no_tiket     VARCHAR(50) NULL CONSTRAINT FK_SecAudit_Trx REFERENCES dbo.transaksi (no_tiket),
    details      NVARCHAR(MAX) NULL,
    ip_address   VARCHAR(45) NULL,
    created_at   DATETIME NOT NULL CONSTRAINT DF_SecAudit_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_SecAudit_Action CHECK (action_type IN ('TRY_SCAN_BLACKLIST', 'OVERRIDE_DRIVER', 'MANUAL_INPUT')),
    CONSTRAINT CK_SecAudit_Json CHECK (details IS NULL OR ISJSON(details) = 1)
);
CREATE INDEX IX_SecAudit_User_Waktu ON dbo.security_audit_logs (user_id, created_at);
CREATE INDEX IX_SecAudit_Created ON dbo.security_audit_logs (created_at DESC);
GO

CREATE TABLE dbo.jadwal_kerja (
    hari             TINYINT PRIMARY KEY,                       -- 1 = Senin ... 7 = Minggu
    nama_hari        VARCHAR(10) NOT NULL,
    jam_masuk        TIME(0) NULL,
    jam_pulang       TIME(0) NULL,
    is_libur         BIT NOT NULL CONSTRAINT DF_Jadwal_Libur DEFAULT (0),
    toleransi_menit  INT NOT NULL CONSTRAINT DF_Jadwal_Toleransi DEFAULT (0),
    CONSTRAINT CK_Jadwal_Hari CHECK (hari BETWEEN 1 AND 7),
    CONSTRAINT CK_Jadwal_Jam CHECK (is_libur = 1 OR (jam_masuk IS NOT NULL AND jam_pulang IS NOT NULL AND jam_pulang > jam_masuk))
);
INSERT INTO dbo.jadwal_kerja (hari, nama_hari, jam_masuk, jam_pulang, is_libur) VALUES
    (1, 'Senin', '08:00', '17:00', 0), (2, 'Selasa', '08:00', '17:00', 0), (3, 'Rabu', '08:00', '17:00', 0),
    (4, 'Kamis', '08:00', '17:00', 0), (5, 'Jumat', '08:00', '17:00', 0), (6, 'Sabtu', '08:00', '12:00', 0),
    (7, 'Minggu', NULL, NULL, 1);
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
    updated_by  INT NULL CONSTRAINT FK_Pengaturan_User REFERENCES dbo.users (id_user),
    updated_at  DATETIME NOT NULL CONSTRAINT DF_Pengaturan_Updated DEFAULT (GETDATE())
);
GO

CREATE TABLE dbo.perangkat_kiosk (
    id_pos      VARCHAR(30)  PRIMARY KEY,
    nama        VARCHAR(100) NOT NULL,
    lokasi      VARCHAR(100) NULL,
    token_hash  CHAR(64)     NOT NULL,
    is_active   BIT NOT NULL CONSTRAINT DF_Kiosk_Aktif DEFAULT (1),
    created_at  DATETIME NOT NULL CONSTRAINT DF_Kiosk_Created DEFAULT (GETDATE()),
    CONSTRAINT CK_Kiosk_Id CHECK (id_pos NOT LIKE '%[^A-Z0-9_-]%')
);
GO

CREATE TABLE dbo.admin_audit_logs (
    id_log      BIGINT IDENTITY(1,1) PRIMARY KEY,
    user_id     INT NOT NULL CONSTRAINT FK_AdminAudit_User REFERENCES dbo.users (id_user),
    aksi        VARCHAR(40)   NOT NULL,
    target      VARCHAR(100)  NULL,
    detail      NVARCHAR(500) NULL,
    ip_address  VARCHAR(45)   NULL,
    created_at  DATETIME NOT NULL CONSTRAINT DF_AdminAudit_Created DEFAULT (GETDATE())
);
CREATE INDEX IX_AdminAudit_Created ON dbo.admin_audit_logs (created_at DESC);
GO

/* Sesi login dari semua PC (Admin > Sesi Aktif, paksa keluar, 1 user 1 perangkat) - migrasi 007 */
CREATE TABLE dbo.sesi_login (
    sid             VARCHAR(24)  NOT NULL PRIMARY KEY,
    user_id         INT          NOT NULL CONSTRAINT FK_SesiLogin_User REFERENCES dbo.users (id_user),
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
-- Akun super admin pertama: admin / admin12345. password_changed_at NULL -> wajib buat password baru saat login pertama
INSERT INTO dbo.users (nama, username, password, role) VALUES ('Super Admin', 'admin',
    'pbkdf2:sha256:1000000$zkbmkQ6HN9jaUBF5$c6b4177f0ac7789efa50b5d512d6b1ae6bd86963b81d2ba9b9208d3349801419', 'ADMIN');
GO
