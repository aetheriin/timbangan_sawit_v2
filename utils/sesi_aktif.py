"""Sesi login aktif (Admin > Sesi Aktif) disimpan di tabel sesi_login.

Di database, bukan di memori, supaya sesi dari semua PC & semua proses server terlihat dan bisa dipaksa keluar,
serta untuk aturan 1 user 1 perangkat. Waktu aktif ditulis paling sering 1x per menit per sesi supaya ringan.
Yang benar-benar menolak sesi lama tetap users.sesi_versi (dicek setiap request di load_user)."""
import logging
import secrets
import threading
import time
from datetime import datetime

from utils.db_utils import get_connection, _rows_to_dicts

log = logging.getLogger("weighbridge")
JEDA_TULIS_DETIK = 60

_lock = threading.Lock()
_terakhir_tulis = {}        # sid -> waktu terakhir menulis terakhir_aktif ke DB (per proses)


def sid_baru():
    return secrets.token_hex(12)


def _jalankan(sql, *params, ambil=False):
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, *params)
            hasil = _rows_to_dicts(cursor) if ambil else cursor.rowcount
            conn.commit()
            return hasil
        finally:
            conn.close()
    except Exception:       # noqa: BLE001 - sesi tetap jalan walau pencatatan gagal (mis. migrasi 007 belum dijalankan)
        log.exception("Gagal mengakses tabel sesi_login")
        return [] if ambil else 0


def catat(sid, user, ip, agen, login=None, aktif=True):
    """Ditulis saat pertama kali sesi terlihat di proses ini, lalu maks. 1x / menit untuk request aktif.
    Polling (aktif=False) tidak memperbarui waktu aktif."""
    sekarang = time.time()
    with _lock:
        terakhir = _terakhir_tulis.get(sid)
        if terakhir is not None and (not aktif or sekarang - terakhir < JEDA_TULIS_DETIK):
            return
        _terakhir_tulis[sid] = sekarang
    waktu_login = datetime.fromtimestamp(login) if login else datetime.now()
    _jalankan("""MERGE sesi_login AS t USING (SELECT ? AS sid) AS s ON t.sid = s.sid
                 WHEN MATCHED THEN UPDATE SET terakhir_aktif = GETDATE(), ip = ?, agen = ?
                 WHEN NOT MATCHED THEN INSERT (sid, user_id, ip, agen, login_at, terakhir_aktif)
                                       VALUES (?, ?, ?, ?, ?, GETDATE());""",
              sid, ip, (agen or "")[:200], sid, user.id, ip, (agen or "")[:200], waktu_login)


def hapus(sid, alasan="LOGOUT"):
    if sid:
        with _lock:
            _terakhir_tulis.pop(sid, None)
        _jalankan("UPDATE sesi_login SET berakhir_at = GETDATE(), alasan = ? WHERE sid = ? AND berakhir_at IS NULL", alasan, sid)


def hapus_user(user_id, alasan="PAKSA_KELUAR", kecuali_sid=None):
    """Akhiri semua sesi aktif seorang user (paksa keluar, reset password, login di perangkat lain)."""
    return _jalankan("""UPDATE sesi_login SET berakhir_at = GETDATE(), alasan = ?
                        WHERE user_id = ? AND berakhir_at IS NULL AND sid <> ?""", alasan, user_id, kecuali_sid or "")


def ada_sesi_lain(user_id, batas_idle_detik):
    rows = _jalankan("""SELECT TOP 1 ip FROM sesi_login WHERE user_id = ? AND berakhir_at IS NULL
                        AND terakhir_aktif >= DATEADD(second, ?, GETDATE())""", user_id, -int(batas_idle_detik), ambil=True)
    return rows[0]["ip"] if rows else None


def alasan_berakhir(sid):
    """Kenapa sesi ini berakhir (untuk pesan di halaman login perangkat lama)."""
    if not sid:
        return None
    rows = _jalankan("SELECT alasan FROM sesi_login WHERE sid = ?", sid, ambil=True)
    return rows[0]["alasan"] if rows else None


def daftar(batas_idle_detik):
    """Sesi yang belum berakhir & belum melewati batas idle, terbaru di atas (dari semua PC / proses server)."""
    rows = _jalankan("""SELECT s.sid, s.user_id, u.username, u.nama, lv.kode AS role, s.ip, s.agen, s.login_at, s.terakhir_aktif
                        FROM sesi_login s JOIN users u ON u.id_user = s.user_id
                        JOIN level lv ON lv.id_level = u.id_level
                        WHERE s.berakhir_at IS NULL AND s.terakhir_aktif >= DATEADD(second, ?, GETDATE())
                        ORDER BY s.terakhir_aktif DESC""", -int(batas_idle_detik), ambil=True)
    return [{**r, "login": r["login_at"].timestamp(), "terakhir_aktif": r["terakhir_aktif"].timestamp()} for r in rows]
