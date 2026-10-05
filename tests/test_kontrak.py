import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("pyodbc", MagicMock())

from utils.db_kontrak import label_angkut
from utils.serializers import _angkut


class TestLabelAngkut(unittest.TestCase):
    def test_pengirim_penerima_ikut_jenis(self):
        self.assertEqual(label_angkut("PENGIRIM", "PEMBELIAN", "PT A"), "Kendaraan PT A (pengirim)")
        self.assertEqual(label_angkut("PENERIMA", "PEMBELIAN", "PT A"), "Kendaraan PT sendiri (penerima)")
        self.assertEqual(label_angkut("PENGIRIM", "PENJUALAN", "PT A"), "Kendaraan PT sendiri (pengirim)")
        self.assertEqual(label_angkut("PENERIMA", "PENJUALAN", "PT A"), "Kendaraan PT A (penerima)")
        self.assertEqual(label_angkut("PIHAK_KETIGA", "PENJUALAN", "PT A", "CV X"), "CV X (pihak ketiga)")

    def test_nilai_pilihan_form(self):
        self.assertEqual(_angkut("PIHAK_KETIGA", 5), "PIHAK_KETIGA:5")
        self.assertEqual(_angkut("PENERIMA", None), "PENERIMA")
        self.assertEqual(_angkut(None, None), "")


if __name__ == "__main__":
    unittest.main()
