SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Jabatan admin (Super Admin) tidak termasuk departemen mana pun. Sebelumnya form jabatan mewajibkan departemen,
   sehingga Super Admin bisa "masuk" ke departemen operasional (mis. Akuntan) bersama akun-akun adminnya.
   - level.id_department & akun.id_department dikosongkan untuk jabatan admin.
   - akun.id_department boleh kosong (hanya untuk akun admin; akun lain tetap diisi dari jabatannya).
   Aman dijalankan ulang.
   ===================================================================================== */
IF EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('dbo.akun') AND name = 'id_department' AND is_nullable = 0)
    ALTER TABLE dbo.akun ALTER COLUMN id_department INT NULL;
GO
UPDATE dbo.level SET id_department = NULL WHERE is_admin = 1 AND id_department IS NOT NULL;
UPDATE u SET id_department = NULL
FROM dbo.akun u JOIN dbo.level l ON l.id_level = u.id_level WHERE l.is_admin = 1 AND u.id_department IS NOT NULL;
GO
