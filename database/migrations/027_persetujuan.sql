SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Persetujuan dinamis (Admin › Persetujuan) + notifikasi bersasaran + hapus (cabut) blacklist.
   - persetujuan_langkah : penyetuju per jenis pengajuan, 1-3 langkah, tiap langkah satu jabatan. Penyetuju harus
                           berada di PT yang sama dengan pengajuan (user kantor pusat: PT yang dikelolanya).
                           Jenis tanpa langkah = langsung berlaku tanpa persetujuan.
   - pengajuan           : satu permintaan (mis. tambah / hapus blacklist), isi permintaan disimpan sebagai JSON.
   - pengajuan_riwayat   : jejak diajukan / disetujui / ditolak per langkah.
   - notifikasi          : sasaran baru: jabatan di PT tertentu (id_level + id_company) atau satu user (id_user).
   - blacklist           : dicabut_at / dicabut_oleh / alasan_cabut. Trigger blacklist permanen tetap menolak
                           pencabutan, kecuali dari jalur persetujuan (SESSION_CONTEXT cabut_blacklist = 1).
   - menu PERSETUJUAN    : halaman Persetujuan, boleh dilihat semua jabatan non-admin.
   Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.persetujuan_langkah', 'U') IS NULL
CREATE TABLE dbo.persetujuan_langkah (
    jenis     VARCHAR(40) NOT NULL,
    urutan    TINYINT     NOT NULL CONSTRAINT CK_SetujuLangkah_Urutan CHECK (urutan BETWEEN 1 AND 3),
    id_level  INT         NOT NULL CONSTRAINT FK_SetujuLangkah_Level REFERENCES dbo.level (id_level),
    CONSTRAINT PK_PersetujuanLangkah PRIMARY KEY (jenis, urutan)
);
GO

IF OBJECT_ID('dbo.pengajuan', 'U') IS NULL
CREATE TABLE dbo.pengajuan (
    id_pengajuan   INT IDENTITY(1,1) PRIMARY KEY,
    jenis          VARCHAR(40)    NOT NULL,
    status         VARCHAR(20)    NOT NULL CONSTRAINT DF_Pengajuan_Status DEFAULT ('MENUNGGU')
                   CONSTRAINT CK_Pengajuan_Status CHECK (status IN ('MENUNGGU', 'DISETUJUI', 'DITOLAK', 'DIBATALKAN')),
    langkah        TINYINT        NOT NULL CONSTRAINT DF_Pengajuan_Langkah DEFAULT (1),
    total_langkah  TINYINT        NOT NULL,
    id_company     INT            NOT NULL CONSTRAINT FK_Pengajuan_Company REFERENCES dbo.company (id_company),
    id_comp_area   INT            NOT NULL CONSTRAINT FK_Pengajuan_Area REFERENCES dbo.comp_area (id_comp_area),
    target         VARCHAR(50)    NOT NULL,          -- mis. PERSONEL:12, KENDARAAN:7, BLACKLIST:3 (cek dobel)
    judul          NVARCHAR(200)  NOT NULL,
    alasan         NVARCHAR(500)  NULL,
    data           NVARCHAR(MAX)  NULL CONSTRAINT CK_Pengajuan_Json CHECK (data IS NULL OR ISJSON(data) = 1),
    diajukan_oleh  INT            NOT NULL CONSTRAINT FK_Pengajuan_User REFERENCES dbo.akun (id_user),
    created_at     DATETIME       NOT NULL CONSTRAINT DF_Pengajuan_Dibuat DEFAULT (GETDATE()),
    selesai_at     DATETIME       NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Pengajuan_Status' AND object_id = OBJECT_ID('dbo.pengajuan'))
    CREATE INDEX IX_Pengajuan_Status ON dbo.pengajuan (status, jenis, id_company);
GO

IF OBJECT_ID('dbo.pengajuan_riwayat', 'U') IS NULL
CREATE TABLE dbo.pengajuan_riwayat (
    id_riwayat    INT IDENTITY(1,1) PRIMARY KEY,
    id_pengajuan  INT           NOT NULL CONSTRAINT FK_PengRiwayat_Pengajuan REFERENCES dbo.pengajuan (id_pengajuan),
    langkah       TINYINT       NOT NULL,           -- 0 = diajukan
    aksi          VARCHAR(20)   NOT NULL CONSTRAINT CK_PengRiwayat_Aksi CHECK (aksi IN ('DIAJUKAN', 'DISETUJUI', 'DITOLAK', 'DIBATALKAN')),
    id_level      INT           NULL CONSTRAINT FK_PengRiwayat_Level REFERENCES dbo.level (id_level),
    id_user       INT           NOT NULL CONSTRAINT FK_PengRiwayat_User REFERENCES dbo.akun (id_user),
    catatan       NVARCHAR(500) NULL,
    waktu         DATETIME      NOT NULL CONSTRAINT DF_PengRiwayat_Waktu DEFAULT (GETDATE())
);
GO

IF COL_LENGTH('dbo.notifikasi', 'id_level') IS NULL
    ALTER TABLE dbo.notifikasi ADD
        id_level    INT NULL CONSTRAINT FK_Notif_Level REFERENCES dbo.level (id_level),
        id_company  INT NULL CONSTRAINT FK_Notif_Company REFERENCES dbo.company (id_company),
        id_user     INT NULL CONSTRAINT FK_Notif_User REFERENCES dbo.akun (id_user);
GO

IF COL_LENGTH('dbo.blacklist', 'dicabut_at') IS NULL
    ALTER TABLE dbo.blacklist ADD
        dicabut_at     DATETIME      NULL,
        dicabut_oleh   INT           NULL CONSTRAINT FK_Blacklist_Pencabut REFERENCES dbo.akun (id_user),
        alasan_cabut   NVARCHAR(500) NULL;
GO

CREATE OR ALTER TRIGGER dbo.TR_Personel_BlacklistPermanen ON dbo.personel AFTER UPDATE AS
BEGIN
    SET NOCOUNT ON;
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
    IF UPDATE(is_blacklisted) AND ISNULL(CAST(SESSION_CONTEXT(N'cabut_blacklist') AS INT), 0) <> 1
       AND EXISTS (SELECT 1 FROM inserted i JOIN deleted d ON d.id_kendaraan = i.id_kendaraan
                   WHERE d.is_blacklisted = 1 AND i.is_blacklisted = 0)
    BEGIN
        RAISERROR('Blacklist kendaraan hanya bisa dicabut lewat persetujuan (menu Persetujuan).', 16, 1);
        ROLLBACK TRANSACTION;
    END
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.menu WHERE kode = 'PERSETUJUAN')
    INSERT INTO dbo.menu (kode, nama, url, ikon, urutan) VALUES ('PERSETUJUAN', N'Persetujuan', '/persetujuan', 'fa-list-check', 47);
GO
IF COL_LENGTH('dbo.level_akses', 'bisa_lihat') IS NOT NULL
    EXEC (N'
    INSERT INTO dbo.level_akses (id_level, id_menu, bisa_lihat, bisa_tambah, bisa_ubah, bisa_hapus)
    SELECT l.id_level, m.id_menu, 1, 0, 0, 0 FROM dbo.level l JOIN dbo.menu m ON m.kode = ''PERSETUJUAN''
    WHERE l.is_admin = 0 AND NOT EXISTS (SELECT 1 FROM dbo.level_akses a WHERE a.id_level = l.id_level AND a.id_menu = m.id_menu);');
GO
