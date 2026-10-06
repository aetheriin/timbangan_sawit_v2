SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Profil indikator per jembatan timbang (merk berbeda tiap cabang) + agen di PC jembatan.
   - mode: LOKAL = indikator dicolok ke PC server (atau alat serial-to-LAN: port socket://ip:port)
           AGEN  = indikator dicolok ke PC jembatan, dibaca agen_timbang.py lalu dikirim ke server
   - data_bits / parity / stop_bits / format_data / pola / faktor: cara membaca indikator
   - toleransi_kg / durasi_stabil / berat_min_kg / wajib_st: aturan berat boleh disimpan
   Nilai bawaan = perilaku lama (7E1, format ST,GS,+00012345kg, stabil 5 kg selama 3 detik).
   Aman dijalankan ulang. Wajib setelah migrasi 016.
   ===================================================================================== */

IF COL_LENGTH('dbo.jembatan_timbang', 'mode') IS NULL
    ALTER TABLE dbo.jembatan_timbang ADD
        mode           VARCHAR(10)   NOT NULL CONSTRAINT DF_Jembatan_Mode DEFAULT ('LOKAL'),
        data_bits      TINYINT       NOT NULL CONSTRAINT DF_Jembatan_DataBits DEFAULT (7),
        parity         CHAR(1)       NOT NULL CONSTRAINT DF_Jembatan_Parity DEFAULT ('E'),
        stop_bits      DECIMAL(2, 1) NOT NULL CONSTRAINT DF_Jembatan_StopBits DEFAULT (1),
        format_data    VARCHAR(20)   NOT NULL CONSTRAINT DF_Jembatan_Format DEFAULT ('ST_GS'),
        pola           VARCHAR(200)  NULL,                -- regex sendiri (format POLA), grup (?P<berat>...)
        faktor         DECIMAL(10, 4) NOT NULL CONSTRAINT DF_Jembatan_Faktor DEFAULT (1),   -- 1000 bila indikator kirim ton
        toleransi_kg   DECIMAL(9, 2) NOT NULL CONSTRAINT DF_Jembatan_Toleransi DEFAULT (5),
        durasi_stabil  DECIMAL(4, 1) NOT NULL CONSTRAINT DF_Jembatan_Durasi DEFAULT (3),
        berat_min_kg   DECIMAL(10, 2) NOT NULL CONSTRAINT DF_Jembatan_BeratMin DEFAULT (100),
        wajib_st       BIT           NOT NULL CONSTRAINT DF_Jembatan_WajibSt DEFAULT (0);
GO

IF OBJECT_ID('dbo.CK_Jembatan_Profil', 'C') IS NULL
    ALTER TABLE dbo.jembatan_timbang ADD CONSTRAINT CK_Jembatan_Profil CHECK (
        mode IN ('LOKAL', 'AGEN') AND data_bits IN (5, 6, 7, 8) AND parity IN ('N', 'E', 'O', 'M', 'S')
        AND stop_bits IN (1, 1.5, 2) AND format_data IN ('ST_GS', 'ANGKA', 'TERBALIK', 'POLA')
        AND faktor > 0 AND toleransi_kg >= 0 AND durasi_stabil >= 0.5 AND berat_min_kg >= 0);
GO

/* Port boleh alamat alat serial-to-LAN (socket://192.168.1.50:4001), lebih panjang dari COMx */
IF COL_LENGTH('dbo.jembatan_timbang', 'port') < 100
    ALTER TABLE dbo.jembatan_timbang ALTER COLUMN port VARCHAR(100) NOT NULL;
GO

SELECT kode, mode, port, baudrate, data_bits, parity, stop_bits, format_data, berat_min_kg FROM dbo.jembatan_timbang;
GO
