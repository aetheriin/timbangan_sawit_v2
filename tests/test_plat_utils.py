import unittest
from utils.plat_utils import normalisasi_plat


class TestNormalisasiPlat(unittest.TestCase):
    def test_format_valid(self):
        kasus = {
            "BM 1455 JJ": "BM 1455 JJ",
            "bm1455jj": "BM 1455 JJ",
            "  bm  1455   jj ": "BM 1455 JJ",
            "BM-1455-JJ": "BM 1455 JJ",
            "BM.1455.JJ": "BM 1455 JJ",
            "A 1234 JJ": "A 1234 JJ",
            "A1234JJ": "A 1234 JJ",
            "AA 456 SJU": "AA 456 SJU",
            "aa456sju": "AA 456 SJU",
            "B 1 A": "B 1 A",
            "B 9": "B 9",
            "BK 8 ABC": "BK 8 ABC",
        }
        for masuk, harapan in kasus.items():
            with self.subTest(masuk=masuk):
                self.assertEqual(normalisasi_plat(masuk), (harapan, None))

    def test_format_tidak_valid(self):
        for masuk in ["", None, "1455 JJ", "BMX 1455 JJ", "BM 12345 JJ", "BM 0123 JJ",
                      "BM 1455 ABCD", "BM JJ", "BM 14A5 JJ", "BM_1455_JJ"]:
            with self.subTest(masuk=masuk):
                plat, error = normalisasi_plat(masuk)
                self.assertIsNone(plat)
                self.assertTrue(error)

    def test_kode_wilayah_tidak_dikenal(self):
        plat, error = normalisasi_plat("MB 1455 JJ")   # salah ketik dari BM
        self.assertIsNone(plat)
        self.assertIn("wilayah", error)


if __name__ == "__main__":
    unittest.main()
