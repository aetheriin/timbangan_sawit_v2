SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Tahap 1 Security: menu Pos Security (kendaraan masuk: scan wajah supir, plat, customer, produk, pengangkutan)
   dan Logbook (truk masih di dalam / sudah keluar). Hak awal: jabatan SECURITY & HO (bila ada).
   Aksi: Pos Security tambah = simpan masuk, ubah = ubah data supir; Logbook ubah = catat keluar.
   Aman dijalankan ulang.
   ===================================================================================== */
IF NOT EXISTS (SELECT 1 FROM dbo.menu WHERE kode = 'POS_SECURITY')
    INSERT INTO dbo.menu (kode, nama, url, ikon, urutan) VALUES ('POS_SECURITY', N'Pos Security', '/pos-security', 'fa-shield-halved', 15);
IF NOT EXISTS (SELECT 1 FROM dbo.menu WHERE kode = 'LOGBOOK')
    INSERT INTO dbo.menu (kode, nama, url, ikon, urutan) VALUES ('LOGBOOK', N'Logbook Kendaraan', '/logbook', 'fa-book', 16);
GO

INSERT INTO dbo.level_akses (id_level, id_menu, bisa_lihat, bisa_tambah, bisa_ubah, bisa_hapus)
SELECT l.id_level, m.id_menu, 1, v.t, v.u, 0
FROM (VALUES ('SECURITY', 'POS_SECURITY', 1, 1), ('SECURITY', 'LOGBOOK', 0, 1),
             ('HO', 'POS_SECURITY', 0, 0), ('HO', 'LOGBOOK', 0, 0)) v (lv, menu, t, u)
JOIN dbo.level l ON l.kode = v.lv
JOIN dbo.menu m ON m.kode = v.menu
WHERE NOT EXISTS (SELECT 1 FROM dbo.level_akses a WHERE a.id_level = l.id_level AND a.id_menu = m.id_menu);
GO
