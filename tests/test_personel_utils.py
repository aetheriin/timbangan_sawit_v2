import unittest
from utils.personel_utils import (format_id, format_nama_personel, kode_berikutnya, validasi_personel,
                                  daftar_perubahan)


class TestFormatPersonel(unittest.TestCase):
    def test_format_id_tiga_digit(self):
        self.assertEqual(format_id(6), "006")
        self.assertEqual(format_id(1234), "1234")

    def test_nama_dengan_kode(self):
        self.assertEqual(format_nama_personel("PRGBS-001", 6, "Budi Santoso"), "PRGBS-001 · Budi Santoso")

    def test_nama_tanpa_kode_pakai_id(self):
        self.assertEqual(format_nama_personel(None, 14, "Rudi Hartono"), "ID 014 · Rudi Hartono")


class TestKodeBerikutnya(unittest.TestCase):
    def test_kosong_mulai_001(self):
        self.assertEqual(kode_berikutnya([]), "PRGBS-001")

    def test_ambil_nomor_terbesar(self):
        self.assertEqual(kode_berikutnya(["PRGBS-001", "PRGBS-009", "prgbs-003"]), "PRGBS-010")

    def test_abaikan_format_lain(self):
        self.assertEqual(kode_berikutnya(["PRGBS-002", "HO-99", None, "PRGBS-X"]), "PRGBS-003")


class TestValidasiPersonel(unittest.TestCase):
    NIK = "1471021203850004"

    def test_valid(self):
        self.assertIsNone(validasi_personel(self.NIK, "Budi", "DRIVER", "1402-8812"))

    def test_driver_wajib_sim(self):
        self.assertIn("SIM", validasi_personel(self.NIK, "Budi", "DRIVER", None))

    def test_non_driver_boleh_tanpa_sim(self):
        self.assertIsNone(validasi_personel(self.NIK, "Siti", "EMPLOYEE", None))

    def test_nik_16_digit(self):
        self.assertIn("16 digit", validasi_personel("12345", "Budi", "SECURITY", None))

    def test_kategori_tidak_valid(self):
        self.assertIn("Kategori", validasi_personel(self.NIK, "Budi", "HO", None))


class TestDaftarPerubahan(unittest.TestCase):
    def test_hanya_kolom_yang_berubah(self):
        row = {"kode_personel_lama": None, "kode_personel_baru": "PRGBS-002", "nik_lama": "1", "nik_baru": "1",
               "nama_lama": "Siti", "nama_baru": "Siti R", "no_sim_lama": None, "no_sim_baru": ""}
        self.assertEqual(daftar_perubahan(row), [("kode_personel", None, "PRGBS-002"), ("nama", "Siti", "Siti R")])


if __name__ == "__main__":
    unittest.main()


class TestKategoriDinamis(unittest.TestCase):
    NIK = "1471021203850004"

    def test_tamu_tanpa_sim(self):
        self.assertIsNone(validasi_personel(self.NIK, "Tamu", "TAMU", None))

    def test_kategori_dari_tabel(self):
        kategori = {"DRIVER": {}, "OPERATOR_ALAT": {}}
        self.assertIn("SIM", validasi_personel(self.NIK, "Andi", "OPERATOR_ALAT", None, kategori, ["OPERATOR_ALAT"]))
        self.assertIsNone(validasi_personel(self.NIK, "Andi", "DRIVER", None, kategori, ["OPERATOR_ALAT"]))
        self.assertIn("Kategori", validasi_personel(self.NIK, "Andi", "TAMU", None, kategori, []))
