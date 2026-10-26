"""Hak akses dari database: aturan per menu (AccessMenu) untuk Semua user / Peran / Jabatan / Departemen / User,
Izinkan atau Larang per aksi (Larang menang). Peran = Departemen + Jabatan (LevelDetails), mis. Security · Staff.
Menu 3 level (flowchart navbar): Lv1 grup, Lv2 halaman, Lv3 bagian; menu hanya terlihat bila dirinya dan semua induknya
boleh dilihat (aturan induk menjadi gerbang). Peran admin (Level.IsAdmin) hanya area Admin.
Aturan hak efektif ada di database (dbo.fn_UserAccess / sp_UserMenu / sp_CekAkses) agar CPOS, Analytics & RekapIn memakai
aturan yang sama; aksi yang berlaku per menu = MenuAction. Dibaca dari cache memori 30 detik per pengguna
(tidak menambah query per request); disimpan ulang -> hapus_cache()."""
import re
from functools import wraps

from flask import abort, jsonify, redirect, request
from flask_login import current_user

from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

AKSI = ("tambah", "ubah", "hapus")
# "setujui" = boleh menyetujui / menolak pengajuan di menu itu (mis. tambah & hapus blacklist); di Daftar Tiket =
# memverifikasi (menandai sudah diperiksa) tiket selesai & menyetujui koreksi tiket (Ubah = mengajukan koreksi).
# "tolak" / "selesai" = menolak / menandai selesai sebuah request (dipakai RekapIn: Request Operator).
# Tidak termasuk "aksi apa pun" pada boleh(kode_menu). Aksi yang berlaku di tiap menu ada di tabel MenuAction.


# ActionType.ActionID untuk tiap aksi (seed schema.sql: 0 Delete, 1 View, 2 Create, 3 Edit, 4 Void, 5 Approve,
# 6 Reject, 7 Done). AKSI_SEMUA = urutan kolom di matriks Hak Akses; AKSI_OPSI = selain Lihat.
ID_AKSI = {"lihat": 1, "tambah": 2, "ubah": 3, "hapus": 0, "setujui": 5, "tolak": 6, "selesai": 7}
NAMA_AKSI = {v: k for k, v in ID_AKSI.items()}
AKSI_SEMUA = ("lihat", "tambah", "ubah", "hapus", "setujui", "tolak", "selesai")
AKSI_OPSI = AKSI_SEMUA[1:]


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def _kosong():
    return dict.fromkeys(AKSI_SEMUA, False)


KOLOM_HAK = {"lihat": "Visible", "tambah": "CanCreate", "ubah": "CanEdit", "hapus": "CanDelete", "setujui": "CanApprove",
             "tolak": "CanReject", "selesai": "CanDone"}


@cache_ttl(30)
def peta_akses():
    """Hak tiap peran dari aturan Semua / Peran / Jabatan / Departemen (tanpa aturan per user):
    {id_level (LevelDetID): {kode_menu: {"lihat", "tambah", ...: bool}}}"""
    peta = {}
    for r in _query("""SELECT ld.LevelDetID AS id_level, f.* FROM LevelDetails ld
                       CROSS APPLY dbo.fn_AccessFor(NULL, ld.LevelDetID) f"""):
        peta.setdefault(r["id_level"], {})[r["MenuCode"]] = {k: bool(r[c]) for k, c in KOLOM_HAK.items()}
    return peta


@cache_ttl(30)
def hak_menu_user(id_user):
    """Hak efektif dari dbo.sp_UserMenu (aturan sama dengan aplikasi lain), hanya menu yang terlihat:
    {kode_menu: {"lihat", "terlihat", "tambah", "ubah", "hapus", "setujui", "tolak", "selesai"}}"""
    hasil = {}
    for r in _query("EXEC dbo.sp_UserMenu @UserID = ?", id_user):
        hasil[r["MenuCode"]] = {"lihat": bool(r["Visible"]), "terlihat": bool(r["Visible"]), "tambah": bool(r["CanCreate"]),
                                "ubah": bool(r["CanEdit"]), "hapus": bool(r["CanDelete"]), "setujui": bool(r["CanApprove"]),
                                "tolak": bool(r["CanReject"]), "selesai": bool(r["CanDone"])}
    return hasil


