"""Perangkat kiosk kamera per pos (menu Admin > Perangkat / Kiosk).

Token asli hanya ditampilkan sekali saat dibuat / diganti; yang disimpan hash SHA-256.
Kiosk mengirim header X-Kiosk-Id (= id_pos) dan X-Kiosk-Token. KIOSK_TOKEN di .env tetap berlaku
sebagai token bersama (cara lama), supaya kiosk yang sudah terpasang tidak langsung putus."""
import hashlib
import hmac
import re
import secrets
import threading
import time

from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

POLA_ID_POS = re.compile(r"^[A-Z0-9_-]{2,30}$")

_lock = threading.Lock()
_terakhir = {}      # id_pos -> {"waktu", "ip"} (memori, tidak menulis DB setiap request)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def token_baru():
    return secrets.token_urlsafe(32)


@cache_ttl(60)
def _perangkat():
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id_pos, token_hash, is_active FROM perangkat_kiosk")
            return {r[0]: (r[1], bool(r[2])) for r in cursor.fetchall() if isinstance(r[0], str)}
        finally:
            conn.close()
    except Exception:       # noqa: BLE001 - tabel belum ada / DB mati -> hanya KIOSK_TOKEN .env
        return {}


def token_cocok(id_pos, token):
    """True bila id_pos terdaftar, aktif, dan token sesuai."""
    data = _perangkat().get(id_pos)
    return bool(data and data[1] and token and hmac.compare_digest(data[0], hash_token(token)))


def catat_terlihat(id_pos, ip):
    with _lock:
        _terakhir[id_pos] = {"waktu": time.time(), "ip": ip}


def terakhir_terlihat():
    with _lock:
        return dict(_terakhir)


def hapus_cache():
    _perangkat.hapus()


# ===== CRUD (dipanggil routes/admin.py) =====
def daftar():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT k.id_pos, k.nama, k.lokasi, k.id_comp_area, a.nama AS area, k.is_active, k.created_at
                          FROM perangkat_kiosk k LEFT JOIN comp_area a ON a.id_comp_area = k.id_comp_area
                          ORDER BY k.id_pos""")
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def daftar_aktif():
    """Pos aktif untuk pilihan "Pos kamera" di Form Security. Gagal / tabel belum ada -> kosong."""
    try:
        return [p for p in daftar() if p["is_active"]]
    except Exception:       # noqa: BLE001
        return []


def tambah(id_pos, nama, lokasi, id_comp_area):
    """Kembalikan token asli (tampilkan sekali ke admin)."""
    token = token_baru()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM perangkat_kiosk WHERE id_pos = ?", id_pos)
        if cursor.fetchone():
            raise ValueError(f"ID pos {id_pos} sudah dipakai")
        cursor.execute("INSERT INTO perangkat_kiosk (id_pos, nama, lokasi, id_comp_area, token_hash) VALUES (?, ?, ?, ?, ?)",
                       id_pos, nama, lokasi or None, id_comp_area, hash_token(token))
        conn.commit()
    finally:
        conn.close()
    hapus_cache()
    return token


def ganti_token(id_pos):
    token = token_baru()
    _ubah("UPDATE perangkat_kiosk SET token_hash = ? WHERE id_pos = ?", hash_token(token), id_pos)
    return token


def ubah(id_pos, nama, lokasi, id_comp_area):
    _ubah("UPDATE perangkat_kiosk SET nama = ?, lokasi = ?, id_comp_area = ? WHERE id_pos = ?",
          nama, lokasi or None, id_comp_area, id_pos)


def set_aktif(id_pos, aktif):
    _ubah("UPDATE perangkat_kiosk SET is_active = ? WHERE id_pos = ?", 1 if aktif else 0, id_pos)


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        if cursor.rowcount == 0:
            raise ValueError("Perangkat tidak ditemukan")
        conn.commit()
    finally:
        conn.close()
    hapus_cache()
