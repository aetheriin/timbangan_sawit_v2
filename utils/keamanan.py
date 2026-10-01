"""Keamanan web: secret key, cookie sesi, header keamanan, sesi idle, token perangkat kiosk, log keamanan.

Semua dipasang dari app.py lewat pasang_keamanan(app). Rincian: docs/KEAMANAN_WEB.md."""
import hmac
import logging
import os
import re
import time
from datetime import timedelta
from functools import wraps
from logging.handlers import RotatingFileHandler

from flask import request, session, jsonify, redirect, abort, g
from flask_login import current_user, logout_user

from extensions import BASE_DIR
from utils import pengaturan, sesi_aktif, kiosk

# ===== LOG KEAMANAN (logs/keamanan.log) =====
_log = logging.getLogger("keamanan")
if not _log.handlers:
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    _h = RotatingFileHandler(os.path.join(BASE_DIR, "logs", "keamanan.log"),
                             maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)


def log_keamanan(kejadian, detail=""):
    """Catat kejadian keamanan: user, IP, kejadian, detail. Tidak pernah memutus proses."""
    try:
        user = current_user.username if current_user and current_user.is_authenticated else "-"
    except Exception:       # noqa: BLE001 - di luar request context
        user = "-"
    ip = request.remote_addr if request else "-"
    _log.warning("%-20s user=%s ip=%s %s", kejadian, user, ip, detail)


_POLA_LOG = re.compile(r"^(\S+ \S+?)(?:,\d+)? (\S+)\s+user=(\S+) ip=(\S+) ?(.*)$")


def baca_log_keamanan(batas=500, cari="", jenis=""):
    """Baris terbaru logs/keamanan.log (Admin > Log Keamanan), terbaru di atas. Hanya ekor file yang dibaca."""
    path = os.path.join(BASE_DIR, "logs", "keamanan.log")
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 512 * 1024))
            baris = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    hasil, cari = [], cari.lower()
    for teks in reversed(baris):
        m = _POLA_LOG.match(teks)
        if not m:
            continue
        waktu, kejadian, user, ip, detail = m.groups()
        if jenis and kejadian != jenis:
            continue
        if cari and cari not in teks.lower():
            continue
        hasil.append({"waktu": waktu, "kejadian": kejadian, "user": user, "ip": ip, "detail": detail})
        if len(hasil) >= batas:
            break
    return hasil


# ===== SECRET KEY =====
CONTOH_SECRET = {"", "isi_dengan_random_string_panjang", "isi_dengan_random_string_panjang_lain", "x", "secret"}


def cek_secret(app):
    """Tolak start bila SECRET_KEY / HASH_SECRET_KEY kosong, masih contoh .env.example, atau terlalu pendek."""
    masalah = []
    for nama in ("SECRET_KEY", "HASH_SECRET_KEY"):
        nilai = os.getenv(nama, "")
        if nilai in CONTOH_SECRET or len(nilai) < 32:
            masalah.append(nama)
    if masalah:
        raise RuntimeError(
            f"{', '.join(masalah)} di .env kosong / masih contoh / kurang dari 32 karakter.\n"
            "Buat nilai acak dengan:  python -c \"import secrets; print(secrets.token_hex(32))\"")
    app.secret_key = os.getenv("SECRET_KEY")


# ===== COOKIE & SESI =====
# Lama idle & umur sesi diatur di Admin > Pengaturan Site (SESI_IDLE_MENIT, SESI_MAKS_JAM).
# Cookie sendiri dibatasi 24 jam; batas yang berlaku dicek di cek_idle().
BATAS_COOKIE_JAM = 24
# Request otomatis (polling) tidak dihitung sebagai aktivitas, supaya layar yang ditinggal tetap logout
PATH_POLLING = ("/api/timbang/status", "/api/status-verifikasi", "/api/kamera/status", "/health")


def pasang_cookie(app):
    app.config.update(
        SESSION_COOKIE_NAME="wb_sesi",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",     # aktifkan bila sudah HTTPS
        PERMANENT_SESSION_LIFETIME=timedelta(hours=BATAS_COOKIE_JAM),
        REMEMBER_COOKIE_DURATION=timedelta(seconds=0),
    )

    @app.context_processor
    def info_sesi():
        return {"sesi_idle_detik": pengaturan.nilai("SESI_IDLE_MENIT") * 60}


def mulai_sesi(user, sesi_versi=0):
    """Dipanggil tepat setelah login_user(): tanda waktu, versi sesi (paksa keluar), daftar sesi aktif."""
    sekarang = int(time.time())
    session.update(_aktif=sekarang, _mulai=sekarang, _versi=sesi_versi, _sid=sesi_aktif.sid_baru())
    sesi_aktif.catat(session["_sid"], user, request.remote_addr, request.user_agent.string)


def _akhiri_sesi(kejadian, detail, alasan):
    log_keamanan(kejadian, detail)
    sesi_aktif.hapus(session.get("_sid"))
    logout_user()
    session.clear()
    if request.path.startswith("/api/"):
        return jsonify({"error": alasan, "sesi_habis": True}), 401
    return redirect("/login?habis=1")