def hak_user(user):
    """Hak efektif pengguna (dihitung di database dari semua aturan yang cocok)."""
    id_user = getattr(user, "id", None)
    return hak_menu_user(id_user) if id_user is not None else {}


@cache_ttl(30)
def semua_menu():
    """Semua menu aktif (urut) dengan kode induknya: dasar navbar 3 level & pencarian kode halaman."""
    return _query("""SELECT m.MenuID AS id_menu, m.MenuCode AS kode, m.MenuName AS nama, m.Url AS url, m.Icon AS ikon,
                            m.MenuLevel AS level, m.AppCode AS aplikasi, p.MenuCode AS induk,
                            (SELECT STRING_AGG(CAST(ma.ActionID AS VARCHAR(3)), ',') FROM MenuAction ma
                             WHERE ma.MenuID = m.MenuID) AS daftar_aksi
                     FROM Menu m LEFT JOIN Menu p ON p.MenuID = m.ParentMenuID
                     WHERE m.Active = 1 ORDER BY m.MenuLevel, m.SortOrder, m.MenuName""")


def aksi_menu(m):
    """Aksi selain Lihat yang berlaku di menu (MenuAction), urut seperti AKSI_OPSI."""
    ada = {NAMA_AKSI.get(int(x)) for x in (m.get("daftar_aksi") or "").split(",") if x.strip().isdigit()}
    return [a for a in AKSI_OPSI if a in ada]


@cache_ttl(30)
def anak_menu():
    """{kode_induk: [kode_anak, ...]} (Lv1 -> Lv2, Lv2 -> Lv3)."""
    peta = {}
    for m in semua_menu():
        if m["induk"]:
            peta.setdefault(m["induk"], []).append(m["kode"])
    return peta


def menu_sidebar():
    """Menu halaman (Lv2) yang punya alamat: halaman awal cadangan & kode halaman dari alamat."""
    return [m for m in semua_menu() if m["level"] == 2 and m["url"]]


def navbar(user, kode_aktif=None, alamat=None):
    """Flowchart navbar: Lv1 yang boleh dilihat -> Lv2 di dalamnya yang boleh dilihat -> Lv3 di dalamnya.
    [{kode, nama, ikon, buka, anak: [{kode, nama, url, ikon, aktif, anak: [...]}]}]. Url None = belum ada ('#')."""
    if not getattr(user, "is_authenticated", False) or getattr(user, "is_admin", False):
        return []
    menu = semua_menu()
    anak = {}
    for m in menu:
        anak.setdefault(m["induk"], []).append(m)

    def terlihat(m):
        return boleh_lihat(m["kode"], user)

    hasil = []
    for g in anak.get(None, []):
        if g["level"] != 1 or not terlihat(g):
            continue
        isi = []
        for m in anak.get(g["kode"], []):
            if not terlihat(m):
                continue
            sub = [{**c, "aktif": bool(alamat and c["url"] and c["url"] == alamat)}
                   for c in anak.get(m["kode"], []) if boleh(c["kode"], "lihat", user=user)]
            # Lv2 tanpa alamat sendiri (mis. Analytical Dashboard) membuka bagian Lv3 pertamanya
            url = m["url"] or next((c["url"] for c in sub if c["url"]), None)
            isi.append({**m, "url": url, "aktif": m["kode"] == kode_aktif, "anak": sub})
        if isi:
            hasil.append({**g, "anak": isi, "buka": any(m["aktif"] for m in isi)})
    return hasil


def remah_menu(kode_menu):
    """Nama menu dari Lv1 sampai menu ini, mis. ['Dashboard', 'Analytical Dashboard', 'PR & PO Outstanding']."""
    per_kode = {m["kode"]: m for m in semua_menu()}
    hasil, m = [], per_kode.get(kode_menu)
    while m:
        hasil.insert(0, m["nama"])
        m = per_kode.get(m["induk"])
    return hasil


