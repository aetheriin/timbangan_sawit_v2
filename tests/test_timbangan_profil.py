import sys
import time
import unittest
from unittest.mock import MagicMock

try:
    import serial  # noqa: F401  (pyserial asli bila terpasang: port loop:// dipakai di tes)
except ImportError:
    sys.modules["serial"] = MagicMock()

from utils import serial_reader as sr


def cfg(**ubah):
    return {**sr.BAWAAN, **ubah}


class TestParser(unittest.TestCase):
    def test_format_bawaan_st_gs(self):
        self.assertEqual(sr.parse("ST,GS,+00024150kg", cfg()), (24150.0, True))
        self.assertEqual(sr.parse("US,GS,+00024130kg", cfg()), (24130.0, False))
        self.assertEqual(sr.parse("rusak", cfg()), (None, False))

    def test_angka_dan_faktor(self):
        self.assertEqual(sr.parse("WN0012340kg", cfg(format_data="ANGKA")), (12340.0, False))
        self.assertEqual(sr.parse("ST  24.15 t", cfg(format_data="ANGKA", faktor=1000)), (24150.0, True))
        self.assertEqual(sr.parse("+0024,15", cfg(format_data="ANGKA", faktor=1000)), (24150.0, False))  # koma desimal

    def test_terbalik_xk3190(self):
        self.assertEqual(sr.parse("0.43210", cfg(format_data="TERBALIK")), (1234.0, False))
        self.assertEqual(sr.parse("0.05142", cfg(format_data="TERBALIK")), (24150.0, False))

    def test_pola_sendiri(self):
        c = cfg(format_data="POLA", pola=r"(?P<stabil>S)?\s*G\s*(?P<berat>\d+)")
        self.assertEqual(sr.parse("S G 24150", c), (24150.0, True))
        self.assertEqual(sr.parse("  G 100", c), (100.0, False))
        self.assertEqual(sr.parse("x", cfg(format_data="POLA", pola="(")), (None, False))  # regex rusak tidak crash

    def test_bingkai(self):
        frames, sisa = sr.bingkai("a\r\nb\r\nc", "ST_GS")
        self.assertEqual((frames, sisa), (["a", "b"], "c"))
        frames, sisa = sr.bingkai("=0.43210=0.43210=0.4", "TERBALIK")
        self.assertEqual((frames, sisa), (["0.43210", "0.43210"], "=0.4"))


class TestStabilDanAgen(unittest.TestCase):
    def setUp(self):
        sr._pembaca.clear()
        sr.atur([{"id_jembatan": 7, "kode": "JT-7", "is_active": True, **cfg(mode="AGEN", format_data="ANGKA",
                                                                                durasi_stabil=0.5, toleransi_kg=5)}])

    def test_agen_stabil_setelah_durasi(self):
        sr.terima_dari_agen(7, "24150 kg\r\n")
        self.assertFalse(sr.baca_status(7)["siap_kunci"])
        time.sleep(0.6)
        sr.terima_dari_agen(7, "24152 kg\r\n")            # selisih 2 kg < toleransi 5 kg
        st = sr.baca_status(7)
        self.assertTrue(st["terhubung"] and st["siap_kunci"])
        self.assertEqual(st["berat"], 24152.0)
        sr.terima_dari_agen(7, "24300 kg\r\n")            # truk bergerak -> mulai hitung lagi
        self.assertFalse(sr.baca_status(7)["siap_kunci"])
        self.assertEqual(sr.data_mentah(7)["baris"][0]["teks"], "24300 kg")

    def test_agen_putus_dan_mode_lokal_ditolak(self):
        sr.terima_dari_agen(7, "")
        sr._pembaca[7]["terakhir"] = time.time() - 10
        st = sr.baca_status(7)
        self.assertFalse(st["terhubung"])
        self.assertIn("Agen", st["error"])
        sr.atur([{"id_jembatan": 8, "kode": "JT-8", "is_active": True, **cfg(mode="LOKAL", port="loop://")}])
        self.assertIsNone(sr.terima_dari_agen(8, "1"))        # jembatan mode lokal tidak menerima data agen
        self.assertNotIn(7, sr._pembaca)                       # jembatan yang tidak ada di daftar dihentikan
        sr._pembaca[8]["stop"] = True

    def test_wajib_st_dan_versi(self):
        sr.atur([{"id_jembatan": 7, "kode": "JT-7", "is_active": True, **cfg(mode="AGEN", format_data="ANGKA",
                  durasi_stabil=0.5, wajib_st=True)}])
        sr.terima_dari_agen(7, "US 1000\r\n")
        time.sleep(0.6)
        sr.terima_dari_agen(7, "US 1000\r\n")
        self.assertFalse(sr.baca_status(7)["siap_kunci"])        # stabil di software tapi indikator belum ST
        sr.terima_dari_agen(7, "ST 1000\r\n")
        self.assertTrue(sr.baca_status(7)["siap_kunci"])
        v = sr.konfigurasi(7)["versi"]
        sr.atur([{"id_jembatan": 7, "kode": "JT-7", "is_active": True, **cfg(mode="AGEN", baudrate=2400)}])
        self.assertEqual(sr.konfigurasi(7)["versi"], v + 1)      # agen akan menyambung ulang dengan baudrate baru


if __name__ == "__main__":
    unittest.main()
