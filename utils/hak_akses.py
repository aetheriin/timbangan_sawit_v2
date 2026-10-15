"""Hak akses dari database (Admin › Level & Hak Akses): jabatan (tabel level) -> menu -> lihat / tambah / ubah / hapus.

Jabatan milik satu departemen (level.id_department, migrasi 026). Lihat = halaman / tab boleh dibuka; menu induk
(Stasiun Timbang, Pengenalan Wajah, Data Master) terlihat bila salah satu tab-nya boleh dilihat. Level is_admin hanya
area Admin. Dibaca dari cache memori 30 detik (tidak menambah query per request); disimpan ulang -> hapus_cache()."""
from functools import wraps

import pyodbc
from flask import abort, jsonify, redirect, request
from flask_login import current_user

from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

AKSI = ("tambah", "ubah", "hapus")
# "setujui" = boleh menyetujui / menolak pengajuan di menu itu (mis. tambah & hapus blacklist); di Daftar Tiket =
# memverifikasi (menandai sudah diperiksa) tiket selesai & menyetujui koreksi tiket (Ubah = mengajukan koreksi).
# Hanya untuk menu
# yang punya proses persetujuan (lihat AKSI_MENU); tidak termasuk "aksi apa pun" pada boleh(kode_menu).
# Aksi yang benar-benar ada di tiap menu (dipakai @izin / boleh di kode). Matriks Hak Akses hanya menampilkan
# centang untuk aksi ini; yang lain tidak berarti apa-apa. Menu baru yang belum terdaftar di sini = semua aksi.
AKSI_MENU = {
    "DASHBOARD": ("ubah",), "LIST": ("ubah", "setujui"), "ABSENSI": (), "AUDIT_LOG": (),
    "FORM_SECURITY": ("tambah", "ubah"), "FORM_TIMBANGAN": ("tambah",), "FORM_SORTASI": ("tambah",),
    "FORM_LAB": ("tambah", "ubah"),
    "PERSONEL": AKSI, "MASTER_DRIVER": AKSI, "MASTER_KENDARAAN": ("tambah", "ubah"),
    "MASTER_MITRA": ("tambah", "ubah"), "MASTER_PRODUK": ("tambah", "ubah"),
    "KONTRAK_DO": ("tambah", "ubah"), "BLACKLIST": ("tambah", "hapus", "setujui"), "KUNJUNGAN": ("tambah", "ubah"),
    "KELEBIHAN_DO": ("tambah", "ubah"),
}


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
    """{id_level: {kode_menu: {"lihat": bool, "tambah": bool, "ubah": bool, "hapus": bool}}}
    Sebelum migrasi 026 (tanpa bisa_lihat) semua menu dianggap boleh dilihat, seperti perilaku lama."""
    try:
        rows = _query("""SELECT la.id_level, m.kode, la.bisa_lihat, la.bisa_tambah, la.bisa_ubah, la.bisa_hapus, la.bisa_setujui
                         FROM level_akses la JOIN menu m ON m.id_menu = la.id_menu WHERE m.is_active = 1""")
    except pyodbc.Error:        # sebelum migrasi 026 / 029
        rows = _query("""SELECT la.id_level, m.kode, 1 AS bisa_lihat, la.bisa_tambah, la.bisa_ubah, la.bisa_hapus, 0 AS bisa_setujui
                         FROM level_akses la JOIN menu m ON m.id_menu = la.id_menu WHERE m.is_active = 1""")
    peta = {}
    for r in rows:
        peta.setdefault(r["id_level"], {})[r["kode"]] = {
            "lihat": bool(r["bisa_lihat"]), "tambah": bool(r["bisa_tambah"]), "ubah": bool(r["bisa_ubah"]),
            "hapus": bool(r["bisa_hapus"]), "setujui": bool(r["bisa_setujui"])}
    return peta


@cache_ttl(30)
def akses_khusus():
    """Hak akses khusus per pengguna (tabel akun_akses, migrasi 031): {id_user: {kode_menu: {lihat, tambah, ...}}}.
    Baris di sini menggantikan hak jabatan untuk menu itu saja (bisa menambah maupun mencabut)."""
    try:
        rows = _query("""SELECT a.id_user, m.kode, a.bisa_lihat, a.bisa_tambah, a.bisa_ubah, a.bisa_hapus, a.bisa_setujui
                         FROM akun_akses a JOIN menu m ON m.id_menu = a.id_menu WHERE m.is_active = 1""")
    except pyodbc.Error:        # sebelum migrasi 031
        return {}
    peta = {}
    for r in rows:
        peta.setdefault(r["id_user"], {})[r["kode"]] = {
            "lihat": bool(r["bisa_lihat"]), "tambah": bool(r["bisa_tambah"]), "ubah": bool(r["bisa_ubah"]),
            "hapus": bool(r["bisa_hapus"]), "setujui": bool(r["bisa_setujui"])}
    return peta