def hapus_cache():
    peta_akses.hapus()
    hak_menu_user.hapus()
    widget_user.hapus()
    semua_menu.hapus()
    anak_menu.hapus()


def jabatan_dengan(kode_menu, aksi):
    """id jabatan (non-admin, aktif) yang punya aksi di menu itu, mis. jabatan_dengan('BLACKLIST', 'setujui')."""
    aktif = {lv["id_level"] for lv in daftar_level() if lv["is_active"] and not lv["is_admin"]}
    return sorted(i for i, hak in peta_akses().items() if i in aktif and hak.get(kode_menu, {}).get(aksi))


def pengguna_khusus_dengan(kode_menu, aksi):
    """id pengguna aktif yang punya aksi itu lewat aturan per User, padahal perannya tidak (di luar jabatannya)."""
    calon = _query("""SELECT DISTINCT u.UserID AS id_user, u.UserLevelID AS id_level FROM AccessMenu a
                      JOIN Menu m ON m.MenuID = a.MenuID JOIN Users u ON u.UserID = a.UserID
                      WHERE a.TargetType = 'USER' AND a.IsDeny = 0 AND a.Active = 1 AND u.Active = 1
                        AND m.MenuCode = ? AND a.ActionID = ?""", kode_menu, ID_AKSI[aksi])
    peran = peta_akses()
    return sorted(c["id_user"] for c in calon
                  if hak_menu_user(c["id_user"]).get(kode_menu, {}).get(aksi)
                  and not peran.get(c["id_level"], {}).get(kode_menu, {}).get(aksi))


def boleh(kode_menu, *aksi, user=None):
    """True bila level user boleh salah satu aksi di menu itu. Admin tidak punya aksi operasional."""
    user = user or current_user
    if not getattr(user, "is_authenticated", False) or getattr(user, "is_admin", False):
        return False
    hak = hak_user(user).get(kode_menu, {})
    return any(hak.get(a) for a in (aksi or AKSI))


def boleh_lihat(kode_menu, user=None):
    """Halaman / grup boleh dibuka. Menu induk terlihat bila dirinya atau salah satu turunannya (Lv2 / Lv3) boleh dilihat."""
    user = user or current_user
    if not getattr(user, "is_authenticated", False) or getattr(user, "is_admin", False):
        return False
    return bool(hak_user(user).get(kode_menu, {}).get("terlihat"))


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
    """Kode menu (Lv2) untuk sebuah alamat halaman, mis. '/weighbridge?view=form' -> FORM, '/weighbridge?tab=x' -> LIST."""
    path, _, query = (url or "").partition("?")
    if path == "/weighbridge":
        return "FORM" if "view=form" in query else "LIST"
    return next((m["kode"] for m in menu_sidebar() if (m["url"] or "").split("?")[0] == path), None)


def halaman_awal_user(user=None):
    """Halaman awal peran bila boleh dilihat, selain itu halaman pertama di navbar yang boleh dilihat."""
    user = user or current_user
    lv = get_level(user.id_level) if getattr(user, "id_level", None) else None
    awal = lv["halaman_awal"] if lv else None
    if awal and boleh_lihat(kode_halaman(awal), user):
        return awal
    return next((m["url"] for m in menu_sidebar() if boleh_lihat(m["kode"], user)), None)


def izin(kode_menu, *aksi):
    """Pengganti role_required: @izin('FORM_SECURITY', 'tambah'). kode_menu boleh tuple (salah satu cukup)
    atau fungsi tanpa argumen yang mengembalikan daftar kode (dihitung tiap request, mis. menu dashboard ber-widget harga)."""
    def dekorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Belum login"}), 401
            kode = kode_menu() if callable(kode_menu) else kode_menu
            daftar_kode = kode if isinstance(kode, (tuple, list)) else (kode,)
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
_SELECT_PERAN = """SELECT ld.LevelDetID AS id_level, ld.LevelDetCode AS kode, ld.LevelDetName AS nama, lv.IsAdmin AS is_admin,
                          ld.HomeUrl AS halaman_awal, ld.Description AS keterangan, ld.Active AS is_active,
                          ld.DeptID AS id_department, d.DeptName AS department, ld.LevelID AS id_jabatan, lv.LevelName AS jabatan,
                          ld.CompAreaID AS id_comp_area,
                          (SELECT COUNT(*) FROM Users u WHERE u.UserLevelID = ld.LevelDetID AND u.Active = 1) AS jumlah_user
                   FROM LevelDetails ld JOIN Level lv ON lv.LevelID = ld.LevelID
                   LEFT JOIN Department d ON d.DeptID = ld.DeptID"""


