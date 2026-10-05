import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, patch

for _m in ("pyodbc", "serial", "face_recognition", "cv2", "mediapipe"):
    sys.modules.setdefault(_m, MagicMock())

from utils import serial_reader

JT1 = {"id_jembatan": 1, "kode": "JT-1", "port": "COM3", "is_active": True}
JT2 = {"id_jembatan": 2, "kode": "JT-2", "port": "COM4", "is_active": True}


class TestSerialPerPort(unittest.TestCase):
    def setUp(self):
        serial_reader._pembaca.clear()
        for port, berat in (("COM3", 1000), ("COM4", 2000)):
            serial_reader._pembaca[port] = {"state": {**serial_reader._state_baru(), "berat": berat, "terhubung": True},
                                            "riwayat": {"berat_terakhir": 5, "waktu_mulai_stabil": 1}, "baudrate": 9600}

    def test_status_per_port(self):
        self.assertEqual(serial_reader.baca_status_asli("COM4")["berat"], 2000)
        self.assertEqual(serial_reader.baca_status_asli()["berat"], 1000)            # bawaan: port pertama
        self.assertFalse(serial_reader.baca_status_asli("COM9")["terhubung"])       # port belum dibaca
        serial_reader.reset_deteksi_stabil("COM4")
        self.assertIsNone(serial_reader._pembaca["COM4"]["riwayat"]["berat_terakhir"])
        self.assertEqual(serial_reader._pembaca["COM3"]["riwayat"]["berat_terakhir"], 5)
        self.assertEqual(len(serial_reader.semua_status()), 2)


class TestTimbangKeluarJembatanSama(unittest.TestCase):
    def setUp(self):
        import os
        os.environ.setdefault("SECRET_KEY", "a" * 64)
        os.environ.setdefault("HASH_SECRET_KEY", "b" * 64)
        import app as appmod
        self.app = appmod.app
        self.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, LOGIN_DISABLED=True)
        import routes.timbangan as rtb
        self.rtb = rtb

    def _simpan(self, jembatan, data_lama):
        trx = NS(status_alur="TIMBANG_2", kategori="TBS")
        with patch.object(self.rtb, "jembatan_dipilih", return_value=jembatan), \
                patch.object(self.rtb, "baca_status_asli", return_value={"siap_kunci": True, "berat": 15000}), \
                patch.object(self.rtb, "cari_transaksi_aktif", return_value=trx), \
                patch.object(self.rtb, "get_data_timbangan", return_value=data_lama), \
                patch.object(self.rtb, "simpan_timbang_kedua", return_value=9000) as kedua, \
                patch.object(self.rtb, "reset_deteksi_stabil"), patch.object(self.rtb, "catat_timeline"), \
                patch("utils.hak_akses.boleh", return_value=True), \
                patch("utils.hak_akses.current_user", NS(is_authenticated=True, role="OPERATOR_TIMBANG")), \
                patch("routes.timbangan.current_user", NS(id=1)):
            hasil = self.rtb.timbang_simpan()
            resp, kode = hasil if isinstance(hasil, tuple) else (hasil, 200)
            return (resp, kode), kedua

    def test_tanpa_jembatan_dan_beda_jembatan(self):
        lama = NS(berat_netto=None, berat_bruto=24000, berat_tara=None, id_jembatan=1, kode_jembatan="JT-1", total_potongan_kg=None)
        with self.app.test_request_context("/api/timbang/simpan", method="POST", data={"no_tiket": "TKT-1"}):
            (resp, kode), _ = self._simpan(None, lama)
            self.assertEqual(kode, 400)
            self.assertIn("Pilih jembatan", resp.get_json()["error"])
            (resp, kode), kedua = self._simpan(JT2, lama)
            self.assertEqual(kode, 400)
            self.assertIn("harus di JT-1", resp.get_json()["error"])
            kedua.assert_not_called()
            (resp, kode), kedua = self._simpan(JT1, lama)
            self.assertEqual(kode, 200, resp.get_json())
            kedua.assert_called_once()


if __name__ == "__main__":
    unittest.main()