def pasang_sesi_idle(app):
    @app.before_request
    def cek_idle():
        if request.path.startswith("/static/") or not current_user.is_authenticated:
            return None
        sekarang, terakhir = int(time.time()), session.get("_aktif")
        if terakhir and sekarang - terakhir > pengaturan.nilai("SESI_IDLE_MENIT") * 60:
            return _akhiri_sesi("SESI_IDLE_HABIS", f"tidak aktif {(sekarang - terakhir) // 60} menit",
                                "Sesi berakhir karena tidak ada aktivitas. Silakan login ulang.")
        mulai = session.get("_mulai")
        if mulai and sekarang - mulai > pengaturan.nilai("SESI_MAKS_JAM") * 3600:
            return _akhiri_sesi("SESI_MAKS_HABIS", f"login {(sekarang - mulai) // 3600} jam lalu",
                                "Sesi sudah terlalu lama. Silakan login ulang.")
        aktif = request.path not in PATH_POLLING
        if aktif:
            session["_aktif"] = sekarang
        if "_sid" not in session:              # sesi dari sebelum fitur ini ada
            session["_sid"] = sesi_aktif.sid_baru()
        sesi_aktif.catat(session["_sid"], current_user, request.remote_addr, request.user_agent.string,
                         login=session.get("_mulai"), aktif=aktif)
        return None


# ===== AREA ADMIN =====
# ADMIN (super admin) hanya mengelola sistem: halaman lain tidak terbuka untuknya,
# dan halaman admin hanya untuk ADMIN.
PATH_UMUM = ("/static/", "/login", "/logout", "/api/sesi/perpanjang", "/health")


def _area_admin(path):
    return path == "/admin" or path.startswith(("/admin/", "/api/admin/"))


def pasang_batas_admin(app):
    @app.before_request
    def batas_admin():
        if not current_user.is_authenticated or request.path.startswith(PATH_UMUM) or request.path == "/":
            return None
        admin = current_user.role == "ADMIN"
        if admin == _area_admin(request.path):
            return None
        log_keamanan("AKSES_DITOLAK", f"role {current_user.role} ke {request.path}")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Akses ditolak untuk role Anda"}), 403
        if admin:
            return redirect("/admin")
        abort(403)


# ===== HEADER KEAMANAN =====
CSP = ("default-src 'self'; "
       # Script hanya dari file .js server sendiri: onclick="..." / <script> inline ditolak browser.
       # Tombol memanggil fungsi lewat data-on-click (static/js/aksi.js). Style inline masih diizinkan
       # (atribut style="..." & library kamera), risikonya jauh lebih kecil daripada script.
       "script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self'; connect-src 'self'; "
       "worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")


def pasang_header_keamanan(app):
    @app.after_request
    def header(resp):
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=(), payment=(), usb=()"
        resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if app.config.get("SESSION_COOKIE_SECURE"):
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        resp.headers.pop("Server", None)
        return resp


def pasang_blok_upload_publik(app):
    """File upload lama di static/uploads tidak boleh diakses publik; gunakan /berkas/... (wajib login)."""
    @app.before_request
    def blok():
        if request.path.startswith("/static/uploads/"):
            abort(404)


# ===== TOKEN PERANGKAT (kiosk kamera) =====
def _token_valid():
    kiriman = request.headers.get("X-Kiosk-Token", "")
    # 1) Token per pos dari Admin > Perangkat / Kiosk
    if kiosk.token_cocok(id_pos(), kiriman):
        return True
    # 2) Token bersama di .env (cara lama)
    token = os.getenv("KIOSK_TOKEN", "")
    if token:
        return hmac.compare_digest(token, kiriman)
    # 3) Tanpa token sama sekali: hanya kiosk di PC yang sama dengan server yang diizinkan
    return request.remote_addr in ("127.0.0.1", "::1")


def perangkat_atau_login(f):
    """Endpoint kiosk: boleh dipanggil user yang login ATAU kiosk yang membawa X-Kiosk-Token benar."""
    @wraps(f)
    def wrapped(*args, **kwargs):
        if current_user.is_authenticated:
            g.dari_kiosk = False
            return f(*args, **kwargs)
        if _token_valid():
            g.dari_kiosk = True
            kiosk.catat_terlihat(id_pos(), request.remote_addr)
            return f(*args, **kwargs)
        log_keamanan("KIOSK_DITOLAK", request.path)
        return jsonify({"error": "Perangkat tidak dikenal"}), 401
    return wrapped


def id_pos():
    """Pos / kiosk kamera. Kiosk mengirim X-Kiosk-Id; browser memakai pos default (satu kiosk per server)."""
    return (request.headers.get("X-Kiosk-Id") or os.getenv("POS_DEFAULT", "UTAMA"))[:30]


def pasang_keamanan(app):
    cek_secret(app)
    pasang_cookie(app)
    pasang_sesi_idle(app)
    pasang_batas_admin(app)
    pasang_header_keamanan(app)
    pasang_blok_upload_publik(app)