def daftar_level():
    """Peran (departemen + jabatan) beserta jumlah pengguna aktifnya."""
    return _query(_SELECT_PERAN + " ORDER BY lv.IsAdmin DESC, d.DeptName, lv.SortOrder, lv.LevelName")


# ===== Jabatan umum (tabel Level) =====
def daftar_jabatan():
    return _query("""SELECT lv.LevelID AS id_jabatan, lv.LevelName AS nama, lv.Description AS keterangan, lv.IsAdmin AS is_admin,
                            lv.SortOrder AS urutan, lv.Active AS is_active,
                            (SELECT COUNT(*) FROM LevelDetails ld WHERE ld.LevelID = lv.LevelID) AS jumlah_peran,
                            (SELECT COUNT(*) FROM Users u JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID
                             WHERE ld.LevelID = lv.LevelID AND u.Active = 1) AS jumlah_user
                     FROM Level lv ORDER BY lv.Active DESC, lv.SortOrder, lv.LevelName""")


def nama_jabatan_dipakai(nama, kecuali=None):
    return any(r["id"] != kecuali for r in _query("SELECT LevelID AS id FROM Level WHERE LevelName = ?", nama))


def simpan_jabatan(id_jabatan, nama, keterangan, urutan):
    """Ganti nama jabatan -> nama peran yang memakainya ikut berubah ("Departemen · Jabatan")."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_jabatan is None:
            cursor.execute("INSERT INTO Level (LevelName, Description, SortOrder) VALUES (?, ?, ?)", nama, keterangan, urutan)
        else:
            cursor.execute("UPDATE Level SET LevelName = ?, Description = ?, SortOrder = ? WHERE LevelID = ?",
                           nama, keterangan, urutan, id_jabatan)
            if cursor.rowcount == 0:
                raise ValueError("Jabatan tidak ditemukan")
            cursor.execute("""UPDATE ld SET LevelDetName = LEFT(d.DeptName + N' · ' + ?, 120) FROM LevelDetails ld
                              JOIN Department d ON d.DeptID = ld.DeptID WHERE ld.LevelID = ?""", nama, id_jabatan)
        conn.commit()
    finally:
        conn.close()
    hapus_cache()


def set_aktif_jabatan(id_jabatan, aktif):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Level SET Active = ? WHERE LevelID = ? AND IsAdmin = 0", 1 if aktif else 0, id_jabatan)
        if cursor.rowcount == 0:
            raise ValueError("Jabatan admin tidak bisa dinonaktifkan")
        conn.commit()
    finally:
        conn.close()


def cari_peran(id_department, id_jabatan):
    rows = _query("""SELECT LevelDetID FROM LevelDetails WHERE LevelID = ? AND CompAreaID IS NULL
                     AND (DeptID = ? OR (DeptID IS NULL AND ? IS NULL))""", id_jabatan, id_department, id_department)
    return rows[0]["LevelDetID"] if rows else None


def peran_untuk(id_department, id_jabatan, halaman_awal="/weighbridge?view=list"):
    """id peran (LevelDetID) untuk departemen + jabatan ini; dibuat bila belum ada (kode & nama otomatis, tanpa hak menu)."""
    ada = cari_peran(id_department, id_jabatan)
    if ada:
        return ada
    info = _query("""SELECT lv.LevelName AS jabatan, lv.IsAdmin AS is_admin, d.DeptName AS department FROM Level lv
                     LEFT JOIN Department d ON d.DeptID = ? WHERE lv.LevelID = ?""", id_department, id_jabatan)[0]
    nama = f"{info['department']} · {info['jabatan']}" if info["department"] else info["jabatan"]
    dasar = re.sub(r"[^A-Z0-9]+", "_", f"{info['department'] or ''}_{info['jabatan']}".upper()).strip("_")[:26] or "PERAN"
    kode, n = dasar, 2
    while kode_level_dipakai(kode):
        kode, n = f"{dasar}_{n}", n + 1
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SET NOCOUNT ON; INSERT INTO LevelDetails (LevelDetCode, LevelDetName, HomeUrl, DeptID, LevelID)
                          VALUES (?, ?, ?, ?, ?); SELECT CAST(SCOPE_IDENTITY() AS INT)""",
                       kode, nama[:120], "/admin" if info["is_admin"] else halaman_awal, id_department, id_jabatan)
        id_level = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    hapus_cache()
    return id_level


