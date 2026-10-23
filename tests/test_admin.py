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
    def test_daftar_terkunci(self):
        rows = [{"Kunci": "ip:10.0.0.7", "SisaDetik": 900, "Dicoba": "asal4, asal3"},
                {"Kunci": "u:joko", "SisaDetik": 600, "Dicoba": None}]
        with patch.object(login_guard, "_exec", return_value=rows):
            hasil = login_guard.daftar_terkunci()
        self.assertEqual(hasil[0], {"kunci": "ip:10.0.0.7", "jenis": "IP", "nama": "10.0.0.7", "sisa_detik": 900,
                                    "dicoba": ["asal4", "asal3"]})
        self.assertEqual(hasil[1]["jenis"], "Username")
        self.assertEqual(hasil[1]["dicoba"], [])

    def test_buka_kunci_teks_username_dan_ip(self):
        with patch.object(login_guard, "_exec", side_effect=[[{"Dibuka": 0}], [{"Dibuka": 1}]]) as ex:
            self.assertEqual(login_guard.buka_kunci_teks(" 10.0.0.7 ", 5), 1)
        self.assertEqual([c[0][1] for c in ex.call_args_list], ["u:10.0.0.7", "ip:10.0.0.7"])
        with patch.object(login_guard, "_exec", return_value=[{"Dibuka": 2}]):
            self.assertEqual(login_guard.buka_semua(5), 2)


class TestSesiAktif(unittest.TestCase):
    def test_tulis_dibatasi_per_menit(self):
        sesi_aktif._terakhir_tulis.clear()
        user = MagicMock(id=7)
        with patch.object(sesi_aktif, "_jalankan") as jalan:
            sesi_aktif.catat("a", user, "10.0.0.1", "Chrome")                 # pertama -> ditulis
            sesi_aktif.catat("a", user, "10.0.0.1", "Chrome")                 # < 1 menit -> dilewati
            sesi_aktif.catat("a", user, "10.0.0.1", "Chrome", aktif=False)    # polling -> dilewati
            self.assertEqual(jalan.call_count, 1)
            sesi_aktif._terakhir_tulis["a"] -= 61
            sesi_aktif.catat("a", user, "10.0.0.1", "Chrome")
            self.assertEqual(jalan.call_count, 2)
            sesi_aktif.hapus("a", "PAKSA_KELUAR")
            self.assertNotIn("a", sesi_aktif._terakhir_tulis)
            self.assertEqual(jalan.call_args[0][1:], ("PAKSA_KELUAR", "a"))

    def test_gagal_db_tidak_menghentikan_request(self):
        with patch.object(sesi_aktif, "get_connection", side_effect=RuntimeError("tabel belum ada")):
            self.assertEqual(sesi_aktif.daftar(60), [])
            self.assertEqual(sesi_aktif.hapus_user(7), 0)
            self.assertIsNone(sesi_aktif.alasan_berakhir("x"))


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


class TestPasswordKedaluwarsa(unittest.TestCase):
    def test_aturan(self):
        from datetime import datetime, timedelta
        from utils.keamanan import password_wajib_diganti
        with patch.object(pengaturan, "nilai", return_value=90):
            self.assertIsNotNone(password_wajib_diganti(None))                                   # baru / direset admin
            self.assertIsNone(password_wajib_diganti(datetime.now() - timedelta(days=10)))
            self.assertIsNotNone(password_wajib_diganti(datetime.now() - timedelta(days=91)))
        with patch.object(pengaturan, "nilai", return_value=0):                                  # 0 = tidak kedaluwarsa
            self.assertIsNone(password_wajib_diganti(datetime.now() - timedelta(days=999)))


class TestPosKamera(unittest.TestCase):
    def test_pilihan_pos_per_pc(self):
        from flask import Flask
        from utils.keamanan import id_pos
        app = Flask(__name__)
        with patch.dict(os.environ, {"POS_DEFAULT": "UTAMA"}):
            for header, cookie, hasil in ((None, None, "UTAMA"), (None, "POS2", "POS2"), (None, "pos<x>", "UTAMA"),
                                          ("POS1", "POS2", "POS1")):
                h = {"Cookie": f"pos_kiosk={cookie}"} if cookie else {}
                if header:
                    h["X-Kiosk-Id"] = header
                with self.subTest(header=header, cookie=cookie), app.test_request_context("/", headers=h):
                    self.assertEqual(id_pos(), hasil)
