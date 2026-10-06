"""Menu Admin (super admin): hanya role ADMIN (dijaga juga oleh utils.keamanan.pasang_batas_admin).

Halaman  : /admin/<halaman>      (satu menu sidebar = satu halaman, tanpa tab)
API      : /api/admin/...        (JSON, semua aksi tercatat di admin_audit_logs)"""
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
from utils.hak_akses import admin_required
from utils.dokumen import simpan_file, hapus_file_info
from utils import db_admin as db, db_organisasi as org, hak_akses, pengaturan, login_guard, sesi_aktif, kiosk
from utils import verifikasi_state as verif
from utils.db_utils import cek_koneksi_db, get_password_hash, get_user_by_id
from utils.db_absensi import get_jadwal_kerja
from utils.keamanan import log_keamanan, baca_log_keamanan
from utils.serial_reader import semua_status, atur as atur_pembaca, data_mentah, FORMAT as FORMAT_TIMBANGAN
from utils import db_jembatan as jembatan_db
from utils import alur, log_aktivitas

admin_bp = Blueprint("admin", __name__)
WAKTU_MULAI = time.time()

# key -> (judul, ikon Font Awesome, keterangan). Urutan = urutan menu sidebar.
HALAMAN = {
    "users": ("Kelola User", "fa-users", "Tambah akun, ubah level / department / area, reset password, aktif / nonaktif"),
    "hak_akses": ("Level & Hak Akses", "fa-user-shield", "Level (pengganti role), halaman awal, dan aksi yang boleh per menu"),
    "organisasi": ("Organisasi", "fa-sitemap", "Company, area (site), department, dan mill"),
    "sesi": ("Sesi Aktif", "fa-user-clock", "User yang sedang login, paksa keluar, buka kunci login"),
    "master": ("Mitra & Produk", "fa-boxes-stacked", "Mitra (customer / pengangkutan) dan produk"),
    "void": ("Void Tiket", "fa-ban", "Batalkan tiket yang salah input; tiket tidak dihapus, tercatat alasannya"),
    "jadwal": ("Jadwal Kerja", "fa-calendar-days", "Jam masuk, jam pulang, dan toleransi absensi per hari"),
    "pengaturan": ("Pengaturan Site", "fa-sliders", "Scan wajah, sesi login, dan kunci login"),
    "perangkat": ("Perangkat / Kiosk", "fa-camera", "Pos kamera kiosk, token per pos, status timbangan"),
    "log": ("Log Keamanan", "fa-shield-halved", "Login, login gagal, akses ditolak, kiosk ditolak"),
    "audit": ("Audit Admin", "fa-clipboard-list", "Jejak semua perubahan yang dilakukan admin"),
    "kesehatan": ("Kesehatan Sistem", "fa-heart-pulse", "Database, backup, disk, versi aplikasi"),
}

POLA_USERNAME = re.compile(r"^[a-z0-9._]{3,50}$")
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
                           level_list=[lv for lv in hak_akses.daftar_level() if lv["is_active"]],
                           department_list=[d for d in org.daftar_department() if d["is_active"]],
                           area_list=[a for a in org.daftar_area() if a["is_active"]],
                           format_timbangan=FORMAT_TIMBANGAN,
                           company_list=[c for c in org.daftar_company() if c["is_active"]],
                           alur_list=alur.daftar_alur(),
                           kategori_produk=db.KATEGORI_PRODUK, password_min=PASSWORD_MIN)


# ===== KELOLA USER =====
@admin_bp.route("/api/admin/users")
@_admin
def users_daftar():
    return jsonify([{**u, "last_login": u["last_login"].strftime("%Y-%m-%d %H:%M") if u["last_login"] else None,
                     "created_at": u["created_at"].strftime("%Y-%m-%d") if u["created_at"] else None,
                     "is_saya": u["id_user"] == current_user.id}
                    for u in db.daftar_user()])


def _id_form(nama, pilihan, label):
    teks = (request.form.get(nama) or "").strip()
    if not teks.isdigit() or int(teks) not in pilihan:
        raise ValueError(f"Pilih {label} dari daftar")
    return int(teks)


