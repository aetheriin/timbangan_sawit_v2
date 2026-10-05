"""Kunjungan tamu (Face Recognition › Kunjungan Tamu). Tamu = personel kategori TAMU (tanpa akun);
setiap kedatangan satu baris kunjungan: orang yang dituju, keperluan, waktu masuk / keluar."""
from datetime import date, datetime, timedelta

from utils.db_utils import get_connection, _rows_to_dicts


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        n = cursor.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def daftar_keperluan():
    try:
        return _query("SELECT id_keperluan, nama FROM keperluan_kunjungan WHERE is_active = 1 ORDER BY id_keperluan")
    except Exception:       # noqa: BLE001 - migrasi 009 belum dijalankan: halaman tetap terbuka
        return []


def daftar_dituju():
    """Orang yang bisa ditemui tamu: karyawan & security aktif."""
    return _query("""SELECT p.id_personel, p.kode_personel, p.nama_personel, k.nama AS kategori
                     FROM personel p JOIN kategori_personel k ON k.kode = p.kategori
                     WHERE p.is_active = 1 AND p.kategori IN ('EMPLOYEE', 'SECURITY')
                     ORDER BY p.nama_personel""")


def daftar_kunjungan(tanggal=None, hanya_didalam=False):
    sql = """SELECT k.id_kunjungan, k.waktu_masuk, k.waktu_keluar, k.asal_perusahaan, k.no_plat, k.keterangan,
                    k.foto_masuk_path, t.id_personel, t.nama_personel AS nama_tamu, t.nik, t.is_blacklisted,
                    t.foto_path, d.id_personel AS id_dituju, d.kode_personel AS kode_dituju, d.nama_personel AS nama_dituju,
                    kp.nama AS keperluan, u.nama AS dicatat_oleh
             FROM kunjungan k
             JOIN v_personel t ON t.id_personel = k.id_personel
             JOIN personel d ON d.id_personel = k.id_dituju
             JOIN keperluan_kunjungan kp ON kp.id_keperluan = k.id_keperluan
             JOIN users u ON u.id_user = k.dicatat_oleh"""
    if hanya_didalam:
        rows = _query(sql + " WHERE k.waktu_keluar IS NULL ORDER BY k.waktu_masuk DESC")
    else:
        hari = tanggal or date.today()
        rows = _query(sql + " WHERE k.waktu_masuk >= ? AND k.waktu_masuk < ? ORDER BY k.waktu_masuk DESC",
                      datetime.combine(hari, datetime.min.time()), datetime.combine(hari + timedelta(days=1), datetime.min.time()))
    for r in rows:
        r["is_blacklisted"] = bool(r["is_blacklisted"])
        for k in ("waktu_masuk", "waktu_keluar"):
            r[k] = r[k].strftime("%Y-%m-%d %H:%M") if r[k] else None
    return rows


def kunjungan_aktif(id_personel):
    rows = _query("SELECT TOP 1 id_kunjungan, waktu_masuk FROM kunjungan WHERE id_personel = ? AND waktu_keluar IS NULL",
                  id_personel)
    return rows[0] if rows else None


def catat_masuk(id_personel, id_dituju, id_keperluan, keterangan, asal_perusahaan, no_plat, id_comp_area,
                foto_masuk_path, user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO kunjungan (id_personel, id_dituju, id_keperluan, keterangan, asal_perusahaan, no_plat,
                                                 id_comp_area, foto_masuk_path, dicatat_oleh)
                          OUTPUT INSERTED.id_kunjungan VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       id_personel, id_dituju, id_keperluan, keterangan, asal_perusahaan, no_plat, id_comp_area,
                       foto_masuk_path, user_id)
        id_baru = cursor.fetchone()[0]
        conn.commit()
        return id_baru
    finally:
        conn.close()


def catat_keluar(id_kunjungan):
    return _ubah("UPDATE kunjungan SET waktu_keluar = GETDATE() WHERE id_kunjungan = ? AND waktu_keluar IS NULL",
                 id_kunjungan)


def area_akun(id_user):
    rows = _query("SELECT id_comp_area FROM users WHERE id_user = ?", id_user)
    return rows[0]["id_comp_area"] if rows else None
