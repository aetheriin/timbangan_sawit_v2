import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyodbc", MagicMock())

from flask import Flask
from utils import hak_akses

PETA = {3: {"FORM_SECURITY": {"tambah": True, "ubah": True, "hapus": False},
            "MASTER_DRIVER": {"tambah": True, "ubah": False, "hapus": False}}}


def user(id_level=3, is_admin=False):
    return NS(is_authenticated=True, id_level=id_level, is_admin=is_admin, role="SECURITY")


class TestBoleh(unittest.TestCase):
    def setUp(self):
        p = patch.object(hak_akses, "peta_akses", return_value=PETA)
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