def simpan_halaman_awal(id_level, halaman_awal):
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE LevelDetails SET HomeUrl = ? WHERE LevelDetID = ?", halaman_awal, id_level)
        conn.commit()
    finally:
        conn.close()


# ===== Admin › Hak Akses: aturan per menu =====
JENIS_TARGET = ("ALL", "ROLE", "LEVEL", "DEPT", "USER")
KOLOM_TARGET = {"ROLE": "LevelDetID", "LEVEL": "LevelID", "DEPT": "DeptID", "USER": "UserID"}


def pohon_menu():
    """Semua menu aktif urut navbar + aksi yang berlaku + jumlah aturan: [{id_menu, kode, nama, level, induk, url, aksi,
    jumlah_aturan}] (induk = kode menu induk)."""
    jumlah = {r["MenuID"]: r["n"] for r in _query("""SELECT MenuID, COUNT(*) AS n FROM (
                  SELECT DISTINCT MenuID, TargetType, LevelDetID, LevelID, DeptID, UserID, IsDeny FROM AccessMenu) x
              GROUP BY MenuID""")}
    menu = semua_menu()
    anak = {}
    for m in menu:
        anak.setdefault(m["induk"], []).append(m)
    hasil = []

    def tambah(kode_induk):
        for m in anak.get(kode_induk, []):
            hasil.append({**{k: m[k] for k in ("id_menu", "kode", "nama", "level", "induk", "url", "aplikasi")},
                          "aksi": aksi_menu(m), "jumlah_aturan": jumlah.get(m["id_menu"], 0)})
            tambah(m["kode"])
    tambah(None)
    return hasil


def aturan_menu(id_menu):
    """Aturan satu menu, satu baris per sasaran + Izinkan / Larang:
    [{jenis, id_target, nama_target, tolak, aksi: {lihat, tambah, ...}, widget: [kode, ...]}]"""
    rows = _query("""SELECT a.AccessMenuID, a.ActionID, a.TargetType AS jenis, a.IsDeny AS tolak,
                            CASE a.TargetType WHEN 'ROLE' THEN ld.DeptID + '|' + CAST(ld.LevelID AS VARCHAR(10))
                                 WHEN 'LEVEL' THEN CAST(a.LevelID AS VARCHAR(20)) WHEN 'DEPT' THEN a.DeptID
                                 WHEN 'USER' THEN CAST(a.UserID AS VARCHAR(20)) END AS id_target,
                            CASE a.TargetType WHEN 'ALL' THEN N'Semua user' WHEN 'ROLE' THEN ld.LevelDetName
                                 WHEN 'LEVEL' THEN lv.LevelName WHEN 'DEPT' THEN d.DeptName
                                 ELSE u.Nama + ISNULL(N' · ' + u.UserName, N'') END AS nama_target,
                            (SELECT STRING_AGG(w.WidgetCode, ',') WITHIN GROUP (ORDER BY w.SortOrder)
                             FROM AccessMenuWidget w WHERE w.AccessMenuID = a.AccessMenuID) AS widget
                     FROM AccessMenu a
                     LEFT JOIN LevelDetails ld ON ld.LevelDetID = a.LevelDetID LEFT JOIN Level lv ON lv.LevelID = a.LevelID
                     LEFT JOIN Department d ON d.DeptID = a.DeptID LEFT JOIN Users u ON u.UserID = a.UserID
                     WHERE a.MenuID = ? AND a.Active = 1""", id_menu)
    urut = {j: i for i, j in enumerate(JENIS_TARGET)}
    per = {}
    for r in rows:
        kunci = (r["jenis"], r["id_target"], bool(r["tolak"]))
        baris = per.setdefault(kunci, {"jenis": r["jenis"], "id_target": r["id_target"], "nama_target": r["nama_target"],
                                       "tolak": bool(r["tolak"]), "aksi": _kosong(), "widget": []})
        if r["ActionID"] in NAMA_AKSI:
            baris["aksi"][NAMA_AKSI[r["ActionID"]]] = True
        if r["widget"]:
            baris["widget"] = r["widget"].split(",")
    return sorted(per.values(), key=lambda b: (b["tolak"], urut[b["jenis"]], b["nama_target"] or ""))


