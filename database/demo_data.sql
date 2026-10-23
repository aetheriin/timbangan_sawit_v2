/* =====================================================================
   DATA DEMO CPOS (hanya untuk database uji / pelatihan, JANGAN di database produksi)
   Jalankan SETELAH database/schema.sql pada database yang masih kosong.

   Isi: 2 perusahaan, akun per peran, supir, karyawan, tamu, kendaraan, supplier (grup + rekening), produk + harga,
   kontrak & DO, tiket di semua status (hari ini & 7 hari terakhir), sortasi, lab, void, kelebihan DO, absensi,
   kunjungan tamu, blacklist (personel, kendaraan, supplier), pengajuan yang menunggu persetujuan.

   Semua akun demo: password  Demo12345!  (tidak wajib ganti). Akun admin bawaan schema.sql tidak diubah.
     ho        Head Office · Manager      (Kantor pusat, mengelola semua PT)
     security  Security · Staff           (PT · PKS)        security2  (YBS · PKS)
     operator  Timbangan · Staff          sortasi   Sortasi · Staff        lab   Laboratorium · Staff
   Catatan: orang demo belum punya data wajah, jadi scan wajah belum mengenali mereka.
   ===================================================================== */
SET NOCOUNT ON;
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO
USE [DbSistemTimbangan]
GO
IF EXISTS (SELECT 1 FROM dbo.WeightBridge) OR EXISTS (SELECT 1 FROM dbo.Users WHERE UserName = 'ho')
BEGIN
    RAISERROR('Database sudah berisi data. Data demo hanya untuk database baru dari schema.sql.', 16, 1);
    SET NOEXEC ON;
END
GO
SET XACT_ABORT ON;     -- satu error = semua dibatalkan
BEGIN TRANSACTION;

DECLARE @hari DATE = CAST(GETDATE() AS DATE);
DECLARE @p BIGINT = CAST(FORMAT(GETDATE(), 'yyMMdd') AS BIGINT) * 10000;      -- UserID = YYMMDD + urutan
DECLARE @pw VARCHAR(255) = 'scrypt:32768:8:1$7Ra1t38qVsAOWWU0$f70afd44aed8736b7e66feb8f4ea0647f51f4d4804d72fb36518b2bd6321358288e94c7a42e0763ef10fecf64a08650d5ac62feeb403ffe7d088d9019bbb4c2e';

/* ---------- Organisasi: PT (nama demo) + YBS, area PKS masing-masing ---------- */
UPDATE dbo.Company SET CompName = N'PT Sawit Nusantara Makmur', CompAddress = N'Jl. Lintas Timur Km 12, Riau' WHERE CompID = 'PT';
INSERT INTO dbo.Company (CompID, CompName, CompAddress) VALUES ('YBS', N'PT Yuni Bersaudara Sejahtera', N'Kab. Pelalawan, Riau');
INSERT INTO dbo.CompanyArea (CompID, MillID, AreaCode, AreaName)
SELECT 'YBS', MillID, '600', N'PKS' FROM dbo.Mill WHERE MillCode = '600';
INSERT INTO dbo.DepartmentDetails (CompAreaID, DeptID, Location)
SELECT a.CompAreaID, d.DeptID, 'SITE' FROM dbo.CompanyArea a CROSS JOIN dbo.Department d
WHERE a.CompID = 'YBS' AND d.DeptID IN ('UMUM', 'SEC', 'TBG', 'SRT', 'LAB');

INSERT INTO dbo.WorkSchedule (CompAreaID, DayNo, DayName, TimeIn, TimeOut, IsHoliday, ToleranceMinutes)     -- jadwal sama dengan PKS PT
SELECT y.CompAreaID, j.DayNo, j.DayName, j.TimeIn, j.TimeOut, j.IsHoliday, j.ToleranceMinutes
FROM dbo.WorkSchedule j CROSS JOIN dbo.CompanyArea y
WHERE y.CompID = 'YBS' AND j.CompAreaID = (SELECT CompAreaID FROM dbo.CompanyArea WHERE CompID = 'PT' AND AreaName = N'PKS');

DECLARE @areaPT BIGINT = (SELECT CompAreaID FROM dbo.CompanyArea WHERE CompID = 'PT' AND AreaName = N'PKS');
DECLARE @areaYBS BIGINT = (SELECT CompAreaID FROM dbo.CompanyArea WHERE CompID = 'YBS');
DECLARE @areaHO BIGINT = (SELECT CompAreaID FROM dbo.CompanyArea WHERE CompID = 'HO');

/* ---------- Akun per peran (Users + PasswordManager) ---------- */
INSERT INTO dbo.Users (UserID, UserName, Nama, CategoryCode, UserLevelID, UserDeptID, CompAreaID, NoKTP, UserCode, Email)
SELECT @p + v.n, v.u, v.nama, v.kat, ld.LevelDetID, dd.DeptDetailID, a.CompAreaID, v.nik, v.kode, v.email
FROM (VALUES (11, 'ho',        N'Andi Wijaya',     'EMPLOYEE', 'HO',               'HO',  'HO',  '1471010101800011', 'KRY-001', 'andi@contoh.co.id'),
             (12, 'security',  N'Budi Santoso',    'SECURITY', 'SECURITY',         'SEC', 'PT',  '1471010101850012', 'SEC-001', NULL),
             (13, 'security2', N'Hendra Gunawan',  'SECURITY', 'SECURITY',         'SEC', 'YBS', '1471010101860013', 'SEC-002', NULL),
             (14, 'operator',  N'Rudi Hartono',    'EMPLOYEE', 'OPERATOR_TIMBANG', 'TBG', 'PT',  '1471010101870014', 'KRY-002', NULL),
             (15, 'sortasi',   N'Siti Rahmawati',  'EMPLOYEE', 'SORTASI',          'SRT', 'PT',  '1471010101880015', 'KRY-003', NULL),
             (16, 'lab',       N'Dewi Lestari',    'EMPLOYEE', 'LAB',              'LAB', 'PT',  '1471010101890016', 'KRY-004', NULL)
     ) v (n, u, nama, kat, peran, dept, comp, nik, kode, email)
