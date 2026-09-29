import re

# Kode wilayah plat Indonesia (1-2 huruf depan)
KODE_WILAYAH = {
    # Sumatera
    "BL", "BB", "BK", "BA", "BM", "BH", "BD", "BG", "BN", "BE", "BP",
    # Jawa, Bali, Nusa Tenggara
    "A", "B", "D", "E", "F", "T", "Z", "G", "H", "K", "R", "AA", "AB", "AD",
    "L", "M", "N", "P", "S", "W", "AE", "AG", "DK", "DR", "EA", "DH", "EB", "ED",
    # Kalimantan
    "KB", "DA", "KH", "KT", "KU",
    # Sulawesi
    "DB", "DL", "DM", "DN", "DT", "DD", "DC", "DW",
    # Maluku & Papua
    "DE", "DG", "PA", "PB", "PG", "PS", "PT", "PY",
}

# Huruf depan 1-2, angka 1-4 (tidak diawali 0), huruf belakang 0-3.
# Spasi / strip / titik antar bagian boleh ada boleh tidak: "bm1455jj", "BM-1455-JJ", "BM 1455 JJ".
_POLA_PLAT = re.compile(r"^([A-Z]{1,2})[\s.\-]*([1-9][0-9]{0,3})[\s.\-]*([A-Z]{0,3})$")


def normalisasi_plat(raw):
    """Ubah input bebas jadi format baku 'BM 1455 JJ'.

    Return (plat_baku, None) kalau valid, atau (None, pesan_error) kalau tidak.
    """
    teks = (raw or "").strip().upper()
    if not teks:
        return None, "Nomor plat kosong"

    m = _POLA_PLAT.match(teks)
    if not m:
        return None, (f"Format plat '{teks}' tidak valid. "
                      "Contoh: BM 1455 JJ, A 1234 JJ, AA 456 SJU")

    wilayah, angka, akhiran = m.groups()
    if wilayah not in KODE_WILAYAH:
        return None, f"Kode wilayah '{wilayah}' tidak dikenal (plat '{teks}')"

    return " ".join(p for p in (wilayah, angka, akhiran) if p), None
