from datetime import datetime

_verifikasi_terakhir = None

def set_terverifikasi(id_driver, nama, nik=None, no_sim=None, is_updated=False):
    global _verifikasi_terakhir
    _verifikasi_terakhir = {
        "id_driver": id_driver, "nama": nama, "nik": nik,
        "no_sim": no_sim, "is_updated": is_updated, "waktu": datetime.now()
    }

def get_verifikasi():
    return _verifikasi_terakhir

def reset_verifikasi():
    global _verifikasi_terakhir
    _verifikasi_terakhir = None