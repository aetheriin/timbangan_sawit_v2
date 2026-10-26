"""Menu Admin (super admin): hanya role ADMIN (dijaga juga oleh utils.keamanan.pasang_batas_admin).

Halaman  : /admin/<halaman>      (satu menu sidebar = satu halaman, tanpa tab)
API      : /api/admin/...        (JSON, semua aksi tercatat di admin_audit_logs)"""
import json
import os
import platform
import re
import shutil
import time
from datetime import date, datetime

from flask import Blueprint, render_template, request, jsonify, redirect, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import BASE_DIR, UPLOAD_FOLDER
from utils.versi import versi_aplikasi
from utils.hak_akses import admin_required
from utils.dokumen import simpan_file, hapus_file_info
from utils import db_admin as db, db_organisasi as org, hak_akses, pengaturan, login_guard, sesi_aktif, kiosk
from utils.db_utils import cek_koneksi_db, get_password_hash, get_user_by_id, cek_nik_ada, password_pernah_dipakai, pesan_riwayat_password
from utils.personel_utils import nik_valid
from utils.db_absensi import get_jadwal_kerja
from utils.keamanan import log_keamanan, baca_log_keamanan
from utils.serial_reader import semua_status, atur as atur_pembaca, data_mentah, FORMAT as FORMAT_TIMBANGAN
from utils import db_jembatan as jembatan_db
from utils import alur, log_aktivitas, kolom_wajib, alur_persetujuan

admin_bp = Blueprint("admin", __name__)
WAKTU_MULAI = time.time()

# key -> (judul, ikon Font Awesome, keterangan). Urutan = urutan menu sidebar.
HALAMAN = {
    "users": ("Kelola Pengguna", "fa-users", "Tambah akun, ubah level / departemen / area, atur ulang password, aktif / nonaktif"),
    "hak_akses": ("Hak Akses", "fa-user-shield", "Siapa mendapat menu apa: aturan per menu untuk semua user, peran, jabatan, departemen, atau user tertentu"),
    "persetujuan": ("Alur Persetujuan", "fa-route", "Tahap persetujuan berjenjang per jenis pengajuan & kategori (mis. blacklist Driver)"),
    "organisasi": ("Organisasi", "fa-sitemap", "Perusahaan, area perusahaan, Mill (tipe area), departemen, jabatan, dan status tiket"),
    "sesi": ("Sesi Aktif", "fa-user-clock", "Pengguna yang sedang login, paksa keluar, buka kunci login"),
    "void": ("Pembatalan Tiket", "fa-ban", "Batalkan tiket yang salah input; tiket tidak dihapus, tercatat alasannya"),
    "jadwal": ("Jadwal Kerja", "fa-calendar-days", "Jam masuk, jam pulang, dan toleransi absensi per hari"),
    "pengaturan": ("Pengaturan Site", "fa-sliders", "Scan wajah, sesi login, kunci login, dan kolom wajib"),
    "perangkat": ("Perangkat", "fa-plug", "Pos (token PC agen timbangan) dan jembatan timbang"),
    "log": ("Log Keamanan", "fa-shield-halved", "Login, login gagal, akses ditolak, kios ditolak"),
    "audit": ("Audit Admin", "fa-clipboard-list", "Jejak semua perubahan yang dilakukan admin"),
    "kesehatan": ("Kesehatan Sistem", "fa-heart-pulse", "Database, cadangan data (backup), disk, versi aplikasi"),
}

POLA_USERNAME = re.compile(r"^[a-z0-9._]{3,50}$")
# Pilihan "Halaman awal setelah login" (admin memilih nama menu, bukan mengetik alamat)
# /weighbridge?tab=... (tanpa view=form) = Daftar Tiket dengan tahap terpilih; view=form&tab=... = tab Stasiun Timbang
HALAMAN_AWAL = [("/dashboard", "Dashboard"), ("/pos-security", "Pos Security"), ("/logbook", "Logbook Kendaraan"),
                ("/weighbridge?view=list", "Daftar Tiket › Semua tahap"),
                ("/weighbridge?tab=security", "Daftar Tiket › Security"), ("/weighbridge?tab=timbangan", "Daftar Tiket › Timbangan"),
                ("/weighbridge?tab=sortasi", "Daftar Tiket › Sortasi"), ("/weighbridge?tab=lab", "Daftar Tiket › Laboratorium"),
                ("/weighbridge?view=form&tab=security", "Stasiun Timbang › Security"),
                ("/weighbridge?view=form&tab=timbangan", "Stasiun Timbang › Timbangan"),
                ("/weighbridge?view=form&tab=sortasi", "Stasiun Timbang › Sortasi"),
                ("/weighbridge?view=form&tab=lab", "Stasiun Timbang › Laboratorium"),
                ("/face-recognition", "Pengenalan Wajah"), ("/blacklist", "Blacklist"), ("/tamu", "Tamu"),
                ("/kontrak", "Kontrak & DO"), ("/master", "Data Master"), ("/kelebihan-do", "Kelebihan DO"),
                ("/admin", "Admin (khusus level admin)")]
POLA_JAM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
PASSWORD_MIN = 8


def _admin(f):
    return login_required(admin_required(f))


def _audit(aksi, target=None, detail=None):
    db.catat_audit_admin(current_user.id, aksi, target, detail, request.remote_addr)


def _teks(nama, wajib=True, maks=100):
    nilai = (request.form.get(nama) or "").strip()
    if wajib and not nilai:
        raise ValueError(f"{nama.replace('_', ' ').capitalize()} wajib diisi")
    if len(nilai) > maks:
        raise ValueError(f"{nama.replace('_', ' ').capitalize()} maksimal {maks} karakter")
    return nilai


def _aktif_dari_form():
    return request.form.get("aktif") in ("1", "true")


def _jalankan(fn):
    """Aksi admin: ValueError -> 400 dengan pesannya, selain itu ditangani error handler umum (500)."""
    try:
        return fn()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ===== HALAMAN =====
@admin_bp.route("/admin")
@_admin
def admin_index():
    return redirect("/admin/users")


@admin_bp.route("/admin/<halaman>")
@_admin
def admin_halaman(halaman):
    if halaman not in HALAMAN:
        abort(404)
    judul, ikon, keterangan = HALAMAN[halaman]
    return render_template("admin/admin.html", halaman=f"admin:{halaman}", menu_admin=HALAMAN,
                           admin_aktif=halaman, judul=judul, ikon=ikon, keterangan=keterangan,
                           jabatan_list=[j for j in hak_akses.daftar_jabatan() if j["is_active"]],
                           department_list=[d for d in org.daftar_department() if d["is_active"]],
                           area_list=[a for a in org.daftar_area() if a["is_active"]],
                           format_timbangan=FORMAT_TIMBANGAN,
                           company_list=[c for c in org.daftar_company() if c["is_active"]],
                           lokasi_list=[l for l in org.daftar_lokasi() if l["is_active"]] if halaman == "organisasi" else [],
                           alur_list=alur.daftar_alur(),
                           kategori_alur=alur_persetujuan.daftar_kategori() if halaman == "persetujuan" else [],
                           jenis_pengajuan=alur_persetujuan.JENIS,
                           password_expired=pengaturan.nilai("PASSWORD_EXPIRED_HARI"),
                           password_min=PASSWORD_MIN, halaman_awal_list=HALAMAN_AWAL)


# ===== KELOLA USER =====
@admin_bp.route("/api/admin/users")
@_admin
def users_daftar():
    pt, pusat = org.pt_kelola_semua(), org.area_pusat()
    return jsonify([{**u, "last_login": u["last_login"].strftime("%Y-%m-%d %H:%M") if u["last_login"] else None,
                     "created_at": u["created_at"].strftime("%Y-%m-%d") if u["created_at"] else None,
                     "is_saya": u["id_user"] == current_user.id, "pt_kelola": pt.get(u["id_user"], []),
                     "di_pusat": u["id_comp_area"] in pusat}
                    for u in db.daftar_user()])


