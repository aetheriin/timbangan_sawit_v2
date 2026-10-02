import secrets
import threading
import time

_lock = threading.Lock()
_sesi = {}      # sid -> {...}


def sid_baru():
    return secrets.token_hex(12)


def catat(sid, user, ip, agen, login=None, aktif=True):
    """Dipanggil saat login & setiap request (aktif=False untuk polling otomatis)."""
    sekarang = time.time()
    with _lock:
        s = _sesi.get(sid)
        if s is None:
            s = _sesi[sid] = {"sid": sid, "login": login or sekarang, "terakhir_aktif": sekarang}
        s.update(user_id=user.id, username=user.username, nama=user.nama_lengkap, role=user.role,
                 ip=ip, agen=(agen or "")[:120], terakhir_dilihat=sekarang)
        if aktif:
            s["terakhir_aktif"] = sekarang


def hapus(sid):
    with _lock:
        _sesi.pop(sid, None)


def hapus_user(user_id):
    with _lock:
        for sid in [k for k, s in _sesi.items() if s["user_id"] == user_id]:
            _sesi.pop(sid, None)


def daftar(batas_idle_detik):
    """Sesi yang belum melewati batas idle, terbaru di atas. Sesi kedaluwarsa dibuang dari memori."""
    sekarang = time.time()
    with _lock:
        for sid in [k for k, s in _sesi.items() if sekarang - s["terakhir_aktif"] > batas_idle_detik]:
            _sesi.pop(sid, None)
        return sorted((dict(s) for s in _sesi.values()), key=lambda s: -s["terakhir_aktif"])
