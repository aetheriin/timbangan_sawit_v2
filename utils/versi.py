"""Versi aplikasi: isi file VERSION di folder aplikasi (mis. 1.1.0). Diubah saat rilis; dibaca ulang tiap 60 detik."""
import os

from extensions import BASE_DIR
from utils.cache import cache_ttl


@cache_ttl(60)
def versi_aplikasi():
    try:
        with open(os.path.join(BASE_DIR, "VERSION"), encoding="utf-8") as f:
            return f.read().strip() or "-"
    except OSError:
        return "-"
