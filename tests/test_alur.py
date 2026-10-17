import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyodbc", MagicMock())

from utils import alur

PETA = {1: {"kode": "TBS", "nama": "TBS", "is_active": True, "tahap": ["SECURITY", "TIMBANG_1", "SORTASI", "TIMBANG_2"]},
        2: {"kode": "PKS", "nama": "PKS", "is_active": True, "tahap": ["SECURITY", "TIMBANG_1", "LAB", "TIMBANG_2"]},
        3: {"kode": "TIMBANG_SAJA", "nama": "TS", "is_active": True, "tahap": ["SECURITY", "TIMBANG_1"]},
        4: {"kode": "LANGSUNG", "nama": "Tanpa inspeksi", "is_active": False, "tahap": ["SECURITY", "TIMBANG_1", "TIMBANG_2"]}}

@patch.object(alur, "peta_alur", lambda: PETA)
class TestAlur(unittest.TestCase):
    def test_status_setelah(self):
        self.assertEqual(alur.status_setelah(1, "SECURITY"), "SECURITY_REGISTER")
        self.assertEqual(alur.status_setelah(1, "TIMBANG_1"), "TIMBANG_1")      # menunggu sortasi
        self.assertEqual(alur.status_setelah(2, "LAB"), "TIMBANG_2")
        self.assertEqual(alur.status_setelah(1, "TIMBANG_2"), "SELESAI")
        self.assertEqual(alur.status_setelah(3, "TIMBANG_1"), "SELESAI")        # penimbangan saja
        self.assertEqual(alur.status_setelah(4, "TIMBANG_1"), "TIMBANG_2")      # alur tanpa inspeksi

    def test_menunggu_dan_tahap(self):
        self.assertEqual(alur.menunggu(1, "TIMBANG_1"), "sortasi")
        self.assertEqual(alur.menunggu(2, "TIMBANG_1"), "hasil lab (Diterima)")
        self.assertEqual(alur.menunggu(1, "SECURITY_REGISTER"), "timbang masuk")
        self.assertTrue(alur.punya_tahap(2, "LAB"))
        self.assertFalse(alur.punya_tahap(1, "LAB"))
        self.assertEqual(alur.tahap_alur(99), [])

    def test_alur_tiket_dan_daftar(self):
        self.assertEqual(alur.alur_tiket("PENIMBANGAN_SAJA", 1), 3)            # penimbangan saja: TIMBANG_SAJA
        self.assertEqual(alur.alur_tiket("PEMBELIAN", 2), 2)                   # selain itu alur produk
        self.assertEqual(alur.id_alur_kode("TIMBANG_SAJA"), 3)
        self.assertEqual([a["id_alur"] for a in alur.daftar_alur()], [1, 2, 3])

if __name__ == "__main__":
    unittest.main()
