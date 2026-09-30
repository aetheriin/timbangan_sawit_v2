"""Pembatas percobaan login: 5x gagal dalam 15 menit -> dikunci 15 menit (per username dan per IP).

Disimpan di memori proses (waitress = 1 proses), cukup untuk aplikasi di jaringan site."""
import os
import threading
import time

MAKS_GAGAL = int(os.getenv("LOGIN_MAKS_GAGAL", "5"))
JENDELA_DETIK = 15 * 60
KUNCI_DETIK = int(os.getenv("LOGIN_KUNCI_MENIT", "15")) * 60

_lock = threading.Lock()
_gagal = {}        # kunci -> [waktu gagal ...]
_terkunci = {}     # kunci -> waktu buka


def _kunci(username, ip):
    return [f"u:{(username or '').lower()}", f"ip:{ip}"]


def sisa_kunci(username, ip, sekarang=None):
    """Detik sampai boleh login lagi (0 = boleh)."""
    sekarang = sekarang or time.time()
    with _lock:
        return int(max([_terkunci.get(k, 0) - sekarang for k in _kunci(username, ip)] + [0]))


def catat_gagal(username, ip, sekarang=None):
    """Kembalikan True bila percobaan ini membuat akun / IP terkunci."""
    sekarang = sekarang or time.time()
    terkunci = False
    with _lock:
        for k in _kunci(username, ip):
            daftar = [t for t in _gagal.get(k, []) if sekarang - t < JENDELA_DETIK] + [sekarang]
            _gagal[k] = daftar
            if len(daftar) >= MAKS_GAGAL:
                _terkunci[k] = sekarang + KUNCI_DETIK
                _gagal[k] = []
                terkunci = True
    return terkunci


def catat_berhasil(username, ip):
    with _lock:
        for k in _kunci(username, ip):
            _gagal.pop(k, None)
            _terkunci.pop(k, None)
