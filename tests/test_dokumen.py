import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

sys.modules.setdefault("pyodbc", MagicMock())

from utils.dokumen import buat_dokumen


class CursorPalsu:
    def __init__(self, jenis):
        self.jenis, self.sql, self._hasil = jenis, [], None

    def execute(self, sql, *params):
        self.sql.append((sql.split()[0], params))
        if "FROM jenis_dokumen" in sql:
            self._hasil = self.jenis
        elif "OUTPUT INSERTED.id_dokumen" in sql:
            self._hasil = (77,)

    def fetchone(self):
        return self._hasil


INFO = {"file_path": "uploads/dokumen/ba_void/x.pdf", "nama_asli": "ba.pdf", "mime": "application/pdf",
        "ukuran_byte": 10, "sha256": "a" * 64}


class TestBuatDokumen(unittest.TestCase):
    def test_dokumen_dan_file(self):
        c = CursorPalsu(NS(id_jenis=2, wajib_file=True))
        self.assertEqual(buat_dokumen(c, "BA_VOID", "BA/1", "2026-10-05", "Void", [INFO, INFO], 1), 77)
        self.assertEqual([s for s, _ in c.sql], ["SELECT", "INSERT", "INSERT", "INSERT"])
        self.assertEqual(c.sql[3][1][-1], 2)                      # urutan file kedua

    def test_wajib_file(self):
        with self.assertRaises(ValueError):
            buat_dokumen(CursorPalsu(NS(id_jenis=1, wajib_file=True)), "SURAT_BLACKLIST", "1", "2026-10-05", None, [], 1)
        self.assertEqual(buat_dokumen(CursorPalsu(NS(id_jenis=3, wajib_file=False)), "COA", "1", "2026-10-05", None, [], 1), 77)

    def test_jenis_tidak_dikenal(self):
        with self.assertRaises(ValueError):
            buat_dokumen(CursorPalsu(None), "XX", "1", "2026-10-05", None, [INFO], 1)


if __name__ == "__main__":
    unittest.main()
