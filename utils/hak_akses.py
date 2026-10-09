"""Hak akses dari database: department -> menu yang boleh dibuka, level (jabatan) -> aksi (tambah / ubah / hapus).

Akses akhir = menu department (Admin › Organisasi › Department) DAN hak level (Admin › Level & Hak Akses).
Department tanpa daftar menu = tidak dibatasi (melihat semua menu). Level is_admin hanya area Admin.
Dibaca dari cache memori 30 detik (tidak menambah query per request); disimpan ulang -> hapus_cache()."""
import logging
from functools import wraps
from urllib.parse import parse_qs, urlparse

from flask import jsonify, request
from flask_login import current_user

from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

AKSI = ("tambah", "ubah", "hapus")
log = logging.getLogger(__name__)


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


@cache_ttl(30)
def peta_department():
    """{id_department: {kode_menu, ...}} hanya department yang dibatasi. Menu induk ikut bila salah satu anaknya ada."""
    try:
        rows = _query("""SELECT dm.id_department, m.kode, p.kode AS induk
                         FROM department_menu dm JOIN menu m ON m.id_menu = dm.id_menu
                         LEFT JOIN menu p ON p.id_menu = m.id_parent WHERE m.is_active = 1""")
    except Exception:          # migrasi 023 belum dijalankan -> department belum membatasi
        log.warning("Tabel department_menu belum ada (jalankan migrasi 023)", exc_info=True)
        return {}
    peta = {}
    for r in rows:
        peta.setdefault(r["id_department"], set()).update(k for k in (r["kode"], r["induk"]) if k)
    return peta


def hapus_cache():
    peta_akses.hapus()
    menu_sidebar.hapus()
    peta_department.hapus()


def boleh_lihat(kode_menu, user=None):
    """True bila department user boleh membuka menu itu (department tanpa daftar menu = semua boleh)."""
    user = user or current_user
    if not getattr(user, "is_authenticated", False) or getattr(user, "is_admin", False):
        return False
    menu = peta_department().get(getattr(user, "id_department", None))
    return menu is None or kode_menu in menu


def boleh(kode_menu, *aksi, user=None):
    """True bila menu boleh dibuka department user DAN level user boleh salah satu aksinya.
    Admin tidak punya aksi operasional."""
    user = user or current_user
    if not boleh_lihat(kode_menu, user):
        return False
    hak = peta_akses().get(user.id_level, {}).get(kode_menu, {})
    return any(hak.get(a) for a in (aksi or AKSI))


# Halaman -> kode menu (sidebar & penjaga halaman di pasang_penjaga_menu)
HALAMAN_MENU = {"/dashboard": "DASHBOARD", "/face-recognition": "FACE_RECOGNITION", "/blacklist": "BLACKLIST",
                "/tamu": "KUNJUNGAN", "/kontrak": "KONTRAK_DO", "/kelebihan-do": "KELEBIHAN_DO", "/master": "MASTER"}


def kode_halaman(url):
    """Kode menu untuk url halaman (mis. '/weighbridge?tab=lab' -> FORM_LAB), None bila bukan halaman menu."""
    u = urlparse(url or "")
    if u.path == "/weighbridge":
        q = parse_qs(u.query)           # tanpa view=form = halaman List (tab hanya memilih tahap awal)
        if q.get("view", [""])[0] != "form":
            return "LIST"
        tab = q.get("tab", [""])[0]
        return f"FORM_{tab.upper()}" if tab else "FORM"
    return HALAMAN_MENU.get(u.path)


def tab_boleh(peta=None):
    """Kunci tab yang boleh dibuka department user. peta = {kunci_tab: kode_menu}, bawaan tab halaman Form."""
    peta = peta or {t: f"FORM_{t.upper()}" for t in ("security", "timbangan", "sortasi", "lab")}
    return [t for t, kode in peta.items() if boleh_lihat(kode)]


def url_awal(user):
    """Halaman awal level bila department boleh membukanya, selain itu menu pertama yang boleh. None = tidak ada."""
    for url in [user.halaman_awal] + [m["url"] for m in menu_sidebar()]:
        kode = kode_halaman(url)
        if kode and boleh_lihat(kode, user):
            return url
    return None


def pasang_penjaga_menu(app):
    """Halaman menu yang tidak boleh dibuka department user -> dialihkan ke halaman yang boleh (atau 403)."""
    from flask import abort, redirect

    @app.before_request
    def jaga_halaman():
        if request.method != "GET" or not current_user.is_authenticated or current_user.is_admin:
            return None
        kode = kode_halaman(request.full_path)
        if kode is None or boleh_lihat(kode):
            return None
        tujuan = url_awal(current_user)
        if tujuan is None or kode_halaman(tujuan) == kode:
            abort(403)
        return redirect(tujuan)


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


# ===== Admin › Organisasi › Department: menu yang boleh dibuka =====
def menu_department():
    """{id_department: [id_menu, ...]} untuk department yang dibatasi."""
    hasil = {}
    for r in _query("SELECT id_department, id_menu FROM department_menu"):
        hasil.setdefault(r["id_department"], []).append(r["id_menu"])
    return hasil


def simpan_menu_department(id_department, daftar_id_menu):
    """Ganti daftar menu department; daftar kosong = tidak dibatasi."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM department_menu WHERE id_department = ?", id_department)
        for id_menu in sorted(set(daftar_id_menu)):
            cursor.execute("INSERT INTO department_menu (id_department, id_menu) VALUES (?, ?)", id_department, id_menu)
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
