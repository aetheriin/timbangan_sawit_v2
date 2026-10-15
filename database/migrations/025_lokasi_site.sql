SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Lokasi & site (Admin › Organisasi).
   - lokasi   : master lokasi yang sama untuk semua PT, mis. 300 (HEAD OFFICE), 600 (PKS), 601 (BRONDOLAN),
                602 (TANGKI DUMAI), 700 (DOWNSTREAM). is_pusat = kantor pusat (mengelola semua PT).
   - comp_area: site = company + lokasi. Kode site = kode lokasi, jadi kode boleh sama antar PT
                (YBS 600 & SUN 600). Unik per (company, lokasi). Alamat tetap per site.
   Data lama: setiap kode area lama menjadi satu lokasi; area yang tercatat di pengaturan AREA_PUSAT
   menjadi lokasi kantor pusat. Semua tabel lain tetap menunjuk ke comp_area, jadi tidak ada yang terputus.
   Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.lokasi', 'U') IS NULL
CREATE TABLE dbo.lokasi (
    id_lokasi   INT IDENTITY(1,1) PRIMARY KEY,
    kode        VARCHAR(10)   NOT NULL CONSTRAINT UX_Lokasi_Kode UNIQUE,
    nama        NVARCHAR(100) NOT NULL,
    jenis       VARCHAR(20)   NOT NULL CONSTRAINT DF_Lokasi_Jenis DEFAULT ('LAINNYA')
                CONSTRAINT CK_Lokasi_Jenis CHECK (jenis IN ('KANTOR_PUSAT', 'PKS', 'REFINERY', 'TANGKI', 'LAB',
                                                            'KEBUN', 'GUDANG', 'LAINNYA')),
    is_pusat    BIT NOT NULL CONSTRAINT DF_Lokasi_Pusat DEFAULT (0),
    is_active   BIT NOT NULL CONSTRAINT DF_Lokasi_Aktif DEFAULT (1),
    created_at  DATETIME NOT NULL CONSTRAINT DF_Lokasi_Dibuat DEFAULT (GETDATE())
);
GO

IF COL_LENGTH('dbo.comp_area', 'id_lokasi') IS NULL
    ALTER TABLE dbo.comp_area ADD id_lokasi INT NULL CONSTRAINT FK_Area_Lokasi REFERENCES dbo.lokasi (id_lokasi);
GO

-- Satu lokasi per kode area lama, lalu hubungkan
INSERT INTO dbo.lokasi (kode, nama)
SELECT a.kode, MIN(a.nama) FROM dbo.comp_area a
WHERE NOT EXISTS (SELECT 1 FROM dbo.lokasi l WHERE l.kode = a.kode)
GROUP BY a.kode;

UPDATE a SET id_lokasi = l.id_lokasi
FROM dbo.comp_area a JOIN dbo.lokasi l ON l.kode = a.kode
WHERE a.id_lokasi IS NULL;

-- Kantor pusat dari pengaturan lama AREA_PUSAT
UPDATE l SET is_pusat = 1, jenis = 'KANTOR_PUSAT'
FROM dbo.lokasi l
JOIN dbo.comp_area a ON a.id_lokasi = l.id_lokasi
JOIN dbo.pengaturan p ON p.kunci = 'AREA_PUSAT' AND p.nilai = CAST(a.id_comp_area AS VARCHAR(20));
GO

-- Kode area boleh sama antar company; yang unik pasangan company + lokasi
IF OBJECT_ID('dbo.UX_Area_Kode', 'UQ') IS NOT NULL
    ALTER TABLE dbo.comp_area DROP CONSTRAINT UX_Area_Kode;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Area_CompanyLokasi' AND object_id = OBJECT_ID('dbo.comp_area'))
    CREATE UNIQUE INDEX UX_Area_CompanyLokasi ON dbo.comp_area (id_company, id_lokasi) WHERE id_lokasi IS NOT NULL;
GO