def simpan_aturan_menu(id_menu, aturan):
    """Ganti semua aturan menu ini. aturan = [{jenis, id_target, tolak, aksi: [nama aksi], widget: [kode]}];
    aksi di luar MenuAction diabaikan, widget hanya untuk baris Izinkan + Lihat."""
    m = next((x for x in semua_menu() if x["id_menu"] == id_menu), None)
    if m is None:
        raise ValueError("Menu tidak ditemukan")
    boleh_aksi = {"lihat", *aksi_menu(m)}
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM AccessMenu WHERE MenuID = ?", id_menu)
        for a in aturan:
            kolom = KOLOM_TARGET.get(a["jenis"])
            for nama in [x for x in AKSI_SEMUA if x in a["aksi"] and x in boleh_aksi]:
                cursor.execute(f"""SET NOCOUNT ON; INSERT INTO AccessMenu (MenuID, ActionID, TargetType, IsDeny{', ' + kolom if kolom else ''})
                                   VALUES (?, ?, ?, ?{', ?' if kolom else ''}); SELECT CAST(SCOPE_IDENTITY() AS INT)""",
                               id_menu, ID_AKSI[nama], a["jenis"], 1 if a["tolak"] else 0, *([a["id_target"]] if kolom else []))
                id_baris = cursor.fetchone()[0]
                if nama == "lihat" and not a["tolak"]:
                    for urut, w in enumerate(a.get("widget") or [], 1):
                        cursor.execute("INSERT INTO AccessMenuWidget (AccessMenuID, WidgetCode, SortOrder) VALUES (?, ?, ?)",
                                       id_baris, w, urut)
        conn.commit()
    finally:
        conn.close()
    hapus_cache()


def sumber_akses(id_user):
    """Aturan yang cocok dengan user (Cek Akses): [{MenuCode, MenuName, ActionID, IsDeny, TargetType, TargetName, ...}]"""
    return _query("EXEC dbo.sp_UserAccessSource @UserID = ?", id_user)


def daftar_widget():
    return _query("""SELECT WidgetCode AS kode, WidgetName AS nama, Description AS keterangan FROM Widget
                     WHERE Active = 1 ORDER BY SortOrder, WidgetCode""")


@cache_ttl(30)
def widget_user(id_user, kode_menu="DASHBOARD"):
    """Widget dashboard user, urut tampil (dbo.sp_UserDashboard): ['harga', 'arus']."""
    return [r["WidgetCode"] for r in _query("EXEC dbo.sp_UserDashboard @UserID = ?, @MenuCode = ?", id_user, kode_menu)]


def get_level(id_level):
    rows = _query(_SELECT_PERAN + " WHERE ld.LevelDetID = ?", id_level)
    return rows[0] if rows else None


def kode_level_dipakai(kode, kecuali=None):
    return any(r["id"] != kecuali for r in _query("SELECT LevelDetID AS id FROM LevelDetails WHERE LevelDetCode = ?", kode))


def set_aktif_level(id_level, aktif):
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE LevelDetails SET Active = ? WHERE LevelDetID = ?", 1 if aktif else 0, id_level)
        conn.commit()
    finally:
        conn.close()
