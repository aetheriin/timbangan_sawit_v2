SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Kendaraan & supplier (ERD: VehicleType, Supplier, Transportir).
   - jenis_kendaraan: berat_kosong_kg (WeightCar), muatan_maks_kg (MaxLoad), kursi (Seat). Dipakai peringatan di
     timbangan: tara jauh dari berat kosong, atau netto melebihi muatan maksimal. Kosong = tidak dicek.
   - mitra.alamat (alamat supplier / customer / transportir).
   - mitra_company: supplier hanya berlaku di PT tertentu (CompAreaID di ERD). Tanpa baris = semua PT.
   Aman dijalankan ulang.
   ===================================================================================== */
IF COL_LENGTH('dbo.jenis_kendaraan', 'berat_kosong_kg') IS NULL
    ALTER TABLE dbo.jenis_kendaraan ADD berat_kosong_kg DECIMAL(10, 2) NULL, muatan_maks_kg DECIMAL(10, 2) NULL, kursi INT NULL;
GO
IF COL_LENGTH('dbo.mitra', 'alamat') IS NULL
    ALTER TABLE dbo.mitra ADD alamat NVARCHAR(255) NULL;
GO
IF OBJECT_ID('dbo.mitra_company', 'U') IS NULL
CREATE TABLE dbo.mitra_company (
    id_supplier INT NOT NULL CONSTRAINT FK_MitraCompany_Mitra REFERENCES dbo.mitra (id_supplier),
    id_company  INT NOT NULL CONSTRAINT FK_MitraCompany_Company REFERENCES dbo.company (id_company),
    CONSTRAINT PK_MitraCompany PRIMARY KEY (id_supplier, id_company)
);
GO
