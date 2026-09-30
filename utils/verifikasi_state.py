"""State scan wajah supir per pos (kiosk).

Sebelumnya satu variabel global untuk seluruh server: hasil scan di satu pos bisa terpakai PC lain.
Sekarang per pos, dan hasilnya hanya bisa dibaca / dipakai oleh user yang menekan "Mulai Scan Wajah"
(pemilik), serta kedaluwarsa setelah BERLAKU."""
import threading
from datetime import datetime, timedelta

BERLAKU = timedelta(minutes=5)          # hasil scan harus dipakai (Submit) dalam 5 menit
KAMERA_MAKS = timedelta(minutes=2)      # kamera kiosk otomatis dianggap selesai setelah 2 menit

_lock = threading.Lock()
_pos = {}       # pos -> {"aktif", "pemilik", "mulai", "hasil"}


def mulai_scan(pos, user_id):
    with _lock:
        _pos[pos] = {"aktif": True, "pemilik": user_id, "mulai": datetime.now(), "hasil": None}


def batal(pos):
    with _lock:
        st = _pos.get(pos)
        if st:
            st["aktif"] = False


def kamera_aktif(pos):
    with _lock:
        st = _pos.get(pos)
        return bool(st and st["aktif"] and datetime.now() - st["mulai"] < KAMERA_MAKS)


def _data(id_driver, nama, nik, no_sim, is_updated, foto_path, kode_personel, kategori, is_blacklisted):
    return {"id_driver": id_driver, "nama": nama, "nik": nik, "no_sim": no_sim, "is_updated": is_updated,
            "foto_path": foto_path, "kode_personel": kode_personel, "kategori": kategori,
            "is_blacklisted": is_blacklisted, "dilog": False, "waktu": datetime.now()}


def simpan_hasil_kiosk(pos, **data):
    """Hasil dari kiosk hanya diterima bila scan di pos itu sedang diminta user."""
    with _lock:
        st = _pos.get(pos)
        if not st or not st["aktif"]:
            return False
        st["hasil"], st["aktif"] = _data(**data), False
        return True


def simpan_hasil_user(pos, user_id, **data):
    """Supir baru direkam / data diubah langsung oleh user di form -> dianggap terverifikasi untuk user itu."""
    with _lock:
        _pos[pos] = {"aktif": False, "pemilik": user_id, "mulai": datetime.now(), "hasil": _data(**data)}


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
