import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyodbc", MagicMock())

from utils import alur

PETA = {1: {"kode": "TBS", "nama": "TBS", "is_active": True, "tahap": ["SECURITY", "TIMBANG_1", "SORTASI", "TIMBANG_2"]},
        2: {"kode": "PKS", "nama": "PKS", "is_active": True, "tahap": ["SECURITY", "TIMBANG_1", "LAB", "TIMBANG_2"]},
        3: {"kode": "TIMBANG_SAJA", "nama": "TS", "is_active": True, "tahap": ["SECURITY", "TIMBANG_1"]},
        4: {"kode": "LANGSUNG", "nama": "Tanpa inspeksi", "is_active": False, "tahap": ["SECURITY", "TIMBANG_1", "TIMBANG_2"]}}
MILL = [{"id_mill": 1, "id_comp_area": 1, "kode": "TBS", "id_alur": 1, "is_active": False},
        {"id_mill": 2, "id_comp_area": 1, "kode": "TBS2", "id_alur": 1, "is_active": True},
        {"id_mill": 3, "id_comp_area": 2, "kode": "PKS", "id_alur": 2, "is_active": True}]


@patch.object(alur, "daftar_mill", lambda: MILL)
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
        self.assertEqual(alur.menunggu(2, "TIMBANG_1"), "hasil lab (Approve)")
        self.assertEqual(alur.menunggu(1, "SECURITY_REGISTER"), "timbang masuk")
        self.assertTrue(alur.punya_tahap(2, "LAB"))
        self.assertFalse(alur.punya_tahap(1, "LAB"))
        self.assertEqual(alur.tahap_alur(99), [])

    def test_pilih_mill_dan_daftar(self):
        self.assertEqual(alur.pilih_mill(1, 1)["id_mill"], 2)                  # mill nonaktif dilewati
        self.assertIsNone(alur.pilih_mill(1, 2))
        self.assertEqual(alur.id_alur_kode("TIMBANG_SAJA"), 3)
        self.assertEqual([a["id_alur"] for a in alur.daftar_alur()], [1, 2, 3])
        self.assertTrue(alur.kode_mill_dipakai(1, "TBS2"))
        self.assertFalse(alur.kode_mill_dipakai(1, "TBS2", kecuali=2))
        self.assertFalse(alur.kode_mill_dipakai(2, "TBS2"))


if __name__ == "__main__":
    unittest.main()
