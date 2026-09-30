import sys
import time
import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from utils.cache import cache_ttl


class TestCacheTTL(unittest.TestCase):
    def test_hasil_disimpan_sampai_kadaluarsa(self):
        panggil = []

        @cache_ttl(0.2)
        def data(x):
            panggil.append(x)
            return x * 2

        self.assertEqual(data(2), 4)
        self.assertEqual(data(2), 4)
        self.assertEqual(len(panggil), 1)          # kedua dari cache
        time.sleep(0.25)
        data(2)
        self.assertEqual(len(panggil), 2)          # kadaluarsa -> ambil ulang

    def test_hapus_mengosongkan_cache(self):
        panggil = []

        @cache_ttl(60)
        def data():
            panggil.append(1)
            return 1

        data()
        data.hapus()
        data()
        self.assertEqual(len(panggil), 2)


class TestFaceCache(unittest.TestCase):
    def setUp(self):
        sys.modules.setdefault("pyodbc", MagicMock())
        from utils import face_cache
        self.fc = face_cache
        self.data = [(6, "Budi", np.zeros(128)), (11, "Siti", np.full(128, 0.1)), (21, "Dedi", np.ones(128))]

    def test_terdekat_di_bawah_ambang(self):
        with patch.object(self.fc, "semua_embedding", return_value=self.data):
            id_p, nama, jarak = self.fc.cari_terdekat(np.full(128, 0.09), 0.55)
        self.assertEqual((id_p, nama), (11, "Siti"))
        self.assertLess(jarak, 0.55)

    def test_tidak_ada_yang_cukup_mirip(self):
        with patch.object(self.fc, "semua_embedding", return_value=self.data):
            id_p, _, jarak = self.fc.cari_terdekat(np.full(128, 0.5), 0.55)
        self.assertIsNone(id_p)
        self.assertGreater(jarak, 0.55)

    def test_exclude_id(self):
        with patch.object(self.fc, "semua_embedding", return_value=self.data):
            id_p, _, _ = self.fc.cari_terdekat(np.full(128, 0.1), 2.0, exclude_id=11)
        self.assertNotEqual(id_p, 11)

    def test_slot_proses_wajah_penuh(self):
        slot = self.fc.SLOT_PROSES_WAJAH
        diambil = []
        while slot.acquire(blocking=False):
            diambil.append(1)
        try:
            with self.assertRaises(self.fc.ServerSibuk):
                with self.fc.slot_proses_wajah(timeout=0.05):
                    pass
        finally:
            for _ in diambil:
                slot.release()


if __name__ == "__main__":
    unittest.main()
