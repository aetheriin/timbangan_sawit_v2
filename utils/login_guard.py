"""Pembatas percobaan login: LOGIN_MAKS_GAGAL kali salah dalam LOGIN_JENDELA_MENIT -> dikunci LOGIN_KUNCI_MENIT
(per username dan per IP). Nilainya diatur di Admin > Pengaturan Site (bawaan 5x / 15 menit / 15 menit).

Disimpan di memori proses (waitress = 1 proses), cukup untuk aplikasi di jaringan site."""
import threading
import time

from utils import pengaturan

_lock = threading.Lock()
_gagal = {}        # kunci -> [waktu gagal ...]
_terkunci = {}     # kunci -> waktu buka
_dicoba = {}       # ip -> username terakhir yang dicoba dari IP itu (ditampilkan di Admin)
MAKS_DICOBA = 5


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
    maks = pengaturan.nilai("LOGIN_MAKS_GAGAL")
    jendela = pengaturan.nilai("LOGIN_JENDELA_MENIT") * 60
    lama_kunci = pengaturan.nilai("LOGIN_KUNCI_MENIT") * 60
    terkunci = False
    with _lock:
        dicoba = [u for u in _dicoba.get(ip, []) if u != username] + [username or "-"]
        _dicoba[ip] = dicoba[-MAKS_DICOBA:]
        for k in _kunci(username, ip):
            daftar = [t for t in _gagal.get(k, []) if sekarang - t < jendela] + [sekarang]
            _gagal[k] = daftar
            if len(daftar) >= maks:
                _terkunci[k] = sekarang + lama_kunci
                _gagal[k] = []
                terkunci = True
    return terkunci


def catat_berhasil(username, ip):
    with _lock:
        for k in _kunci(username, ip):
            _gagal.pop(k, None)
            _terkunci.pop(k, None)


def daftar_terkunci(sekarang=None):
    """Untuk Admin > Sesi Aktif: [{kunci, jenis, nama, sisa_detik}] yang masih terkunci."""
    sekarang = sekarang or time.time()
    with _lock:
        hasil = [{"kunci": k, "jenis": "Username" if k.startswith("u:") else "IP", "nama": k.split(":", 1)[1],
                  "sisa_detik": int(buka - sekarang),
                  "dicoba": list(reversed(_dicoba.get(k[3:], []))) if k.startswith("ip:") else []}
                 for k, buka in _terkunci.items() if buka > sekarang]
    return sorted(hasil, key=lambda r: -r["sisa_detik"])


def buka_kunci(kunci):
    """Admin membuka kunci lebih cepat. Kembalikan True bila memang sedang terkunci."""
    with _lock:
        _gagal.pop(kunci, None)
        if kunci.startswith("ip:"):
            _dicoba.pop(kunci[3:], None)
        return _terkunci.pop(kunci, None) is not None


def buka_kunci_teks(teks):
    """Admin mengetik username ATAU IP. Hitungan salah & kuncinya dihapus. Kembalikan jumlah kunci yang dibuka."""
    teks = (teks or "").strip()
    return sum(buka_kunci(k) for k in (f"u:{teks.lower()}", f"ip:{teks}"))


def buka_semua():
    with _lock:
        jumlah = len(_terkunci)
        _terkunci.clear()
        _gagal.clear()
        _dicoba.clear()
    return jumlah