JOIN dbo.LevelDetails ld ON ld.LevelDetCode = v.peran
JOIN dbo.CompanyArea a ON a.CompID = v.comp
JOIN dbo.DepartmentDetails dd ON dd.DeptID = v.dept AND dd.CompAreaID = a.CompAreaID;
INSERT INTO dbo.PasswordManager (UserID, UserPasswd, MustChange, History)
SELECT UserID, @pw, 0, N'[]' FROM dbo.Users WHERE UserID BETWEEN @p + 11 AND @p + 16;
DECLARE @ho BIGINT = @p + 11, @sec BIGINT = @p + 12, @sec2 BIGINT = @p + 13, @op BIGINT = @p + 14, @srt BIGINT = @p + 15, @lab BIGINT = @p + 16;

/* ---------- Orang tanpa akun: supir, karyawan, BHL, tamu ---------- */
INSERT INTO dbo.Users (UserID, Nama, CategoryCode, NoKTP, UserCode, IsUpload)
VALUES (@p + 21, N'Joko Susilo',      'DRIVER',   '1471020202800021', 'DRV-001', 1),
       (@p + 22, N'Agus Salim',       'DRIVER',   '1471020202810022', 'DRV-002', 1),
       (@p + 23, N'Bambang Prasetyo', 'DRIVER',   '1471020202820023', 'DRV-003', 1),
       (@p + 24, N'Dedi Kurniawan',   'DRIVER',   '1471020202830024', 'DRV-004', 1),
       (@p + 25, N'Eko Saputra',      'DRIVER',   '1471020202840025', 'DRV-005', 1),
       (@p + 26, N'Fajar Nugroho',    'DRIVER',   '1471020202850026', 'DRV-006', 1),
       (@p + 27, N'Gilang Ramadhan',  'DRIVER',   '1471020202860027', 'DRV-007', 0),
       (@p + 28, N'Hari Wibowo',      'DRIVER',   '1471020202870028', 'DRV-008', 1),
       (@p + 29, N'Irfan Hakim',      'DRIVER',   '1471020202880029', 'DRV-009', 1),
       (@p + 30, N'Yusuf Maulana',    'DRIVER',   '1471020202890030', 'DRV-010', 1),
       (@p + 31, N'Rina Marlina',     'EMPLOYEE', '1471030303900031', 'KRY-005', 1),
       (@p + 32, N'Tono Sugiarto',    'BHL',      '1471030303910032', 'BHL-001', 0),
       (@p + 33, N'Lina Kusuma',      'TAMU',     '3171040404920033', 'TMU-001', 0),
       (@p + 34, N'Rudy Tanjung',     'TAMU',     '1271040404930034', 'TMU-002', 0);
INSERT INTO dbo.LicenseDetail (UserID, SIMType, LicenseNumber, ExpiredSIM, CreateBy)
SELECT @p + v.n, l.LicenseID, v.sim, DATEADD(MONTH, v.bulan, @hari), @sec
FROM (VALUES (21, 'B1_UMUM', '140112340021', 30), (22, 'B1_UMUM', '140112340022', 18), (23, 'B2_UMUM', '140112340023', 40),
             (24, 'B1', '140112340024', 1), (25, 'B1_UMUM', '140112340025', 24), (26, 'B2', '140112340026', 12),
             (27, 'B1', '140112340027', -2), (28, 'B1_UMUM', '140112340028', 9), (29, 'B2_UMUM', '140112340029', 15),
             (30, 'B1_UMUM', '140112340030', 20)) v (n, jenis, sim, bulan)
JOIN dbo.License l ON l.LicenseCode = v.jenis;

/* ---------- Kendaraan + supir terdaftar ---------- */
INSERT INTO dbo.DetailVehicle (NoVehicle, NoSTNK, VehicleType)
SELECT v.plat, v.stnk, t.VehicleTypeID
FROM (VALUES ('BM 8821 KA', 'STNK-0001', 'DUMP_TRUK'), ('BM 9012 RB', 'STNK-0002', 'TRUK'), ('BM 7734 TC', 'STNK-0003', 'TRUK'),
             ('BK 1450 XY', 'STNK-0004', 'DUMP_TRUK'), ('BM 8890 AD', 'STNK-0005', 'TANGKI'), ('BM 8891 AD', 'STNK-0006', 'TANGKI'),
             ('BM 6601 QE', 'STNK-0007', 'TRUK'), ('BA 9123 LK', 'STNK-0008', 'PICKUP')) v (plat, stnk, jenis)
