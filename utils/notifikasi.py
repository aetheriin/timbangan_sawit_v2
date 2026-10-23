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
        sql = """INSERT INTO Notification (MenuCode, CompAreaID, Title, Message, Link, LevelDetID, CompID, UserID)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        args = (kode_menu, id_comp_area, judul[:150], (isi or "")[:500] or None, tautan, id_level, id_company, id_user)
    else:
        sql = "INSERT INTO Notification (MenuCode, CompAreaID, Title, Message, Link) VALUES (?, ?, ?, ?, ?)"
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
    sql, args = sql_area("n.CompAreaID", id_area)
    return (f" AND (n.CompAreaID IS NULL{sql.replace(' AND ', ' OR ', 1)})", args) if sql else ("", [])


def _syarat(user, id_area):
    """(SQL syarat, argumen) notifikasi yang terlihat user: per menu (area), per jabatan (PT), atau per user."""
    from utils.area import company_user
    menu = _menu_user(user)
    f_area, a_area = _filter_area(id_area)
    bagian, args = [], []
    if menu:
        bagian.append(f"(n.LevelDetID IS NULL AND n.UserID IS NULL AND n.MenuCode IN ({', '.join('?' * len(menu))}){f_area})")
        args += [*menu, *a_area]
    bagian.append("n.UserID = ?")
    args.append(user.id)
    if not getattr(user, "is_admin", False):
        pt = company_user(user.id)
        f_pt = "" if pt is None else f" AND (n.CompID IS NULL OR n.CompID IN ({', '.join('?' * len(pt or [0]))}))"
        bagian.append(f"(n.UserID IS NULL AND n.LevelDetID = ?{f_pt})")
        args += [user.id_level, *((sorted(pt) or [""]) if pt is not None else [])]
    return "(" + " OR ".join(bagian) + ")", args


def _syarat_lama(user, id_area):
    """Sebelum migrasi 027 (tanpa kolom sasaran): hanya per menu."""
    menu = _menu_user(user)
    if not menu:
        return "1 = 0", []
    f_area, a_area = _filter_area(id_area)
    return f"(n.MenuCode IN ({', '.join('?' * len(menu))}){f_area})", [*menu, *a_area]


def daftar(user, batas=30, id_area=None):
    """(daftar notifikasi terbaru, jumlah belum dibaca) untuk user ini."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for buat_syarat in (_syarat, _syarat_lama):
            syarat, args = buat_syarat(user, id_area)
            try:
                cursor.execute(f"""SELECT TOP ({int(batas)}) n.NotificationID AS id_notifikasi, n.Title AS judul, n.Message AS isi, n.Link AS tautan, n.CreateDate AS waktu, ar.AreaName AS area,
                                          CASE WHEN b.UserID IS NULL THEN 0 ELSE 1 END AS dibaca
                                   FROM Notification n
                                   LEFT JOIN NotificationRead b ON b.NotificationID = n.NotificationID AND b.UserID = ?
                                   LEFT JOIN CompanyArea ar ON ar.CompAreaID = n.CompAreaID
                                   WHERE {syarat} AND n.CreateDate >= DATEADD(DAY, -{HARI_SIMPAN}, GETDATE())
                                   ORDER BY n.CreateDate DESC""", user.id, *args)
                break
            except pyodbc.Error:
                if buat_syarat is _syarat_lama:
                    raise
        rows = _rows_to_dicts(cursor)
        cursor.execute(f"""SELECT COUNT(*) FROM Notification n
                           WHERE {syarat} AND n.CreateDate >= DATEADD(DAY, -{HARI_SIMPAN}, GETDATE())
                             AND NOT EXISTS (SELECT 1 FROM NotificationRead b
                                             WHERE b.NotificationID = n.NotificationID AND b.UserID = ?)""",
                       *args, user.id)
        belum = cursor.fetchone()[0]
    finally:
        conn.close()
    return [{**r, "waktu": r["waktu"].strftime("%Y-%m-%d %H:%M"), "dibaca": bool(r["dibaca"])} for r in rows], belum


def tandai_baca(user, id_notifikasi=None, id_area=None):
    """Satu notifikasi, atau semua yang terlihat user ini bila id_notifikasi None."""
    syarat, args = _syarat(user, id_area)
    filter_id = "AND n.NotificationID = ?" if id_notifikasi else ""
    conn = get_connection()
    try:
        conn.cursor().execute(f"""INSERT INTO NotificationRead (NotificationID, UserID)
                                  SELECT n.NotificationID, ? FROM Notification n
                                  WHERE {syarat} {filter_id}
                                    AND NOT EXISTS (SELECT 1 FROM NotificationRead b
                                                    WHERE b.NotificationID = n.NotificationID AND b.UserID = ?)""",
                              user.id, *args, *([id_notifikasi] if id_notifikasi else []), user.id)
        conn.commit()
    finally:
        conn.close()
