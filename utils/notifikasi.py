"""Notifikasi lonceng di top bar. Sasaran memakai hak akses menu (Admin › Level & Hak Akses), bukan nama level:
level yang punya aksi apa pun di menu `kode_menu` melihat notifikasinya. Dibaca / belum per user."""
from utils.db_utils import get_connection, _rows_to_dicts
from utils.hak_akses import peta_akses

HARI_SIMPAN = 30        # yang ditampilkan di lonceng


def buat(kode_menu, judul, isi=None, tautan=None, id_comp_area=None, cursor=None):
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


def daftar(user, batas=30):
    """(daftar notifikasi terbaru, jumlah belum dibaca) untuk user ini."""
    menu = _menu_user(user)
    if not menu:
        return [], 0
    tanda = ", ".join("?" * len(menu))
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""SELECT TOP ({int(batas)}) n.id_notifikasi, n.judul, n.isi, n.tautan, n.waktu, ar.nama AS area,
                                  CASE WHEN b.id_user IS NULL THEN 0 ELSE 1 END AS dibaca
                           FROM notifikasi n
                           LEFT JOIN notifikasi_baca b ON b.id_notifikasi = n.id_notifikasi AND b.id_user = ?
                           LEFT JOIN comp_area ar ON ar.id_comp_area = n.id_comp_area
                           WHERE n.kode_menu IN ({tanda}) AND n.waktu >= DATEADD(DAY, -{HARI_SIMPAN}, GETDATE())
                           ORDER BY n.waktu DESC""", user.id, *menu)
        rows = _rows_to_dicts(cursor)
        cursor.execute(f"""SELECT COUNT(*) FROM notifikasi n
                           WHERE n.kode_menu IN ({tanda}) AND n.waktu >= DATEADD(DAY, -{HARI_SIMPAN}, GETDATE())
                             AND NOT EXISTS (SELECT 1 FROM notifikasi_baca b
                                             WHERE b.id_notifikasi = n.id_notifikasi AND b.id_user = ?)""", *menu, user.id)
        belum = cursor.fetchone()[0]
    finally:
        conn.close()
    return [{**r, "waktu": r["waktu"].strftime("%Y-%m-%d %H:%M"), "dibaca": bool(r["dibaca"])} for r in rows], belum


def tandai_baca(user, id_notifikasi=None):
    """Satu notifikasi, atau semua yang terlihat user ini bila id_notifikasi None."""
    menu = _menu_user(user)
    if not menu:
        return
    tanda = ", ".join("?" * len(menu))
    filter_id = "AND n.id_notifikasi = ?" if id_notifikasi else ""
    conn = get_connection()
    try:
        conn.cursor().execute(f"""INSERT INTO notifikasi_baca (id_notifikasi, id_user)
                                  SELECT n.id_notifikasi, ? FROM notifikasi n
                                  WHERE n.kode_menu IN ({tanda}) {filter_id}
                                    AND NOT EXISTS (SELECT 1 FROM notifikasi_baca b
                                                    WHERE b.id_notifikasi = n.id_notifikasi AND b.id_user = ?)""",
                              user.id, *menu, *([id_notifikasi] if id_notifikasi else []), user.id)
        conn.commit()
    finally:
        conn.close()