def hak_user(user):
    """Hak efektif pengguna: hak jabatan, ditimpa hak khusus pengguna per menu."""
    hak = peta_akses().get(user.id_level, {})
    khusus = akses_khusus().get(getattr(user, "id", None))
    return {**hak, **khusus} if khusus else hak


@cache_ttl(30)
def anak_menu():
    """{kode_induk: [kode_anak, ...]} untuk menu yang punya tab (bagian halaman)."""
    peta = {}
    for r in _query("""SELECT p.kode AS induk, m.kode FROM menu m JOIN menu p ON p.id_menu = m.id_parent
                       WHERE m.is_active = 1 ORDER BY m.urutan"""):
        peta.setdefault(r["induk"], []).append(r["kode"])
    return peta


@cache_ttl(30)
def menu_sidebar():
    """Menu utama (punya url) untuk sidebar non-admin, urut sesuai kolom urutan."""
    return _query("""SELECT kode, nama, url, ikon FROM menu
                     WHERE id_parent IS NULL AND url IS NOT NULL AND is_active = 1 ORDER BY urutan, nama""")


def hapus_cache():
    peta_akses.hapus()
    akses_khusus.hapus()
    menu_sidebar.hapus()
    anak_menu.hapus()


def jabatan_dengan(kode_menu, aksi):
    """id jabatan (non-admin, aktif) yang punya aksi di menu itu, mis. jabatan_dengan('BLACKLIST', 'setujui')."""
    aktif = {lv["id_level"] for lv in daftar_level() if lv["is_active"] and not lv["is_admin"]}
    return sorted(i for i, hak in peta_akses().items() if i in aktif and hak.get(kode_menu, {}).get(aksi))


def pengguna_khusus_dengan(kode_menu, aksi):
    """id pengguna aktif yang diberi aksi itu lewat hak khusus (di luar jabatannya)."""
    calon = [i for i, hak in akses_khusus().items() if hak.get(kode_menu, {}).get(aksi)]
    if not calon:
        return []
    aktif = {r["id_user"] for r in _query(f"""SELECT u.id_user FROM akun u JOIN level l ON l.id_level = u.id_level
                                             WHERE u.is_active = 1 AND l.is_admin = 0
                                               AND u.id_user IN ({",".join("?" * len(calon))})""", *calon)}
    return sorted(i for i in calon if i in aktif)


def boleh(kode_menu, *aksi, user=None):
    """True bila level user boleh salah satu aksi di menu itu. Admin tidak punya aksi operasional."""
    user = user or current_user
    if not getattr(user, "is_authenticated", False) or getattr(user, "is_admin", False):
        return False
    hak = hak_user(user).get(kode_menu, {})
    return any(hak.get(a) for a in (aksi or AKSI))


def boleh_lihat(kode_menu, user=None):
    """Halaman / tab boleh dibuka. Menu induk terlihat bila dirinya atau salah satu tab-nya boleh dilihat."""
    user = user or current_user
    if not getattr(user, "is_authenticated", False) or getattr(user, "is_admin", False):
        return False
    hak = hak_user(user)
    return any(hak.get(k, {}).get("lihat") for k in (kode_menu, *anak_menu().get(kode_menu, ())))


def tab_lihat(tabs):
    """[(key, label, kode_menu), ...] -> [(key, label), ...] yang boleh dilihat user (untuk tab_header)."""
    return [(key, label) for key, label, kode in tabs if boleh_lihat(kode)]


def halaman(kode_menu):
    """Halaman yang hanya terbuka bila jabatan boleh melihatnya; selain itu ke halaman awal jabatan (atau 403)."""
    def dekorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            kode = kode_menu(request) if callable(kode_menu) else kode_menu
            if current_user.is_authenticated and not current_user.is_admin and not boleh_lihat(kode):
                from utils.keamanan import log_keamanan
                log_keamanan("AKSES_DITOLAK", f"level {current_user.role} ke halaman {kode} ({request.path})")
                awal = halaman_awal_user()
                if awal and awal.split("?")[0] != request.path:
                    return redirect(awal)
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return dekorator


def kode_halaman(url):
    """Kode menu untuk sebuah alamat halaman, mis. '/weighbridge?view=form' -> FORM, '/weighbridge?tab=x' -> LIST."""
    path, _, query = (url or "").partition("?")
    if path == "/weighbridge":
        return "FORM" if "view=form" in query else "LIST"
    return next((m["kode"] for m in menu_sidebar() if (m["url"] or "").split("?")[0] == path), None)


