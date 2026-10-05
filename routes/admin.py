"""Menu Admin (super admin): hanya role ADMIN (dijaga juga oleh utils.keamanan.pasang_batas_admin).

Halaman  : /admin/<halaman>      (satu menu sidebar = satu halaman, tanpa tab)
API      : /api/admin/...        (JSON, semua aksi tercatat di admin_audit_logs)"""
import os
import platform
import re
import shutil
import time
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, redirect, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import role_required, BASE_DIR, UPLOAD_FOLDER
from utils import db_admin as db, pengaturan, login_guard, sesi_aktif, kiosk
from utils import verifikasi_state as verif
from utils.db_utils import cek_koneksi_db, get_password_hash
from utils.db_absensi import get_jadwal_kerja
from utils.keamanan import log_keamanan, baca_log_keamanan
from utils.serial_reader import baca_status_asli, PORT as PORT_TIMBANGAN

admin_bp = Blueprint("admin", __name__)
WAKTU_MULAI = time.time()

# key -> (judul, ikon Font Awesome, keterangan). Urutan = urutan menu sidebar.
HALAMAN = {
    "users": ("Kelola User", "fa-users", "Tambah akun, ubah role, reset password, aktif / nonaktif"),
    "sesi": ("Sesi Aktif", "fa-user-clock", "User yang sedang login, paksa keluar, buka kunci login"),
    "master": ("Supplier & Produk", "fa-boxes-stacked", "Master data supplier / buyer dan produk"),
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
    return login_required(role_required("ADMIN")(f))


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
                           role_list=db.ROLE_VALID, tipe_supplier=db.TIPE_SUPPLIER,
                           kategori_produk=db.KATEGORI_PRODUK, password_min=PASSWORD_MIN)


# ===== KELOLA USER =====
@admin_bp.route("/api/admin/users")
@_admin
def users_daftar():
    return jsonify([{**u, "last_login": u["last_login"].strftime("%Y-%m-%d %H:%M") if u["last_login"] else None,
                     "created_at": u["created_at"].strftime("%Y-%m-%d") if u["created_at"] else None,
                     "is_saya": u["id_user"] == current_user.id}
                    for u in db.daftar_user()])


def _role_form():
    role = _teks("role").upper()
    if role not in db.ROLE_VALID:
        raise ValueError("Role tidak dikenal")
    return role


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
        nama, role, pw = _teks("nama"), _role_form(), _password_form()
        db.tambah_user(username, nama, role, generate_password_hash(pw))
        _audit("USER_TAMBAH", username, f"role {role}")
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
        nama, role = _teks("nama"), _role_form()
        if u["role"] == "ADMIN" and role != "ADMIN":
            if id_user == current_user.id:
                raise ValueError("Tidak bisa mengubah role akun sendiri")
            if db.jumlah_admin_aktif(kecuali=id_user) == 0:
                raise ValueError("Minimal harus ada 1 admin aktif")
        db.ubah_user(id_user, nama, role)
        detail = f"role {u['role']} -> {role}" if u["role"] != role else "nama diubah"
        _audit("USER_UBAH", u["username"], detail)
        if u["role"] != role:
            sesi_aktif.hapus_user(id_user, "ROLE_DIUBAH")
        return jsonify({"message": f"User {u['username']} diperbarui" +
                        (" (sesi lamanya diakhiri, login ulang dengan role baru)" if u["role"] != role else "")})
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
            if u["role"] == "ADMIN" and db.jumlah_admin_aktif(kecuali=id_user) == 0:
                raise ValueError("Minimal harus ada 1 admin aktif")
        db.set_aktif_user(id_user, aktif)
        sesi_aktif.hapus_user(id_user, "NONAKTIF")
        _audit("USER_AKTIF" if aktif else "USER_NONAKTIF", u["username"])
        return jsonify({"message": f"User {u['username']} {'diaktifkan' if aktif else 'dinonaktifkan'}"})
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
        kode, nama, tipe = _teks("kode_supplier", maks=20).upper(), _teks("nama_supplier"), _teks("tipe").upper()
        if tipe not in db.TIPE_SUPPLIER:
            raise ValueError("Tipe tidak dikenal")
        if db.kode_supplier_dipakai(kode, kecuali=id_supplier):
            raise ValueError(f"Kode {kode} sudah dipakai")
        db.simpan_supplier(id_supplier, kode, nama, tipe)
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
        db.simpan_produk(id_produk, nama, kategori)
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
        db.void_tiket(no_tiket, alasan, current_user.id)
        _audit("TIKET_VOID", no_tiket, alasan)
        return jsonify({"message": f"Tiket {no_tiket} di-void"})
    return _jalankan(aksi)


