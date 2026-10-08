import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyodbc", MagicMock())
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="wb_upload_"))

from PIL import Image
from werkzeug.datastructures import FileStorage

from utils import login_guard, verifikasi_state as verif
from utils.upload_utils import simpan_upload, simpan_frames, path_disk_dari_relatif


def _gambar(fmt="JPEG"):
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 10, 10)).save(buf, format=fmt)
    return buf.getvalue()


class TestLoginGuard(unittest.TestCase):
    def setUp(self):
        login_guard._gagal.clear()
        login_guard._terkunci.clear()

    def test_kunci_setelah_5_gagal(self):
        for i in range(4):
            self.assertFalse(login_guard.catat_gagal("ho", "10.0.0.1", 1000 + i))
        self.assertTrue(login_guard.catat_gagal("ho", "10.0.0.1", 1004))
        self.assertGreater(login_guard.sisa_kunci("ho", "10.0.0.9", 1005), 0)     # username terkunci
        self.assertGreater(login_guard.sisa_kunci("lain", "10.0.0.1", 1005), 0)   # IP terkunci
        self.assertEqual(login_guard.sisa_kunci("ho", "10.0.0.1", 1004 + 15 * 60 + 1), 0)

    def test_berhasil_menghapus_hitungan(self):
        for i in range(4):
            login_guard.catat_gagal("ho", "10.0.0.1", 1000 + i)
        login_guard.catat_berhasil("ho", "10.0.0.1")
        self.assertFalse(login_guard.catat_gagal("ho", "10.0.0.1", 1010))


class TestUpload(unittest.TestCase):
    def test_jpg_valid_dibersihkan(self):
        path, relatif = simpan_upload(FileStorage(io.BytesIO(_gambar()), "foto.JPG"), "personel")
        self.assertTrue(relatif.startswith("uploads/personel/") and relatif.endswith(".jpg"))
        self.assertTrue(os.path.isfile(path))

    def test_isi_bukan_gambar_ditolak(self):
        with self.assertRaises(ValueError):
            simpan_upload(FileStorage(io.BytesIO(b"<script>alert(1)</script>"), "foto.jpg"), "personel")

    def test_ekstensi_ditolak(self):
        with self.assertRaises(ValueError):
            simpan_upload(FileStorage(io.BytesIO(b"MZ..."), "virus.exe"), "personel")

    def test_pdf_harus_berisi_pdf(self):
        from utils.upload_utils import SURAT_EKSTENSI
        simpan_upload(FileStorage(io.BytesIO(b"%PDF-1.4 isi"), "surat.pdf"), "surat", SURAT_EKSTENSI)
        with self.assertRaises(ValueError):
            simpan_upload(FileStorage(io.BytesIO(_gambar()), "surat.pdf"), "surat", SURAT_EKSTENSI)

    def test_frame_dibatasi(self):
        frames = [FileStorage(io.BytesIO(_gambar()), f"f{i}.jpg") for i in range(21)]
        with self.assertRaises(ValueError):
            simpan_frames(frames, maks=20)

    def test_path_traversal_ditolak(self):
        self.assertIsNone(path_disk_dari_relatif("uploads/../../app.py"))
        self.assertIsNone(path_disk_dari_relatif("static/css/tailwind.css"))
        self.assertIsNotNone(path_disk_dari_relatif("uploads/personel/a.jpg"))


class TestVerifikasiPerPos(unittest.TestCase):
    DATA = dict(id_driver=6, nama="Budi", nik="1", no_sim="2", is_updated=False, foto_path=None,
                kode_personel="PRGBS-001", kategori="DRIVER", is_blacklisted=False)

    def test_hasil_hanya_untuk_pemilik(self):
        verif.simpan_hasil_user("POS-A", 1, **self.DATA)
        self.assertIsNone(verif.ambil("POS-A", user_id=2))          # user lain tidak bisa memakai
        self.assertEqual(verif.ambil("POS-A", user_id=1)["id_driver"], 6)

    def test_hasil_kedaluwarsa(self):
        verif.simpan_hasil_user("POS-C", 1, **self.DATA)
        verif._pos["POS-C"]["hasil"]["waktu"] = datetime.now() - verif.BERLAKU - timedelta(seconds=1)
        self.assertIsNone(verif.ambil("POS-C", 1))


class TestSecret(unittest.TestCase):
    def test_secret_contoh_ditolak(self):
        from utils.keamanan import cek_secret
        with patch.dict(os.environ, {"SECRET_KEY": "isi_dengan_random_string_panjang", "HASH_SECRET_KEY": "x" * 40}):
            with self.assertRaises(RuntimeError):
                cek_secret(MagicMock())
        with patch.dict(os.environ, {"SECRET_KEY": "a" * 64, "HASH_SECRET_KEY": "b" * 64}):
            cek_secret(MagicMock())


if __name__ == "__main__":
    unittest.main()


class TestTanpaScriptInline(unittest.TestCase):
    """CSP script-src 'self': template tidak boleh berisi onclick="..." / <script> inline / javascript:."""
    POLA = __import__("re").compile(r"""\son[a-z]+\s*=\s*["']|<script(?![^>]*\bsrc=)[^>]*>|javascript:""", __import__("re").I)

    def test_csp_tanpa_unsafe_inline_script(self):
        from utils.keamanan import CSP
        script_src = next(b for b in CSP.split(";") if b.strip().startswith("script-src"))
        self.assertNotIn("unsafe-inline", script_src)

    def test_template_bersih(self):
        akar = os.path.join(os.path.dirname(__file__), "..", "templates")
        for dirpath, _, files in os.walk(akar):
            for nama in files:
                path = os.path.join(dirpath, nama)
                with open(path, encoding="utf-8") as f:
                    for no, baris in enumerate(f, 1):
                        with self.subTest(file=nama, baris=no):
                            self.assertIsNone(self.POLA.search(baris), baris.strip())
