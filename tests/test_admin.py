import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyodbc", MagicMock())

from utils import pengaturan, login_guard, sesi_aktif, kiosk
from utils.keamanan import _area_admin


class TestPengaturan(unittest.TestCase):
    def setUp(self):
        pengaturan.hapus_cache()

    def test_bawaan_bila_db_kosong(self):
        with patch.object(pengaturan, "_dari_db", return_value={}), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOGIN_KUNCI_MENIT", None)
            self.assertEqual(pengaturan.nilai("LOGIN_KUNCI_MENIT"), 15)
            self.assertIs(pengaturan.nilai("WAJIB_SCAN_WAJAH"), os.getenv("WAJIB_SCAN_WAJAH", "true") == "true")

    def test_urutan_db_lalu_env(self):
        with patch.dict(os.environ, {"LOGIN_KUNCI_MENIT": "30"}):
            with patch.object(pengaturan, "_dari_db", return_value={}):
                self.assertEqual(pengaturan.nilai("LOGIN_KUNCI_MENIT"), 30)
            with patch.object(pengaturan, "_dari_db", return_value={"LOGIN_KUNCI_MENIT": "45"}):
                self.assertEqual(pengaturan.nilai("LOGIN_KUNCI_MENIT"), 45)
            with patch.object(pengaturan, "_dari_db", return_value={"LOGIN_KUNCI_MENIT": "rusak"}):
                self.assertEqual(pengaturan.nilai("LOGIN_KUNCI_MENIT"), 30)

    def test_validasi(self):
        self.assertEqual(pengaturan.validasi("LOGIN_KUNCI_MENIT", "20"), "20")
        self.assertEqual(pengaturan.validasi("WAJIB_SCAN_WAJAH", "on"), "true")
        self.assertEqual(pengaturan.validasi("AMBANG_WAJAH", "0.5"), "0.5")
        for kunci, teks in (("LOGIN_KUNCI_MENIT", "0"), ("AMBANG_WAJAH", "0.9"), ("SESI_IDLE_MENIT", "abc"), ("TIDAK_ADA", "1")):
            with self.subTest(kunci=kunci), self.assertRaises(ValueError):
                pengaturan.validasi(kunci, teks)


class TestLoginGuardAdmin(unittest.TestCase):
    def setUp(self):
        login_guard._gagal.clear()
        login_guard._terkunci.clear()

    def test_ikut_pengaturan_dan_bisa_dibuka(self):
        nilai = {"LOGIN_MAKS_GAGAL": 3, "LOGIN_JENDELA_MENIT": 15, "LOGIN_KUNCI_MENIT": 20}
        with patch.object(pengaturan, "nilai", side_effect=nilai.get):
            for i in range(3):
                login_guard.catat_gagal("joko", "10.0.0.5", 1000 + i)
        self.assertEqual(login_guard.sisa_kunci("joko", "10.0.0.5", 1003), 20 * 60 - 1)
        terkunci = login_guard.daftar_terkunci(1003)
        self.assertEqual({t["kunci"] for t in terkunci}, {"u:joko", "ip:10.0.0.5"})
        self.assertTrue(login_guard.buka_kunci("u:joko"))
        self.assertTrue(login_guard.buka_kunci("ip:10.0.0.5"))
        self.assertEqual(login_guard.sisa_kunci("joko", "10.0.0.5", 1003), 0)
        self.assertFalse(login_guard.buka_kunci("u:joko"))


class TestSesiAktif(unittest.TestCase):
    def test_catat_dan_kedaluwarsa(self):
        sesi_aktif._sesi.clear()
        user = MagicMock(id=7, username="joko", nama_lengkap="Joko", role="SECURITY")
        sesi_aktif.catat("a", user, "10.0.0.1", "Chrome")
        sesi_aktif.catat("b", user, "10.0.0.2", "Edge")
        self.assertEqual(len(sesi_aktif.daftar(60)), 2)
        sesi_aktif._sesi["a"]["terakhir_aktif"] = time.time() - 120
        self.assertEqual([s["sid"] for s in sesi_aktif.daftar(60)], ["b"])
        sesi_aktif.hapus_user(7)
        self.assertEqual(sesi_aktif.daftar(60), [])


class TestKiosk(unittest.TestCase):
    def test_token_per_pos(self):
        tok = kiosk.token_baru()
        data = {"POS-A": (kiosk.hash_token(tok), True), "POS-B": (kiosk.hash_token(tok), False)}
        with patch.object(kiosk, "_perangkat", return_value=data):
            self.assertTrue(kiosk.token_cocok("POS-A", tok))
            self.assertFalse(kiosk.token_cocok("POS-A", tok + "x"))
            self.assertFalse(kiosk.token_cocok("POS-B", tok))          # nonaktif
            self.assertFalse(kiosk.token_cocok("POS-X", tok))          # tidak terdaftar
            self.assertFalse(kiosk.token_cocok("POS-A", ""))


class TestAreaAdmin(unittest.TestCase):
    def test_path(self):
        for path in ("/admin", "/admin/users", "/api/admin/users"):
            self.assertTrue(_area_admin(path), path)
        for path in ("/administrasi", "/weighbridge", "/api/personel", "/api/adminx"):
            self.assertFalse(_area_admin(path), path)


if __name__ == "__main__":
    unittest.main()