def _akun_form():
    """(id_level, id_department, id_comp_area) dari form; hanya yang aktif."""
    level = {lv["id_level"]: lv for lv in hak_akses.daftar_level() if lv["is_active"]}
    id_level = _id_form("id_level", level, "level")
    id_department = _id_form("id_department", {d["id_department"] for d in org.daftar_department() if d["is_active"]},
                             "department")
    id_area = _id_form("id_comp_area", {a["id_comp_area"] for a in org.daftar_area() if a["is_active"]}, "area")
    return level[id_level], id_department, id_area


def _password_form(nama="password"):
    pw = request.form.get(nama) or ""
    if len(pw) < PASSWORD_MIN:
        raise ValueError(f"Password minimal {PASSWORD_MIN} karakter")
    if pw != (request.form.get("password_ulang") or ""):
        raise ValueError("Ulangi password tidak sama")
    return pw


@admin_bp.route("/api/admin/users/tambah", methods=["POST"])
@_admin
def users_tambah():
    def aksi():
        username = _teks("username", maks=50).lower()
        if not POLA_USERNAME.match(username):
            raise ValueError("Username 3-50 karakter: huruf kecil, angka, titik, garis bawah")
        if db.username_dipakai(username):
            raise ValueError(f"Username {username} sudah dipakai")
        nama, (level, id_department, id_area), pw = _teks("nama"), _akun_form(), _password_form()
        db.tambah_user(username, nama, level["id_level"], id_department, id_area, generate_password_hash(pw))
        _audit("USER_TAMBAH", username, f"level {level['kode']}")
        return jsonify({"message": f"User {username} ditambahkan"})
    return _jalankan(aksi)


def _user_atau_404(id_user):
    u = db.get_user(id_user)
    if not u:
        raise ValueError("User tidak ditemukan")
    return u


@admin_bp.route("/api/admin/users/<int:id_user>/ubah", methods=["POST"])
@_admin
def users_ubah(id_user):
    def aksi():
        u = _user_atau_404(id_user)
        nama, (level, id_department, id_area) = _teks("nama"), _akun_form()
        ganti_level = u["id_level"] != level["id_level"]
        if u["is_admin"] and not level["is_admin"]:
            if id_user == current_user.id:
                raise ValueError("Tidak bisa menurunkan level akun sendiri")
            if db.jumlah_admin_aktif(kecuali=id_user) == 0:
                raise ValueError("Minimal harus ada 1 admin aktif")
        db.ubah_user(id_user, nama, level["id_level"], id_department, id_area)
        _audit("USER_UBAH", u["username"], f"level {u['role']} -> {level['kode']}" if ganti_level else "data diubah")
        if ganti_level:
            sesi_aktif.hapus_user(id_user, "ROLE_DIUBAH")
        return jsonify({"message": f"User {u['username']} diperbarui" +
                        (" (sesi lamanya diakhiri, login ulang dengan level baru)" if ganti_level else "")})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/users/<int:id_user>/reset-password", methods=["POST"])
@_admin
def users_reset_password(id_user):
    def aksi():
        u = _user_atau_404(id_user)
        baru = _password_form()
        lama = get_password_hash(id_user)
        if lama and check_password_hash(lama, baru):
            raise ValueError("Password baru tidak boleh sama dengan password lama")
        db.reset_password(id_user, generate_password_hash(baru))
        sesi_aktif.hapus_user(id_user, "RESET_PASSWORD")
        _audit("USER_RESET_PASSWORD", u["username"])
        log_keamanan("RESET_PASSWORD", f"username={u['username']}")
        return jsonify({"message": f"Password {u['username']} direset. Ia wajib membuat password baru saat login."})
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
        return jsonify({"message": f"User {u['username']} {'diaktifkan' if aktif else 'dinonaktifkan'}"})
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
        raise ValueError("Level tidak ditemukan")
    return lv


