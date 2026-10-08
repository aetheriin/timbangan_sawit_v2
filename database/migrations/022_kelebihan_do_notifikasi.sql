SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   DO melebihi kuota (kontrak.qty_kg): saat Timbang 2 total netto DO melewati kuota, kelebihannya menjadi
   tiket baru (no tiket asli + '-S1', truk & supir yang sama, tanpa timbang ulang) dan tercatat di
   tabel kelebihan_do. Krani mengisi No. DO baru dari Ascend, KTU / HO menetapkan.
   Notifikasi (lonceng top bar) untuk level yang punya hak menu KELEBIHAN_DO.
   Aman dijalankan ulang.
   ===================================================================================== */
IF COL_LENGTH('dbo.transaksi', 'no_tiket_induk') IS NULL
    ALTER TABLE dbo.transaksi ADD
        no_tiket_induk  VARCHAR(50)    NULL CONSTRAINT FK_Trx_Induk REFERENCES dbo.transaksi (no_tiket),
        berat_split_kg  DECIMAL(14, 2) NULL;      -- netto tiket split (kelebihan DO), tanpa penimbangan sendiri
GO

IF OBJECT_ID('dbo.kelebihan_do', 'U') IS NULL
CREATE TABLE dbo.kelebihan_do (
    id_kelebihan     INT IDENTITY(1,1) PRIMARY KEY,
    no_tiket         VARCHAR(50)    NOT NULL CONSTRAINT FK_Lebih_Tiket REFERENCES dbo.transaksi (no_tiket),
    no_tiket_split   VARCHAR(50)    NOT NULL CONSTRAINT FK_Lebih_Split REFERENCES dbo.transaksi (no_tiket),
    id_do            INT            NOT NULL CONSTRAINT FK_Lebih_DO REFERENCES dbo.delivery_order (id_do),
    kuota_kg         DECIMAL(14, 2) NOT NULL,
    realisasi_kg     DECIMAL(14, 2) NOT NULL,     -- total netto DO termasuk tiket ini
    netto_tiket_kg   DECIMAL(14, 2) NOT NULL,
    kelebihan_kg     DECIMAL(14, 2) NOT NULL,
    no_do_baru       VARCHAR(50)    NULL,         -- dari Ascend, diisi krani
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
GO

IF OBJECT_ID('dbo.notifikasi', 'U') IS NULL
CREATE TABLE dbo.notifikasi (
    id_notifikasi  INT IDENTITY(1,1) PRIMARY KEY,
    kode_menu      VARCHAR(40)    NOT NULL,       -- sasaran: level yang punya hak menu ini
    id_comp_area   INT NULL CONSTRAINT FK_Notif_Area REFERENCES dbo.comp_area (id_comp_area),
    judul          NVARCHAR(150)  NOT NULL,
    isi            NVARCHAR(500)  NULL,
    tautan         VARCHAR(200)   NULL,
    waktu          DATETIME NOT NULL CONSTRAINT DF_Notif_Waktu DEFAULT (GETDATE())
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Notif_Waktu')
    CREATE INDEX IX_Notif_Waktu ON dbo.notifikasi (waktu DESC);
GO
IF OBJECT_ID('dbo.notifikasi_baca', 'U') IS NULL
CREATE TABLE dbo.notifikasi_baca (
    id_notifikasi  INT NOT NULL CONSTRAINT FK_NotifBaca_Notif REFERENCES dbo.notifikasi (id_notifikasi),
    id_user        INT NOT NULL CONSTRAINT FK_NotifBaca_User REFERENCES dbo.akun (id_user),
    dibaca_at      DATETIME NOT NULL CONSTRAINT DF_NotifBaca_Waktu DEFAULT (GETDATE()),
    CONSTRAINT PK_NotifBaca PRIMARY KEY (id_notifikasi, id_user)
);
GO

/* Menu Kelebihan DO: krani timbangan = tambah (isi No. DO baru), KTU / HO = ubah (tetapkan / kembalikan) */
INSERT INTO dbo.menu (kode, nama, url, ikon, urutan)
SELECT 'KELEBIHAN_DO', N'Kelebihan DO', '/kelebihan-do', 'fa-scale-unbalanced', 55
WHERE NOT EXISTS (SELECT 1 FROM dbo.menu WHERE kode = 'KELEBIHAN_DO');
GO
INSERT INTO dbo.level_akses (id_level, id_menu, bisa_tambah, bisa_ubah, bisa_hapus)
SELECT l.id_level, m.id_menu, v.t, v.u, 0
FROM (VALUES ('OPERATOR_TIMBANG', 1, 0), ('HO', 0, 1)) v (lv, t, u)
JOIN dbo.level l ON l.kode = v.lv
JOIN dbo.menu m ON m.kode = 'KELEBIHAN_DO'
WHERE NOT EXISTS (SELECT 1 FROM dbo.level_akses a WHERE a.id_level = l.id_level AND a.id_menu = m.id_menu);
GO

SELECT kode, nama, url FROM dbo.menu WHERE kode = 'KELEBIHAN_DO';
GO