JOIN dbo.VehicleType t ON t.VehicleTypeCode = v.jenis;
UPDATE dbo.VehicleType SET WeightCar = 7500, MaxLoad = 20000, Seat = 3 WHERE VehicleTypeCode = 'TRUK';
UPDATE dbo.VehicleType SET WeightCar = 9000, MaxLoad = 26000, Seat = 3 WHERE VehicleTypeCode = 'DUMP_TRUK';
UPDATE dbo.VehicleType SET WeightCar = 12000, MaxLoad = 32000, Seat = 2 WHERE VehicleTypeCode = 'TANGKI';
INSERT INTO dbo.VehicleDriver (IDVehicle, UserID, IsMain, CreateBy)
SELECT k.IDVehicle, @p + v.n, v.utama, @sec
FROM (VALUES ('BM 8821 KA', 21, 1), ('BM 8821 KA', 27, 0), ('BM 9012 RB', 22, 1), ('BM 7734 TC', 23, 1), ('BK 1450 XY', 24, 1),
             ('BM 8890 AD', 25, 1), ('BM 8891 AD', 26, 1), ('BM 6601 QE', 28, 1), ('BM 6601 QE', 29, 0), ('BA 9123 LK', 30, 1)) v (plat, n, utama)
JOIN dbo.DetailVehicle k ON k.NoVehicle = v.plat;

/* ---------- Bank, rekening, grup & supplier ---------- */
INSERT INTO dbo.Bank (BankName, BankRegion, CurrencyID, CompAreaID)
SELECT v.nama, v.cabang, c.CurrencyID, NULL FROM (VALUES (N'Bank Mandiri', N'Pekanbaru'), (N'Bank BRI', N'Pangkalan Kerinci'), (N'Bank BCA', N'Pekanbaru')) v (nama, cabang)
CROSS JOIN dbo.Currency c WHERE c.CurrencyCode = 'IDR';
INSERT INTO dbo.BankDetails (BankAccountID, BankAccountCode, BankName, Balance)
SELECT b.BankAccountID, v.norek, v.an, NULL
FROM (VALUES (N'Bank Mandiri', '1080012345678', N'KUD Sawit Jaya'), (N'Bank BRI', '0231010004567', N'CV Tandan Mas'),
             (N'Bank BCA', '8720345566', N'PT Angkut Lancar'), (N'Bank Mandiri', '1080098765432', N'PT Minyak Prima')) v (bank, norek, an)
JOIN dbo.Bank b ON b.BankName = v.bank;
INSERT INTO dbo.SupplierGroup (NameGroup, Description) VALUES (N'Plasma', N'Kebun plasma / KUD'), (N'Pihak Ketiga', N'Pemasok luar'), (N'Pembeli CPO', N'Customer produk PKS');
INSERT INTO dbo.Supplier (SupplierCode, SupplierName, SupplierAddress, SupplierGroupID, BankAccountDetailsID)
SELECT v.kode, v.nama, v.alamat, g.SupplierGroupID, bd.BankAccountDetailsID
FROM (VALUES ('SUP-001', 'KUD Sawit Jaya',       N'Desa Sei Lala, Kampar',   N'Plasma',       '1080012345678'),
             ('SUP-002', 'CV Tandan Mas',        N'Pangkalan Kerinci',       N'Pihak Ketiga', '0231010004567'),
             ('SUP-003', 'UD Berkah Tani',       N'Ukui, Pelalawan',         N'Pihak Ketiga', NULL),
             ('SUP-004', 'PT Minyak Prima',      N'Dumai',                   N'Pembeli CPO',  '1080098765432'),
             ('SUP-005', 'CV Sawit Nakal',       N'Siak',                    N'Pihak Ketiga', NULL),
             ('ANG-001', 'PT Angkut Lancar',     N'Pekanbaru',               NULL,            '8720345566'),
             ('ANG-002', 'CV Transportir Riau',  N'Pekanbaru',               NULL,            NULL)) v (kode, nama, alamat, grup, norek)
LEFT JOIN dbo.SupplierGroup g ON g.NameGroup = v.grup
LEFT JOIN dbo.BankDetails bd ON bd.BankAccountCode = v.norek;
INSERT INTO dbo.SupplierTypeDetails (SupplierID, TypeCode)
SELECT s.SupplierID, CASE WHEN s.SupplierCode LIKE 'ANG-%' THEN 'PENGANGKUTAN' ELSE 'CUSTOMER' END FROM dbo.Supplier s;
INSERT INTO dbo.SupplierTypeDetails (SupplierID, TypeCode) SELECT SupplierID, 'PENGANGKUTAN' FROM dbo.Supplier WHERE SupplierCode = 'SUP-002';
INSERT INTO dbo.SupplierCompany (SupplierID, CompID) SELECT SupplierID, 'YBS' FROM dbo.Supplier WHERE SupplierCode = 'SUP-003';

/* ---------- Produk, standar mutu, harga ---------- */
INSERT INTO dbo.Product (ProductName, Category, FlowID, StandardFFA, StandardMoist, StandardDirt)
SELECT v.nama, v.kat, f.FlowID, v.ffa, v.air, v.kotor
FROM (VALUES ('TBS', 'TBS', 'TBS', 5.0, 0.5, 0.5), ('CPO', 'PRODUK_PKS', 'PKS', 5.0, 0.25, 0.02),
             ('Kernel', 'PRODUK_PKS', 'PKS', 2.0, 7.0, 6.0)) v (nama, kat, alur, ffa, air, kotor)
