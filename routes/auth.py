from flask import Blueprint, request, render_template, redirect, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from utils.auth import User
from utils.db_utils import (get_user_by_username, catat_login_terakhir, get_password_hash, ganti_password_sendiri,
                            naikkan_sesi_versi)
from utils.keamanan import log_keamanan, mulai_sesi, password_wajib_diganti
from utils import sesi_aktif, pengaturan
from utils.login_guard import sisa_kunci, catat_gagal, catat_berhasil

auth_bp = Blueprint('auth', __name__)

TAB_DEFAULT = {'SECURITY': 'security', 'OPERATOR_TIMBANG': 'timbangan',
               'SORTASI': 'sortasi', 'LAB': 'lab'}


PESAN_KELUAR = {
    "IDLE": "Sesi Anda berakhir karena tidak ada aktivitas. Silakan login ulang.",
    "UMUR_MAKS": "Sesi Anda sudah terlalu lama. Silakan login ulang.",
    "PERANGKAT_LAIN": "Akun Anda login di perangkat lain, jadi sesi di perangkat ini diakhiri.",
    "PAKSA_KELUAR": "Sesi Anda diakhiri oleh admin.",
    "RESET_PASSWORD": "Password Anda direset admin. Silakan login dengan password baru.",
    "ROLE_DIUBAH": "Role Anda diubah admin. Silakan login ulang.",
    "NONAKTIF": "Akun Anda dinonaktifkan admin.",
    "GANTI_PASSWORD": "Password akun Anda diganti dari perangkat lain. Silakan login ulang.",
}


def _halaman_awal(role):
    if role == 'ADMIN':                 # super admin hanya punya halaman Admin
        return "/admin"
    if role == 'HO':
        return "/dashboard"
    return f"/weighbridge?tab={TAB_DEFAULT.get(role, 'security')}"


@auth_bp.route("/")
def index():
    return redirect(_halaman_awal(current_user.role) if current_user.is_authenticated else "/login")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Sudah login (mis. tombol Back ke halaman login) -> kembali ke halaman kerja, form login tidak ditampilkan
    if current_user.is_authenticated:
        return redirect(_halaman_awal(current_user.role))

    kode = session.pop("_keluar", None) or request.args.get("keluar") or ("IDLE" if request.args.get("habis") else None)
    info = PESAN_KELUAR.get(kode, "Sesi Anda berakhir. Silakan login ulang." if kode else None)
    if request.method == "GET":
        return render_template("auth/login.html", error=None, info=info)

    username = request.form.get("username", "").strip()
    ip = request.remote_addr
    tunggu = sisa_kunci(username, ip)
    if tunggu:
        log_keamanan("LOGIN_TERKUNCI", f"username={username}")
        return render_template("auth/login.html", info=None,
                               error=f"Terlalu banyak percobaan gagal. Coba lagi dalam {tunggu // 60 + 1} menit."), 429

    row = get_user_by_username(username)
    if row is None or not check_password_hash(row.password, request.form.get("password", "")):
        terkunci = catat_gagal(username, ip)
        log_keamanan("LOGIN_GAGAL", f"username={username}" + (" -> DIKUNCI" if terkunci else ""))
        return render_template("auth/login.html", info=None, error="Username atau password salah"), 401

    catat_berhasil(username, ip)
    session.clear()                 # cegah session fixation: sesi lama dibuang, dibuat baru
    session.permanent = True
    user = User(row.id_user, row.username, row.nama, row.role)
    login_user(user)
    versi = row.sesi_versi or 0
    if pengaturan.nilai("SATU_PERANGKAT"):      # 1 user 1 perangkat: sesi di perangkat lain dicabut
        versi = naikkan_sesi_versi(row.id_user)
    sid = mulai_sesi(user, versi)
    if pengaturan.nilai("SATU_PERANGKAT") and sesi_aktif.hapus_user(row.id_user, "PERANGKAT_LAIN", kecuali_sid=sid):
        log_keamanan("SESI_PERANGKAT_LAIN", f"username={row.username} sesi lama diakhiri")
    catat_login_terakhir(row.id_user)
    alasan = password_wajib_diganti(row.password_changed_at)
    if alasan:                                  # kedaluwarsa / baru direset: hanya halaman ganti password yang terbuka
        session["_wajib_ganti_pw"] = alasan
        return redirect("/ganti-password")
    log_keamanan("LOGIN", f"username={row.username} role={row.role}")
    return redirect(_halaman_awal(row.role))


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    log_keamanan("LOGOUT")
    sesi_aktif.hapus(session.get("_sid"), "LOGOUT")
    logout_user()
    session.clear()
    return redirect("/login")


@auth_bp.route("/api/sesi/perpanjang", methods=["POST"])
@login_required
def sesi_perpanjang():
    """Dipanggil tombol "Tetap masuk" pada peringatan sesi hampir habis (aktivitas dicatat before_request)."""
    return jsonify({"message": "Sesi diperpanjang"})


PASSWORD_MIN = 8


@auth_bp.route("/ganti-password", methods=["GET", "POST"])
@login_required
def ganti_password():
    """Hanya saat login dengan password kedaluwarsa (Admin > Pengaturan Site) / baru direset admin.
    Ganti password sebelum kedaluwarsa lewat Admin (Kelola User > Reset Password)."""
    alasan = session.get("_wajib_ganti_pw")
    if not alasan:
        return redirect(_halaman_awal(current_user.role))
    tampil = lambda error=None, kode=200: (render_template("auth/ganti_password.html", alasan=alasan, error=error,
                                                           password_min=PASSWORD_MIN), kode)
    if request.method == "GET":
        return tampil()
    lama, baru = request.form.get("password_lama", ""), request.form.get("password_baru", "")
    hash_lama = get_password_hash(current_user.id)
    if not hash_lama or not check_password_hash(hash_lama, lama):
        log_keamanan("GANTI_PASSWORD_GAGAL", "password lama salah")
        return tampil("Password lama salah", 400)
    if len(baru) < PASSWORD_MIN:
        return tampil(f"Password baru minimal {PASSWORD_MIN} karakter", 400)
    if baru != request.form.get("password_ulang", ""):
        return tampil("Ulangi password baru tidak sama", 400)
    if check_password_hash(hash_lama, baru):
        return tampil("Password baru tidak boleh sama dengan password lama", 400)
    session["_versi"] = ganti_password_sendiri(current_user.id, generate_password_hash(baru))
    sesi_aktif.hapus_user(current_user.id, "GANTI_PASSWORD", kecuali_sid=session.get("_sid"))
    session.pop("_wajib_ganti_pw", None)
    log_keamanan("GANTI_PASSWORD", f"username={current_user.username}")
    return redirect(_halaman_awal(current_user.role))

