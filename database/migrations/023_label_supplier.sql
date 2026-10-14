SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Label menu "Data Master › Mitra" menjadi "Data Master › Supplier" (tampil di Admin › Level & Hak Akses).
   Hanya teks; kode menu MASTER_MITRA dan tabel mitra tidak berubah. Aman dijalankan ulang.
   ===================================================================================== */
UPDATE dbo.menu SET nama = N'Data Master › Supplier' WHERE kode = 'MASTER_MITRA';
GO
