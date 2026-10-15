SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Organisasi mengikuti ERD: Company → CompanyArea → Mill.
   - lokasi     : sekarang "Mill" = tipe area yang sama untuk semua PT (300 HO, 600 PKS, DOWNSTREAM, TANGKI, ...).
                  Kolom jenis dihapus (cukup tanda kantor pusat), ditambah keterangan.
   - comp_area  : Area Perusahaan dengan nama sendiri (OFFICE, REFINERY, LOADING RAMP) + keterangan + tipe (Mill).
                  Kode area tetap mengikuti kode Mill-nya.
   - department_area (DepartmentDetails): departemen yang tersedia di area tertentu. Departemen tanpa baris di sini
                  tersedia di semua area.
   - Head Office dipisah dari YBS: area bertipe kantor pusat dipindah ke perusahaan HO.
   Aman dijalankan ulang.
   ===================================================================================== */
IF COL_LENGTH('dbo.lokasi', 'keterangan') IS NULL
    ALTER TABLE dbo.lokasi ADD keterangan NVARCHAR(255) NULL;
GO
IF COL_LENGTH('dbo.lokasi', 'jenis') IS NOT NULL
BEGIN
    IF OBJECT_ID('dbo.CK_Lokasi_Jenis', 'C') IS NOT NULL ALTER TABLE dbo.lokasi DROP CONSTRAINT CK_Lokasi_Jenis;
    IF OBJECT_ID('dbo.DF_Lokasi_Jenis', 'D') IS NOT NULL ALTER TABLE dbo.lokasi DROP CONSTRAINT DF_Lokasi_Jenis;
    ALTER TABLE dbo.lokasi DROP COLUMN jenis;
END
GO

IF COL_LENGTH('dbo.comp_area', 'keterangan') IS NULL
    ALTER TABLE dbo.comp_area ADD keterangan NVARCHAR(255) NULL;
GO

IF OBJECT_ID('dbo.department_area', 'U') IS NULL
CREATE TABLE dbo.department_area (
    id_department INT NOT NULL CONSTRAINT FK_DeptArea_Dept REFERENCES dbo.department (id_department),
    id_comp_area  INT NOT NULL CONSTRAINT FK_DeptArea_Area REFERENCES dbo.comp_area (id_comp_area),
    CONSTRAINT PK_DepartmentArea PRIMARY KEY (id_department, id_comp_area)
);
GO

-- Satu perusahaan boleh punya beberapa area bertipe sama (mis. dua PKS); yang unik nama area per perusahaan
IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Area_CompanyLokasi' AND object_id = OBJECT_ID('dbo.comp_area'))
    DROP INDEX UX_Area_CompanyLokasi ON dbo.comp_area;
GO

-- Head Office jadi perusahaan sendiri. Bila ada beberapa area kantor pusat (di PT berbeda), semuanya pindah ke HO
-- dan namanya diberi kode PT asal supaya tetap bisa dibedakan.
IF EXISTS (SELECT 1 FROM dbo.comp_area a JOIN dbo.lokasi l ON l.id_lokasi = a.id_lokasi
           JOIN dbo.company c ON c.id_company = a.id_company WHERE l.is_pusat = 1 AND c.kode <> 'HO')
BEGIN
    IF NOT EXISTS (SELECT 1 FROM dbo.company WHERE kode = 'HO')
        INSERT INTO dbo.company (kode, nama, alamat)
        SELECT TOP 1 'HO', N'HEAD OFFICE', a.alamat
        FROM dbo.comp_area a JOIN dbo.lokasi l ON l.id_lokasi = a.id_lokasi WHERE l.is_pusat = 1 ORDER BY a.id_comp_area;
    IF (SELECT COUNT(*) FROM dbo.comp_area a JOIN dbo.lokasi l ON l.id_lokasi = a.id_lokasi WHERE l.is_pusat = 1) > 1
        UPDATE a SET nama = LEFT(a.nama + N' (' + c.kode + N')', 100)
        FROM dbo.comp_area a JOIN dbo.lokasi l ON l.id_lokasi = a.id_lokasi JOIN dbo.company c ON c.id_company = a.id_company
        WHERE l.is_pusat = 1 AND c.kode <> 'HO';
    UPDATE a SET id_company = (SELECT id_company FROM dbo.company WHERE kode = 'HO')
    FROM dbo.comp_area a JOIN dbo.lokasi l ON l.id_lokasi = a.id_lokasi WHERE l.is_pusat = 1;
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Area_CompanyNama' AND object_id = OBJECT_ID('dbo.comp_area'))
    CREATE UNIQUE INDEX UX_Area_CompanyNama ON dbo.comp_area (id_company, nama);
GO