JOIN dbo.Flow f ON f.FlowCode = v.alur;
INSERT INTO dbo.ProductPrice (ProductID, PriceDate, Price, CurrencyID, CreateBy)
SELECT p.ProductID, DATEADD(DAY, -d.n, @hari), v.harga + d.n * v.naik, c.CurrencyID, @ho
FROM (VALUES ('TBS', 2650, -15), ('CPO', 12400, -40), ('Kernel', 7100, -25)) v (nama, harga, naik)
JOIN dbo.Product p ON p.ProductName = v.nama
CROSS JOIN (VALUES (0), (7), (14)) d (n)
CROSS JOIN dbo.Currency c WHERE c.CurrencyCode = 'IDR';
INSERT INTO dbo.DailyPrice (PriceDate, CPOPrice, KernelPrice, OERCPO, ProcessingCost, UpdateBy)
SELECT DATEADD(DAY, -n, @hari), 12400 - n * 35, 7100 - n * 20, 21.5 - n * 0.1, 155, @ho
FROM (VALUES (0), (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11), (12), (13)) d (n);

/* ---------- Kontrak & DO (DO-TBS-002 hampir habis kuota -> kelebihan DO) ---------- */
INSERT INTO dbo.Contract (ContractNumber, TransactionType, SupplierID, ProductID, ContractDate, ContractQty, Price, PPN, IncludePPN, CompID, CreateBy)
SELECT v.no, v.jenis, s.SupplierID, p.ProductID, DATEADD(DAY, -v.hari, @hari), v.qty, v.harga, v.ppn, 0, 'PT', @ho
FROM (VALUES ('KTR/2026/001', 'PEMBELIAN', 'SUP-001', 'TBS', 20, 500000, 2650, 0),
             ('KTR/2026/002', 'PEMBELIAN', 'SUP-002', 'TBS', 10, 15000, 2600, 0),
             ('KTR/2026/003', 'PENJUALAN', 'SUP-004', 'CPO', 15, 300000, 12400, 1),
             ('KTR/2026/004', 'PENJUALAN', 'SUP-004', 'Kernel', 15, 100000, 7100, 1)) v (no, jenis, sup, prod, hari, qty, harga, ppn)
JOIN dbo.Supplier s ON s.SupplierCode = v.sup JOIN dbo.Product p ON p.ProductName = v.prod;
INSERT INTO dbo.DeliveryOrder (DONumber, ContractID, DODate, ExpiredDate, CreateBy)
SELECT v.do, k.ContractID, DATEADD(DAY, -v.hari, @hari), DATEADD(DAY, 30, @hari), @ho
FROM (VALUES ('DO-TBS-001', 'KTR/2026/001', 20), ('DO-TBS-002', 'KTR/2026/002', 10),
             ('DO-CPO-001', 'KTR/2026/003', 15), ('DO-KRN-001', 'KTR/2026/004', 15)) v (do, ktr, hari)
JOIN dbo.Contract k ON k.ContractNumber = v.ktr;
INSERT INTO dbo.DOTransport (DeliveryOrderID, TransportMode, TransportID, DOQty, PriceTransport)
SELECT d.DeliveryOrderID, v.cara, s.SupplierID, NULL, v.ongkos
FROM (VALUES ('DO-TBS-001', 'PENGIRIM', NULL, NULL), ('DO-TBS-002', 'PENGIRIM', NULL, NULL),
             ('DO-CPO-001', 'PIHAK_KETIGA', 'ANG-001', 85), ('DO-KRN-001', 'PIHAK_KETIGA', 'ANG-002', 90)) v (do, cara, ang, ongkos)
JOIN dbo.DeliveryOrder d ON d.DONumber = v.do LEFT JOIN dbo.Supplier s ON s.SupplierCode = v.ang;

/* ---------- Jembatan timbang ---------- */
INSERT INTO dbo.Scale (CompAreaID, ScaleCode, ScaleName, Port)
SELECT v.area, v.kode, v.nama, v.port
FROM (VALUES (@areaPT, 'JT-1', N'Jembatan Timbang 1', 'COM3'), (@areaPT, 'JT-2', N'Jembatan Timbang 2', 'COM4'),
             (@areaYBS, 'JT-1', N'Jembatan Timbang YBS', 'COM3')) v (area, kode, nama, port)
WHERE NOT EXISTS (SELECT 1 FROM dbo.Scale j WHERE j.CompAreaID = v.area AND j.ScaleCode = v.kode);     -- schema.sql sudah membuat JT-1
DECLARE @jt1 INT = (SELECT ScaleID FROM dbo.Scale WHERE CompAreaID = @areaPT AND ScaleCode = 'JT-1');
DECLARE @jt2 INT = (SELECT ScaleID FROM dbo.Scale WHERE CompAreaID = @areaPT AND ScaleCode = 'JT-2');

/* ---------- Tiket: (no, menit lalu, jenis, supplier, produk, plat, supir, DO, status, timbang1, timbang2, jembatan, keluar?) ---------- */
DECLARE @t TABLE (no VARCHAR(50), menit INT, jenis VARCHAR(20), sup VARCHAR(20), prod VARCHAR(50), plat VARCHAR(15), supir INT,
                  do VARCHAR(50), st VARCHAR(30), w1 DECIMAL(10, 2), w2 DECIMAL(10, 2), jt INT, keluar BIT);