# ===== JADWAL KERJA =====
def _jam_teks(j):
    return j.strftime("%H:%M") if hasattr(j, "strftime") else (str(j)[:5] if j else None)


@admin_bp.route("/api/admin/jadwal")
@_admin
def jadwal_daftar():
    return jsonify([{"hari": j["hari"], "nama_hari": j["nama_hari"], "is_libur": bool(j["is_libur"]),
                     "jam_masuk": _jam_teks(j["jam_masuk"]), "jam_pulang": _jam_teks(j["jam_pulang"]),
                     "toleransi_menit": j["toleransi_menit"]} for j in get_jadwal_kerja()])


@admin_bp.route("/api/admin/jadwal/simpan", methods=["POST"])
@_admin
def jadwal_simpan():
    def aksi():
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
        db.ubah_jadwal(hari, libur, masuk, pulang, toleransi)
        _audit("JADWAL_UBAH", str(hari), "libur" if libur else f"{masuk}-{pulang}, toleransi {toleransi} mnt")
        return jsonify({"message": "Jadwal disimpan"})
    return _jalankan(aksi)


# ===== PENGATURAN SITE =====
@admin_bp.route("/api/admin/pengaturan")
@_admin
def pengaturan_daftar():
    return jsonify(pengaturan.semua())


@admin_bp.route("/api/admin/pengaturan/simpan", methods=["POST"])
@_admin
def pengaturan_simpan():
    def aksi():
        # Hanya yang nilainya berubah yang disimpan, supaya sisanya tetap mengikuti .env / bawaan
        lama = {p["kunci"]: p["nilai"] for p in pengaturan.semua()}
        masuk = {k: pengaturan.validasi(k, v) for k, v in request.form.items() if k in pengaturan.DEFINISI}
        berubah = {k: v for k, v in masuk.items() if pengaturan.validasi(k, lama[k]) != v}
        if not berubah:
            return jsonify({"message": "Tidak ada perubahan"})
        pengaturan.simpan(berubah, current_user.id)
        for kunci, teks in berubah.items():
            _audit("PENGATURAN_UBAH", kunci, f"{lama[kunci]} -> {teks}")
        return jsonify({"message": f"{len(berubah)} pengaturan disimpan dan langsung berlaku"})
    return _jalankan(aksi)


@admin_bp.route("/api/admin/pengaturan/bawaan", methods=["POST"])
@_admin
def pengaturan_bawaan():
    kunci = request.form.get("kunci") or ""
    if kunci not in pengaturan.DEFINISI:
        return jsonify({"error": "Pengaturan tidak dikenal"}), 400
    pengaturan.kembalikan_bawaan(kunci)
    _audit("PENGATURAN_BAWAAN", kunci)
    return jsonify({"message": "Dikembalikan ke nilai bawaan"})


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
    timbang = baca_status_asli()
    return jsonify({"perangkat": hasil, "token_env": bool(os.getenv("KIOSK_TOKEN")),
                    "timbangan": {"terhubung": bool(timbang.get("terhubung")), "berat": timbang.get("berat"),
                                  "stabil": bool(timbang.get("stabil")), "port": PORT_TIMBANGAN}})


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
    timbang = baca_status_asli()
    return jsonify({
        "database": {"ok": db_ok, "latensi_ms": latensi, **info_db},
        "disk": {"total_gb": round(disk.total / 1073741824, 1), "sisa_gb": round(disk.free / 1073741824, 1),
                 "terpakai_persen": round(disk.used * 100 / disk.total, 1)},
        "upload": {"ukuran_mb": upload_mb, "lebih": upload_terpotong},
        "timbangan": {"terhubung": bool(timbang.get("terhubung"))},
        "aplikasi": {"versi": _versi_git(), "python": platform.python_version(),
                     "berjalan_sejak": datetime.fromtimestamp(WAKTU_MULAI).strftime("%Y-%m-%d %H:%M"),
                     "uptime_jam": round((time.time() - WAKTU_MULAI) / 3600, 1),
                     "sesi_aktif": len(sesi_aktif.daftar(pengaturan.nilai("SESI_IDLE_MENIT") * 60))},
    })
