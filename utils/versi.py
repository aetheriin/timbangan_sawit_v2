"""Versi aplikasi: isi file VERSION di folder aplikasi (mis. 1.1.0). Diubah saat rilis; dibaca ulang tiap 60 detik."""
import os
import re

from extensions import BASE_DIR
from utils.cache import cache_ttl


@cache_ttl(60)
def versi_aplikasi():
    try:
        with open(os.path.join(BASE_DIR, "VERSION"), encoding="utf-8") as f:
            teks = f.read().strip()
    except OSError:
        return "-"
    # Boleh ditulis "1.1.0", "v1.1.0", atau "CPOS v1.1.0": yang ditampilkan cukup angkanya
    return re.sub(r"^(cpos)?\s*v?\s*", "", teks, flags=re.I) or "-"
