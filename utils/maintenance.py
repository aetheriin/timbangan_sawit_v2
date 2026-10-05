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


def pindahkan_upload_lama():
    """Sekali saat start: pindahkan file dari static/uploads (lama, publik) ke folder upload privat.
    Path di database tidak berubah ('uploads/...'), hanya lokasi filenya."""
    import shutil
    from extensions import UPLOAD_LAMA
    if not os.path.isdir(UPLOAD_LAMA) or os.path.abspath(UPLOAD_LAMA) == os.path.abspath(UPLOAD_FOLDER):
        return
    jumlah = 0
    for akar, _, files in os.walk(UPLOAD_LAMA):
        for nama in files:
            if nama == ".gitkeep":
                continue
            asal = os.path.join(akar, nama)
            tujuan = os.path.join(UPLOAD_FOLDER, os.path.relpath(asal, UPLOAD_LAMA))
            os.makedirs(os.path.dirname(tujuan), exist_ok=True)
            if not os.path.exists(tujuan):
                shutil.move(asal, tujuan)
                jumlah += 1
    if jumlah:
        log.info("%d file upload dipindah dari static/uploads ke %s (privat)", jumlah, UPLOAD_FOLDER)
