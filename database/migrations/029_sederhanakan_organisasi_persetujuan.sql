SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Penyederhanaan organisasi & persetujuan.
   - company.alamat : alamat pindah ke perusahaan (diisi dari alamat area pertama yang terisi).
   - comp_area      : tidak lagi diatur sebagai "site" tersendiri. Baris tetap ada sebagai pasangan perusahaan +
                      lokasi (lokasi yang dicentang di form Perusahaan), nama & kode ikut lokasi.
   - level_akses.bisa_setujui : hak menyetujui per menu (Admin › Level & Hak Akses, kolom Setujui).
                      Jabatan yang sebelumnya diatur di Admin › Persetujuan langsung diberi hak Setujui di Blacklist.
   - Menu Persetujuan dinonaktifkan (antrean persetujuan pindah ke tab di halaman Blacklist); tabel
     persetujuan_langkah dihapus.
   Aman dijalankan ulang.
   ===================================================================================== */
IF COL_LENGTH('dbo.company', 'alamat') IS NULL
    ALTER TABLE dbo.company ADD alamat NVARCHAR(255) NULL;
GO
UPDATE c SET alamat = (SELECT TOP 1 a.alamat FROM dbo.comp_area a WHERE a.id_company = c.id_company AND a.alamat IS NOT NULL
                       ORDER BY a.id_comp_area)
FROM dbo.company c WHERE c.alamat IS NULL;
GO

UPDATE a SET kode = l.kode, nama = l.nama
FROM dbo.comp_area a JOIN dbo.lokasi l ON l.id_lokasi = a.id_lokasi
WHERE a.kode <> l.kode OR a.nama <> l.nama;
GO

IF COL_LENGTH('dbo.level_akses', 'bisa_setujui') IS NULL
BEGIN
    ALTER TABLE dbo.level_akses ADD bisa_setujui BIT NOT NULL CONSTRAINT DF_LevelAkses_Setujui DEFAULT (0);
    IF OBJECT_ID('dbo.persetujuan_langkah', 'U') IS NOT NULL
        EXEC (N'
        UPDATE a SET bisa_setujui = 1, bisa_lihat = 1
        FROM dbo.level_akses a JOIN dbo.menu m ON m.id_menu = a.id_menu AND m.kode = ''BLACKLIST''
        WHERE a.id_level IN (SELECT id_level FROM dbo.persetujuan_langkah WHERE jenis LIKE ''BLACKLIST%'');');
END
GO

UPDATE dbo.menu SET is_active = 0 WHERE kode = 'PERSETUJUAN';
GO

-- Pengaturan penyetuju per langkah tidak dipakai lagi (sudah dipindah ke hak Setujui di atas)
IF OBJECT_ID('dbo.persetujuan_langkah', 'U') IS NOT NULL
    DROP TABLE dbo.persetujuan_langkah;
GO
