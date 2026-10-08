SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Blacklist & Tamu menjadi menu sendiri di sidebar (keluar dari tab Face Recognition).
   Hak akses tetap memakai kode menu BLACKLIST & KUNJUNGAN (centang di Admin › Level & Hak Akses).
   Surat blacklist boleh menyusul: blacklist.id_dokumen boleh kosong.
   Aman dijalankan ulang.
   ===================================================================================== */
UPDATE dbo.menu SET id_parent = NULL, url = '/blacklist', ikon = 'fa-ban', nama = N'Blacklist', urutan = 45
WHERE kode = 'BLACKLIST';
UPDATE dbo.menu SET id_parent = NULL, url = '/tamu', ikon = 'fa-id-card', nama = N'Tamu', urutan = 46
WHERE kode = 'KUNJUNGAN';
GO

IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.blacklist') AND name = 'id_dokumen' AND is_nullable = 0)
BEGIN
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Blacklist_Dokumen' AND object_id = OBJECT_ID('dbo.blacklist'))
        DROP INDEX IX_Blacklist_Dokumen ON dbo.blacklist;
    ALTER TABLE dbo.blacklist ALTER COLUMN id_dokumen INT NULL;
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Blacklist_Dokumen' AND object_id = OBJECT_ID('dbo.blacklist'))
    CREATE INDEX IX_Blacklist_Dokumen ON dbo.blacklist (id_dokumen);
GO

SELECT kode, nama, url, id_parent FROM dbo.menu WHERE kode IN ('BLACKLIST', 'KUNJUNGAN');
GO
