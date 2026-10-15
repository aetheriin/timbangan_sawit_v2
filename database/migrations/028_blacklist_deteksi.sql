SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Log Validasi Blacklist (menu Blacklist › Log Validasi).
   Satu baris per kejadian orang / kendaraan blacklist terdeteksi: scan wajah Form Security, absensi, tamu,
   tambah supir, pendaftaran personel, cek plat di info bar, atau tiket yang tetap dibuat.
   Dipakai untuk: jam datang, berapa kali mencoba scan hari itu, dan kunjungan ke berapa di site tersebut.
   Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.blacklist_deteksi', 'U') IS NULL
CREATE TABLE dbo.blacklist_deteksi (
    id_deteksi    BIGINT IDENTITY(1,1) PRIMARY KEY,
    waktu         DATETIME      NOT NULL CONSTRAINT DF_BlDeteksi_Waktu DEFAULT (GETDATE()),
    id_comp_area  INT           NULL CONSTRAINT FK_BlDeteksi_Area REFERENCES dbo.comp_area (id_comp_area),
    id_personel   INT           NULL CONSTRAINT FK_BlDeteksi_Personel REFERENCES dbo.personel (id_personel),
    id_kendaraan  INT           NULL CONSTRAINT FK_BlDeteksi_Kendaraan REFERENCES dbo.kendaraan (id_kendaraan),
    no_plat       VARCHAR(15)   NULL,
    sumber        VARCHAR(20)   NOT NULL,      -- SCAN_WAJAH, ABSENSI, TAMU, TAMU_MASUK, TIKET, TAMBAH_SUPIR, PENDAFTARAN, PLAT
    tindakan      VARCHAR(20)   NOT NULL CONSTRAINT CK_BlDeteksi_Tindakan CHECK (tindakan IN ('DITOLAK', 'PERINGATAN', 'DILOLOSKAN')),
    jarak_wajah   FLOAT         NULL,          -- jarak embedding (kecil = makin mirip)
    keterangan    NVARCHAR(300) NULL,
    no_tiket      VARCHAR(50)   NULL,
    id_user       INT           NULL CONSTRAINT FK_BlDeteksi_User REFERENCES dbo.akun (id_user),
    CONSTRAINT CK_BlDeteksi_Target CHECK (id_personel IS NOT NULL OR id_kendaraan IS NOT NULL)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_BlDeteksi_Area_Waktu' AND object_id = OBJECT_ID('dbo.blacklist_deteksi'))
    CREATE INDEX IX_BlDeteksi_Area_Waktu ON dbo.blacklist_deteksi (id_comp_area, waktu DESC);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_BlDeteksi_Personel' AND object_id = OBJECT_ID('dbo.blacklist_deteksi'))
    CREATE INDEX IX_BlDeteksi_Personel ON dbo.blacklist_deteksi (id_personel, waktu) WHERE id_personel IS NOT NULL;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_BlDeteksi_Kendaraan' AND object_id = OBJECT_ID('dbo.blacklist_deteksi'))
    CREATE INDEX IX_BlDeteksi_Kendaraan ON dbo.blacklist_deteksi (id_kendaraan, waktu) WHERE id_kendaraan IS NOT NULL;
GO
