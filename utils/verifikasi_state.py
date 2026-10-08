"""Hasil scan wajah supir di Form Security (webcam browser).

Disimpan per PC (cookie pos) dan per user: hanya user yang men-scan yang bisa memakainya untuk membuat tiket,
dan kedaluwarsa setelah BERLAKU."""
import threading
from datetime import datetime, timedelta

BERLAKU = timedelta(minutes=5)          # hasil scan harus dipakai (Submit) dalam 5 menit

_lock = threading.Lock()
_pos = {}       # pos -> {"pemilik", "hasil"}


def _data(id_driver, nama, nik, no_sim, is_updated, foto_path, kode_personel, kategori, is_blacklisted):
    return {"id_driver": id_driver, "nama": nama, "nik": nik, "no_sim": no_sim, "is_updated": is_updated,
            "foto_path": foto_path, "kode_personel": kode_personel, "kategori": kategori,
            "is_blacklisted": is_blacklisted, "dilog": False, "waktu": datetime.now()}


def simpan_hasil_user(pos, user_id, **data):
    """Scan wajah berhasil / supir baru direkam / data diubah oleh user di form -> terverifikasi untuk user itu."""
    with _lock:
        _pos[pos] = {"pemilik": user_id, "hasil": _data(**data)}


def ambil(pos, user_id):
    with _lock:
        st = _pos.get(pos)
        if not st or st["pemilik"] != user_id or not st["hasil"]:
            return None
        if datetime.now() - st["hasil"]["waktu"] > BERLAKU:
            st["hasil"] = None
            return None
        return st["hasil"]


def hapus(pos, user_id):
    with _lock:
        st = _pos.get(pos)
        if st and st["pemilik"] == user_id:
            _pos.pop(pos, None)
