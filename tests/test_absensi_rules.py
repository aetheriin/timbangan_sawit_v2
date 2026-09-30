import unittest
from datetime import datetime, time
from utils.absensi_rules import tentukan_jenis, is_duplikat, hitung_status_waktu, hari_iso

SENIN = {"is_libur": False, "jam_masuk": time(8, 0), "jam_pulang": time(17, 0), "toleransi_menit": 0}
SABTU = {"is_libur": False, "jam_masuk": time(8, 0), "jam_pulang": time(12, 0), "toleransi_menit": 0}
MINGGU = {"is_libur": True, "jam_masuk": None, "jam_pulang": None, "toleransi_menit": 0}


def jam(h, m, s=0):
    return datetime(2026, 9, 28, h, m, s)      # Senin


class TestJenis(unittest.TestCase):
    def test_scan_pertama_masuk(self):
        self.assertEqual(tentukan_jenis(False), "MASUK")

    def test_scan_berikutnya_pulang(self):
        self.assertEqual(tentukan_jenis(True), "PULANG")

    def test_duplikat_kurang_5_menit(self):
        self.assertTrue(is_duplikat(jam(8, 0), jam(8, 4, 59)))
        self.assertFalse(is_duplikat(jam(8, 0), jam(8, 5)))
        self.assertFalse(is_duplikat(None, jam(8, 0)))


class TestStatusWaktu(unittest.TestCase):
    def test_tepat_jam_masuk(self):
        self.assertEqual(hitung_status_waktu("MASUK", jam(8, 0, 59), SENIN), ("TEPAT_WAKTU", 0))

    def test_terlambat_satu_menit_tanpa_toleransi(self):
        self.assertEqual(hitung_status_waktu("MASUK", jam(8, 1), SENIN), ("TERLAMBAT", 1))

    def test_terlambat_12_menit(self):
        self.assertEqual(hitung_status_waktu("MASUK", jam(8, 12, 4), SENIN), ("TERLAMBAT", 12))

    def test_datang_lebih_awal(self):
        self.assertEqual(hitung_status_waktu("MASUK", jam(7, 45), SENIN), ("TEPAT_WAKTU", -15))

    def test_toleransi_dihormati(self):
        jadwal = {**SENIN, "toleransi_menit": 5}
        self.assertEqual(hitung_status_waktu("MASUK", jam(8, 5), jadwal), ("TEPAT_WAKTU", 5))
        self.assertEqual(hitung_status_waktu("MASUK", jam(8, 6), jadwal), ("TERLAMBAT", 6))

    def test_pulang_awal_senin(self):
        self.assertEqual(hitung_status_waktu("PULANG", jam(16, 30), SENIN), ("PULANG_AWAL", 30))

    def test_pulang_sabtu_jam_12(self):
        self.assertEqual(hitung_status_waktu("PULANG", jam(12, 0), SABTU), ("TEPAT_WAKTU", 0))
        self.assertEqual(hitung_status_waktu("PULANG", jam(13, 0), SABTU), ("TEPAT_WAKTU", -60))

    def test_minggu_libur(self):
        self.assertEqual(hitung_status_waktu("MASUK", jam(9, 0), MINGGU), ("HARI_LIBUR", None))
        self.assertEqual(hitung_status_waktu("MASUK", jam(9, 0), None), ("HARI_LIBUR", None))

    def test_hari_iso(self):
        self.assertEqual(hari_iso(datetime(2026, 9, 28)), 1)   # Senin
        self.assertEqual(hari_iso(datetime(2026, 10, 4)), 7)   # Minggu


if __name__ == "__main__":
    unittest.main()
