SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

USE [DbSistemTimbangan_Test]
GO

/* =====================================================================================
   Transaksi, kontrak & status (ERD: WeightBridgeType, WeightBridge.IsCheck/CheckDate, Contract, DeliveryOrder, Status).
   - jenis_transaksi : master jenis tiket + is_bayar (isPayment). Disiapkan untuk tahap keuangan (invoice);
                       belum ditampilkan di aplikasi.
   - transaksi.diperiksa_oleh / diperiksa_pada : verifikasi tiket selesai (hak Setujui di menu Daftar Tiket).
   - kontrak.id_company / ppn / harga_termasuk_ppn.
   - do_pengangkutan.ongkos_per_kg : ongkos angkut per pengangkut di DO (PriceTransport).
   - status_tiket : nama & warna status tiket, diatur di Admin › Organisasi.
   Aman dijalankan ulang.
   ===================================================================================== */
IF OBJECT_ID('dbo.jenis_transaksi', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.jenis_transaksi (
        kode      VARCHAR(20)  NOT NULL PRIMARY KEY,
        nama      NVARCHAR(50) NOT NULL,
        is_bayar  BIT NOT NULL CONSTRAINT DF_JenisTrx_Bayar DEFAULT (0),     -- tiket jenis ini masuk tagihan / pembayaran
        is_active BIT NOT NULL CONSTRAINT DF_JenisTrx_Aktif DEFAULT (1)
    );
    INSERT INTO dbo.jenis_transaksi (kode, nama, is_bayar) VALUES
        ('PEMBELIAN', N'Pembelian', 1), ('PENJUALAN', N'Penjualan', 1), ('PENIMBANGAN_SAJA', N'Penimbangan Saja', 0);
END
GO

IF COL_LENGTH('dbo.transaksi', 'diperiksa_pada') IS NULL
    ALTER TABLE dbo.transaksi ADD diperiksa_pada DATETIME NULL,
        diperiksa_oleh INT NULL CONSTRAINT FK_Trx_Pemeriksa REFERENCES dbo.akun (id_user);
GO

IF COL_LENGTH('dbo.kontrak', 'ppn') IS NULL
    ALTER TABLE dbo.kontrak ADD
        ppn                BIT NOT NULL CONSTRAINT DF_Kontrak_Ppn DEFAULT (0),
        harga_termasuk_ppn BIT NOT NULL CONSTRAINT DF_Kontrak_InclPpn DEFAULT (0),
        id_company         INT NULL CONSTRAINT FK_Kontrak_Company REFERENCES dbo.company (id_company);
GO

IF COL_LENGTH('dbo.do_pengangkutan', 'ongkos_per_kg') IS NULL
    ALTER TABLE dbo.do_pengangkutan ADD ongkos_per_kg DECIMAL(14, 2) NULL;
GO

IF OBJECT_ID('dbo.status_tiket', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.status_tiket (
        kode   VARCHAR(30)  NOT NULL PRIMARY KEY,
        nama   NVARCHAR(50) NOT NULL,
        warna  VARCHAR(10)  NOT NULL CONSTRAINT DF_StatusTiket_Warna DEFAULT ('abu'),
        urutan TINYINT NOT NULL CONSTRAINT DF_StatusTiket_Urutan DEFAULT (0)
    );
    INSERT INTO dbo.status_tiket (kode, nama, warna, urutan) VALUES
        ('SECURITY_REGISTER', N'Registrasi Security', 'oranye', 1), ('SCAN_WAJAH', N'Scan Wajah', 'oranye', 2),
        ('TIMBANG_1', N'Timbang 1', 'biru', 3), ('INSPEKSI_PROSES', N'Inspeksi', 'ungu', 4),
        ('TIMBANG_2', N'Timbang 2', 'biru', 5), ('SELESAI', N'Selesai', 'hijau', 6),
        ('REJECTED', N'Ditolak', 'merah', 7), ('VOID', N'Dibatalkan', 'abu', 8);
END
GO

-- Verifikasi tiket = hak Setujui di menu Daftar Tiket; awalnya diberikan ke Kepala Tata Usaha
IF NOT EXISTS (SELECT 1 FROM dbo.level_akses a JOIN dbo.menu m ON m.id_menu = a.id_menu WHERE m.kode = 'LIST' AND a.bisa_setujui = 1)
    UPDATE a SET bisa_setujui = 1
    FROM dbo.level_akses a JOIN dbo.menu m ON m.id_menu = a.id_menu JOIN dbo.level l ON l.id_level = a.id_level
    WHERE m.kode = 'LIST' AND l.kode = 'KTU';
GO
