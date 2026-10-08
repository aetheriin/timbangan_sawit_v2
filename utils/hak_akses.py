"""Hak akses dari database (Admin › Hak Akses): level -> menu -> aksi (tambah / ubah / hapus).

Semua level non-admin MELIHAT semua menu; yang dibatasi hanya aksinya. Level is_admin hanya area Admin.
Dibaca dari cache memori 30 detik (tidak menambah query per request); disimpan ulang -> hapus_cache()."""
from functools import wraps

from flask import jsonify, request
from flask_login import current_user

from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

AKSI = ("tambah", "ubah", "hapus")


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


@cache_ttl(30)
def peta_akses():
    """{id_level: {kode_menu: {"tambah": bool, "ubah": bool, "hapus": bool}}}"""
    peta = {}
    for r in _query("""SELECT la.id_level, m.kode, la.bisa_tambah, la.bisa_ubah, la.bisa_hapus
                       FROM level_akses la JOIN menu m ON m.id_menu = la.id_menu WHERE m.is_active = 1"""):
        peta.setdefault(r["id_level"], {})[r["kode"]] = {
            "tambah": bool(r["bisa_tambah"]), "ubah": bool(r["bisa_ubah"]), "hapus": bool(r["bisa_hapus"])}
    return peta


@cache_ttl(30)
def menu_sidebar():
    """Menu utama (punya url) untuk sidebar non-admin, urut sesuai kolom urutan."""
    return _query("""SELECT kode, nama, url, ikon FROM menu
                     WHERE id_parent IS NULL AND url IS NOT NULL AND is_active = 1 ORDER BY urutan, nama""")


def hapus_cache():
    peta_akses.hapus()
    menu_sidebar.hapus()


def boleh(kode_menu, *aksi, user=None):
    """True bila level user boleh salah satu aksi di menu itu. Admin tidak punya aksi operasional."""
    user = user or current_user
    if not getattr(user, "is_authenticated", False) or getattr(user, "is_admin", False):
        return False
    hak = peta_akses().get(user.id_level, {}).get(kode_menu, {})
    return any(hak.get(a) for a in (aksi or AKSI))


def izin(kode_menu, *aksi):
    """Pengganti role_required: @izin('FORM_SECURITY', 'tambah'). kode_menu boleh tuple (salah satu cukup)."""
    daftar_kode = kode_menu if isinstance(kode_menu, (tuple, list)) else (kode_menu,)

    def dekorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Belum login"}), 401
            if not any(boleh(k, *aksi) for k in daftar_kode):
                from utils.keamanan import log_keamanan
                log_keamanan("AKSES_DITOLAK", f"level {current_user.role} ke {f.__name__} ({request.path})")
                return jsonify({"error": "Level Anda tidak punya akses untuk aksi ini"}), 403
            return f(*args, **kwargs)
        return wrapped
    return dekorator


def admin_required(f):
    """Halaman / API Admin: hanya level is_admin."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Belum login"}), 401
        if not current_user.is_admin:
            from utils.keamanan import log_keamanan
            log_keamanan("AKSES_DITOLAK", f"level {current_user.role} ke {f.__name__}")
            return jsonify({"error": "Khusus Admin"}), 403
        return f(*args, **kwargs)
    return wrapped


# ===== Admin › Hak Akses =====
def daftar_level():
    return _query("""SELECT l.id_level, l.kode, l.nama, l.is_admin, l.halaman_awal, l.keterangan, l.is_active,
                            (SELECT COUNT(*) FROM akun u WHERE u.id_level = l.id_level AND u.is_active = 1) AS jumlah_user
                     FROM level l ORDER BY l.is_admin DESC, l.nama""")


def daftar_menu_akses():
    """Menu yang punya aksi (bagian halaman), dikelompokkan per induk untuk matriks."""
    return _query("""SELECT m.id_menu, m.kode, m.nama, p.nama AS induk
                     FROM menu m LEFT JOIN menu p ON p.id_menu = m.id_parent
                     WHERE m.is_active = 1 AND (m.id_parent IS NOT NULL
                           OR NOT EXISTS (SELECT 1 FROM menu c WHERE c.id_parent = m.id_menu))
                     ORDER BY COALESCE(p.urutan, m.urutan), m.urutan""")


def akses_level(id_level):
    return {r["id_menu"]: r for r in _query(
        "SELECT id_menu, bisa_tambah, bisa_ubah, bisa_hapus FROM level_akses WHERE id_level = ?", id_level)}


def simpan_akses_level(id_level, akses):
    """akses = {id_menu: (tambah, ubah, hapus)}; menu tanpa centang dihapus barisnya."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM level_akses WHERE id_level = ?", id_level)
        for id_menu, (t, u, h) in akses.items():
            if t or u or h:
                cursor.execute("""INSERT INTO level_akses (id_level, id_menu, bisa_tambah, bisa_ubah, bisa_hapus)
                                  VALUES (?, ?, ?, ?, ?)""", id_level, id_menu, int(t), int(u), int(h))
        conn.commit()
    finally:
        conn.close()
    hapus_cache()


def get_level(id_level):
    rows = _query("SELECT id_level, kode, nama, is_admin, halaman_awal, keterangan, is_active FROM level WHERE id_level = ?",
                  id_level)
    return rows[0] if rows else None


def kode_level_dipakai(kode, kecuali=None):
    return any(r["id_level"] != kecuali for r in _query("SELECT id_level FROM level WHERE kode = ?", kode))


def simpan_level(id_level, kode, nama, halaman_awal, keterangan):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_level is None:
            cursor.execute("""INSERT INTO level (kode, nama, halaman_awal, keterangan) OUTPUT INSERTED.id_level
                              VALUES (?, ?, ?, ?)""", kode, nama, halaman_awal, keterangan)
            id_level = cursor.fetchone()[0]
        else:
            cursor.execute("UPDATE level SET nama = ?, halaman_awal = ?, keterangan = ? WHERE id_level = ?",
                           nama, halaman_awal, keterangan, id_level)
        conn.commit()
        return id_level
    finally:
        conn.close()


def set_aktif_level(id_level, aktif):
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE level SET is_active = ? WHERE id_level = ?", 1 if aktif else 0, id_level)
        conn.commit()
    finally:
        conn.close()
