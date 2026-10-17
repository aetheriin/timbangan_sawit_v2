SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   - Departemen tersedia per PERUSAHAAN (department_company), bukan per area. Isi lama dari department_area
     dipindah ke perusahaan pemilik area itu. Tanpa baris = departemen ada di semua perusahaan.
   - Masa berlaku password hanya dari Pengaturan Site: kolom akun.masa_berlaku_password dihapus.
   Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.department_company') IS NULL
    CREATE TABLE dbo.department_company (
        id_department INT NOT NULL CONSTRAINT FK_DeptCompany_Dept REFERENCES dbo.department (id_department),
        id_company    INT NOT NULL CONSTRAINT FK_DeptCompany_Company REFERENCES dbo.company (id_company),
        CONSTRAINT PK_DepartmentCompany PRIMARY KEY (id_department, id_company)
    );
GO

IF OBJECT_ID('dbo.department_area') IS NOT NULL
BEGIN
    EXEC('INSERT INTO dbo.department_company (id_department, id_company)
          SELECT DISTINCT da.id_department, a.id_company
          FROM dbo.department_area da JOIN dbo.comp_area a ON a.id_comp_area = da.id_comp_area
          WHERE NOT EXISTS (SELECT 1 FROM dbo.department_company x
                            WHERE x.id_department = da.id_department AND x.id_company = a.id_company)');
    DROP TABLE dbo.department_area;
END
GO

IF COL_LENGTH('dbo.akun', 'masa_berlaku_password') IS NOT NULL
BEGIN
    DECLARE @sql NVARCHAR(MAX) = N'';
    SELECT @sql += N'ALTER TABLE dbo.akun DROP CONSTRAINT ' + QUOTENAME(dc.name) + N';'
    FROM sys.default_constraints dc
    JOIN sys.columns c ON c.object_id = dc.parent_object_id AND c.column_id = dc.parent_column_id
    WHERE dc.parent_object_id = OBJECT_ID('dbo.akun') AND c.name = 'masa_berlaku_password';
    SELECT @sql += N'ALTER TABLE dbo.akun DROP CONSTRAINT ' + QUOTENAME(cc.name) + N';'
    FROM sys.check_constraints cc
    JOIN sys.columns c ON c.object_id = cc.parent_object_id AND c.column_id = cc.parent_column_id
    WHERE cc.parent_object_id = OBJECT_ID('dbo.akun') AND c.name = 'masa_berlaku_password';
    EXEC sp_executesql @sql;
    ALTER TABLE dbo.akun DROP COLUMN masa_berlaku_password;
END
GO
