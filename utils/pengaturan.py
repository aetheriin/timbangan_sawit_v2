"""Pengaturan site yang bisa diubah Admin (menu Admin > Pengaturan Site) tanpa restart.

Urutan nilai: tabel `pengaturan_area` (khusus PER_AREA, area akun / perangkat) -> tabel `pengaturan` (global, bila
sudah diubah admin) -> .env -> bawaan di DEFINISI. Pengaturan keamanan (sesi, login, password) selalu global.
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
    "TANTANGAN_SECURITY": ("Tantangan wajah di Form Security", "Face Recognition", "bool", "true", None, None,
                           "Aktif: supir mengikuti tantangan acak (kedip / menoleh). Mati: cukup menghadap kamera"),
    "TANTANGAN_ABSENSI": ("Tantangan wajah saat absensi", "Face Recognition", "bool", "true", None, None,
                          "Aktif: tantangan acak (kedip / menoleh). Mati: cukup menghadap kamera"),
    "TANTANGAN_TAMU": ("Tantangan wajah saat scan tamu", "Face Recognition", "bool", "false", None, None,
                       "Aktif: tamu mengikuti tantangan acak. Mati: cukup menghadap kamera"),
    "TOLERANSI_KELEBIHAN_DO": ("Toleransi kelebihan DO (kg)", "Kelebihan DO", "int", "0", 0, 1000000,
                               "Kelebihan sampai angka ini masih diterima di DO yang sama (tanpa tiket baru & notifikasi). "
                               "Di atasnya seluruh kelebihan menjadi tiket baru -S1"),
    "AREA_PUSAT": ("Area kantor pusat (melihat semua area)", "Area", "area", "0", None, None,
                   "Akun di area ini melihat data semua site (List, history, Kelebihan DO, notifikasi). "
                   "Akun di area lain hanya melihat site-nya sendiri"),
    "SESI_IDLE_MENIT": ("Logout otomatis bila tidak aktif (menit)", "Sesi Login", "int", "120", 5, 720,
                        "Peringatan muncul 2 menit sebelumnya"),
    "SATU_PERANGKAT": ("1 user 1 perangkat", "Sesi Login", "bool", "true", None, None,
                       "Login di perangkat baru otomatis mengeluarkan sesi user itu di perangkat lain"),
    "SESI_MAKS_JAM": ("Umur sesi maksimal (jam)", "Sesi Login", "int", "12", 1, 24,
                      "Setelah ini user wajib login ulang walau masih aktif (±1 shift)"),
    "LOGIN_MAKS_GAGAL": ("Batas salah password", "Kunci Login", "int", "5", 3, 20,
                         "Jumlah salah password sebelum akun / IP dikunci"),
    "LOGIN_JENDELA_MENIT": ("Rentang hitung salah password (menit)", "Kunci Login", "int", "15", 1, 120,
                            "Salah password dihitung dalam rentang waktu ini"),
    "PASSWORD_EXPIRED_HARI": ("Password kedaluwarsa (hari)", "Password", "int", "90", 0, 365,
                              "Setelah lewat, user wajib ganti password saat login. 0 = tidak pernah kedaluwarsa"),
    "LOGIN_KUNCI_MENIT": ("Lama dikunci (menit)", "Kunci Login", "int", "15", 1, 240,
                          "Akun / IP tidak bisa login selama ini (admin bisa membuka lebih cepat)"),
}

# Operasional, boleh berbeda per area (migrasi 014). Sisanya keamanan: global.
PER_AREA = ("WAJIB_SCAN_WAJAH", "AMBANG_WAJAH", "TANTANGAN_SECURITY", "TANTANGAN_ABSENSI", "TANTANGAN_TAMU")

_lock = threading.Lock()
_cache = {"waktu": 0.0, "data": {}, "area": {}}


def _ubah_tipe(tipe, teks):
    if tipe == "bool":
        return str(teks).strip().lower() in ("1", "true", "ya", "on")
    if tipe in ("int", "area"):
        return int(float(teks))
    if tipe == "float":
        return float(teks)
    return teks


def _muat():
    sekarang = time.monotonic()
    with _lock:
        if sekarang - _cache["waktu"] < CACHE_DETIK:
            return _cache
    data, area = {}, {}
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT kunci, nilai FROM pengaturan")
            data = {r[0]: r[1] for r in cursor.fetchall() if isinstance(r[0], str) and isinstance(r[1], str)}
            try:
                cursor.execute("SELECT id_comp_area, kunci, nilai FROM pengaturan_area")
                for r in cursor.fetchall():
                    if isinstance(r[1], str) and isinstance(r[2], str):
                        area.setdefault(r[0], {})[r[1]] = r[2]
            except Exception:       # noqa: BLE001 - migrasi 014 belum dijalankan: tanpa nilai per area
                area = {}
        finally:
            conn.close()
    except Exception:       # noqa: BLE001 - DB mati / tabel belum dibuat -> pakai .env / bawaan
        data = {}
    with _lock:
        _cache.update(waktu=sekarang, data=data, area=area)
    return _cache


def _dari_db():
    return _muat()["data"]


def _dari_area(id_comp_area):
    return _muat()["area"].get(id_comp_area, {}) if id_comp_area else {}


def _bawaan(kunci):
    return os.getenv(kunci, DEFINISI[kunci][3])


def nilai(kunci, id_comp_area=None):
    """Nilai pengaturan sesuai tipenya. Kunci PER_AREA memakai nilai area bila diatur. Nilai rusak -> berikutnya."""
    tipe, bawaan = DEFINISI[kunci][2], DEFINISI[kunci][3]
    teks_area = _dari_area(id_comp_area).get(kunci) if kunci in PER_AREA else None
    for teks in (teks_area, _dari_db().get(kunci), _bawaan(kunci), bawaan):
        if teks is None:
            continue
        try:
            return _ubah_tipe(tipe, teks)
        except (TypeError, ValueError):
            continue
    return _ubah_tipe(tipe, bawaan)


def semua(id_comp_area=None):
    """Untuk halaman Pengaturan Site: daftar pengaturan + nilai sekarang + sumbernya.
    Dengan area: hanya kunci PER_AREA; "bawaan" = nilai global yang dipakai bila area tidak mengatur sendiri."""
    db, area = _dari_db(), _dari_area(id_comp_area)
    hasil = []
    for kunci, (label, grup, tipe, bawaan, mn, mx, ket) in DEFINISI.items():
        if id_comp_area and kunci not in PER_AREA:
            continue
        sumber = "Admin" if kunci in db else (".env" if os.getenv(kunci) else "Bawaan")
        if id_comp_area:
            sumber = "Area" if kunci in area else f"Global ({sumber})"
        hasil.append({"kunci": kunci, "label": label, "grup": grup, "tipe": tipe, "min": mn, "max": mx,
                      "keterangan": ket, "nilai": nilai(kunci, id_comp_area), "per_area": kunci in PER_AREA,
                      "bawaan": nilai(kunci) if id_comp_area else _ubah_tipe(tipe, _bawaan(kunci)), "sumber": sumber})
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


def simpan(perubahan, user_id, id_comp_area=None):
    """perubahan = {kunci: teks}. Validasi semua dulu, baru simpan (semua atau tidak sama sekali).
    Dengan area: hanya kunci PER_AREA, disimpan di pengaturan_area."""
    bersih = {k: validasi(k, v) for k, v in perubahan.items()}
    if id_comp_area and any(k not in PER_AREA for k in bersih):
        raise ValueError("Pengaturan keamanan hanya bisa diatur global")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for kunci, teks in bersih.items():
            if id_comp_area:
                cursor.execute("""
                    MERGE pengaturan_area AS t USING (SELECT ? AS id_comp_area, ? AS kunci) AS s
                        ON t.id_comp_area = s.id_comp_area AND t.kunci = s.kunci
                    WHEN MATCHED THEN UPDATE SET nilai = ?, updated_by = ?, updated_at = GETDATE()
                    WHEN NOT MATCHED THEN INSERT (id_comp_area, kunci, nilai, updated_by) VALUES (?, ?, ?, ?);""",
                               id_comp_area, kunci, teks, user_id, id_comp_area, kunci, teks, user_id)
                continue
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


def kembalikan_bawaan(kunci, id_comp_area=None):
    """Global: kembali ke .env / bawaan. Area: hapus nilai area sehingga ikut global."""
    conn = get_connection()
    try:
        if id_comp_area:
            conn.cursor().execute("DELETE FROM pengaturan_area WHERE id_comp_area = ? AND kunci = ?", id_comp_area, kunci)
        else:
            conn.cursor().execute("DELETE FROM pengaturan WHERE kunci = ?", kunci)
        conn.commit()
    finally:
        conn.close()
    hapus_cache()


def hapus_cache():
    with _lock:
        _cache.update(waktu=0.0, data={})
