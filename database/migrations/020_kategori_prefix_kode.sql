SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Kode personel per kategori: prefix diatur di Admin › Organisasi › Kategori Personel
   (mis. DRV-001, SEC-001). Kode lama (PRGBS-###) tidak diubah. Aman dijalankan ulang.
   ===================================================================================== */
IF COL_LENGTH('dbo.kategori_personel', 'prefix_kode') IS NULL
    ALTER TABLE dbo.kategori_personel ADD prefix_kode VARCHAR(10) NULL;
GO

UPDATE k SET prefix_kode = v.prefix
FROM dbo.kategori_personel k
JOIN (VALUES ('DRIVER', 'DRV'), ('SECURITY', 'SEC'), ('EMPLOYEE', 'KRY'), ('TAMU', 'TMU')) v (kode, prefix) ON v.kode = k.kode
WHERE k.prefix_kode IS NULL;
GO

SELECT kode, nama, prefix_kode, wajib_sim, boleh_akun, is_active FROM dbo.kategori_personel;
GO
