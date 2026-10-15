"""Notifikasi lonceng di top bar. Sasaran:
- per menu (lama): jabatan yang punya hak apa pun di menu `kode_menu` melihatnya, disaring per area;
- per jabatan di PT tertentu (id_level + id_company), mis. persetujuan menunggu KTU di PT YBS;
- per user (id_user), mis. hasil persetujuan ke yang mengajukan.
Diklik -> tautan dibuka (halaman tujuan menyorot datanya). Dibaca / belum per user."""
import pyodbc

from utils.db_utils import get_connection, _rows_to_dicts
from utils.hak_akses import peta_akses

HARI_SIMPAN = 30        # yang ditampilkan di lonceng


def buat(kode_menu, judul, isi=None, tautan=None, id_comp_area=None, cursor=None, id_level=None, id_company=None,
         id_user=None):
    if id_level or id_user:
        sql = """INSERT INTO notifikasi (kode_menu, id_comp_area, judul, isi, tautan, id_level, id_company, id_user)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        args = (kode_menu, id_comp_area, judul[:150], (isi or "")[:500] or None, tautan, id_level, id_company, id_user)
    else:
        sql = "INSERT INTO notifikasi (kode_menu, id_comp_area, judul, isi, tautan) VALUES (?, ?, ?, ?, ?)"
        args = (kode_menu, id_comp_area, judul[:150], (isi or "")[:500] or None, tautan)
    if cursor is not None:
        cursor.execute(sql, *args)
        return
    conn = get_connection()
    try:
        conn.cursor().execute(sql, *args)
        conn.commit()
    finally:
        conn.close()


def _menu_user(user):
    if getattr(user, "is_admin", False):
        return []
    hak = peta_akses().get(user.id_level, {})
    return [k for k, v in hak.items() if any(v.values())]


def _filter_area(id_area):
    """Notifikasi tanpa area = untuk semua; selain itu hanya area user (id_area None = kantor pusat, semua)."""
    from utils.area_filter import sql_area
    sql, args = sql_area("n.id_comp_area", id_area)
    return (f" AND (n.id_comp_area IS NULL{sql.replace(' AND ', ' OR ', 1)})", args) if sql else ("", [])


def _syarat(user, id_area):
    """(SQL syarat, argumen) notifikasi yang terlihat user: per menu (area), per jabatan (PT), atau per user."""
    from utils.area import company_user
    menu = _menu_user(user)
    f_area, a_area = _filter_area(id_area)
    bagian, args = [], []
    if menu:
        bagian.append(f"(n.id_level IS NULL AND n.id_user IS NULL AND n.kode_menu IN ({', '.join('?' * len(menu))}){f_area})")
        args += [*menu, *a_area]
    bagian.append("n.id_user = ?")
    args.append(user.id)
    if not getattr(user, "is_admin", False):
        pt = company_user(user.id)
        f_pt = "" if pt is None else f" AND (n.id_company IS NULL OR n.id_company IN ({', '.join('?' * len(pt or [0]))}))"
        bagian.append(f"(n.id_user IS NULL AND n.id_level = ?{f_pt})")
        args += [user.id_level, *((sorted(pt) or [-1]) if pt is not None else [])]
    return "(" + " OR ".join(bagian) + ")", args


def _syarat_lama(user, id_area):
    """Sebelum migrasi 027 (tanpa kolom sasaran): hanya per menu."""
    menu = _menu_user(user)
    if not menu:
        return "1 = 0", []
    f_area, a_area = _filter_area(id_area)
    return f"(n.kode_menu IN ({', '.join('?' * len(menu))}){f_area})", [*menu, *a_area]


def daftar(user, batas=30, id_area=None):
    """(daftar notifikasi terbaru, jumlah belum dibaca) untuk user ini."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for buat_syarat in (_syarat, _syarat_lama):
            syarat, args = buat_syarat(user, id_area)
            try:
                cursor.execute(f"""SELECT TOP ({int(batas)}) n.id_notifikasi, n.judul, n.isi, n.tautan, n.waktu, ar.nama AS area,
                                          CASE WHEN b.id_user IS NULL THEN 0 ELSE 1 END AS dibaca
                                   FROM notifikasi n
                                   LEFT JOIN notifikasi_baca b ON b.id_notifikasi = n.id_notifikasi AND b.id_user = ?
                                   LEFT JOIN comp_area ar ON ar.id_comp_area = n.id_comp_area
                                   WHERE {syarat} AND n.waktu >= DATEADD(DAY, -{HARI_SIMPAN}, GETDATE())
                                   ORDER BY n.waktu DESC""", user.id, *args)
                break
            except pyodbc.Error:
                if buat_syarat is _syarat_lama:
                    raise
        rows = _rows_to_dicts(cursor)
        cursor.execute(f"""SELECT COUNT(*) FROM notifikasi n
                           WHERE {syarat} AND n.waktu >= DATEADD(DAY, -{HARI_SIMPAN}, GETDATE())
                             AND NOT EXISTS (SELECT 1 FROM notifikasi_baca b
                                             WHERE b.id_notifikasi = n.id_notifikasi AND b.id_user = ?)""",
                       *args, user.id)
        belum = cursor.fetchone()[0]
    finally:
        conn.close()
    return [{**r, "waktu": r["waktu"].strftime("%Y-%m-%d %H:%M"), "dibaca": bool(r["dibaca"])} for r in rows], belum


def tandai_baca(user, id_notifikasi=None, id_area=None):
    """Satu notifikasi, atau semua yang terlihat user ini bila id_notifikasi None."""
    syarat, args = _syarat(user, id_area)
    filter_id = "AND n.id_notifikasi = ?" if id_notifikasi else ""
    conn = get_connection()
    try:
        conn.cursor().execute(f"""INSERT INTO notifikasi_baca (id_notifikasi, id_user)
                                  SELECT n.id_notifikasi, ? FROM notifikasi n
                                  WHERE {syarat} {filter_id}
                                    AND NOT EXISTS (SELECT 1 FROM notifikasi_baca b
                                                    WHERE b.id_notifikasi = n.id_notifikasi AND b.id_user = ?)""",
                              user.id, *args, *([id_notifikasi] if id_notifikasi else []), user.id)
        conn.commit()
    finally:
        conn.close()
