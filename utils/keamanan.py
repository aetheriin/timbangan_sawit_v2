"""Keamanan web: secret key, cookie sesi, header keamanan, sesi idle, token perangkat kiosk, log keamanan.

Semua dipasang dari app.py lewat pasang_keamanan(app). Rincian: docs/KEAMANAN_WEB.md."""
import hmac
import logging
import os
import time
from datetime import timedelta
from functools import wraps
from logging.handlers import RotatingFileHandler

from flask import request, session, jsonify, redirect, abort, g
from flask_login import current_user, logout_user

from extensions import BASE_DIR

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
IDLE_MENIT = int(os.getenv("SESI_IDLE_MENIT", "120"))            # logout otomatis bila tidak ada aktivitas
MAKS_JAM_SESI = int(os.getenv("SESI_MAKS_JAM", "12"))             # batas umur sesi (±1 shift)
# Request otomatis (polling) tidak dihitung sebagai aktivitas, supaya layar yang ditinggal tetap logout
PATH_POLLING = ("/api/timbang/status", "/api/status-verifikasi", "/api/kamera/status", "/health")


def pasang_cookie(app):
    app.config.update(
        SESSION_COOKIE_NAME="wb_sesi",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",     # aktifkan bila sudah HTTPS
        PERMANENT_SESSION_LIFETIME=timedelta(hours=MAKS_JAM_SESI),
        REMEMBER_COOKIE_DURATION=timedelta(seconds=0),
    )

    @app.context_processor
    def info_sesi():
        return {"sesi_idle_detik": IDLE_MENIT * 60}


def tandai_aktif():
    session["_aktif"] = int(time.time())


def pasang_sesi_idle(app):
    @app.before_request
    def cek_idle():
        if request.path.startswith("/static/") or not current_user.is_authenticated:
            return None
        sekarang, terakhir = int(time.time()), session.get("_aktif")
        if terakhir and sekarang - terakhir > IDLE_MENIT * 60:
            log_keamanan("SESI_IDLE_HABIS", f"tidak aktif {(sekarang - terakhir) // 60} menit")
            logout_user()
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify({"error": "Sesi berakhir karena tidak ada aktivitas. Silakan login ulang.",
                                "sesi_habis": True}), 401
            return redirect("/login?habis=1")
        if request.path not in PATH_POLLING:
            session["_aktif"] = sekarang
        return None


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
    token = os.getenv("KIOSK_TOKEN", "")
    kiriman = request.headers.get("X-Kiosk-Token", "")
    if token:
        return hmac.compare_digest(token, kiriman)
    # Tanpa KIOSK_TOKEN: hanya kiosk di PC yang sama dengan server yang diizinkan
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
    pasang_header_keamanan(app)
    pasang_blok_upload_publik(app)