INSERT INTO @t VALUES
    ('PKS-' + FORMAT(@hari, 'yyMMdd') + '-001', 330, 'PEMBELIAN', 'SUP-001', 'TBS', 'BM 8821 KA', 21, 'DO-TBS-001', 'SELESAI',   28500, 10150, 1, 1),
    ('PKS-' + FORMAT(@hari, 'yyMMdd') + '-002', 285, 'PEMBELIAN', 'SUP-002', 'TBS', 'BM 9012 RB', 22, NULL,         'SELESAI',   21900,  8300, 1, 1),
    ('PKS-' + FORMAT(@hari, 'yyMMdd') + '-003', 250, 'PENJUALAN', 'SUP-004', 'CPO', 'BM 8890 AD', 25, 'DO-CPO-001', 'SELESAI',   12100, 41850, 2, 1),
    ('PKS-' + FORMAT(@hari, 'yyMMdd') + '-004', 190, 'PEMBELIAN', 'SUP-001', 'TBS', 'BM 7734 TC', 23, 'DO-TBS-001', 'TIMBANG_2', 26750, NULL, 1, 0),
    ('PKS-' + FORMAT(@hari, 'yyMMdd') + '-005', 120, 'PEMBELIAN', 'SUP-003', 'TBS', 'BK 1450 XY', 24, NULL,         'TIMBANG_1', 24300, NULL, 2, 0),
    ('PKS-' + FORMAT(@hari, 'yyMMdd') + '-006',  75, 'PENJUALAN', 'SUP-004', 'CPO', 'BM 8891 AD', 26, 'DO-CPO-001', 'TIMBANG_1', 12350, NULL, 2, 0),
    ('PKS-' + FORMAT(@hari, 'yyMMdd') + '-007',  20, 'PEMBELIAN', 'SUP-001', 'TBS', 'BM 6601 QE', 28, 'DO-TBS-001', 'SECURITY_REGISTER', NULL, NULL, NULL, 0),
    ('PKS-' + FORMAT(DATEADD(DAY, -1, @hari), 'yyMMdd') + '-011', 1500, 'PENJUALAN', 'SUP-004', 'Kernel', 'BM 8890 AD', 25, 'DO-KRN-001', 'REJECTED', 12050, NULL, 1, 1),
    ('PKS-' + FORMAT(DATEADD(DAY, -1, @hari), 'yyMMdd') + '-012', 1380, 'PEMBELIAN', 'SUP-005', 'TBS', 'BA 9123 LK', 30, NULL, 'VOID', NULL, NULL, NULL, 1),
    ('PKS-' + FORMAT(DATEADD(DAY, -1, @hari), 'yyMMdd') + '-013', 1320, 'PEMBELIAN', 'SUP-002', 'TBS', 'BM 9012 RB', 22, 'DO-TBS-002', 'SELESAI', 29800, 9900, 1, 1);
-- Riwayat 6 hari ke belakang: 4 tiket TBS selesai per hari (grafik & laporan terisi)
DECLARE @d INT = 2;
WHILE @d <= 7
BEGIN
    INSERT INTO @t
    SELECT 'PKS-' + FORMAT(DATEADD(DAY, -@d, @hari), 'yyMMdd') + '-0' + CAST(20 + x.n AS VARCHAR(3)), @d * 1440 - 600 + x.n * 95,
           'PEMBELIAN', x.sup, 'TBS', x.plat, x.supir, x.do, 'SELESAI', 22000 + (x.n * 1700 + @d * 430) % 7000,
           8200 + (x.n * 310 + @d * 90) % 2000, 1 + x.n % 2, 1
    FROM (VALUES (1, 'SUP-001', 'BM 8821 KA', 21, 'DO-TBS-001'), (2, 'SUP-003', 'BK 1450 XY', 24, NULL),
                 (3, 'SUP-001', 'BM 7734 TC', 23, 'DO-TBS-001'), (4, 'SUP-005', 'BM 6601 QE', 29, NULL)) x (n, sup, plat, supir, do);
    SET @d += 1;
END

INSERT INTO dbo.WeightBridge (TicketNumber, TicketDate, WeightTypeCode, SupplierID, ProductID, IDVehicle, DriverID, TransportMode, TransportID,
                              DONumber, DeliveryOrderID, StatusCode, IsQRActive, QRExpiredDate, ScaleID, CompAreaID, FlowID, CreateBy,
                              CheckDate, CheckBy, ExitDate, ExitBy)
SELECT t.no, DATEADD(MINUTE, -t.menit, GETDATE()), t.jenis, s.SupplierID, p.ProductID, k.IDVehicle, @p + t.supir,
       CASE WHEN dt.TransportID IS NULL THEN 'PENGIRIM' ELSE 'PIHAK_KETIGA' END, dt.TransportID,
       t.do, d.DeliveryOrderID, t.st, CASE WHEN t.st IN ('SELESAI', 'VOID', 'REJECTED') THEN 0 ELSE 1 END,
       DATEADD(MINUTE, 1440 - t.menit, GETDATE()), CASE t.jt WHEN 1 THEN @jt1 WHEN 2 THEN @jt2 END, @areaPT, p.FlowID, @sec,
       CASE WHEN t.st = 'SELESAI' AND t.menit > 1440 THEN DATEADD(MINUTE, -t.menit + 120, GETDATE()) END,
       CASE WHEN t.st = 'SELESAI' AND t.menit > 1440 THEN @ho END,
       CASE WHEN t.keluar = 1 THEN DATEADD(MINUTE, -t.menit + 70, GETDATE()) END, CASE WHEN t.keluar = 1 THEN @sec END
FROM @t t
JOIN dbo.Supplier s ON s.SupplierCode = t.sup JOIN dbo.Product p ON p.ProductName = t.prod
JOIN dbo.DetailVehicle k ON k.NoVehicle = t.plat
LEFT JOIN dbo.DeliveryOrder d ON d.DONumber = t.do
OUTER APPLY (SELECT TOP 1 TransportID FROM dbo.DOTransport WHERE DeliveryOrderID = d.DeliveryOrderID ORDER BY DOTransportID) dt;

