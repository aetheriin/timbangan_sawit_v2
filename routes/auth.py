from flask import Blueprint, request, render_template, redirect, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from utils.auth import User
from utils.db_utils import get_user_by_username, catat_login_terakhir, get_password_hash, ganti_password_sendiri
from utils.keamanan import log_keamanan, mulai_sesi, password_wajib_diganti
from utils import sesi_aktif
from utils.login_guard import sisa_kunci, catat_gagal, catat_berhasil

auth_bp = Blueprint('auth', __name__)

TAB_DEFAULT = {'SECURITY': 'security', 'OPERATOR_TIMBANG': 'timbangan',
               'SORTASI': 'sortasi', 'LAB': 'lab', 'HO': 'security'}


def _halaman_awal(role):
    if role == 'ADMIN':                 # super admin hanya punya halaman Admin
        return "/admin"
    return f"/weighbridge?tab={TAB_DEFAULT.get(role, 'security')}"


@auth_bp.route("/")
def index():
    return redirect(_halaman_awal(current_user.role) if current_user.is_authenticated else "/login")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # Sudah login (mis. tombol Back ke halaman login) -> kembali ke halaman kerja, form login tidak ditampilkan
    if current_user.is_authenticated:
        return redirect(_halaman_awal(current_user.role))

    info = "Sesi Anda berakhir karena tidak ada aktivitas. Silakan login ulang." if request.args.get("habis") else None
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
    mulai_sesi(user, row.sesi_versi or 0)
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
    sesi_aktif.hapus(session.get("_sid"))
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
    """Ganti password sendiri. Wajib bila kedaluwarsa (Admin > Pengaturan Site) atau baru direset admin."""
    alasan = session.get("_wajib_ganti_pw")
    tampil = lambda error=None, kode=200: (render_template("auth/ganti_password.html", alasan=alasan, error=error,
                                                           wajib=bool(alasan), password_min=PASSWORD_MIN), kode)
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
    session.pop("_wajib_ganti_pw", None)
    log_keamanan("GANTI_PASSWORD", f"username={current_user.username}")
    return redirect(_halaman_awal(current_user.role))

