SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Nama menu memakai bahasa Indonesia (sidebar & Admin › Level & Hak Akses).
   Hanya teks; kode menu, url, dan hak akses tidak berubah. Aman dijalankan ulang.
   ===================================================================================== */
UPDATE dbo.menu SET nama = N'Daftar Tiket'                    WHERE kode = 'LIST';
UPDATE dbo.menu SET nama = N'Stasiun Timbang'                 WHERE kode = 'FORM';
UPDATE dbo.menu SET nama = N'Pengenalan Wajah'                WHERE kode = 'FACE_RECOGNITION';
UPDATE dbo.menu SET nama = N'Stasiun Timbang › Security'      WHERE kode = 'FORM_SECURITY';
UPDATE dbo.menu SET nama = N'Stasiun Timbang › Timbangan'     WHERE kode = 'FORM_TIMBANGAN';
UPDATE dbo.menu SET nama = N'Stasiun Timbang › Sortasi'       WHERE kode = 'FORM_SORTASI';
UPDATE dbo.menu SET nama = N'Stasiun Timbang › Laboratorium'  WHERE kode = 'FORM_LAB';
UPDATE dbo.menu SET nama = N'Pengenalan Wajah › Absensi'      WHERE kode = 'ABSENSI';
UPDATE dbo.menu SET nama = N'Pengenalan Wajah › Personel'     WHERE kode = 'PERSONEL';
UPDATE dbo.menu SET nama = N'Pengenalan Wajah › Log Audit'    WHERE kode = 'AUDIT_LOG';
UPDATE dbo.menu SET nama = N'Data Master › Supir'             WHERE kode = 'MASTER_DRIVER';
UPDATE dbo.menu SET nama = N'Data Master › Supplier'          WHERE kode = 'MASTER_MITRA';
GO