-- Penimbangan ke-1 (masuk) dan ke-2 (keluar) di jembatan yang sama
INSERT INTO dbo.Weighing (TicketNumber, WeighNo, ScaleID, Weight, WeighDate, OperatorID)
SELECT t.no, 1, CASE t.jt WHEN 1 THEN @jt1 ELSE @jt2 END, t.w1, DATEADD(MINUTE, -t.menit + 10, GETDATE()), @op FROM @t t WHERE t.w1 IS NOT NULL;
INSERT INTO dbo.Weighing (TicketNumber, WeighNo, ScaleID, Weight, WeighDate, OperatorID)
SELECT t.no, 2, CASE t.jt WHEN 1 THEN @jt1 ELSE @jt2 END, t.w2, DATEADD(MINUTE, -t.menit + 55, GETDATE()), @op FROM @t t WHERE t.w2 IS NOT NULL;

-- Sortasi TBS (tiket yang sudah lewat timbang 1 dan bukan menunggu sortasi)
INSERT INTO dbo.Grading (TicketNumber, UnripePct, RottenPct, LongStalkPct, DirtPct, RipePct, LooseFruitPct, DeductionKg, Notes, GradedBy, GradingDate)
SELECT t.no, 2.0 + (t.menit % 3), 0.5, 1.0, 0.5 + (t.menit % 2) * 0.5, 90.0, 6.0,
       CASE WHEN t.w2 IS NOT NULL THEN ROUND(ABS(t.w1 - t.w2) * (2.0 + (t.menit % 3) + 1.0 + 0.5 + (t.menit % 2) * 0.5) / 100, 2) END,
       NULL, @srt, DATEADD(MINUTE, -t.menit + 30, GETDATE())
FROM @t t WHERE t.prod = 'TBS' AND t.st IN ('SELESAI', 'TIMBANG_2');

-- Lab produk PKS: CPO selesai = APPROVE (dengan COA), Kernel = REJECT
INSERT INTO dbo.Document (DocTypeID, DocNumber, DocDate, Subject, CreateBy)
SELECT dt.DocTypeID, 'COA-' + t.no, @hari, N'COA tiket ' + t.no, @lab FROM @t t CROSS JOIN dbo.DocumentType dt
WHERE t.prod = 'CPO' AND t.st = 'SELESAI' AND dt.DocTypeCode = 'COA';
INSERT INTO dbo.LabResult (TicketNumber, FFA, Moisture, Dirt, LovibondColor, Decision, COADocID, TestedBy, TestDate)
SELECT t.no, CASE WHEN t.st = 'REJECTED' THEN 3.4 ELSE 3.8 END, CASE WHEN t.st = 'REJECTED' THEN 9.1 ELSE 0.18 END,
       CASE WHEN t.st = 'REJECTED' THEN 7.5 ELSE 0.015 END, CASE WHEN t.st = 'REJECTED' THEN NULL ELSE '3.2R' END,
       CASE WHEN t.st = 'REJECTED' THEN 'REJECT' ELSE 'APPROVE' END, doc.DocumentID, @lab, DATEADD(MINUTE, -t.menit + 30, GETDATE())
FROM @t t LEFT JOIN dbo.Document doc ON doc.DocNumber = 'COA-' + t.no
WHERE t.prod IN ('CPO', 'Kernel') AND t.st IN ('SELESAI', 'REJECTED');

-- Void (admin) & reject lab
INSERT INTO dbo.TicketVoid (TicketNumber, VoidType, Reason, VoidBy, VoidDate)
SELECT t.no, CASE t.st WHEN 'VOID' THEN 'VOID' ELSE 'REJECT' END,
       CASE t.st WHEN 'VOID' THEN N'Salah input supplier, tiket dibuat ulang' ELSE N'Kadar air & kotoran di atas standar' END,
       CASE t.st WHEN 'VOID' THEN (SELECT MIN(UserID) FROM dbo.Users WHERE UserName = 'admin') ELSE @lab END,
       DATEADD(MINUTE, -t.menit + 60, GETDATE())
FROM @t t WHERE t.st IN ('VOID', 'REJECTED');

-- Kelebihan DO: DO-TBS-002 kuota 15.000 kg, tiket netto 19.900 kg -> lebih 4.900 kg jadi tiket split
DECLARE @tLebih VARCHAR(50) = 'PKS-' + FORMAT(DATEADD(DAY, -1, @hari), 'yyMMdd') + '-013';
DECLARE @doLebih INT = (SELECT DeliveryOrderID FROM dbo.DeliveryOrder WHERE DONumber = 'DO-TBS-002');
INSERT INTO dbo.WeightBridge (TicketNumber, TicketDate, WeightTypeCode, SupplierID, ProductID, IDVehicle, DriverID, TransportMode, StatusCode,
                              IsQRActive, QRExpiredDate, ScaleID, CompAreaID, FlowID, CreateBy, ParentTicketNumber, SplitWeight, ExitDate, ExitBy)
SELECT TicketNumber + '-S1', TicketDate, WeightTypeCode, SupplierID, ProductID, IDVehicle, DriverID, TransportMode, 'SELESAI',
       0, QRExpiredDate, ScaleID, CompAreaID, FlowID, CreateBy, TicketNumber, 4900, ExitDate, ExitBy
