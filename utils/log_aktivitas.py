"""Satu log untuk semua aktivitas (tabel log_aktivitas, migrasi 015).

Ditulis hanya lewat prosedur dbo.sp_catat_log: isi lama / baru berupa JSON dan setiap baris membawa hash baris
sebelumnya (rantai hash), sehingga baris yang diubah / dihapus ketahuan lewat view dbo.v_log_rusak.
Kategori: ADMIN, SECURITY, PERSONEL, STANDAR_MUTU, TIMELINE."""
import json
import logging
from datetime import date, datetime
from decimal import Decimal

from utils.db_utils import get_connection, _rows_to_dicts

log = logging.getLogger("weighbridge")


def _json(nilai):
    if nilai is None:
        return None

    def bawaan(v):
        if isinstance(v, (datetime, date)):
            return v.isoformat()
        if isinstance(v, Decimal):
            return float(v)
        return str(v)
    return json.dumps(nilai, ensure_ascii=False, default=bawaan)


def _exec(cursor, kategori, aksi, tabel, id_baris, lama, baru, user_id, ip):
    cursor.execute("""EXEC dbo.sp_catat_log @kategori = ?, @aksi = ?, @tabel = ?, @id_baris = ?, @nilai_lama = ?,
                                            @nilai_baru = ?, @id_user = ?, @ip = ?""",
                   kategori, aksi[:40], tabel, None if id_baris is None else str(id_baris)[:100],
                   _json(lama), _json(baru), user_id, (ip or None) and ip[:45])


def catat(kategori, aksi, *, tabel=None, id_baris=None, lama=None, baru=None, user_id=None, ip=None, cursor=None):
    """cursor diberikan: ikut transaksi pemanggil (gagal = ikut batal). Tanpa cursor: koneksi sendiri dan
    kegagalan mencatat tidak menggagalkan proses utama."""
    if cursor is not None:
        _exec(cursor, kategori, aksi, tabel, id_baris, lama, baru, user_id, ip)
        return
    try:
        conn = get_connection()
        try:
            _exec(conn.cursor(), kategori, aksi, tabel, id_baris, lama, baru, user_id, ip)
            conn.commit()
        finally:
            conn.close()
    except Exception:       # noqa: BLE001 - log tidak boleh memutus alur
        log.exception("Gagal mencatat log %s/%s", kategori, aksi)


def daftar(kategori, hari=7, batas=300, aksi=None):
    """Baris log satu kategori N hari terakhir, terbaru dulu. nilai_lama / nilai_baru sudah jadi dict."""
    sql = f"""SELECT TOP {int(batas)} l.id_log, l.waktu, l.aksi, l.tabel, l.id_baris, l.nilai_lama, l.nilai_baru, l.ip,
                     l.id_user, u.nama AS oleh, u.username, lv.kode AS role_oleh, p.kode_personel AS kode_oleh
              FROM log_aktivitas l
              LEFT JOIN akun u ON u.id_user = l.id_user
              LEFT JOIN level lv ON lv.id_level = u.id_level
              LEFT JOIN personel p ON p.id_personel = u.id_personel
              WHERE l.kategori = ? AND l.waktu >= DATEADD(DAY, ?, CAST(GETDATE() AS DATE))
                    {"AND l.aksi = ?" if aksi else ""}
              ORDER BY l.id_log DESC"""
    params = [kategori, -(int(hari) - 1)] + ([aksi] if aksi else [])
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        rows = _rows_to_dicts(cursor)
    finally:
        conn.close()
    for r in rows:
        r["nilai_lama"] = json.loads(r["nilai_lama"]) if r["nilai_lama"] else {}
        r["nilai_baru"] = json.loads(r["nilai_baru"]) if r["nilai_baru"] else {}
    return rows


def verifikasi():
    """Cek rantai hash. Kembalikan {"utuh": bool, "jumlah": n, "rusak": [baris pertama yang bermasalah...]}."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM log_aktivitas")
        jumlah = cursor.fetchone()[0]
        cursor.execute("SELECT TOP 20 id_log, waktu, kategori, aksi, masalah FROM v_log_rusak ORDER BY id_log")
        rusak = _rows_to_dicts(cursor)
    finally:
        conn.close()
    for r in rusak:
        r["waktu"] = r["waktu"].strftime("%Y-%m-%d %H:%M:%S") if r["waktu"] else None
    return {"utuh": not rusak, "jumlah": jumlah, "rusak": rusak}
