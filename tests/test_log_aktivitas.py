import json
import sys
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyodbc", MagicMock())

from utils import log_aktivitas


class TestCatat(unittest.TestCase):
    def test_ikut_cursor_pemanggil_dan_json(self):
        cur = MagicMock()
        log_aktivitas.catat("PERSONEL", "UPDATE", tabel="personel", id_baris=7, lama={"nama": "Budi"},
                            baru={"nama": "Budí", "waktu": datetime(2026, 10, 1, 8, 0), "kg": Decimal("1.5")},
                            user_id=3, cursor=cur)
        args = cur.execute.call_args[0]
        self.assertIn("sp_catat_log", args[0])
        self.assertEqual(args[1:5], ("PERSONEL", "UPDATE", "personel", "7"))
        self.assertEqual(json.loads(args[5]), {"nama": "Budi"})
        self.assertEqual(json.loads(args[6]), {"nama": "Budí", "waktu": "2026-10-01T08:00:00", "kg": 1.5})
        self.assertEqual(args[7], 3)

    def test_tanpa_cursor_gagal_tidak_melempar(self):
        with patch.object(log_aktivitas, "get_connection", side_effect=RuntimeError("DB mati")):
            log_aktivitas.catat("ADMIN", "USER_TAMBAH", user_id=1)          # tidak error


if __name__ == "__main__":
    unittest.main()