FROM dbo.WeightBridge WHERE TicketNumber = @tLebih;
INSERT INTO dbo.DOExcess (TicketNumber, SplitTicketNumber, DeliveryOrderID, QuotaKg, RealizedKg, TicketNettoKg, ExcessKg, Status, CompAreaID)
VALUES (@tLebih, @tLebih + '-S1', @doLebih, 15000, 19900, 19900, 4900, 'MENUNGGU', @areaPT);
INSERT INTO dbo.Notification (MenuCode, CompAreaID, Title, Message, Link)
VALUES ('KELEBIHAN_DO', @areaPT, N'DO DO-TBS-002 melebihi kuota 4.900 kg',
        N'Tiket ' + @tLebih + N': kelebihan 4.900 kg menjadi tiket ' + @tLebih + N'-S1. Isi No. DO baru dari Ascend.', '/kelebihan-do');

-- Pos Security saja (tanpa timbang): satu kendaraan masih di dalam
INSERT INTO dbo.WeightBridge (TicketNumber, TicketDate, WeightTypeCode, SupplierID, ProductID, IDVehicle, DriverID, TransportMode, StatusCode,
                              QRExpiredDate, CompAreaID, FlowID, CreateBy)
SELECT 'POS-' + FORMAT(@hari, 'yyMMdd') + '-001', DATEADD(MINUTE, -45, GETDATE()), 'PENIMBANGAN_SAJA', s.SupplierID, p.ProductID,
       k.IDVehicle, @p + 29, 'PENGIRIM', 'SECURITY_REGISTER', DATEADD(HOUR, 23, GETDATE()), @areaPT, f.FlowID, @sec
FROM dbo.Supplier s, dbo.Product p, dbo.DetailVehicle k, dbo.Flow f
WHERE s.SupplierCode = 'SUP-003' AND p.ProductName = 'TBS' AND k.NoVehicle = 'BM 7734 TC' AND f.FlowCode = 'POS_SAJA';

/* ---------- Absensi 5 hari terakhir (karyawan & security) ---------- */
INSERT INTO dbo.FaceActivity (UserID, ActivityType, Status, TimeStatus, DiffMinutes, FaceDistance, LivenessChallenge, Device, LogDate)
SELECT u.n, j.jenis, 'BERHASIL',
       CASE WHEN j.jenis = 'MASUK' AND (u.n + d.n) % 4 = 0 THEN 'TERLAMBAT' ELSE 'TEPAT_WAKTU' END,
       CASE WHEN j.jenis = 'MASUK' AND (u.n + d.n) % 4 = 0 THEN 12 ELSE 0 END, 0.32, 'KEDIP', 'KIOSK-PKS',
       DATEADD(MINUTE, CASE j.jenis WHEN 'MASUK' THEN 7 * 60 + 50 + CASE WHEN (u.n + d.n) % 4 = 0 THEN 22 ELSE 0 END ELSE 17 * 60 + 5 END,
               CAST(DATEADD(DAY, -d.n, @hari) AS DATETIME))
FROM (VALUES (@sec), (@op), (@srt), (@lab), (@p + 31)) u (n)
CROSS JOIN (VALUES (1), (2), (3), (4), (5)) d (n)
CROSS JOIN (VALUES ('MASUK'), ('PULANG')) j (jenis)
WHERE DATEPART(WEEKDAY, DATEADD(DAY, -d.n, @hari)) NOT IN (1);
INSERT INTO dbo.FaceActivity (UserID, ActivityType, Status, TimeStatus, DiffMinutes, FaceDistance, LivenessChallenge, Device, LogDate)
SELECT n, 'MASUK', 'BERHASIL', 'TEPAT_WAKTU', 0, 0.3, 'KEDIP', 'KIOSK-PKS', DATEADD(MINUTE, 7 * 60 + 48, CAST(@hari AS DATETIME))
FROM (VALUES (@sec), (@op), (@srt), (@lab)) u (n);

/* ---------- Kunjungan tamu ---------- */
INSERT INTO dbo.Guest (UserID, VisitToID, PurposeID, Description, CompanyFrom, NoVehicle, CompAreaID, CheckInDate, CheckOutDate, CreateBy)
SELECT @p + 33, @p + 31, (SELECT PurposeID FROM dbo.VisitPurpose WHERE PurposeName = N'Audit / Inspeksi'), N'Audit sertifikasi ISPO',
       N'PT Sertifikasi Hijau', 'B 1234 KLM', @areaPT, DATEADD(MINUTE, -150, GETDATE()), NULL, @sec
UNION ALL
SELECT @p + 34, @ho, (SELECT PurposeID FROM dbo.VisitPurpose WHERE PurposeName = N'Perbaikan / Servis'), N'Kalibrasi timbangan JT-2',
       N'CV Teknik Timbang', 'BK 7788 ZZ', @areaPT, DATEADD(HOUR, -26, GETDATE()), DATEADD(HOUR, -23, GETDATE()), @sec;

/* ---------- Blacklist: supir, kendaraan, supplier (aktif) + satu yang sudah dicabut ---------- */
DECLARE @bl TABLE (id BIGINT, jenis VARCHAR(20));
INSERT INTO dbo.Blacklist (TableName, UserID, IDVehicle, SupplierID, Reason, CreateBy, CreateDate, NoVehicle, CustomerID, CategoryCode, CompAreaID,
                           AliasName, NewValue)
OUTPUT INSERTED.BlacklistID, INSERTED.TargetType INTO @bl
SELECT 'Users', @p + 27, NULL, NULL, 'Menukar tiket timbang dengan truk lain', @ho, DATEADD(DAY, -12, GETDATE()), 'BM 8821 KA',
       (SELECT SupplierID FROM dbo.Supplier WHERE SupplierCode = 'SUP-005'), 'DRIVER', @areaPT, N'Gilang Bewok', N'{"alasan":"demo"}'
