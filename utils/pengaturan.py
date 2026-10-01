"""Pengaturan site yang bisa diubah Admin (menu Admin > Pengaturan Site) tanpa restart.

Urutan nilai: tabel `pengaturan` (bila sudah diubah admin) -> .env -> bawaan di DEFINISI.
Dibaca dari cache memori (30 detik), jadi tidak menambah query di setiap request."""
import os
import threading
import time

from utils.db_utils import get_connection

CACHE_DETIK = 30

# kunci: (label, grup, tipe, bawaan, min, maks, keterangan)
DEFINISI = {
    "WAJIB_SCAN_WAJAH": ("Wajib scan wajah supir", "Face Recognition", "bool", "true", None, None,
                         "Tiket hanya bisa dibuat setelah wajah supir terverifikasi"),
    "AMBANG_WAJAH": ("Ambang kemiripan wajah", "Face Recognition", "float", "0.55", 0.30, 0.70,
                     "Jarak maksimal wajah dianggap sama. Kecil = lebih ketat (0.50-0.60 disarankan)"),
    "SESI_IDLE_MENIT": ("Logout otomatis bila tidak aktif (menit)", "Sesi Login", "int", "120", 5, 720,
                        "Peringatan muncul 2 menit sebelumnya"),
    "SESI_MAKS_JAM": ("Umur sesi maksimal (jam)", "Sesi Login", "int", "12", 1, 24,
                      "Setelah ini user wajib login ulang walau masih aktif (±1 shift)"),
    "LOGIN_MAKS_GAGAL": ("Batas salah password", "Kunci Login", "int", "5", 3, 20,
                         "Jumlah salah password sebelum akun / IP dikunci"),
    "LOGIN_JENDELA_MENIT": ("Rentang hitung salah password (menit)", "Kunci Login", "int", "15", 1, 120,
                            "Salah password dihitung dalam rentang waktu ini"),
    "LOGIN_KUNCI_MENIT": ("Lama dikunci (menit)", "Kunci Login", "int", "15", 1, 240,
                          "Akun / IP tidak bisa login selama ini (admin bisa membuka lebih cepat)"),
}

_lock = threading.Lock()
_cache = {"waktu": 0.0, "data": {}}


def _ubah_tipe(tipe, teks):
    if tipe == "bool":
        return str(teks).strip().lower() in ("1", "true", "ya", "on")
    if tipe == "int":
        return int(float(teks))
    if tipe == "float":
        return float(teks)
    return teks


def _dari_db():
    sekarang = time.monotonic()
    with _lock:
        if sekarang - _cache["waktu"] < CACHE_DETIK:
            return _cache["data"]
    data = {}
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT kunci, nilai FROM pengaturan")
            data = {r[0]: r[1] for r in cursor.fetchall() if isinstance(r[0], str) and isinstance(r[1], str)}
        finally:
            conn.close()
    except Exception:       # noqa: BLE001 - DB mati / tabel belum dibuat -> pakai .env / bawaan
        data = {}
    with _lock:
        _cache.update(waktu=sekarang, data=data)
    return data


def _bawaan(kunci):
    return os.getenv(kunci, DEFINISI[kunci][3])


def nilai(kunci):
    """Nilai pengaturan sesuai tipenya. Nilai rusak di DB / .env -> bawaan."""
    tipe, bawaan = DEFINISI[kunci][2], DEFINISI[kunci][3]
    for teks in (_dari_db().get(kunci), _bawaan(kunci), bawaan):
        if teks is None:
            continue
        try:
            return _ubah_tipe(tipe, teks)
        except (TypeError, ValueError):
            continue
    return _ubah_tipe(tipe, bawaan)


def semua():
    """Untuk halaman Pengaturan Site: daftar pengaturan + nilai sekarang + sumbernya."""
    db = _dari_db()
    hasil = []
    for kunci, (label, grup, tipe, bawaan, mn, mx, ket) in DEFINISI.items():
        hasil.append({"kunci": kunci, "label": label, "grup": grup, "tipe": tipe, "min": mn, "max": mx,
                      "keterangan": ket, "nilai": nilai(kunci), "bawaan": _ubah_tipe(tipe, _bawaan(kunci)),
                      "sumber": "Admin" if kunci in db else (".env" if os.getenv(kunci) else "Bawaan")})
    return hasil


def validasi(kunci, teks):
    """Kembalikan teks nilai yang sudah dirapikan. ValueError bila tidak valid."""
    if kunci not in DEFINISI:
        raise ValueError("Pengaturan tidak dikenal")
    label, _, tipe, _, mn, mx, _ = DEFINISI[kunci]
    try:
        v = _ubah_tipe(tipe, teks)
    except (TypeError, ValueError):
        raise ValueError(f"{label}: nilai tidak valid")
    if mn is not None and not (mn <= v <= mx):
        raise ValueError(f"{label}: harus antara {mn} dan {mx}")
    return ("true" if v else "false") if tipe == "bool" else str(v)


def simpan(perubahan, user_id):
    """perubahan = {kunci: teks}. Validasi semua dulu, baru simpan (semua atau tidak sama sekali)."""
    bersih = {k: validasi(k, v) for k, v in perubahan.items()}
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for kunci, teks in bersih.items():
            cursor.execute("""
                MERGE pengaturan AS t USING (SELECT ? AS kunci) AS s ON t.kunci = s.kunci
                WHEN MATCHED THEN UPDATE SET nilai = ?, updated_by = ?, updated_at = GETDATE()
                WHEN NOT MATCHED THEN INSERT (kunci, nilai, updated_by) VALUES (?, ?, ?);""",
                           kunci, teks, user_id, kunci, teks, user_id)
        conn.commit()
    finally:
        conn.close()
    hapus_cache()
    return bersih


def kembalikan_bawaan(kunci):
    conn = get_connection()
    try:
        conn.cursor().execute("DELETE FROM pengaturan WHERE kunci = ?", kunci)
        conn.commit()
    finally:
        conn.close()
    hapus_cache()


def hapus_cache():
    with _lock:
        _cache.update(waktu=0.0, data={})
