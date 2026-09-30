"""Query tabel blacklist (menu Face Recognition > Blacklist). Blacklist permanen: hanya tambah."""
from datetime import date, datetime
from utils.db_utils import get_connection, _rows_to_dicts

TIPE_VALID = ("PERSONEL", "KENDARAAN")


def _format(r):
    for k, v in list(r.items()):
        if isinstance(v, datetime):
            r[k] = v.strftime("%Y-%m-%d %H:%M")
        elif isinstance(v, date):
            r[k] = v.isoformat()
    return r


def get_riwayat_blacklist(tipe=None, cari=None, batas=200):
    sql = """
        SELECT TOP (?) b.id_blacklist, b.tipe_entitas, b.no_surat_blacklist, b.alasan_blacklist, b.file_surat_blacklist,
               b.tgl_blacklist, b.created_at, u.nama AS oleh, u.role AS role_oleh,
               p.id_personel, p.kode_personel, p.nama_personel, k.no_plat
        FROM blacklist b
        JOIN users u ON b.created_by = u.id_user
        LEFT JOIN personel p ON b.id_personel = p.id_personel
        LEFT JOIN kendaraan k ON b.id_kendaraan = k.id_kendaraan
        WHERE 1 = 1"""
    params = [batas]
    if tipe:
        sql += " AND b.tipe_entitas = ?"
        params.append(tipe)
    if cari:
        pola = f"%{cari}%"
        sql += """ AND (p.kode_personel LIKE ? OR p.nama_personel LIKE ? OR p.nik LIKE ?
                        OR k.no_plat LIKE ? OR b.no_surat_blacklist LIKE ?)"""
        params += [pola] * 5
    sql += " ORDER BY b.tgl_blacklist DESC, b.id_blacklist DESC"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, *params)
    data = [_format(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


def cari_target(tipe, kata, batas=8):
    """Kandidat target: personel (kode / NIK / nama / ID) atau kendaraan (plat)."""
    conn = get_connection()
    cursor = conn.cursor()
    pola = f"%{kata}%"
    if tipe == "PERSONEL":
        cursor.execute(f"""
            SELECT TOP {int(batas)} p.id_personel AS id_target, p.kode_personel, p.nama_personel, p.nik, p.kategori,
                   p.foto_path, p.is_blacklisted,
                   (SELECT TOP 1 k.no_plat FROM transaksi t JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
                    WHERE t.id_driver = p.id_personel ORDER BY t.created_at DESC) AS plat_terakhir
            FROM personel p
            WHERE p.is_active = 1 AND (p.kode_personel LIKE ? OR p.nik LIKE ? OR p.nama_personel LIKE ?
                                       OR CAST(p.id_personel AS VARCHAR) = ?)
            ORDER BY p.nama_personel""", pola, pola, pola, kata.lstrip("0") or "0")
    else:
        compact = kata.replace(" ", "")
        cursor.execute(f"""
            SELECT TOP {int(batas)} k.id_kendaraan AS id_target, k.no_plat, k.no_stnk, k.is_blacklisted
            FROM kendaraan k
            WHERE REPLACE(k.no_plat, ' ', '') LIKE ?
            ORDER BY k.no_plat""", f"%{compact}%")
    data = _rows_to_dicts(cursor)
    conn.close()
    for r in data:
        r["is_blacklisted"] = bool(r["is_blacklisted"])
    return data


def tambah_blacklist(tipe, id_target, no_surat, alasan, file_surat, tgl_blacklist, user_id):
    """INSERT blacklist + set is_blacklisted = 1 dalam satu transaksi. Error bila target sudah diblacklist."""
    tabel, kolom = ("personel", "id_personel") if tipe == "PERSONEL" else ("kendaraan", "id_kendaraan")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT is_blacklisted FROM {tabel} WHERE {kolom} = ?", id_target)
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Target tidak ditemukan")
        if row.is_blacklisted:
            raise ValueError("Target sudah masuk blacklist")
        cursor.execute(f"""INSERT INTO blacklist (tipe_entitas, {kolom}, no_surat_blacklist, alasan_blacklist,
                                                  file_surat_blacklist, tgl_blacklist, created_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       tipe, id_target, no_surat, alasan, file_surat, tgl_blacklist, user_id)
        cursor.execute(f"UPDATE {tabel} SET is_blacklisted = 1 WHERE {kolom} = ?", id_target)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_surat_blacklist(tipe, id_target):
    """Surat blacklist terbaru untuk banner di Form Create Ticket."""
    kolom = "id_personel" if tipe == "PERSONEL" else "id_kendaraan"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""SELECT TOP 1 b.no_surat_blacklist, b.tgl_blacklist, b.file_surat_blacklist, u.nama AS oleh
                       FROM blacklist b JOIN users u ON b.created_by = u.id_user
                       WHERE b.{kolom} = ? ORDER BY b.tgl_blacklist DESC, b.id_blacklist DESC""", id_target)
    data = _rows_to_dicts(cursor)
    conn.close()
    return _format(data[0]) if data else None
