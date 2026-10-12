import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

sys.modules.setdefault("face_recognition", MagicMock())

from utils import face_cache, face_utils


def mata(ear):
    """6 titik mata dengan EAR tertentu (lebar 2, tinggi 2*ear)."""
    h = ear * 2
    return [(0, 0), (0.5, h / 2), (1.5, h / 2), (2, 0), (1.5, -h / 2), (0.5, -h / 2)]


def landmark(rasio, ear=0.3):
    # hidung di x=0; mata kiri berjarak `rasio`, mata kanan berjarak 1 -> hitung_rasio_yaw = rasio
    return {"nose_tip": [(0, 0)], "left_eye": [(-rasio + p[0], p[1]) for p in mata(ear)],
            "right_eye": [(-1 + p[0], p[1]) for p in mata(ear)]}


class TestKonsisten(unittest.TestCase):
    def setUp(self):
        data = [(1, "A", np.zeros(128)), (2, "B", np.full(128, 0.1))]       # jarak A-B = 1.13
        p = patch.object(face_cache, "semua_embedding", return_value=data)
        p.start()
        self.addCleanup(p.stop)

    def test_semua_frame_harus_orang_sama(self):
        dekat_a = np.full(128, 0.02)                                       # jarak ke A 0.23
        self.assertEqual(face_cache.cari_terdekat_konsisten([dekat_a, dekat_a], 0.5)[0], 1)
        jauh = np.full(128, 0.05)                                          # jarak ke A 0.57, ke B 0.57
        id_, _, jarak = face_cache.cari_terdekat_konsisten([dekat_a, jauh], 0.5)
        self.assertIsNone(id_)                                             # satu frame meleset = ditolak
        self.assertAlmostEqual(jarak, float(np.linalg.norm(jauh)), places=5)
        self.assertIsNone(face_cache.cari_terdekat_konsisten([dekat_a, np.full(128, 0.09)], 0.5)[0])   # A vs B

    def test_kosong(self):
        self.assertEqual(face_cache.cari_terdekat_konsisten([], 0.5), (None, None, None))


class TestFrontal(unittest.TestCase):
    def test_pilih_frame_lurus_mata_terbuka(self):
        frames = [f"f{i}" for i in range(15)]
        # f0 lurus, f1 menoleh, f2 lurus tapi merem, f13 menoleh, f14 agak lurus; frame tengah tidak dinilai
        lm = {"f0": landmark(1.0), "f1": landmark(3.0), "f2": landmark(1.0, ear=0.1),
              "f13": landmark(0.3), "f14": landmark(1.2)}
        fr = face_utils.face_recognition
        fr.load_image_file.side_effect = lambda p: p
        fr.face_locations.side_effect = lambda img: [(0, 1, 1, 0)]
        fr.face_landmarks.side_effect = lambda img, lok: [lm[img]]
        fr.face_encodings.side_effect = lambda img, lok: [img]
        embeddings, wajah, terbaik = face_utils.embedding_frontal(frames)
        self.assertEqual((embeddings, wajah, terbaik), (["f0", "f14"], 1, "f0"))
        self.assertNotIn("f7", [c.args[0] for c in fr.load_image_file.call_args_list])

    def test_dua_wajah_dilewati(self):
        fr = face_utils.face_recognition
        fr.load_image_file.side_effect = lambda p: p
        fr.face_locations.side_effect = lambda img: [(0, 1, 1, 0), (2, 3, 3, 2)]
        embeddings, wajah, terbaik = face_utils.embedding_frontal(["a", "b", "c"])
        self.assertEqual((embeddings, wajah, terbaik), ([], 2, None))


if __name__ == "__main__":
    unittest.main()
