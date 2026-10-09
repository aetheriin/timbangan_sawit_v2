SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Department membatasi MENU yang boleh dibuka; level (jabatan) menentukan aksi tambah / ubah / hapus.
   Akses akhir = menu department  DAN  hak level. Department tanpa baris di sini = tidak dibatasi (semua menu).
   Diatur di Admin > Organisasi > Department. Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.department_menu', 'U') IS NULL
    CREATE TABLE dbo.department_menu (
        id_department INT NOT NULL CONSTRAINT FK_DeptMenu_Department REFERENCES dbo.department (id_department),
        id_menu       INT NOT NULL CONSTRAINT FK_DeptMenu_Menu REFERENCES dbo.menu (id_menu),
        CONSTRAINT PK_DepartmentMenu PRIMARY KEY (id_department, id_menu)
    );
GO