def _id_form(nama, pilihan, label):
    teks = (request.form.get(nama) or "").strip()
    if not teks.isdigit() or int(teks) not in pilihan:
        raise ValueError(f"Pilih {label} dari daftar")
    return int(teks)


def _akun_form():
    """(peran, id_department, id_comp_area) dari form. Peran = departemen + jabatan (dibuat bila belum ada);
    jabatan admin sistem tanpa departemen."""
    jabatan = {j["id_jabatan"]: j for j in hak_akses.daftar_jabatan() if j["is_active"]}
    id_jabatan = _id_form("id_jabatan", jabatan, "jabatan")
    id_area = _id_form("id_comp_area", {a["id_comp_area"] for a in org.daftar_area() if a["is_active"]}, "area")
    if jabatan[id_jabatan]["is_admin"]:
        id_department = None
    else:
        id_department = (request.form.get("id_department") or "").strip().upper()
        if id_department not in {d["id_department"] for d in org.daftar_department() if d["is_active"]}:
            raise ValueError("Pilih departemen dari daftar")
        if not org.department_di_area(id_department, id_area):
            raise ValueError("Departemen ini tidak ada di area yang dipilih. Atur di Admin › Organisasi › Departemen")
    id_level = hak_akses.peran_untuk(id_department, id_jabatan)
    peran = hak_akses.get_level(id_level)
    if not peran["is_active"]:
        raise ValueError(f"Peran {peran['nama']} dinonaktifkan")
    return peran, id_department, id_area


def _simpan_pt_kelola(id_user, id_area):
    """PT yang dikelola hanya berlaku untuk user di site kantor pusat; selain itu dikosongkan."""
    pilihan = {v.strip() for v in request.form.getlist("pt_kelola") if v.strip()}
    semua = {c["id_company"] for c in org.daftar_company()}
    org.simpan_pt_kelola(id_user, pilihan & semua if id_area in org.area_pusat() else set())


def _password_form(nama="password"):
    pw = request.form.get(nama) or ""
    if len(pw) < PASSWORD_MIN:
        raise ValueError(f"Password minimal {PASSWORD_MIN} karakter")
    if pw != (request.form.get("password_ulang") or ""):
        raise ValueError("Ulangi password tidak sama")
    return pw


def _personel_form(user_lama=None):
    """Data orang di akun: hanya nama & NIK 16 digit (kategori, email, SIM, wajah diatur di menu Personel).
    Akun baru: NIK wajib; bila NIK sudah terdaftar sebagai personel tanpa akun, personel itu yang dihubungkan
    (kategorinya harus boleh punya akun). Personel baru otomatis berkategori Karyawan.
    Akun lama yang belum punya NIK boleh disimpan tanpa NIK."""
    nama, nik = _teks("nama"), (request.form.get("nik") or "").strip()
    if nik and not nik_valid(nik):
        raise ValueError("NIK harus 16 digit angka.")
    if not nik and (user_lama is None or user_lama["nik"]):
        raise ValueError("NIK wajib diisi.")
    id_personel = user_lama["id_personel"] if user_lama else None
    if nik and user_lama is None:
        ada = db.personel_untuk_nik(nik)
        if ada:
            if ada["akun"]:
                raise ValueError(f"NIK ini sudah dipakai akun {ada['akun']}.")
            if not ada["boleh_akun"]:
                raise ValueError(f"NIK ini terdaftar sebagai {ada['nama_kategori'] or ada['kategori']} dan tidak bisa dibuatkan akun.")
            id_personel = ada["id_personel"]
    elif nik and cek_nik_ada(nik, exclude_id=id_personel):
        raise ValueError("NIK sudah terdaftar pada personel lain.")
    return {"id_personel": id_personel, "nama": nama, "nik": nik or None}


@admin_bp.route("/api/admin/users/nik/<nik>")
@_admin
def users_cek_nik(nik):
    """Untuk form Tambah Pengguna: NIK yang sudah terdaftar sebagai personel langsung mengisi nama & kategorinya."""
    ada = db.personel_untuk_nik(nik) if nik_valid(nik) else None
    return jsonify(ada or {})


@admin_bp.route("/api/admin/users/tambah", methods=["POST"])
@_admin
def users_tambah():
    def aksi():
        username = _teks("username", maks=50).lower()
        if not POLA_USERNAME.match(username):
            raise ValueError("Username 3-50 karakter: huruf kecil, angka, titik, garis bawah")
        if db.username_dipakai(username):
            raise ValueError(f"Username {username} sudah dipakai")
        personel, (level, id_department, id_area), pw = _personel_form(), _akun_form(), _password_form()
        id_user = db.tambah_user(username, level["id_level"], id_department, id_area, generate_password_hash(pw), personel)
        _simpan_pt_kelola(id_user, id_area)
        _audit("USER_TAMBAH", username, f"jabatan {level['kode']}")
        return jsonify({"message": f"Pengguna {username} berhasil ditambahkan"})
    return _jalankan(aksi)


def _user_atau_404(id_user):
    u = db.get_user(id_user)
    if not u:
        raise ValueError("Pengguna tidak ditemukan")
    return u


@admin_bp.route("/api/admin/users/<int:id_user>/ubah", methods=["POST"])
@_admin
def users_ubah(id_user):
    def aksi():
        u = _user_atau_404(id_user)
        personel, (level, id_department, id_area) = _personel_form(u), _akun_form()
        ganti_level = u["id_level"] != level["id_level"]
        if u["is_admin"] and not level["is_admin"]:
            if id_user == current_user.id:
                raise ValueError("Tidak bisa menurunkan level akun sendiri")
            if db.jumlah_admin_aktif(kecuali=id_user) == 0:
                raise ValueError("Minimal harus ada 1 admin aktif")
        db.ubah_user(id_user, level["id_level"], id_department, id_area, personel)
        _simpan_pt_kelola(id_user, id_area)
        _audit("USER_UBAH", u["username"], f"level {u['role']} -> {level['kode']}" if ganti_level else "data diubah")
        if ganti_level:
            sesi_aktif.hapus_user(id_user, "ROLE_DIUBAH")
        return jsonify({"message": f"Pengguna {u['username']} berhasil diperbarui" +
                        (" (sesi lamanya diakhiri, login ulang dengan level baru)" if ganti_level else "")})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/users/<int:id_user>/reset-password", methods=["POST"])
@_admin
def users_reset_password(id_user):
    def aksi():
        u = _user_atau_404(id_user)
        baru = _password_form()
        lama = get_password_hash(id_user)
        if (lama and check_password_hash(lama, baru)) or password_pernah_dipakai(id_user, baru):
            raise ValueError(pesan_riwayat_password())
        db.reset_password(id_user, generate_password_hash(baru))
        sesi_aktif.hapus_user(id_user, "RESET_PASSWORD")
        _audit("USER_RESET_PASSWORD", u["username"])
        log_keamanan("RESET_PASSWORD", f"username={u['username']}")
        return jsonify({"message": f"Password pengguna {u['username']} berhasil diatur ulang. Pengguna wajib membuat password baru saat login berikutnya."})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/users/<int:id_user>/aktif", methods=["POST"])
@_admin
def users_aktif(id_user):
    def aksi():
        u, aktif = _user_atau_404(id_user), _aktif_dari_form()
        if not aktif:
            if id_user == current_user.id:
                raise ValueError("Tidak bisa menonaktifkan akun sendiri")
            if u["is_admin"] and db.jumlah_admin_aktif(kecuali=id_user) == 0:
                raise ValueError("Minimal harus ada 1 admin aktif")
        db.set_aktif_user(id_user, aktif)
        sesi_aktif.hapus_user(id_user, "NONAKTIF")
        _audit("USER_AKTIF" if aktif else "USER_NONAKTIF", u["username"])
        return jsonify({"message": f"Pengguna {u['username']} berhasil {'diaktifkan' if aktif else 'dinonaktifkan'}"})
    return _jalankan(aksi)