def halaman_awal_user(user=None):
    """Halaman awal jabatan bila boleh dilihat, selain itu menu pertama di sidebar yang boleh dilihat."""
    user = user or current_user
    lv = get_level(user.id_level) if getattr(user, "id_level", None) else None
    awal = lv["halaman_awal"] if lv else None
    if awal and boleh_lihat(kode_halaman(awal), user):
        return awal
    return next((m["url"] for m in menu_sidebar() if boleh_lihat(m["kode"], user)), None)


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
                return jsonify({"error": "Level Anda tidak memiliki akses untuk tindakan ini"}), 403
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
    """Jabatan beserta departemennya (sebelum migrasi 026: tanpa departemen)."""
    try:
        return _query("""SELECT l.id_level, l.kode, l.nama, l.is_admin, l.halaman_awal, l.keterangan, l.is_active,
                                l.id_department, d.nama AS department,
                                (SELECT COUNT(*) FROM akun u WHERE u.id_level = l.id_level AND u.is_active = 1) AS jumlah_user
                         FROM level l LEFT JOIN department d ON d.id_department = l.id_department
                         ORDER BY l.is_admin DESC, d.nama, l.nama""")
    except pyodbc.Error:
        return _query("""SELECT l.id_level, l.kode, l.nama, l.is_admin, l.halaman_awal, l.keterangan, l.is_active,
                                NULL AS id_department, NULL AS department,
                                (SELECT COUNT(*) FROM akun u WHERE u.id_level = l.id_level AND u.is_active = 1) AS jumlah_user
                         FROM level l ORDER BY l.is_admin DESC, l.nama""")


def daftar_menu_akses():
    """Menu yang punya aksi (bagian halaman), dikelompokkan per induk untuk matriks; "aksi" = aksi yang berlaku."""
    return [{**m, "aksi": list(AKSI_MENU.get(m["kode"], AKSI))} for m in _query("""SELECT m.id_menu, m.kode, m.nama, p.nama AS induk
                     FROM menu m LEFT JOIN menu p ON p.id_menu = m.id_parent
                     WHERE m.is_active = 1 AND (m.id_parent IS NOT NULL
                           OR NOT EXISTS (SELECT 1 FROM menu c WHERE c.id_parent = m.id_menu))
                     ORDER BY COALESCE(p.urutan, m.urutan), m.urutan""")]


def akses_level(id_level):
    return {r["id_menu"]: r for r in _query(
        "SELECT id_menu, bisa_lihat, bisa_tambah, bisa_ubah, bisa_hapus, bisa_setujui FROM level_akses WHERE id_level = ?",
        id_level)}


def simpan_akses_level(id_level, akses):
    """akses = {id_menu: (lihat, tambah, ubah, hapus, setujui)}. Aksi apa pun berarti halaman itu juga boleh dilihat.
    Menu tanpa centang dihapus barisnya."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM level_akses WHERE id_level = ?", id_level)
        for id_menu, (lh, t, u, h, s) in akses.items():
            if lh or t or u or h or s:
                cursor.execute("""INSERT INTO level_akses (id_level, id_menu, bisa_lihat, bisa_tambah, bisa_ubah, bisa_hapus, bisa_setujui)
                                  VALUES (?, ?, 1, ?, ?, ?, ?)""", id_level, id_menu, int(t), int(u), int(h), int(s))
        conn.commit()
    finally:
        conn.close()
    hapus_cache()


def akses_user(id_user):
    """Baris hak khusus pengguna: {id_menu: {...}}"""
    return {r["id_menu"]: r for r in _query(
        "SELECT id_menu, bisa_lihat, bisa_tambah, bisa_ubah, bisa_hapus, bisa_setujui FROM akun_akses WHERE id_user = ?",
        id_user)}


def simpan_akses_user(id_user, akses):
    """akses = {id_menu: (lihat, tambah, ubah, hapus, setujui)} hanya untuk menu yang berbeda dari jabatannya.
    Semua dikosongkan = kembali mengikuti jabatan."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM akun_akses WHERE id_user = ?", id_user)
        for id_menu, (lh, t, u, h, s) in akses.items():
            lh = lh or t or u or h or s
            cursor.execute("""INSERT INTO akun_akses (id_user, id_menu, bisa_lihat, bisa_tambah, bisa_ubah, bisa_hapus, bisa_setujui)
                              VALUES (?, ?, ?, ?, ?, ?, ?)""", id_user, id_menu, int(lh), int(t), int(u), int(h), int(s))
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


def simpan_level(id_level, kode, nama, halaman_awal, keterangan, id_department):
    """Departemen jabatan diubah -> departemen semua pengguna jabatan itu ikut berubah."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_level is None:
            cursor.execute("""SET NOCOUNT ON; INSERT INTO level (kode, nama, halaman_awal, keterangan, id_department)
                              VALUES (?, ?, ?, ?, ?); SELECT CAST(SCOPE_IDENTITY() AS INT)""",
                           kode, nama, halaman_awal, keterangan, id_department)
            id_level = cursor.fetchone()[0]
        else:
            cursor.execute("""UPDATE level SET nama = ?, halaman_awal = ?, keterangan = ?, id_department = ?
                              WHERE id_level = ?""", nama, halaman_awal, keterangan, id_department, id_level)
            cursor.execute("UPDATE akun SET id_department = ? WHERE id_level = ?", id_department, id_level)
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
