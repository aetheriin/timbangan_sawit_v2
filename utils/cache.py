"""Cache kecil di memori server untuk data yang jarang berubah (supplier, produk, jadwal, standar mutu).
Satu proses waitress = satu cache; bila datanya diubah lewat aplikasi, panggil .hapus() pada fungsi tsb."""
import threading
import time
from functools import wraps


def cache_ttl(detik):
    def dekorator(fn):
        simpan = {}
        kunci_lock = threading.Lock()

        @wraps(fn)
        def pembungkus(*args):
            sekarang = time.monotonic()
            with kunci_lock:
                ada = simpan.get(args)
                if ada and sekarang - ada[0] < detik:
                    return ada[1]
            hasil = fn(*args)
            with kunci_lock:
                simpan[args] = (sekarang, hasil)
            return hasil

        def hapus():
            with kunci_lock:
                simpan.clear()

        pembungkus.hapus = hapus
        return pembungkus
    return dekorator
