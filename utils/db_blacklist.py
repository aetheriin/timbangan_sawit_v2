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
               b.tgl_blacklist, b.created_at, u.nama AS oleh, lv.kode AS role_oleh,
               p.id_personel, p.kode_personel, p.nama_personel, k.no_plat, b.no_plat_terkait,
               c.nama_supplier AS customer_terkait, a.nama_supplier AS pengangkutan_terkait
        FROM blacklist b
        LEFT JOIN supplier c ON b.id_customer_terkait = c.id_supplier
        LEFT JOIN supplier a ON b.id_pengangkutan_terkait = a.id_supplier
        JOIN users u ON b.created_by = u.id_user
        JOIN level lv ON lv.id_level = u.id_level
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


# Data personel + transaksi terakhirnya sebagai SUPIR (plat, customer, pengangkutan saat itu).
# Bukan supir / belum pernah membawa truk -> kolom transaksi NULL (form blacklist tidak menampilkannya).
_SELECT_PERSONEL = """
    SELECT {top} p.id_personel AS id_target, p.kode_personel, p.nama_personel, p.nik, p.no_sim, p.kategori,
           p.foto_path, p.is_blacklisted, tr.no_plat AS plat_terakhir, tr.id_supplier AS id_customer_terakhir,
           tr.customer AS customer_terakhir, tr.id_pengangkutan AS id_pengangkutan_terakhir,
           tr.pengangkutan AS pengangkutan_terakhir, tr.created_at AS waktu_terakhir
    FROM v_personel p
    OUTER APPLY (SELECT TOP 1 k.no_plat, t.id_supplier, s.nama_supplier AS customer, t.id_pengangkutan,
                        a.nama_supplier AS pengangkutan, t.created_at
                 FROM transaksi t JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
                 JOIN supplier s ON t.id_supplier = s.id_supplier
                 LEFT JOIN supplier a ON t.id_pengangkutan = a.id_supplier
                 WHERE t.id_driver = p.id_personel ORDER BY t.created_at DESC) tr
    WHERE p.is_active = 1"""


def _rapikan_target(data):
    for r in data:
        r["is_blacklisted"] = bool(r["is_blacklisted"])
        if r.get("waktu_terakhir") is not None:
            r["waktu_terakhir"] = r["waktu_terakhir"].strftime("%Y-%m-%d %H:%M")
    return data


def cari_target(tipe, kata, batas=8):
    """Kandidat target: personel (kode / NIK / nama / no SIM / ID) atau kendaraan (plat)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        pola = f"%{kata}%"
        if tipe == "PERSONEL":
            cursor.execute(_SELECT_PERSONEL.format(top=f"TOP {int(batas)}") + """
                AND (p.kode_personel LIKE ? OR p.nik LIKE ? OR p.nama_personel LIKE ? OR p.no_sim LIKE ?
                     OR CAST(p.id_personel AS VARCHAR) = ?)
                ORDER BY p.nama_personel""", pola, pola, pola, pola, kata.lstrip("0") or "0")
        else:
            # Plat + STNK, supir utama, jumlah supir terdaftar, dan transaksi terakhir (supir, customer, angkutan)
            cursor.execute(f"""
                SELECT TOP {int(batas)} k.id_kendaraan AS id_target, k.no_plat, k.no_stnk, k.is_blacklisted, k.is_active,
                       u.id_personel AS id_supir_utama, u.kode_personel AS kode_supir_utama, u.nama_personel AS nama_supir_utama,
                       (SELECT COUNT(*) FROM kendaraan_driver kd JOIN personel p ON p.id_personel = kd.id_driver
                        WHERE kd.id_kendaraan = k.id_kendaraan AND kd.is_active = 1 AND p.is_active = 1) AS jumlah_supir,
                       tr.id_driver AS id_supir_terakhir, tr.kode_personel AS kode_supir_terakhir,
                       tr.nama_personel AS nama_supir_terakhir, tr.customer AS customer_terakhir,
                       tr.pengangkutan AS pengangkutan_terakhir, tr.created_at AS waktu_terakhir
                FROM kendaraan k
                OUTER APPLY (SELECT TOP 1 p.id_personel, p.kode_personel, p.nama_personel
                             FROM kendaraan_driver kd JOIN personel p ON p.id_personel = kd.id_driver
                             WHERE kd.id_kendaraan = k.id_kendaraan AND kd.is_active = 1 AND kd.is_utama = 1) u
                OUTER APPLY (SELECT TOP 1 t.id_driver, p.kode_personel, p.nama_personel, s.nama_supplier AS customer,
                                    a.nama_supplier AS pengangkutan, t.created_at
                             FROM transaksi t JOIN personel p ON p.id_personel = t.id_driver
                             JOIN supplier s ON t.id_supplier = s.id_supplier
                             LEFT JOIN supplier a ON t.id_pengangkutan = a.id_supplier
                             WHERE t.id_kendaraan = k.id_kendaraan ORDER BY t.created_at DESC) tr
                WHERE REPLACE(k.no_plat, ' ', '') LIKE ?
                ORDER BY k.no_plat""", f"%{kata.replace(' ', '')}%")
        return _rapikan_target(_rows_to_dicts(cursor))
    finally:
        conn.close()


def get_target_personel(id_personel):
    """Satu personel (hasil cocok wajah) dengan data transaksi terakhir."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_SELECT_PERSONEL.format(top="") + " AND p.id_personel = ?", id_personel)
        rows = _rapikan_target(_rows_to_dicts(cursor))
        return rows[0] if rows else None
    finally:
        conn.close()


def tambah_blacklist(tipe, id_target, no_surat, alasan, file_surat, tgl_blacklist, user_id, terkait=None):
    """terkait (personel): {no_plat, id_customer, id_pengangkutan} saat itu -> disimpan sebagai informasi."""
    terkait = terkait or {}
    """INSERT blacklist + set is_blacklisted = 1 dalam satu transaksi. Error bila target sudah diblacklist."""
    if tipe not in TIPE_VALID:                        # nama tabel disisipkan ke SQL -> hanya daftar tetap
        raise ValueError("Tipe blacklist tidak valid")
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
                                                  file_surat_blacklist, tgl_blacklist, created_by,
                                                  no_plat_terkait, id_customer_terkait, id_pengangkutan_terkait)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       tipe, id_target, no_surat, alasan, file_surat, tgl_blacklist, user_id,
                       terkait.get("no_plat"), terkait.get("id_customer"), terkait.get("id_pengangkutan"))
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
