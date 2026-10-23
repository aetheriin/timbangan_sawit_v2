SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Alur persetujuan berjenjang (dinamis) + blacklist: kategori BHL, nama alias, lokasi blacklist.

   - alur_persetujuan       : satu alur per jenis pengajuan + kategori target (NULL = semua kategori).
   - alur_persetujuan_tahap : urutan tahap, tiap tahap = satu PERAN (level = departemen + jabatan).
     Penyetuju tahap = pengguna aktif dengan peran itu di PT pengajuan (user kantor pusat: PT yang dikelolanya).
     Disusun di Admin › Alur Persetujuan, tidak ada nama jabatan yang ditanam di kode.
   - pengajuan_tahap        : salinan tahap saat diajukan (perubahan alur tidak mengganggu pengajuan berjalan).
   - Tanpa alur untuk jenis/kategori itu -> cara lama (satu tahap lewat hak Setujui).
   Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.alur_persetujuan') IS NULL
    CREATE TABLE dbo.alur_persetujuan (
        id_alur_persetujuan INT IDENTITY(1,1) PRIMARY KEY,
        jenis       VARCHAR(40)   NOT NULL,           -- BLACKLIST_TAMBAH, BLACKLIST_HAPUS, KOREKSI_TIKET
        kategori    VARCHAR(20)   NULL,               -- kategori personel / KENDARAAN; NULL = semua kategori
        keterangan  NVARCHAR(255) NULL,
        is_active   BIT NOT NULL CONSTRAINT DF_AlurSetuju_Aktif DEFAULT (1),
        created_at  DATETIME NOT NULL CONSTRAINT DF_AlurSetuju_Dibuat DEFAULT (GETDATE())
    );
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_AlurSetuju_Jenis')
    CREATE UNIQUE INDEX UX_AlurSetuju_Jenis ON dbo.alur_persetujuan (jenis, kategori);
GO
IF OBJECT_ID('dbo.alur_persetujuan_tahap') IS NULL
    CREATE TABLE dbo.alur_persetujuan_tahap (
        id_tahap            INT IDENTITY(1,1) PRIMARY KEY,
        id_alur_persetujuan INT NOT NULL CONSTRAINT FK_AlurSetujuTahap_Alur REFERENCES dbo.alur_persetujuan (id_alur_persetujuan),
        urutan              TINYINT NOT NULL,
        id_level            INT NOT NULL CONSTRAINT FK_AlurSetujuTahap_Level REFERENCES dbo.level (id_level),
        CONSTRAINT UX_AlurSetujuTahap_Urutan UNIQUE (id_alur_persetujuan, urutan)
    );
GO
IF OBJECT_ID('dbo.pengajuan_tahap') IS NULL
    CREATE TABLE dbo.pengajuan_tahap (
        id_pengajuan INT NOT NULL CONSTRAINT FK_PengTahap_Pengajuan REFERENCES dbo.pengajuan (id_pengajuan),
        urutan       TINYINT NOT NULL,
        id_level     INT NOT NULL CONSTRAINT FK_PengTahap_Level REFERENCES dbo.level (id_level),
        CONSTRAINT PK_PengTahap PRIMARY KEY (id_pengajuan, urutan)
    );
GO
IF COL_LENGTH('dbo.pengajuan', 'kategori') IS NULL
    ALTER TABLE dbo.pengajuan ADD kategori VARCHAR(20) NULL;
GO
-- Riwayat: tahap yang perannya dipegang pengaju sendiri dilewati otomatis
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_PengRiwayat_Aksi')
    ALTER TABLE dbo.pengajuan_riwayat DROP CONSTRAINT CK_PengRiwayat_Aksi;
GO
ALTER TABLE dbo.pengajuan_riwayat ADD CONSTRAINT CK_PengRiwayat_Aksi
    CHECK (aksi IN ('DIAJUKAN', 'DISETUJUI', 'DITOLAK', 'DIBATALKAN', 'DILEWATI'));
GO

/* ===== Blacklist: nama alias, kategori target saat itu, lokasi (area pengaju) ===== */
IF COL_LENGTH('dbo.blacklist', 'nama_alias') IS NULL
    ALTER TABLE dbo.blacklist ADD nama_alias NVARCHAR(100) NULL;
GO
IF COL_LENGTH('dbo.blacklist', 'kategori') IS NULL
    ALTER TABLE dbo.blacklist ADD kategori VARCHAR(20) NULL;
GO
IF COL_LENGTH('dbo.blacklist', 'id_comp_area') IS NULL
    ALTER TABLE dbo.blacklist ADD id_comp_area INT NULL CONSTRAINT FK_Blacklist_Area REFERENCES dbo.comp_area (id_comp_area);
GO
UPDATE b SET b.kategori = COALESCE(b.kategori, CASE WHEN b.tipe_entitas = 'KENDARAAN' THEN 'KENDARAAN' ELSE p.kategori END),
             b.id_comp_area = COALESCE(b.id_comp_area, u.id_comp_area)
FROM dbo.blacklist b JOIN dbo.akun u ON u.id_user = b.created_by
LEFT JOIN dbo.personel p ON p.id_personel = b.id_personel
WHERE b.kategori IS NULL OR b.id_comp_area IS NULL;
GO

/* ===== Kategori personel BHL (Buruh Harian Lepas) ===== */
IF NOT EXISTS (SELECT 1 FROM dbo.kategori_personel WHERE kode = 'BHL')
    INSERT INTO dbo.kategori_personel (kode, nama, wajib_sim, boleh_akun, prefix_kode) VALUES ('BHL', N'BHL', 0, 0, 'BHL');
GO