# ===== LEVEL & HAK AKSES =====
POLA_KODE = re.compile(r"^[A-Z0-9_]{2,30}$")


@admin_bp.route("/api/admin/level")
@_admin
def level_daftar():
    return jsonify(hak_akses.daftar_level())


def _level_atau_404(id_level):
    lv = hak_akses.get_level(id_level)
    if not lv:
        raise ValueError("Jabatan tidak ditemukan")
    return lv


@admin_bp.route("/api/admin/level/<int:id_level>/aktif", methods=["POST"])
@_admin
def level_aktif(id_level):
    def aksi():
        lv, aktif = _level_atau_404(id_level), _aktif_dari_form()
        if not aktif and lv["is_admin"]:
            raise ValueError("Level admin tidak bisa dinonaktifkan")
        hak_akses.set_aktif_level(id_level, aktif)
        get_user_by_id.hapus()          # user level nonaktif langsung tidak bisa memakai sesinya
        _audit("LEVEL_AKTIF" if aktif else "LEVEL_NONAKTIF", lv["kode"])
        return jsonify({"message": f"Level {lv['kode']} berhasil {'diaktifkan' if aktif else 'dinonaktifkan'}"})
    return _jalankan(aksi)


# ===== HAK AKSES: aturan per menu =====
@admin_bp.route("/api/admin/akses")
@_admin
def akses_awal():
    """Pohon menu + pilihan sasaran (peran = departemen + jabatan, jabatan, departemen) + widget dashboard."""
    return jsonify({"menu": hak_akses.pohon_menu(), "widget": hak_akses.daftar_widget(),
                    "jabatan": [{"id": j["id_jabatan"], "nama": j["nama"]} for j in hak_akses.daftar_jabatan()
                                if j["is_active"] and not j["is_admin"]],
                    "departemen": [{"id": d["id_department"], "nama": d["nama"]} for d in org.daftar_department() if d["is_active"]],
                    "peran": [{"id": lv["id_level"], "nama": lv["nama"], "halaman_awal": lv["halaman_awal"],
                               "jumlah_user": lv["jumlah_user"], "is_active": lv["is_active"]}
                              for lv in hak_akses.daftar_level() if not lv["is_admin"]],
                    "halaman_awal": [{"url": u, "nama": n} for u, n in HALAMAN_AWAL if u != "/admin"]})


@admin_bp.route("/api/admin/akses/menu/<int:id_menu>")
@_admin
def akses_menu(id_menu):
    return jsonify(hak_akses.aturan_menu(id_menu))


def _aturan_dari_json(m, data):
    """Validasi aturan dari layar; peran (departemen + jabatan) dibuat otomatis bila belum ada."""
    jabatan = {j["id_jabatan"] for j in hak_akses.daftar_jabatan() if not j["is_admin"]}
    departemen = {d["id_department"] for d in org.daftar_department()}
    widget_ada = {w["kode"] for w in hak_akses.daftar_widget()}
    hasil, kunci = [], set()
    for a in data if isinstance(data, list) else []:
        jenis, target = str(a.get("jenis") or ""), str(a.get("id_target") or "").strip()
        if jenis not in hak_akses.JENIS_TARGET:
            raise ValueError("Jenis sasaran tidak dikenal")
        if jenis == "ROLE":
            dept, _, jab = target.partition("|")
            if dept not in departemen or not jab.isdigit() or int(jab) not in jabatan:
                raise ValueError("Pilih departemen dan jabatan untuk aturan Peran")
            target = hak_akses.peran_untuk(dept, int(jab))
        elif jenis == "LEVEL":
            if not target.isdigit() or int(target) not in jabatan:
                raise ValueError("Pilih jabatan untuk aturan Jabatan")
            target = int(target)
        elif jenis == "DEPT":
            if target not in departemen:
                raise ValueError("Pilih departemen untuk aturan Departemen")
        elif jenis == "USER":
            u = db.get_user(int(target)) if target.isdigit() else None
            if not u or u["is_admin"] or not u["username"]:
                raise ValueError("Pilih user untuk aturan User")
            target = int(target)
        else:
            target = None
        tolak = bool(a.get("tolak"))
        if (jenis, target, tolak) in kunci:
            raise ValueError("Ada aturan ganda untuk sasaran yang sama. Gabungkan jadi satu baris")
        kunci.add((jenis, target, tolak))
        aksi = [x for x in (a.get("aksi") or []) if x in hak_akses.AKSI_SEMUA]
        if not aksi:
            continue
        widget = [w for w in dict.fromkeys(a.get("widget") or []) if w in widget_ada] if m["kode"] == "DASHBOARD" else []
        hasil.append({"jenis": jenis, "id_target": target, "tolak": tolak, "aksi": aksi, "widget": widget})
    return hasil