UNION ALL
SELECT 'DetailVehicle', NULL, (SELECT IDVehicle FROM dbo.DetailVehicle WHERE NoVehicle = 'BA 9123 LK'), NULL, 'Plat tidak sesuai STNK',
       @ho, DATEADD(DAY, -5, GETDATE()), NULL, NULL, 'KENDARAAN', @areaPT, NULL, N'{"alasan":"demo"}'
UNION ALL
SELECT 'Supplier', NULL, NULL, (SELECT SupplierID FROM dbo.Supplier WHERE SupplierCode = 'SUP-005'), 'Mencampur buah busuk & batu di TBS',
       @ho, DATEADD(DAY, -3, GETDATE()), NULL, NULL, 'SUPPLIER', @areaHO, NULL, N'{"alasan":"demo"}';
UPDATE u SET BlacklistID = b.id FROM dbo.Users u JOIN dbo.Blacklist x ON x.UserID = u.UserID JOIN @bl b ON b.id = x.BlacklistID;
UPDATE k SET BlacklistID = b.id FROM dbo.DetailVehicle k JOIN dbo.Blacklist x ON x.IDVehicle = k.IDVehicle JOIN @bl b ON b.id = x.BlacklistID;
UPDATE s SET BlacklistID = b.id FROM dbo.Supplier s JOIN dbo.Blacklist x ON x.SupplierID = s.SupplierID JOIN @bl b ON b.id = x.BlacklistID;
-- Riwayat: pernah diblacklist lalu dicabut lewat persetujuan
INSERT INTO dbo.Blacklist (TableName, UserID, Reason, CreateBy, CreateDate, RevokeDate, RevokeBy, RevokeReason, CategoryCode, CompAreaID)
VALUES ('Users', @p + 22, 'Membawa penumpang tanpa izin', @ho, DATEADD(DAY, -60, GETDATE()), DATEADD(DAY, -30, GETDATE()), @ho,
        N'Sudah mendapat pembinaan, surat pernyataan ditandatangani', 'DRIVER', @areaPT);
-- Deteksi blacklist (Log Validasi)
INSERT INTO dbo.BlacklistDetection (DetectDate, CompAreaID, UserID, IDVehicle, NoVehicle, Source, Action, FaceDistance, Description, CreateBy)
VALUES (DATEADD(HOUR, -3, GETDATE()), @areaPT, @p + 27, NULL, 'BM 8821 KA', 'SCAN_WAJAH', 'DITOLAK', 0.29, N'Supir mencoba masuk lewat pos', @sec),
       (DATEADD(DAY, -1, GETDATE()), @areaPT, NULL, (SELECT IDVehicle FROM dbo.DetailVehicle WHERE NoVehicle = 'BA 9123 LK'), 'BA 9123 LK',
        'PLAT', 'PERINGATAN', NULL, N'Plat terbaca di pos', @sec);

/* ---------- Pengajuan menunggu persetujuan + contoh alur berjenjang ---------- */
DECLARE @lvHO INT = (SELECT LevelDetID FROM dbo.LevelDetails WHERE LevelDetCode = 'HO');
INSERT INTO dbo.ApprovalFlow (RequestType, CategoryCode, Description) VALUES ('BLACKLIST_TAMBAH', 'DRIVER', N'Blacklist supir: disetujui Head Office');
INSERT INTO dbo.ApprovalFlowStep (ApprovalFlowID, StepNo, LevelDetID) SELECT ApprovalFlowID, 1, @lvHO FROM dbo.ApprovalFlow WHERE CategoryCode = 'DRIVER';
DECLARE @aju INT;
INSERT INTO dbo.ApprovalRequest (RequestType, TotalSteps, CurrentStep, CompID, CompAreaID, Target, Title, Reason, Data, RequestBy, CategoryCode)
VALUES ('BLACKLIST_TAMBAH', 1, 1, 'PT', @areaPT, 'PERSONEL:' + CAST(@p + 24 AS VARCHAR(20)), N'Tambah blacklist DRV-004 · Dedi Kurniawan',
        N'Kedapatan membuang sampah di area timbangan & berkata kasar ke petugas',
        N'{"tipe":"PERSONEL","id_target":' + CAST(@p + 24 AS VARCHAR(20)) + N',"no_surat":null,"alasan":"Kedapatan membuang sampah di area timbangan & berkata kasar ke petugas","file_info":null,"tgl":null,"terkait":{"no_plat":"BK 1450 XY","id_customer":null,"id_pengangkutan":null},"alias":null,"kategori":"DRIVER","id_area":' + CAST(@areaPT AS VARCHAR(20)) + N',"_info":{"nama":"Dedi Kurniawan","nik":"1471020202830024","kategori":"Driver","produk":"TBS","alias":null,"plat":"BK 1450 XY","supplier":null,"pengangkutan":null}}',
        @sec, 'DRIVER');
SET @aju = SCOPE_IDENTITY();
INSERT INTO dbo.ApprovalRequestStep (RequestID, StepNo, LevelDetID) VALUES (@aju, 1, @lvHO);
INSERT INTO dbo.ApprovalHistory (RequestID, StepNo, Action, UserID, Notes) VALUES (@aju, 0, 'DIAJUKAN', @sec, N'Kedapatan membuang sampah di area timbangan');

COMMIT TRANSACTION;
PRINT 'Data demo berhasil dibuat. Login: ho / security / operator / sortasi / lab, password Demo12345!';
GO
SET NOEXEC OFF;
GO