@admin_bp.route("/api/admin/level/simpan", methods=["POST"])
@_admin
def level_simpan():
    def aksi():
        teks_id = (request.form.get("id_level") or "").strip()
        id_level = int(teks_id) if teks_id.isdigit() else None
        nama = _teks("nama")
        halaman_awal = _teks("halaman_awal", maks=100)
        if not halaman_awal.startswith("/") or halaman_awal.startswith("//"):
            raise ValueError("Halaman awal harus alamat di aplikasi ini, mis. /dashboard atau /weighbridge?tab=security")
        keterangan = _teks("keterangan", wajib=False, maks=255) or None
        if id_level is None:
            kode = _teks("kode", maks=30).upper()
            if not POLA_KODE.match(kode):
                raise ValueError("Kode 2-30 karakter: huruf besar, angka, garis bawah")
            if hak_akses.kode_level_dipakai(kode):
                raise ValueError(f"Kode level {kode} sudah dipakai")
        else:
            kode = _level_atau_404(id_level)["kode"]
        hak_akses.simpan_level(id_level, kode, nama, halaman_awal, keterangan)
        get_user_by_id.hapus()
        _audit("LEVEL_SIMPAN", kode, nama)
        return jsonify({"message": f"Level {kode} disimpan"})
    return _jalankan(aksi)


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
        return jsonify({"message": f"Level {lv['kode']} {'diaktifkan' if aktif else 'dinonaktifkan'}"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/level/<int:id_level>/akses")
@_admin
def level_akses_lihat(id_level):
    def aksi():
        lv = _level_atau_404(id_level)
        akses = hak_akses.akses_level(id_level)
        return jsonify({"level": lv, "menu": [{**m, **{k: bool(akses.get(m["id_menu"], {}).get(f"bisa_{k}"))
                                                       for k in hak_akses.AKSI}}
                                              for m in hak_akses.daftar_menu_akses()]})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/level/<int:id_level>/akses", methods=["POST"])
@_admin
def level_akses_simpan(id_level):
    def aksi():
        lv = _level_atau_404(id_level)
        if lv["is_admin"]:
            raise ValueError("Level admin hanya untuk area Admin, tidak punya aksi operasional")
        akses = {m["id_menu"]: tuple(request.form.get(f"{m['id_menu']}_{k}") == "1" for k in hak_akses.AKSI)
                 for m in hak_akses.daftar_menu_akses()}
        hak_akses.simpan_akses_level(id_level, akses)
        jumlah = sum(any(v) for v in akses.values())
        _audit("HAK_AKSES_UBAH", lv["kode"], f"{jumlah} menu punya aksi")
        return jsonify({"message": f"Hak akses {lv['nama']} disimpan, langsung berlaku (±30 detik di semua PC)"})
    return _jalankan(aksi)


# ===== ORGANISASI =====
POLA_KODE_ORG = re.compile(r"^[A-Z0-9_-]{2,10}$")


def _kode_org(tabel, kolom_id, id_baris):
    kode = _teks("kode", maks=10).upper()
    if not POLA_KODE_ORG.match(kode):
        raise ValueError("Kode 2-10 karakter: huruf besar, angka, - atau _")
    if org.kode_dipakai(tabel, kolom_id, "kode", kode, kecuali=id_baris):
        raise ValueError(f"Kode {kode} sudah dipakai")
    return kode


def _id_opsional(nama):
    teks = (request.form.get(nama) or "").strip()
    return int(teks) if teks.isdigit() else None


@admin_bp.route("/api/admin/organisasi")
@_admin
def organisasi_daftar():
    return jsonify({"company": org.daftar_company(), "area": org.daftar_area(), "department": org.daftar_department(),
                    "mill": alur.daftar_mill()})


@admin_bp.route("/api/admin/organisasi/company/simpan", methods=["POST"])
@_admin
def company_simpan():
    def aksi():
        id_c = _id_opsional("id_company")
        kode, nama = _kode_org("company", "id_company", id_c), _teks("nama")
        org.simpan_company(id_c, kode, nama)
        _audit("COMPANY_SIMPAN", kode, nama)
        return jsonify({"message": f"Company {nama} disimpan"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/area/simpan", methods=["POST"])
@_admin
def area_simpan():
    def aksi():
        id_a = _id_opsional("id_comp_area")
        id_c = _id_form("id_company", {c["id_company"] for c in org.daftar_company() if c["is_active"]}, "company")
        kode, nama = _kode_org("comp_area", "id_comp_area", id_a), _teks("nama")
        org.simpan_area(id_a, id_c, kode, nama, _teks("alamat", wajib=False, maks=255) or None)
        _audit("AREA_SIMPAN", kode, nama)
        return jsonify({"message": f"Area {nama} disimpan"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/department/simpan", methods=["POST"])
@_admin
def department_simpan():
    def aksi():
        id_d, nama = _id_opsional("id_department"), _teks("nama")
        if org.kode_dipakai("department", "id_department", "nama", nama, kecuali=id_d):
            raise ValueError(f"Department {nama} sudah ada")
        org.simpan_department(id_d, nama, _teks("keterangan", wajib=False, maks=255) or None)
        _audit("DEPARTMENT_SIMPAN", nama)
        return jsonify({"message": f"Department {nama} disimpan"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/mill/simpan", methods=["POST"])
@_admin
def mill_simpan():
    def aksi():
        id_m = _id_opsional("id_mill")
        id_a = _id_form("id_comp_area", {a["id_comp_area"] for a in org.daftar_area() if a["is_active"]}, "area")
        id_alur = _id_form("id_alur", {a["id_alur"] for a in alur.daftar_alur()}, "alur")
        kode, nama = _teks("kode", maks=10).upper(), _teks("nama")
        if not POLA_KODE_ORG.match(kode):
            raise ValueError("Kode 2-10 karakter: huruf besar, angka, - atau _")
        if alur.kode_mill_dipakai(id_a, kode, kecuali=id_m):
            raise ValueError(f"Kode {kode} sudah dipakai di area ini")
        alur.simpan_mill(id_m, id_a, kode, nama, id_alur)
        _audit("MILL_SIMPAN", kode, nama)
        return jsonify({"message": f"Mill {nama} disimpan"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/organisasi/<jenis>/<int:id_baris>/aktif", methods=["POST"])
@_admin
def organisasi_aktif(jenis, id_baris):
    fungsi = {"company": org.set_aktif_company, "area": org.set_aktif_area, "department": org.set_aktif_department,
              "mill": alur.set_aktif_mill}
    if jenis not in fungsi:
        abort(404)

    def aksi():
        aktif = _aktif_dari_form()
        if not aktif and jenis != "mill":
            dipakai = {"company": [(c["id_company"], c["jumlah_area"]) for c in org.daftar_company()],
                       "area": [(a["id_comp_area"], a["jumlah_user"]) for a in org.daftar_area()],
                       "department": [(d["id_department"], d["jumlah_user"]) for d in org.daftar_department()]}[jenis]
            if dict(dipakai).get(id_baris):
                raise ValueError(f"{jenis.capitalize()} masih dipakai, pindahkan dulu user / area-nya")
        fungsi[jenis](id_baris, aktif)
        _audit(f"{jenis.upper()}_{'AKTIF' if aktif else 'NONAKTIF'}", str(id_baris))
        return jsonify({"message": f"{jenis.capitalize()} {'diaktifkan' if aktif else 'dinonaktifkan'}"})
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
        return jsonify({"message": f"Semua sesi {u['username']} diakhiri"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/sesi/buka-kunci", methods=["POST"])
@_admin
def sesi_buka_kunci():
    """Dari baris tabel (kunci "u:joko" / "ip:10.0.0.7") atau dari form (username ATAU IP diketik admin)."""
    kunci, teks = request.form.get("kunci") or "", (request.form.get("teks") or "").strip()
    if teks:
        dibuka = login_guard.buka_kunci_teks(teks)
        target = teks
    else:
        dibuka = int(login_guard.buka_kunci(kunci))
        target = kunci
    if not dibuka:
        return jsonify({"error": f"{target or 'Data'} tidak sedang terkunci"}), 400
    _audit("BUKA_KUNCI_LOGIN", target)
    return jsonify({"message": f"Kunci login {target} dibuka"})


@admin_bp.route("/api/admin/sesi/buka-semua", methods=["POST"])
@_admin
def sesi_buka_semua():
    jumlah = login_guard.buka_semua()
    if not jumlah:
        return jsonify({"error": "Tidak ada login yang terkunci"}), 400
    _audit("BUKA_KUNCI_LOGIN", "SEMUA", f"{jumlah} kunci")
    return jsonify({"message": f"{jumlah} kunci login dibuka"})


# ===== SUPPLIER & PRODUK =====
@admin_bp.route("/api/admin/supplier")
@_admin
def supplier_daftar():
    return jsonify([{**s, "created_at": s["created_at"].strftime("%Y-%m-%d") if s["created_at"] else None}
                    for s in db.daftar_supplier()])


@admin_bp.route("/api/admin/supplier/simpan", methods=["POST"])
@_admin
def supplier_simpan():
    def aksi():
        id_supplier = int(request.form.get("id_supplier") or 0) or None
        kode, nama = _teks("kode_supplier", maks=20).upper(), _teks("nama_supplier")
        peran = [p for p, f in zip(db.PERAN_SUPPLIER, ("is_customer", "is_angkutan")) if request.form.get(f)]
        if not peran:
            raise ValueError("Pilih minimal satu peran: customer / pengangkutan")
        if db.kode_supplier_dipakai(kode, kecuali=id_supplier):
            raise ValueError(f"Kode {kode} sudah dipakai")
        db.simpan_supplier(id_supplier, kode, nama, peran)
        _audit("SUPPLIER_UBAH" if id_supplier else "SUPPLIER_TAMBAH", kode, nama)
        return jsonify({"message": f"Supplier {nama} disimpan"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/supplier/<int:id_supplier>/aktif", methods=["POST"])
@_admin
def supplier_aktif(id_supplier):
    def aksi():
        aktif = _aktif_dari_form()
        db.set_aktif_supplier(id_supplier, aktif)
        _audit("SUPPLIER_AKTIF" if aktif else "SUPPLIER_NONAKTIF", str(id_supplier))
        return jsonify({"message": "Supplier " + ("diaktifkan" if aktif else "dinonaktifkan")})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/produk")
@_admin
def produk_daftar():
    return jsonify(db.daftar_produk())


@admin_bp.route("/api/admin/produk/simpan", methods=["POST"])
@_admin
def produk_simpan():
    def aksi():
        id_produk = int(request.form.get("id_produk") or 0) or None
        nama, kategori = _teks("nama_produk"), _teks("kategori").upper()
        if kategori not in db.KATEGORI_PRODUK:
            raise ValueError("Kategori tidak dikenal")
        if db.nama_produk_dipakai(nama, kecuali=id_produk):
            raise ValueError(f"Produk {nama} sudah ada")
        id_alur = _id_form("id_alur", {a["id_alur"] for a in alur.daftar_alur()}, "alur")
        db.simpan_produk(id_produk, nama, kategori, id_alur)
        _audit("PRODUK_UBAH" if id_produk else "PRODUK_TAMBAH", nama, kategori)
        return jsonify({"message": f"Produk {nama} disimpan"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/produk/<int:id_produk>/aktif", methods=["POST"])
@_admin
def produk_aktif(id_produk):
    def aksi():
        aktif = _aktif_dari_form()
        db.set_aktif_produk(id_produk, aktif)
        _audit("PRODUK_AKTIF" if aktif else "PRODUK_NONAKTIF", str(id_produk))
        return jsonify({"message": "Produk " + ("diaktifkan" if aktif else "dinonaktifkan")})
    return _jalankan(aksi)


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
        return jsonify({"message": f"Tiket {no_tiket} di-void" + ("" if ba else ". Berita acara bisa dilampirkan menyusul.")})
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
        return jsonify({"message": f"Berita acara tiket {no_tiket} dilampirkan"})
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
        return jsonify({"message": "Jadwal disimpan"})
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
            return jsonify({"message": "Tidak ada perubahan"})
        pengaturan.simpan(berubah, current_user.id, id_area)
        for kunci, teks in berubah.items():
            _audit("PENGATURAN_UBAH", f"{kunci} (area {id_area})" if id_area else kunci, f"{lama[kunci]} -> {teks}")
        return jsonify({"message": f"{len(berubah)} pengaturan disimpan dan langsung berlaku"})
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
    return jsonify({"message": "Kembali mengikuti nilai global" if id_area else "Dikembalikan ke nilai bawaan"})


# ===== PERANGKAT / KIOSK =====
@admin_bp.route("/api/admin/perangkat")
@_admin
def perangkat_daftar():
    terlihat, sekarang = kiosk.terakhir_terlihat(), time.time()
    hasil = []
    for p in kiosk.daftar():
        t = terlihat.get(p["id_pos"])
        hasil.append({**p, "created_at": p["created_at"].strftime("%Y-%m-%d") if p["created_at"] else None,
                      "terakhir_detik": int(sekarang - t["waktu"]) if t else None, "ip": t["ip"] if t else None,
                      "kamera_aktif": verif.kamera_aktif(p["id_pos"])})
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
        return jsonify({"message": f"Jembatan {kode} disimpan dan langsung berlaku"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/jembatan/<int:id_jembatan>/aktif", methods=["POST"])
@_admin
def jembatan_aktif(id_jembatan):
    def aksi():
        aktif = _aktif_dari_form()
        jembatan_db.set_aktif_jembatan(id_jembatan, aktif)
        _atur_pembaca()
        _audit("JEMBATAN_AKTIF" if aktif else "JEMBATAN_NONAKTIF", str(id_jembatan))
        return jsonify({"message": "Jembatan " + ("diaktifkan" if aktif else "dinonaktifkan")})
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


@admin_bp.route("/api/admin/perangkat/tambah", methods=["POST"])
@_admin
def perangkat_tambah():
    def aksi():
        id_pos, nama, lokasi = _id_pos_form(), _teks("nama"), _teks("lokasi", wajib=False)
        token = kiosk.tambah(id_pos, nama, lokasi)
        _audit("KIOSK_TAMBAH", id_pos, nama)
        return jsonify({"message": f"Pos {id_pos} ditambahkan", "id_pos": id_pos, "token": token})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/perangkat/ubah", methods=["POST"])
@_admin
def perangkat_ubah():
    def aksi():
        id_pos = _id_pos_form()
        kiosk.ubah(id_pos, _teks("nama"), _teks("lokasi", wajib=False))
        _audit("KIOSK_UBAH", id_pos)
        return jsonify({"message": f"Pos {id_pos} diperbarui"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/perangkat/ganti-token", methods=["POST"])
@_admin
def perangkat_ganti_token():
    def aksi():
        id_pos = _id_pos_form()
        token = kiosk.ganti_token(id_pos)
        _audit("KIOSK_GANTI_TOKEN", id_pos)
        log_keamanan("KIOSK_GANTI_TOKEN", f"pos={id_pos}")
        return jsonify({"message": f"Token pos {id_pos} diganti. Token lama langsung tidak berlaku.",
                        "id_pos": id_pos, "token": token})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/perangkat/aktif", methods=["POST"])
@_admin
def perangkat_aktif():
    def aksi():
        id_pos, aktif = _id_pos_form(), _aktif_dari_form()
        kiosk.set_aktif(id_pos, aktif)
        _audit("KIOSK_AKTIF" if aktif else "KIOSK_NONAKTIF", id_pos)
        return jsonify({"message": f"Pos {id_pos} {'diaktifkan' if aktif else 'dinonaktifkan'}"})
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
        "aplikasi": {"versi": _versi_git(), "python": platform.python_version(),
                     "berjalan_sejak": datetime.fromtimestamp(WAKTU_MULAI).strftime("%Y-%m-%d %H:%M"),
                     "uptime_jam": round((time.time() - WAKTU_MULAI) / 3600, 1),
                     "sesi_aktif": len(sesi_aktif.daftar(pengaturan.nilai("SESI_IDLE_MENIT") * 60))},
    })
