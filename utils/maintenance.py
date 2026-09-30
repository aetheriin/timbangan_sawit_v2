"""Pembersihan berkala file sementara & snapshot lama di static/uploads (thread latar)."""
import logging
import os
import threading
import time
from extensions import UPLOAD_FOLDER

log = logging.getLogger("weighbridge")

UMUR_TMP_DETIK = 60 * 60                                           # file tmp > 1 jam
HARI_SIMPAN_ABSENSI = int(os.getenv("HARI_SIMPAN_FOTO_ABSENSI", "90"))
INTERVAL_DETIK = 60 * 60


def _hapus_lebih_lama(folder, umur_detik, awalan=None):
    if not os.path.isdir(folder):
        return 0
    batas, jumlah = time.time() - umur_detik, 0
    for nama in os.listdir(folder):
        path = os.path.join(folder, nama)
        if awalan and not nama.startswith(awalan):
            continue
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < batas:
                os.remove(path)
                jumlah += 1
        except OSError:
            pass
    return jumlah


def bersihkan():
    n = _hapus_lebih_lama(os.path.join(UPLOAD_FOLDER, "tmp"), UMUR_TMP_DETIK)
    n += _hapus_lebih_lama(UPLOAD_FOLDER, UMUR_TMP_DETIK, awalan="tmp_")       # frame kiosk lama
    if HARI_SIMPAN_ABSENSI > 0:
        n += _hapus_lebih_lama(os.path.join(UPLOAD_FOLDER, "absensi"), HARI_SIMPAN_ABSENSI * 86400)
    if n:
        log.info("Pembersihan uploads: %d file dihapus", n)


def mulai_pembersihan_berkala():
    def loop():
        while True:
            try:
                bersihkan()
            except Exception as e:      # noqa: BLE001 - jangan hentikan thread
                log.warning("Pembersihan uploads gagal: %s", e)
            time.sleep(INTERVAL_DETIK)
    threading.Thread(target=loop, daemon=True, name="pembersihan-uploads").start()