@admin_bp.route("/api/admin/akses/menu/<int:id_menu>", methods=["POST"])
@_admin
def akses_menu_simpan(id_menu):
    def aksi():
        m = next((x for x in hak_akses.pohon_menu() if x["id_menu"] == id_menu), None)
        if m is None:
            raise ValueError("Menu tidak ditemukan")
        try:
            data = json.loads(request.form.get("aturan") or "[]")
        except ValueError:
            raise ValueError("Data aturan tidak valid") from None
        aturan = _aturan_dari_json(m, data)
        hak_akses.simpan_aturan_menu(id_menu, aturan)
        get_user_by_id.hapus()
        _audit("HAK_AKSES_UBAH", m["kode"], f"{m['nama']} · {len(aturan)} aturan")
        return jsonify({"message": f"Hak akses {m['nama']} berhasil disimpan dan berlaku di semua PC dalam ±30 detik"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/akses/user")
@_admin
def akses_cari_user():
    """Cari user ber-akun (bukan admin) lewat NIK / nama / username, untuk aturan User & Cek Akses."""
    q = (request.args.get("q") or "").strip().lower()
    hasil = [{"id_user": u["id_user"], "nama": u["nama"], "username": u["username"], "nik": u.get("nik"),
              "peran": u.get("nama_level")}
             for u in db.daftar_user() if not u["is_admin"] and u["is_active"]
             and (not q or q in " ".join(str(u.get(k) or "") for k in ("nama", "username", "nik")).lower())]
    return jsonify(hasil[:20])


@admin_bp.route("/api/admin/akses/cek/<int:id_user>")
@_admin
def akses_cek(id_user):
    """Cek Akses: menu yang terlihat user, aksinya, sumber aturannya, dan isi dashboard-nya."""
    def aksi():
        u = _user_atau_404(id_user)
        hak = hak_akses.hak_menu_user(id_user)
        sumber = {}
        for r in hak_akses.sumber_akses(id_user):
            sumber.setdefault(r["MenuCode"], []).append({
                "aksi": hak_akses.NAMA_AKSI.get(r["ActionID"]), "tolak": bool(r["IsDeny"]),
                "jenis": r["TargetType"], "nama": r["TargetName"]})
        menu = [{**m, "hak": hak.get(m["kode"]), "sumber": sumber.get(m["kode"], [])} for m in hak_akses.pohon_menu()]
        return jsonify({"user": {k: u.get(k) for k in ("id_user", "username", "nama", "nama_level", "is_admin")},
                        "menu": menu, "widget": hak_akses.widget_user(id_user)})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/level/<int:id_level>/halaman-awal", methods=["POST"])
@_admin
def level_halaman_awal(id_level):
    def aksi():
        lv = _level_atau_404(id_level)
        halaman_awal = _teks("halaman_awal", maks=100)
        if halaman_awal not in dict(HALAMAN_AWAL) and halaman_awal != lv["halaman_awal"]:
            raise ValueError("Pilih halaman awal dari daftar")
        hak_akses.simpan_halaman_awal(id_level, halaman_awal)
        get_user_by_id.hapus()
        _audit("HALAMAN_AWAL_UBAH", lv["kode"], halaman_awal)
        return jsonify({"message": f"Halaman awal {lv['nama']} disimpan"})
    return _jalankan(aksi)


# ===== ORGANISASI =====
POLA_KODE_ORG = re.compile(r"^[A-Z0-9_-]{2,10}$")


POLA_KODE_PENDEK = re.compile(r"^[A-Z0-9_-]{2,5}$")


def _kode_org(tabel, kolom_id, id_baris, kolom_kode=None, maks=10):
    kode = _teks("kode", maks=maks).upper()
    if not (POLA_KODE_PENDEK if maks == 5 else POLA_KODE_ORG).match(kode):
        raise ValueError(f"Kode 2-{maks} karakter: huruf besar, angka, - atau _")
    if org.kode_dipakai(tabel, kolom_id, kolom_kode or kolom_id, kode, kecuali=id_baris):
        raise ValueError(f"Kode {kode} sudah dipakai")
    return kode


def _id_opsional(nama):
    teks = (request.form.get(nama) or "").strip()
    return int(teks) if teks.isdigit() else None


@admin_bp.route("/api/admin/organisasi")
@_admin
def organisasi_daftar():
    return jsonify({"company": org.daftar_company(), "lokasi": org.daftar_lokasi(), "area": org.daftar_area(),
                    "department": org.daftar_department(), "jabatan": hak_akses.daftar_jabatan(),
                    "status": alur.daftar_status()})


@admin_bp.route("/api/admin/organisasi/company/simpan", methods=["POST"])
@_admin
def company_simpan():
    def aksi():
        id_c = (request.form.get("id_company") or "").strip().upper() or None
        kode, nama = _kode_org("Company", "CompID", id_c, maks=5), _teks("nama")
        kolom_wajib.cek("PERUSAHAAN", request.form)
        org.simpan_company(id_c, kode, nama, _teks("alamat", wajib=False, maks=255) or None)
        _audit("COMPANY_SIMPAN", kode, nama)
        return jsonify({"message": f"Perusahaan {nama} berhasil disimpan."})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/area/simpan", methods=["POST"])
@_admin
def area_simpan():
    """Area Perusahaan (CompanyArea): perusahaan + Mill (tipe) + nama sendiri, mis. YBS · REFINERY."""
    def aksi():
        id_a = _id_opsional("id_comp_area")
        lama = next((a for a in org.daftar_area() if a["id_comp_area"] == id_a), None) if id_a else None
        id_c = (request.form.get("id_company") or "").strip().upper()
        if id_c not in {c["id_company"] for c in org.daftar_company()
                        if c["is_active"] or (lama and c["id_company"] == lama["id_company"])}:
            raise ValueError("Pilih perusahaan dari daftar")
        id_l = _id_form("id_lokasi", {l["id_lokasi"] for l in org.daftar_lokasi()
                                      if l["is_active"] or (lama and l["id_lokasi"] == lama["id_lokasi"])}, "Mill")
        nama = _teks("nama").upper()
        if org.nama_area_dipakai(id_c, nama, kecuali=id_a):
            raise ValueError(f"Area {nama} sudah ada di perusahaan ini.")
        if lama and lama["jumlah_user"] and (lama["id_company"] != id_c):
            raise ValueError(f"Area ini masih dipakai {lama['jumlah_user']} pengguna aktif, perusahaannya tidak bisa diganti.")
        org.simpan_area(id_a, id_c, id_l, nama, _teks("keterangan", wajib=False, maks=255) or None)
        _audit("AREA_SIMPAN", nama, id_c)
        return jsonify({"message": f"Area {nama} berhasil disimpan."})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/lokasi/simpan", methods=["POST"])
@_admin
def lokasi_simpan():
    """Mill = tipe area untuk semua PT; kode sama dipakai semua PT (600 = PKS di YBS maupun SUN)."""
    def aksi():
        id_l = _id_opsional("id_lokasi")
        kode, nama = _kode_org("Mill", "MillID", id_l, "MillCode"), _teks("nama").upper()
        is_pusat = request.form.get("is_pusat") == "1"
        org.simpan_lokasi(id_l, kode, nama, _teks("keterangan", wajib=False, maks=255) or None, is_pusat)
        _audit("LOKASI_SIMPAN", kode, f"{nama}{' (kantor pusat)' if is_pusat else ''}")
        return jsonify({"message": f"Mill {kode} ({nama}) berhasil disimpan."})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/department/simpan", methods=["POST"])
@_admin
def department_simpan():
    def aksi():
        id_d = (request.form.get("id_department") or "").strip().upper() or None
        kode, nama = _kode_org("Department", "DeptID", id_d, maks=5), _teks("nama")
        if org.kode_dipakai("Department", "DeptID", "DeptName", nama, kecuali=id_d or kode):
            raise ValueError(f"Departemen {nama} sudah ada.")
        semua = {a["id_comp_area"] for a in org.daftar_area()}
        area = {int(v) for v in request.form.getlist("area") if v.isdigit()}
        if not area:
            raise ValueError("Pilih minimal satu area tempat departemen ini ada.")
        if area - semua:
            raise ValueError("Pilih area dari daftar.")
        org.simpan_department(id_d, kode, nama, _teks("keterangan", wajib=False, maks=255) or None, area)
        _audit("DEPARTMENT_SIMPAN", nama)
        return jsonify({"message": f"Departemen {nama} berhasil disimpan."})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/jabatan/simpan", methods=["POST"])
@_admin
def jabatan_simpan():
    def aksi():
        id_j, nama = _id_opsional("id_jabatan"), _teks("nama")
        if hak_akses.nama_jabatan_dipakai(nama, kecuali=id_j):
            raise ValueError(f"Jabatan {nama} sudah ada.")
        teks = (request.form.get("urutan") or "").strip()
        urutan = int(teks) if teks.isdigit() else 100
        hak_akses.simpan_jabatan(id_j, nama, _teks("keterangan", wajib=False, maks=255) or None, urutan)
        get_user_by_id.hapus()
        _audit("JABATAN_SIMPAN", nama)
        return jsonify({"message": f"Jabatan {nama} berhasil disimpan."})
    return _jalankan(aksi)


# ===== ALUR PERSETUJUAN (migrasi 043) =====
@admin_bp.route("/api/admin/alur-persetujuan")
@_admin
def alur_persetujuan_daftar():
    return jsonify(alur_persetujuan.daftar())


@admin_bp.route("/api/admin/alur-persetujuan/simpan", methods=["POST"])
@_admin
def alur_persetujuan_simpan():
    """tahap = "id_department:id_jabatan,..." sesuai urutan; peran dibuat otomatis bila belum ada."""
    def aksi():
        f = request.form
        jabatan = {j["id_jabatan"]: j for j in hak_akses.daftar_jabatan() if j["is_active"]}
        departemen = {d["id_department"] for d in org.daftar_department() if d["is_active"]}
        daftar_level = []
        for n, bagian in enumerate([b for b in (f.get("tahap") or "").split(",") if b.strip()], 1):
            id_d, _, teks_j = bagian.partition(":")
            id_d = id_d.strip().upper()
            if not teks_j.strip().isdigit():
                raise ValueError(f"Tahap {n}: pilih departemen dan jabatan")
            id_j = int(teks_j)
            if id_j not in jabatan or jabatan[id_j]["is_admin"]:
                raise ValueError(f"Tahap {n}: jabatan tidak valid")
            if id_d not in departemen:
                raise ValueError(f"Tahap {n}: departemen tidak valid")
            daftar_level.append(hak_akses.peran_untuk(id_d, id_j))
        jenis, kategori = (f.get("jenis") or "").strip(), (f.get("kategori") or "").strip() or None
        id_alur = alur_persetujuan.simpan(_id_opsional("id_alur_persetujuan"), jenis, kategori,
                                          _teks("keterangan", wajib=False, maks=255) or None, daftar_level)
        _audit("ALUR_PERSETUJUAN_SIMPAN", f"{jenis}/{kategori or 'SEMUA'}",
               " → ".join(hak_akses.get_level(i)["nama"] for i in daftar_level))
        return jsonify({"message": "Alur persetujuan berhasil disimpan.", "id": id_alur})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/alur-persetujuan/<int:id_alur>/aktif", methods=["POST"])
@_admin
def alur_persetujuan_aktif(id_alur):
    aktif = _aktif_dari_form()
    alur_persetujuan.set_aktif(id_alur, aktif)
    _audit(f"ALUR_PERSETUJUAN_{'AKTIF' if aktif else 'NONAKTIF'}", str(id_alur))
    return jsonify({"message": f"Alur persetujuan berhasil {'diaktifkan' if aktif else 'dinonaktifkan'}."})


@admin_bp.route("/api/admin/alur-persetujuan/<int:id_alur>/hapus", methods=["POST"])
@_admin
def alur_persetujuan_hapus(id_alur):
    alur_persetujuan.hapus(id_alur)
    _audit("ALUR_PERSETUJUAN_HAPUS", str(id_alur))
    return jsonify({"message": "Alur persetujuan berhasil dihapus. Pengajuan yang sedang berjalan tetap memakai tahap lamanya."})


@admin_bp.route("/api/admin/organisasi/status/simpan", methods=["POST"])
@_admin
def status_simpan():
    """Nama & warna status tiket (ERD Status: StatusName, StatusColor)."""
    def aksi():
        kode = (request.form.get("kode") or "").strip().upper()
        if kode not in {s["kode"] for s in alur.daftar_status()}:
            raise ValueError("Status tidak ditemukan.")
        nama, warna = _teks("nama", maks=50), (request.form.get("warna") or "").strip()
        if warna not in alur.WARNA_STATUS:
            raise ValueError("Pilih warna dari daftar.")
        alur.simpan_status(kode, nama, warna)
        _audit("STATUS_TIKET_SIMPAN", kode, f"{nama} ({warna})")
        return jsonify({"message": f"Status {nama} berhasil disimpan."})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/<jenis>/<id_baris>/aktif", methods=["POST"])
@_admin
def organisasi_aktif(jenis, id_baris):
    if jenis not in ("company", "department"):          # perusahaan & departemen memakai kode, sisanya angka
        if not id_baris.isdigit():
            abort(404)
        id_baris = int(id_baris)
    fungsi = {"company": org.set_aktif_company, "area": org.set_aktif_area, "lokasi": org.set_aktif_lokasi,
              "department": org.set_aktif_department, "jabatan": hak_akses.set_aktif_jabatan}
    if jenis not in fungsi:
        abort(404)
    label = {"company": "Perusahaan", "area": "Area", "lokasi": "Mill", "department": "Departemen", "jabatan": "Jabatan"}[jenis]

    def aksi():
        aktif = _aktif_dari_form()
        if not aktif:
            dipakai = {"company": [(c["id_company"], c["jumlah_area"]) for c in org.daftar_company()],
                       "area": [(a["id_comp_area"], a["jumlah_user"]) for a in org.daftar_area()],
                       "lokasi": [(l["id_lokasi"], l["jumlah_area"]) for l in org.daftar_lokasi()],
                       "department": [(d["id_department"], d["jumlah_user"]) for d in org.daftar_department()],
                       "jabatan": [(j["id_jabatan"], j["jumlah_user"]) for j in hak_akses.daftar_jabatan()]}[jenis]
            if dict(dipakai).get(id_baris):
                raise ValueError(f"{label} masih digunakan. Pindahkan pengguna / area terkait terlebih dahulu.")
        fungsi[jenis](id_baris, aktif)
        _audit(f"{jenis.upper()}_{'AKTIF' if aktif else 'NONAKTIF'}", str(id_baris))
        return jsonify({"message": f"{label} berhasil {'diaktifkan' if aktif else 'dinonaktifkan'}."})
    return _jalankan(aksi)


# ===== SESI AKTIF =====
@admin_bp.route("/api/admin/sesi")
@_admin
def sesi_daftar():
    batas = pengaturan.nilai("SESI_IDLE_MENIT") * 60
    sekarang = time.time()
    sesi = [{"user_id": s["user_id"], "username": s["username"], "nama": s["nama"], "role": s["role"],
             "ip": s["ip"], "agen": s["agen"], "is_saya": s["user_id"] == current_user.id,
             "login": datetime.fromtimestamp(s["login"]).strftime("%Y-%m-%d %H:%M"),
             "idle_menit": int((sekarang - s["terakhir_aktif"]) // 60)}
            for s in sesi_aktif.daftar(batas)]
    return jsonify({"sesi": sesi, "terkunci": login_guard.daftar_terkunci()})


@admin_bp.route("/api/admin/sesi/paksa-keluar", methods=["POST"])
@_admin
def sesi_paksa_keluar():
    def aksi():
        id_user = int(request.form.get("id_user") or 0)
        if id_user == current_user.id:
            raise ValueError("Untuk keluar dari akun sendiri gunakan tombol Keluar")
        u = _user_atau_404(id_user)
        db.cabut_sesi(id_user)
        sesi_aktif.hapus_user(id_user)
        _audit("SESI_PAKSA_KELUAR", u["username"])
        log_keamanan("PAKSA_KELUAR", f"username={u['username']}")
        return jsonify({"message": f"Semua sesi {u['username']} berhasil diakhiri"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/sesi/buka-kunci", methods=["POST"])
@_admin
def sesi_buka_kunci():
    """Dari baris tabel (kunci "u:joko" / "ip:10.0.0.7") atau dari form (username ATAU IP diketik admin)."""
    kunci, teks = request.form.get("kunci") or "", (request.form.get("teks") or "").strip()
    if teks:
        dibuka = login_guard.buka_kunci_teks(teks, current_user.id)
        target = teks
    else:
        dibuka = int(login_guard.buka_kunci(kunci, current_user.id))
        target = kunci
    if not dibuka:
        return jsonify({"error": f"{target or 'Data'} tidak sedang terkunci"}), 400
    _audit("BUKA_KUNCI_LOGIN", target)
    return jsonify({"message": f"Kunci login {target} berhasil dibuka"})


@admin_bp.route("/api/admin/sesi/buka-semua", methods=["POST"])
@_admin
def sesi_buka_semua():
    jumlah = login_guard.buka_semua(current_user.id)
    if not jumlah:
        return jsonify({"error": "Tidak ada login yang terkunci"}), 400
    _audit("BUKA_KUNCI_LOGIN", "SEMUA", f"{jumlah} kunci")
    return jsonify({"message": f"{jumlah} kunci login berhasil dibuka"})


# ===== VOID TIKET =====
@admin_bp.route("/api/admin/tiket")
@_admin
def tiket_daftar():
    hari = min(max(int(request.args.get("hari") or 30), 1), 365)
    return jsonify([{**r, "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M"),
                     "void_at": r["void_at"].strftime("%Y-%m-%d %H:%M") if r["void_at"] else None}
                    for r in db.daftar_tiket(request.args.get("cari", ""), hari)])


@admin_bp.route("/api/admin/tiket/void", methods=["POST"])
@_admin
def tiket_void():
    def aksi():
        no_tiket, alasan = _teks("no_tiket", maks=50), _teks("alasan", maks=255)
        if len(alasan) < 5:
            raise ValueError("Alasan minimal 5 karakter")
        ba = _berita_acara(wajib=False)
        try:
            db.void_tiket(no_tiket, alasan, current_user.id, ba)
        except Exception:
            hapus_file_info([ba["file_info"]] if ba else [])
            raise
        _audit("TIKET_VOID", no_tiket, alasan + (f" · BA {ba['no']}" if ba else " · BA menyusul"))
        return jsonify({"message": f"Tiket {no_tiket} berhasil dibatalkan" + ("" if ba else ". Berita acara bisa dilampirkan menyusul.")})
    return _jalankan(aksi)


def _berita_acara(wajib):
    """No, tanggal, dan file berita acara dari form; None bila kosong semua (menyusul) dan tidak wajib."""
    no = (request.form.get("no_ba") or "").strip()
    file = request.files.get("file_ba")
    ada_file = bool(file and file.filename)
    if not wajib and not no and not ada_file:
        return None
    if not no or not ada_file:
        raise ValueError("Berita acara: isi No. BA dan unggah filenya (atau kosongkan keduanya bila menyusul)")
    if len(no) > 100:
        raise ValueError("No. BA maksimal 100 karakter")
    try:
        tanggal = date.fromisoformat((request.form.get("tgl_ba") or "").strip())
    except ValueError:
        raise ValueError("Tanggal BA tidak valid")
    if tanggal > date.today():
        raise ValueError("Tanggal BA tidak boleh setelah hari ini")
    return {"no": no, "tanggal": tanggal, "file_info": simpan_file(file, "BA_VOID")}


@admin_bp.route("/api/admin/tiket/<path:no_tiket>/ba", methods=["POST"])
@_admin
def tiket_ba(no_tiket):
    def aksi():
        ba = _berita_acara(wajib=True)
        try:
            db.lampirkan_ba_void(no_tiket, ba, current_user.id)
        except Exception:
            hapus_file_info([ba["file_info"]])
            raise
        _audit("TIKET_VOID_BA", no_tiket, f"BA {ba['no']}")
        return jsonify({"message": f"Berita acara tiket {no_tiket} berhasil dilampirkan"})
    return _jalankan(aksi)


# ===== JADWAL KERJA =====
def _jam_teks(j):
    return j.strftime("%H:%M") if hasattr(j, "strftime") else (str(j)[:5] if j else None)


@admin_bp.route("/api/admin/jadwal")
@_admin
def jadwal_daftar():
    area = request.args.get("area", "")
    return jsonify([{"hari": j["hari"], "nama_hari": j["nama_hari"], "is_libur": bool(j["is_libur"]),
                     "jam_masuk": _jam_teks(j["jam_masuk"]), "jam_pulang": _jam_teks(j["jam_pulang"]),
                     "toleransi_menit": j["toleransi_menit"]}
                    for j in get_jadwal_kerja(int(area) if area.isdigit() else None)])


@admin_bp.route("/api/admin/jadwal/simpan", methods=["POST"])
@_admin
def jadwal_simpan():
    def aksi():
        id_area = _id_form("id_comp_area", {a["id_comp_area"] for a in org.daftar_area()}, "area")
        hari = int(request.form.get("hari") or 0)
        if not 1 <= hari <= 7:
            raise ValueError("Hari tidak valid")
        libur = request.form.get("is_libur") in ("1", "true")
        masuk, pulang = (request.form.get("jam_masuk") or "").strip(), (request.form.get("jam_pulang") or "").strip()
        toleransi = int(request.form.get("toleransi_menit") or 0)
        if not 0 <= toleransi <= 120:
            raise ValueError("Toleransi 0-120 menit")
        if libur:
            masuk = pulang = None
        else:
            if not (POLA_JAM.match(masuk) and POLA_JAM.match(pulang)):
                raise ValueError("Jam harus format JJ:MM, mis. 08:00")
            if pulang <= masuk:
                raise ValueError("Jam pulang harus setelah jam masuk")
        db.ubah_jadwal(id_area, hari, libur, masuk, pulang, toleransi)
        _audit("JADWAL_UBAH", f"area {id_area} hari {hari}", "libur" if libur else f"{masuk}-{pulang}, toleransi {toleransi} mnt")
        return jsonify({"message": "Jadwal berhasil disimpan"})
    return _jalankan(aksi)


# ===== PENGATURAN SITE =====
def _area_pengaturan(nilai):
    """'' = global; selain itu id area yang valid."""
    nilai = (nilai or "").strip()
    if not nilai:
        return None
    if not nilai.isdigit() or int(nilai) not in {a["id_comp_area"] for a in org.daftar_area()}:
        raise ValueError("Area tidak dikenal")
    return int(nilai)


@admin_bp.route("/api/admin/pengaturan")
@_admin
def pengaturan_daftar():
    try:
        return jsonify(pengaturan.semua(_area_pengaturan(request.args.get("area"))))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.route("/api/admin/pengaturan/simpan", methods=["POST"])
@_admin
def pengaturan_simpan():
    def aksi():
        # Hanya yang nilainya berubah yang disimpan, supaya sisanya tetap mengikuti .env / bawaan
        id_area = _area_pengaturan(request.form.get("id_comp_area"))
        lama = {p["kunci"]: p["nilai"] for p in pengaturan.semua(id_area)}
        masuk = {k: pengaturan.validasi(k, v) for k, v in request.form.items() if k in lama}
        berubah = {k: v for k, v in masuk.items() if pengaturan.validasi(k, lama[k]) != v}
        if not berubah:
            return jsonify({"message": "Tidak ada perubahan yang disimpan"})
        pengaturan.simpan(berubah, current_user.id, id_area)
        for kunci, teks in berubah.items():
            _audit("PENGATURAN_UBAH", f"{kunci} (area {id_area})" if id_area else kunci, f"{lama[kunci]} -> {teks}")
        return jsonify({"message": f"{len(berubah)} pengaturan berhasil disimpan dan langsung berlaku"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/pengaturan/salin-company", methods=["POST"])
@_admin
def pengaturan_salin_company():
    """Pengaturan per area dari area ini diterapkan ke semua area aktif lain di company yang sama."""
    def aksi():
        id_area = _area_pengaturan(request.form.get("id_comp_area"))
        if not id_area:
            raise ValueError("Silakan pilih area")
        areas = org.daftar_area()
        id_company = next(a["id_company"] for a in areas if a["id_comp_area"] == id_area)
        tujuan = [a for a in areas if a["id_company"] == id_company and a["is_active"] and a["id_comp_area"] != id_area]
        if not tujuan:
            raise ValueError("Company ini tidak punya area lain")
        nilai = {p["kunci"]: pengaturan.validasi(p["kunci"], p["nilai"]) for p in pengaturan.semua(id_area)}
        for a in tujuan:
            pengaturan.simpan(nilai, current_user.id, a["id_comp_area"])
        _audit("PENGATURAN_SALIN_COMPANY", f"area {id_area}", ", ".join(a["nama"] for a in tujuan))
        return jsonify({"message": f"Pengaturan berhasil diterapkan ke {len(tujuan)} area lain: {', '.join(a['nama'] for a in tujuan)}"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/pengaturan/bawaan", methods=["POST"])
@_admin
def pengaturan_bawaan():
    kunci = request.form.get("kunci") or ""
    if kunci not in pengaturan.DEFINISI:
        return jsonify({"error": "Pengaturan tidak dikenal"}), 400
    try:
        id_area = _area_pengaturan(request.form.get("id_comp_area"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    pengaturan.kembalikan_bawaan(kunci, id_area)
    _audit("PENGATURAN_BAWAAN", f"{kunci} (area {id_area})" if id_area else kunci)
    return jsonify({"message": "Pengaturan kembali mengikuti nilai global" if id_area else "Dikembalikan ke nilai bawaan"})


# ===== PERANGKAT / KIOSK =====
@admin_bp.route("/api/admin/perangkat")
@_admin
def perangkat_daftar():
    terlihat, sekarang = kiosk.terakhir_terlihat(), time.time()
    hasil = []
    for p in kiosk.daftar():
        t = terlihat.get(p["id_pos"])
        hasil.append({**p, "created_at": p["created_at"].strftime("%Y-%m-%d") if p["created_at"] else None,
                      "terakhir_detik": int(sekarang - t["waktu"]) if t else None, "ip": t["ip"] if t else None})
    status = semua_status()
    jembatan = [{**j, "created_at": j["created_at"].strftime("%Y-%m-%d") if j["created_at"] else None,
                 "status": status.get(j["id_jembatan"])} for j in _daftar_jembatan_aman()]
    return jsonify({"perangkat": hasil, "token_env": bool(os.getenv("KIOSK_TOKEN")), "jembatan": jembatan,
                    "timbangan": {"terhubung": sum(1 for s in status.values() if s["terhubung"]), "jumlah": len(status)}})


def _daftar_jembatan_aman():
    try:
        return jembatan_db.daftar_jembatan()
    except Exception:       # noqa: BLE001 - migrasi 011 belum dijalankan
        return []


POLA_PORT = re.compile(r"^(COM\d{1,3}|/dev/tty[A-Za-z0-9]{1,12})$")
POLA_PORT_LAN = re.compile(r"^(socket|rfc2217)://[A-Za-z0-9.-]{1,60}:\d{1,5}$")       # alat serial-to-LAN


def _angka_form(nama, label, minimal, maksimal, bawaan):
    teks = (request.form.get(nama) or "").strip().replace(",", ".")
    try:
        nilai = float(teks) if teks else float(bawaan)
    except ValueError:
        raise ValueError(f"{label} harus angka")
    if not minimal <= nilai <= maksimal:
        raise ValueError(f"{label} harus {minimal:g} - {maksimal:g}")
    return nilai


def _profil_jembatan_form(port):
    """Profil indikator dari form Admin (lihat utils/serial_reader.py)."""
    f = request.form
    mode = (f.get("mode") or "LOKAL").upper()
    if mode not in ("LOKAL", "AGEN"):
        raise ValueError("Sumber data tidak dikenal")
    if mode == "AGEN" and POLA_PORT_LAN.match(port):
        raise ValueError("Mode agen membaca COM di PC jembatan; alamat socket:// dipakai mode Lokal (alat serial-to-LAN)")
    fmt = (f.get("format_data") or "ST_GS").upper()
    if fmt not in FORMAT_TIMBANGAN:
        raise ValueError("Format data tidak dikenal")
    pola = (f.get("pola") or "").strip()[:200] or None
    if fmt == "POLA":
        try:
            if "berat" not in re.compile(pola or "").groupindex:
                raise ValueError("Pola wajib punya grup (?P<berat>...)")
        except re.error as e:
            raise ValueError(f"Pola regex tidak valid: {e}")
    parity = (f.get("parity") or "E").upper()
    if parity not in ("N", "E", "O", "M", "S"):
        raise ValueError("Parity: N / E / O")
    data_bits = int(f.get("data_bits") or 7)
    if data_bits not in (5, 6, 7, 8):
        raise ValueError("Data bits: 7 atau 8")
    stop_bits = _angka_form("stop_bits", "Stop bits", 1, 2, 1)
    if stop_bits not in (1, 1.5, 2):
        raise ValueError("Stop bits: 1 atau 2")
    return {"mode": mode, "data_bits": data_bits, "parity": parity, "stop_bits": stop_bits, "format_data": fmt,
            "pola": pola if fmt == "POLA" else None,
            "faktor": _angka_form("faktor", "Faktor", 0.0001, 100000, 1),
            "toleransi_kg": _angka_form("toleransi_kg", "Toleransi stabil", 0, 500, 5),
            "durasi_stabil": _angka_form("durasi_stabil", "Durasi stabil", 0.5, 30, 3),
            "berat_min_kg": _angka_form("berat_min_kg", "Berat minimum", 0, 100000, 100),
            "wajib_st": f.get("wajib_st") in ("1", "true", "on")}


def _atur_pembaca():
    """Perubahan jembatan dari Admin langsung berlaku di pembaca timbangan (tanpa restart)."""
    try:
        atur_pembaca(jembatan_db.daftar_jembatan())
    except Exception:       # noqa: BLE001
        import logging
        logging.getLogger("weighbridge").exception("Gagal menerapkan pengaturan jembatan")


@admin_bp.route("/api/admin/jembatan/simpan", methods=["POST"])
@_admin
def jembatan_simpan():
    def aksi():
        teks_id = (request.form.get("id_jembatan") or "").strip()
        id_j = int(teks_id) if teks_id.isdigit() else None
        id_area = _id_form("id_comp_area", {a["id_comp_area"] for a in org.daftar_area() if a["is_active"]}, "area")
        kode = _teks("kode", maks=10).upper()
        if not re.match(r"^[A-Z0-9_-]{2,10}$", kode):
            raise ValueError("Kode 2-10 karakter: huruf besar, angka, - atau _ (mis. JT-1)")
        if jembatan_db.kode_dipakai(id_area, kode, kecuali=id_j):
            raise ValueError(f"Kode {kode} sudah dipakai di area ini")
        port = _teks("port", maks=100)
        port = port.upper() if port.upper().startswith("COM") else port
        if not (POLA_PORT.match(port) or POLA_PORT_LAN.match(port)):
            raise ValueError("Port: COM1-COM999, /dev/ttyUSB0, atau socket://IP:PORT (alat serial-to-LAN)")
        baud = int(request.form.get("baudrate") or 9600)
        if baud not in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200):
            raise ValueError("Baudrate tidak umum")
        profil = _profil_jembatan_form(port)
        jembatan_db.simpan_jembatan(id_j, id_area, kode, _teks("nama"), port, baud, profil)
        _atur_pembaca()
        _audit("JEMBATAN_SIMPAN", kode, f"{profil['mode']} {port} {baud} {profil['data_bits']}{profil['parity']}"
                                        f"{profil['stop_bits']:g} {profil['format_data']}")
        return jsonify({"message": f"Jembatan {kode} berhasil disimpan dan langsung berlaku"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/jembatan/<int:id_jembatan>/aktif", methods=["POST"])
@_admin
def jembatan_aktif(id_jembatan):
    def aksi():
        aktif = _aktif_dari_form()
        jembatan_db.set_aktif_jembatan(id_jembatan, aktif)
        _atur_pembaca()
        _audit("JEMBATAN_AKTIF" if aktif else "JEMBATAN_NONAKTIF", str(id_jembatan))
        return jsonify({"message": "Jembatan berhasil " + ("diaktifkan" if aktif else "dinonaktifkan")})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/jembatan/<int:id_jembatan>/mentah")
@_admin
def jembatan_mentah(id_jembatan):
    """Bingkai data terakhir dari indikator + hasil bacanya, untuk menyetel format / baudrate di lokasi."""
    hasil = data_mentah(id_jembatan)
    if hasil is None:
        return jsonify({"error": "Jembatan tidak aktif / belum dibaca"}), 404
    return jsonify(hasil)


def _id_pos_form():
    id_pos = _teks("id_pos", maks=30).upper()
    if not kiosk.POLA_ID_POS.match(id_pos):
        raise ValueError("ID pos 2-30 karakter: huruf besar, angka, - atau _")
    return id_pos


def _area_pos_form():
    return _id_form("id_comp_area", {a["id_comp_area"] for a in org.daftar_area() if a["is_active"]}, "area")


@admin_bp.route("/api/admin/perangkat/tambah", methods=["POST"])
@_admin
def perangkat_tambah():
    def aksi():
        id_pos, nama, lokasi = _id_pos_form(), _teks("nama"), _teks("lokasi", wajib=False)
        token = kiosk.tambah(id_pos, nama, lokasi, _area_pos_form())
        _audit("KIOSK_TAMBAH", id_pos, nama)
        return jsonify({"message": f"Pos {id_pos} berhasil ditambahkan", "id_pos": id_pos, "token": token})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/perangkat/ubah", methods=["POST"])
@_admin
def perangkat_ubah():
    def aksi():
        id_pos = _id_pos_form()
        kiosk.ubah(id_pos, _teks("nama"), _teks("lokasi", wajib=False), _area_pos_form())
        _audit("KIOSK_UBAH", id_pos)
        return jsonify({"message": f"Pos {id_pos} berhasil diperbarui"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/perangkat/ganti-token", methods=["POST"])
@_admin
def perangkat_ganti_token():
    def aksi():
        id_pos = _id_pos_form()
        token = kiosk.ganti_token(id_pos)
        _audit("KIOSK_GANTI_TOKEN", id_pos)
        log_keamanan("KIOSK_GANTI_TOKEN", f"pos={id_pos}")
        return jsonify({"message": f"Token pos {id_pos} berhasil diganti. Token lama langsung tidak berlaku.",
                        "id_pos": id_pos, "token": token})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/perangkat/aktif", methods=["POST"])
@_admin
def perangkat_aktif():
    def aksi():
        id_pos, aktif = _id_pos_form(), _aktif_dari_form()
        kiosk.set_aktif(id_pos, aktif)
        _audit("KIOSK_AKTIF" if aktif else "KIOSK_NONAKTIF", id_pos)
        return jsonify({"message": f"Pos {id_pos} berhasil {'diaktifkan' if aktif else 'dinonaktifkan'}"})
    return _jalankan(aksi)


# ===== LOG KEAMANAN & AUDIT ADMIN =====
@admin_bp.route("/api/admin/log-keamanan")
@_admin
def log_keamanan_daftar():
    return jsonify(baca_log_keamanan(batas=500, cari=(request.args.get("cari") or "").strip(),
                                     jenis=(request.args.get("jenis") or "").strip().upper()))


@admin_bp.route("/api/admin/audit")
@_admin
def audit_admin_daftar():
    hari = min(max(int(request.args.get("hari") or 7), 1), 90)
    return jsonify([{**r, "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S")}
                    for r in db.daftar_audit_admin(hari)])


@admin_bp.route("/api/admin/kolom-wajib")
@_admin
def kolom_wajib_daftar():
    aktif = kolom_wajib.wajib()
    return jsonify([{"kode": kode, "nama": nama,
                     "kolom": [{"kolom": k, "label": label, "wajib": k in aktif.get(kode, ())} for k, label in kolom.items()]}
                    for kode, (nama, _, kolom) in kolom_wajib.DAFTAR.items()])


@admin_bp.route("/api/admin/kolom-wajib", methods=["POST"])
@_admin
def kolom_wajib_simpan():
    def aksi():
        pilihan = {tuple(v.split("|", 1)) for v in request.form.getlist("wajib") if "|" in v}
        kolom_wajib.simpan(pilihan)
        _audit("KOLOM_WAJIB_SIMPAN", None, ", ".join(sorted(f"{f}.{k}" for f, k in pilihan)) or "tidak ada")
        return jsonify({"message": "Kolom wajib berhasil disimpan. Berlaku saat formulir dibuka berikutnya."})
    return _jalankan(aksi)


# Nama tabel yang dicatat trigger log perubahan data (migrasi 034) untuk pilihan filter
TABEL_LOG_DATA = {
    "Users": "Pengguna", "Company": "Perusahaan", "CompanyArea": "Area Perusahaan", "Mill": "Mill", "Department": "Departemen",
    "LevelDetails": "Jabatan", "Supplier": "Supplier", "Product": "Produk & Standar Mutu", "DetailVehicle": "Kendaraan",
    "VehicleType": "Jenis Kendaraan", "Contract": "Kontrak", "DeliveryOrder": "DO", "Scale": "Jembatan Timbang",
    "DailyPrice": "Harga Harian", "Setting": "Pengaturan", "SettingArea": "Pengaturan Area",
    "Status": "Status Tiket", "UserCategory": "Kategori Personel", "License": "Jenis SIM",
    "VisitPurpose": "Keperluan Kunjungan", "WeightBridge": "Tiket",
}


@admin_bp.route("/api/admin/audit/data")
@_admin
def audit_data_daftar():
    """Log perubahan data (kategori DATA & koreksi tiket): hanya kolom yang berubah, lama -> baru."""
    hari = min(max(int(request.args.get("hari") or 7), 1), 90)
    tabel = (request.args.get("tabel") or "").strip()
    hasil = []
    for r in log_aktivitas.daftar("DATA", hari, 500):
        if tabel and r["tabel"] != tabel:
            continue
        lama, baru = r["nilai_lama"] or {}, r["nilai_baru"] or {}
        kolom = sorted(set(lama) | set(baru), key=lambda k: list(baru or lama).index(k) if k in (baru or lama) else 999)
        ubah = [{"kolom": k, "lama": lama.get(k), "baru": baru.get(k)} for k in kolom
                if r["aksi"] != "DATA_UBAH" or lama.get(k) != baru.get(k)]
        hasil.append({"id_log": r["id_log"], "waktu": r["waktu"].strftime("%Y-%m-%d %H:%M:%S"), "aksi": r["aksi"],
                      "tabel": r["tabel"], "nama_tabel": TABEL_LOG_DATA.get(r["tabel"], r["tabel"]), "id_baris": r["id_baris"],
                      "oleh": r["oleh"], "username": r["username"], "ip": r["ip"], "perubahan": ubah})
    return jsonify({"tabel": TABEL_LOG_DATA, "data": hasil})


@admin_bp.route("/api/admin/audit/verifikasi")
@_admin
def audit_verifikasi():
    """Cek rantai hash log_aktivitas: baris yang diubah / dihapus langsung di database ketahuan."""
    return jsonify(log_aktivitas.verifikasi())


# ===== KESEHATAN SISTEM =====
def _ukuran_folder_mb(path, batas_file=20000):
    total, n = 0, 0
    for akar, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(akar, f))
            except OSError:
                pass
            n += 1
            if n >= batas_file:
                return round(total / 1048576, 1), True
    return round(total / 1048576, 1), False


def _versi_git():
    try:
        with open(os.path.join(BASE_DIR, ".git", "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            path = os.path.join(BASE_DIR, ".git", *ref.split("/"))
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return f"{ref.rsplit('/', 1)[-1]} @ {f.read().strip()[:7]}"
            return ref.rsplit("/", 1)[-1]
        return head[:7]
    except OSError:
        return "-"


@admin_bp.route("/api/admin/kesehatan")
@_admin
def kesehatan():
    mulai = time.perf_counter()
    try:
        db_ok = cek_koneksi_db()
        info_db = db.info_database()
    except Exception as e:      # noqa: BLE001 - tampilkan sebagai status, bukan error 500
        db_ok, info_db = False, {"error": str(e)[:200]}
    latensi = round((time.perf_counter() - mulai) * 1000)
    if isinstance(info_db.get("backup_terakhir"), datetime):
        b = info_db["backup_terakhir"]
        info_db["backup_umur_jam"] = round((datetime.now() - b).total_seconds() / 3600, 1)
        info_db["backup_terakhir"] = b.strftime("%Y-%m-%d %H:%M")
    disk = shutil.disk_usage(BASE_DIR)
    upload_mb, upload_terpotong = _ukuran_folder_mb(UPLOAD_FOLDER)
    status = semua_status()
    return jsonify({
        "database": {"ok": db_ok, "latensi_ms": latensi, **info_db},
        "disk": {"total_gb": round(disk.total / 1073741824, 1), "sisa_gb": round(disk.free / 1073741824, 1),
                 "terpakai_persen": round(disk.used * 100 / disk.total, 1)},
        "upload": {"ukuran_mb": upload_mb, "lebih": upload_terpotong},
        "timbangan": {"terhubung": bool(status) and all(s["terhubung"] for s in status.values()),
                      "jumlah": len(status), "jumlah_terhubung": sum(1 for s in status.values() if s["terhubung"])},
        "aplikasi": {"versi": versi_aplikasi(), "git": _versi_git(), "python": platform.python_version(),
                     "berjalan_sejak": datetime.fromtimestamp(WAKTU_MULAI).strftime("%Y-%m-%d %H:%M"),
                     "uptime_jam": round((time.time() - WAKTU_MULAI) / 3600, 1),
                     "sesi_aktif": len(sesi_aktif.daftar(pengaturan.nilai("SESI_IDLE_MENIT") * 60))},
    })

