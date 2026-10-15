SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Kolom wajib dinamis (ERD RequiredDataField): baris = kolom opsional yang diwajibkan di sebuah formulir.
   Daftar formulir & kolom yang bisa diatur ada di utils/kolom_wajib.py. Diatur di Admin › Pengaturan Site.
   Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.kolom_wajib', 'U') IS NULL
CREATE TABLE dbo.kolom_wajib (
    form   VARCHAR(30) NOT NULL,
    kolom  VARCHAR(50) NOT NULL,
    CONSTRAINT PK_KolomWajib PRIMARY KEY (form, kolom)
);
GO
