"""Embedding wajah personel aktif di memori server.

Sebelumnya setiap scan membaca SEMUA embedding dari database lalu mengubahnya ke numpy satu per satu.
Sekarang dimuat sekali, lalu dimuat ulang hanya bila personel ditambah / diubah / dihapus (invalidate()).
Juga membatasi proses face recognition yang berjalan bersamaan supaya CPU tidak penuh dan web tetap responsif."""
import os
import threading
from contextlib import contextmanager
import numpy as np

_lock = threading.Lock()
_data = None            # list[(id_personel, nama, np.ndarray)]

# Maks proses wajah (dlib) sekaligus; request lain menunggu giliran, bukan membuat server macet
SLOT_PROSES_WAJAH = threading.BoundedSemaphore(int(os.getenv("MAKS_PROSES_WAJAH", "2")))


class ServerSibuk(Exception):
    """Semua slot proses wajah terpakai terlalu lama -> 503 (ditangani web_setup)."""


@contextmanager
def slot_proses_wajah(timeout=30):
    if not SLOT_PROSES_WAJAH.acquire(timeout=timeout):
        raise ServerSibuk()
    try:
        yield
    finally:
        SLOT_PROSES_WAJAH.release()


def _muat():
    from utils.db_utils import get_all_driver_embeddings
    hasil = []
    for id_personel, nama, emb_bin in get_all_driver_embeddings():
        if emb_bin is not None:
            hasil.append((id_personel, nama, np.frombuffer(emb_bin, dtype=np.float64)))
    return hasil


def semua_embedding():
    global _data
    with _lock:
        if _data is None:
            _data = _muat()
        return _data


def invalidate():
    global _data
    with _lock:
        _data = None


def cari_terdekat(embedding, ambang, exclude_id=None):
    """(id_personel, nama, jarak) terdekat; id/nama None bila jarak > ambang atau belum ada data."""
    data = [d for d in semua_embedding() if d[0] != exclude_id] if exclude_id else semua_embedding()
    if not data:
        return None, None, None
    matriks = np.stack([e for _, _, e in data])
    jarak = np.linalg.norm(matriks - embedding, axis=1)
    i = int(np.argmin(jarak))
    if jarak[i] > ambang:
        return None, None, float(jarak[i])
    return data[i][0], data[i][1], float(jarak[i])
