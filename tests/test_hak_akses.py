import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyodbc", MagicMock())

from flask import Flask
from utils import hak_akses

PETA = {3: {"FORM_SECURITY": {"tambah": True, "ubah": True, "hapus": False},
            "MASTER_DRIVER": {"tambah": True, "ubah": False, "hapus": False}}}


def user(id_level=3, is_admin=False, id_department=1, halaman_awal="/weighbridge?view=list"):
    return NS(is_authenticated=True, id_level=id_level, is_admin=is_admin, role="SECURITY",
              id_department=id_department, halaman_awal=halaman_awal)


# Department 2 (Security) hanya boleh Form › Security & Data Master › Driver; department 1 tidak dibatasi
PETA_DEPT = {2: {"FORM_SECURITY", "FORM", "MASTER_DRIVER", "MASTER"}}
SIDEBAR = [{"kode": "DASHBOARD", "url": "/dashboard"}, {"kode": "LIST", "url": "/weighbridge?view=list"},
           {"kode": "FORM", "url": "/weighbridge?view=form"}, {"kode": "MASTER", "url": "/master"}]


class TestDepartment(unittest.TestCase):
    def setUp(self):
        for p in (patch.object(hak_akses, "peta_akses", return_value=PETA),
                  patch.object(hak_akses, "peta_department", return_value=PETA_DEPT),
                  patch.object(hak_akses, "menu_sidebar", return_value=SIDEBAR)):
            p.start()
            self.addCleanup(p.stop)

    def test_department_membatasi_menu_dan_aksi(self):
        sec = user(id_department=2)
        self.assertTrue(hak_akses.boleh_lihat("FORM", sec))                     # induk ikut anaknya
        self.assertFalse(hak_akses.boleh_lihat("DASHBOARD", sec))
        self.assertTrue(hak_akses.boleh("FORM_SECURITY", "tambah", user=sec))
        self.assertFalse(hak_akses.boleh("FORM_SECURITY", "hapus", user=sec))   # aksi tetap dari level
        self.assertTrue(hak_akses.boleh_lihat("DASHBOARD", user(id_department=1)))   # tidak dibatasi
        self.assertFalse(hak_akses.boleh_lihat("DASHBOARD", user(is_admin=True)))

    def test_kode_halaman(self):
        self.assertEqual(hak_akses.kode_halaman("/weighbridge?view=form&tab=lab"), "FORM_LAB")
        self.assertEqual(hak_akses.kode_halaman("/weighbridge?view=form"), "FORM")
        self.assertEqual(hak_akses.kode_halaman("/weighbridge?tab=lab"), "LIST")
        self.assertEqual(hak_akses.kode_halaman("/tamu"), "KUNJUNGAN")
        self.assertIsNone(hak_akses.kode_halaman("/api/x"))

    def test_url_awal_dan_tab(self):
        self.assertEqual(hak_akses.url_awal(user(id_department=2)), "/weighbridge?view=form")
        self.assertEqual(hak_akses.url_awal(user(id_department=1)), "/weighbridge?view=list")
        with patch.object(hak_akses, "current_user", user(id_department=2)):
            self.assertEqual(hak_akses.tab_boleh(), ["security"])

    def test_penjaga_halaman(self):
        app = Flask(__name__)
        hak_akses.pasang_penjaga_menu(app)
        app.add_url_rule("/dashboard", "d", lambda: "ok")
        with patch.object(hak_akses, "current_user", user(id_department=2)):
            r = app.test_client().get("/dashboard")
            self.assertEqual((r.status_code, r.headers["Location"]), (302, "/weighbridge?view=form"))
        with patch.object(hak_akses, "current_user", user(id_department=1)):
            self.assertEqual(app.test_client().get("/dashboard").status_code, 200)


class TestBoleh(unittest.TestCase):
    def setUp(self):
        for p in (patch.object(hak_akses, "peta_akses", return_value=PETA),
                  patch.object(hak_akses, "peta_department", return_value={})):
            p.start()
            self.addCleanup(p.stop)

    def test_aksi_per_menu(self):
        u = user()
        self.assertTrue(hak_akses.boleh("FORM_SECURITY", "tambah", user=u))
        self.assertFalse(hak_akses.boleh("FORM_SECURITY", "hapus", user=u))
        self.assertTrue(hak_akses.boleh("MASTER_DRIVER", user=u))              # tanpa aksi = salah satu
        self.assertFalse(hak_akses.boleh("KONTRAK_DO", user=u))
        self.assertFalse(hak_akses.boleh("FORM_SECURITY", "tambah", user=user(id_level=9)))

    def test_admin_tanpa_aksi_operasional(self):
        self.assertFalse(hak_akses.boleh("FORM_SECURITY", "tambah", user=user(is_admin=True)))

    def test_izin_decorator(self):
        app = Flask(__name__)

        @hak_akses.izin(("PERSONEL", "MASTER_DRIVER"), "tambah")
        def tambah():
            return "ok"

        @hak_akses.izin("KONTRAK_DO", "ubah")
        def ubah_do():
            return "ok"

        with app.test_request_context("/x"), patch.object(hak_akses, "current_user", user()), \
                patch("utils.keamanan.log_keamanan"):
            self.assertEqual(tambah(), "ok")
            hasil, kode = ubah_do()
            self.assertEqual(kode, 403)


if __name__ == "__main__":
    unittest.main()
