SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Mitra & Produk pindah dari Admin ke Data Master. Hak aksesnya diatur per level di
   Admin › Level & Hak Akses (menu Data Master › Mitra / Data Master › Produk).
   Awal: level HO boleh tambah & ubah. Aman dijalankan ulang.
   ===================================================================================== */

INSERT INTO dbo.menu (kode, nama, id_parent, urutan)
SELECT v.kode, v.nama, p.id_menu, v.urutan
FROM (VALUES ('MASTER_MITRA',  N'Data Master › Mitra',  3),
             ('MASTER_PRODUK', N'Data Master › Produk', 4)) v (kode, nama, urutan)
JOIN dbo.menu p ON p.kode = 'MASTER'
WHERE NOT EXISTS (SELECT 1 FROM dbo.menu m WHERE m.kode = v.kode);
GO

INSERT INTO dbo.level_akses (id_level, id_menu, bisa_tambah, bisa_ubah, bisa_hapus)
SELECT l.id_level, m.id_menu, 1, 1, 0
FROM dbo.level l
JOIN dbo.menu m ON m.kode IN ('MASTER_MITRA', 'MASTER_PRODUK')
WHERE l.kode = 'HO'
  AND NOT EXISTS (SELECT 1 FROM dbo.level_akses a WHERE a.id_level = l.id_level AND a.id_menu = m.id_menu);
GO

SELECT m.kode, m.nama FROM dbo.menu m WHERE m.kode LIKE 'MASTER%';
GO
