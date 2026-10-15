SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Pengajuan koreksi tiket (ERD DatabaseRequestLog) memakai tabel pengajuan yang sudah ada (jenis KOREKSI_TIKET).
   Hak di menu Daftar Tiket: Ubah = mengajukan koreksi, Setujui = menyetujui koreksi & memeriksa tiket.
   Awalnya hak Ubah diberikan ke jabatan yang menginput tiket (punya hak Tambah di Form Security / Timbangan).
   Aman dijalankan ulang.
   ===================================================================================== */
IF NOT EXISTS (SELECT 1 FROM dbo.level_akses a JOIN dbo.menu m ON m.id_menu = a.id_menu WHERE m.kode = 'LIST' AND a.bisa_ubah = 1)
    UPDATE a SET bisa_ubah = 1, bisa_lihat = 1
    FROM dbo.level_akses a JOIN dbo.menu m ON m.id_menu = a.id_menu
    WHERE m.kode = 'LIST' AND a.id_level IN (
        SELECT x.id_level FROM dbo.level_akses x JOIN dbo.menu mx ON mx.id_menu = x.id_menu
        WHERE mx.kode IN ('FORM_SECURITY', 'FORM_TIMBANGAN') AND x.bisa_tambah = 1);
GO
