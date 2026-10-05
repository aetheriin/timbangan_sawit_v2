SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   ERD v3 Fase 4d:
   - jenis_kendaraan + kendaraan.id_jenis_kendaraan; No STNK unik (dan NOT NULL bila semua kendaraan sudah punya STNK)
   - jadwal_kerja per area: PK (id_comp_area, hari), absensi memakai jadwal area akun yang men-scan
   - pengaturan_area: nilai pengaturan operasional per area (menimpa nilai global di tabel pengaturan)
   - COA lab menjadi dokumen (lab_hasil.id_dokumen, kolom no_dokumen_coa dihapus)
   Wajib setelah migrasi 013.
   ===================================================================================== */

/* ---------- 1. Jenis kendaraan & STNK ---------- */
IF OBJECT_ID('dbo.jenis_kendaraan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.jenis_kendaraan (
        id_jenis_kendaraan  INT IDENTITY(1,1) PRIMARY KEY,
        kode                VARCHAR(20)  NOT NULL CONSTRAINT UX_JenisKendaraan_Kode UNIQUE,
        nama                NVARCHAR(50) NOT NULL,
        is_active           BIT NOT NULL CONSTRAINT DF_JenisKendaraan_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.jenis_kendaraan (kode, nama) VALUES
        ('TRUK', N'Truk'), ('DUMP_TRUK', N'Dump Truk'), ('TANGKI', N'Truk Tangki'),
        ('PICKUP', N'Pick-up'), ('LAINNYA', N'Lainnya');
END
GO
IF COL_LENGTH('dbo.kendaraan', 'id_jenis_kendaraan') IS NULL
    ALTER TABLE dbo.kendaraan ADD id_jenis_kendaraan INT NULL
        CONSTRAINT FK_Kendaraan_Jenis REFERENCES dbo.jenis_kendaraan (id_jenis_kendaraan);
GO

/* STNK kosong ('') dianggap belum diisi */
UPDATE dbo.kendaraan SET no_stnk = NULL WHERE LTRIM(RTRIM(no_stnk)) = '';
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Kendaraan_Stnk' AND object_id = OBJECT_ID('dbo.kendaraan'))
BEGIN
    IF EXISTS (SELECT no_stnk FROM dbo.kendaraan WHERE no_stnk IS NOT NULL GROUP BY no_stnk HAVING COUNT(*) > 1)
        PRINT 'PERHATIAN: ada No STNK ganda, perbaiki dulu (Data Master > Kendaraan) lalu jalankan ulang migrasi ini.';
    ELSE
        CREATE UNIQUE INDEX UX_Kendaraan_Stnk ON dbo.kendaraan (no_stnk) WHERE no_stnk IS NOT NULL;
END
GO
/* NOT NULL hanya bila semua kendaraan sudah punya STNK; sebelum itu STNK wajib diisi lewat form aplikasi */
IF COLUMNPROPERTY(OBJECT_ID('dbo.kendaraan'), 'no_stnk', 'AllowsNull') = 1
   AND NOT EXISTS (SELECT 1 FROM dbo.kendaraan WHERE no_stnk IS NULL)
BEGIN
    IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_Kendaraan_Stnk' AND object_id = OBJECT_ID('dbo.kendaraan'))
        DROP INDEX UX_Kendaraan_Stnk ON dbo.kendaraan;
    ALTER TABLE dbo.kendaraan ALTER COLUMN no_stnk VARCHAR(50) NOT NULL;
    CREATE UNIQUE INDEX UX_Kendaraan_Stnk ON dbo.kendaraan (no_stnk) WHERE no_stnk IS NOT NULL;
END
ELSE IF EXISTS (SELECT 1 FROM dbo.kendaraan WHERE no_stnk IS NULL)
    PRINT 'Info: masih ada kendaraan tanpa STNK; kolom no_stnk tetap NULL sampai dilengkapi.';
GO

/* ---------- 2. Jadwal kerja per area ---------- */
IF COL_LENGTH('dbo.jadwal_kerja', 'id_comp_area') IS NULL
BEGIN
    ALTER TABLE dbo.jadwal_kerja ADD id_comp_area INT NULL CONSTRAINT FK_Jadwal_Area REFERENCES dbo.comp_area (id_comp_area);
END
GO
IF EXISTS (SELECT 1 FROM dbo.jadwal_kerja WHERE id_comp_area IS NULL)
BEGIN
    /* Jadwal lama dipakai area pertama, lalu disalin ke area lain */
    EXEC(N'UPDATE dbo.jadwal_kerja SET id_comp_area = (SELECT MIN(id_comp_area) FROM dbo.comp_area) WHERE id_comp_area IS NULL;
           INSERT INTO dbo.jadwal_kerja (id_comp_area, hari, nama_hari, jam_masuk, jam_pulang, is_libur, toleransi_menit)
           SELECT a.id_comp_area, j.hari, j.nama_hari, j.jam_masuk, j.jam_pulang, j.is_libur, j.toleransi_menit
           FROM dbo.comp_area a CROSS JOIN dbo.jadwal_kerja j
           WHERE j.id_comp_area = (SELECT MIN(id_comp_area) FROM dbo.comp_area)
             AND a.id_comp_area <> j.id_comp_area
             AND NOT EXISTS (SELECT 1 FROM dbo.jadwal_kerja x WHERE x.id_comp_area = a.id_comp_area AND x.hari = j.hari);');
END
GO
/* PK lama (hari) diganti (id_comp_area, hari) */
IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = 'PK_JadwalKerja' AND parent_object_id = OBJECT_ID('dbo.jadwal_kerja'))
BEGIN
    DECLARE @pk SYSNAME = (SELECT name FROM sys.key_constraints WHERE type = 'PK' AND parent_object_id = OBJECT_ID('dbo.jadwal_kerja'));
    IF @pk IS NOT NULL
        EXEC(N'ALTER TABLE dbo.jadwal_kerja DROP CONSTRAINT ' + @pk);
    IF COLUMNPROPERTY(OBJECT_ID('dbo.jadwal_kerja'), 'id_comp_area', 'AllowsNull') = 1
        ALTER TABLE dbo.jadwal_kerja ALTER COLUMN id_comp_area INT NOT NULL;
    ALTER TABLE dbo.jadwal_kerja ADD CONSTRAINT PK_JadwalKerja PRIMARY KEY (id_comp_area, hari);
END
GO

/* ---------- 3. Pengaturan per area ---------- */
IF OBJECT_ID('dbo.pengaturan_area', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pengaturan_area (
        id_comp_area  INT NOT NULL CONSTRAINT FK_PengArea_Area REFERENCES dbo.comp_area (id_comp_area),
        kunci         VARCHAR(50)  NOT NULL,
        nilai         VARCHAR(200) NOT NULL,
        updated_by    INT NULL CONSTRAINT FK_PengArea_User REFERENCES dbo.users (id_user),
        updated_at    DATETIME NOT NULL CONSTRAINT DF_PengArea_Updated DEFAULT (GETDATE()),
        CONSTRAINT PK_PengaturanArea PRIMARY KEY (id_comp_area, kunci)
    );
END
GO

/* ---------- 4. COA lab -> dokumen ---------- */
IF COL_LENGTH('dbo.lab_hasil', 'id_dokumen') IS NULL
    ALTER TABLE dbo.lab_hasil ADD id_dokumen INT NULL CONSTRAINT FK_Lab_Dokumen REFERENCES dbo.dokumen (id_dokumen);
GO
IF COL_LENGTH('dbo.lab_hasil', 'no_dokumen_coa') IS NOT NULL
BEGIN
    /* dokumen.created_by wajib: operator lab, atau admin pertama untuk data lama tanpa operator */
    EXEC(N'
    DECLARE @lab TABLE (id_lab INT, id_dokumen INT);
    MERGE dbo.dokumen AS d
    USING (SELECT l.id_lab, l.no_dokumen_coa, l.no_tiket, j.id_jenis,
                  CAST(COALESCE(l.waktu_pemeriksaan, GETDATE()) AS DATE) AS tanggal,
                  COALESCE(l.operator_lab_id, u.id_user) AS oleh
           FROM dbo.lab_hasil l
           CROSS JOIN (SELECT id_jenis FROM dbo.jenis_dokumen WHERE kode = ''COA'') j
           CROSS JOIN (SELECT MIN(id_user) AS id_user FROM dbo.users) u
           WHERE l.no_dokumen_coa IS NOT NULL AND l.id_dokumen IS NULL) AS s
    ON 1 = 0
    WHEN NOT MATCHED THEN
        INSERT (id_jenis, no_dokumen, tanggal, perihal, created_by)
        VALUES (s.id_jenis, s.no_dokumen_coa, s.tanggal, N''COA tiket '' + s.no_tiket, s.oleh)
    OUTPUT s.id_lab, INSERTED.id_dokumen INTO @lab (id_lab, id_dokumen);
    UPDATE l SET l.id_dokumen = x.id_dokumen FROM dbo.lab_hasil l JOIN @lab x ON x.id_lab = l.id_lab;');
    ALTER TABLE dbo.lab_hasil DROP COLUMN no_dokumen_coa;
END
GO
