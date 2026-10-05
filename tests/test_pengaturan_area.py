import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyodbc", MagicMock())

from utils import pengaturan

CACHE = {"waktu": 0.0, "data": {"AMBANG_WAJAH": "0.5", "SESI_IDLE_MENIT": "60"},
         "area": {2: {"AMBANG_WAJAH": "0.45", "SESI_IDLE_MENIT": "5"}}}


@patch.object(pengaturan, "_muat", lambda: CACHE)
class TestPengaturanArea(unittest.TestCase):
    def test_area_menimpa_global_hanya_per_area(self):
        self.assertEqual(pengaturan.nilai("AMBANG_WAJAH"), 0.5)
        self.assertEqual(pengaturan.nilai("AMBANG_WAJAH", 2), 0.45)
        self.assertEqual(pengaturan.nilai("AMBANG_WAJAH", 3), 0.5)            # area tanpa nilai sendiri -> global
        self.assertEqual(pengaturan.nilai("SESI_IDLE_MENIT", 2), 60)          # keamanan selalu global

    def test_semua_per_area(self):
        daftar = {p["kunci"]: p for p in pengaturan.semua(2)}
        self.assertEqual(set(daftar), set(pengaturan.PER_AREA))
        self.assertEqual(daftar["AMBANG_WAJAH"]["sumber"], "Area")
        self.assertEqual(daftar["AMBANG_WAJAH"]["bawaan"], 0.5)
        self.assertTrue(daftar["WAJIB_SCAN_WAJAH"]["sumber"].startswith("Global"))

    def test_simpan_keamanan_per_area_ditolak(self):
        with self.assertRaises(ValueError):
            pengaturan.simpan({"SESI_IDLE_MENIT": "30"}, 1, id_comp_area=2)


if __name__ == "__main__":
    unittest.main()
