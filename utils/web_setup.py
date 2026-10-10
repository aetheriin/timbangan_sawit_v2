"""Pengaturan web app: cache statis, header no-store, kompresi, penanganan error, log request lambat."""
import logging
import os
import secrets
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from flask import request, jsonify, render_template, g
from werkzeug.exceptions import HTTPException

log = logging.getLogger("weighbridge")

SATU_TAHUN = 60 * 60 * 24 * 365
BATAS_LAMBAT_MS = int(os.getenv("LOG_REQUEST_LAMBAT_MS", "1000"))

PESAN_ERROR = {
    400: "Permintaan tidak valid.",
    401: "Sesi Anda berakhir. Silakan login ulang.",
    403: "Anda tidak punya akses untuk tindakan ini.",
    404: "Halaman atau data tidak ditemukan.",
    405: "Metode tidak diizinkan.",
    413: "Ukuran file terlalu besar (maks 16 MB).",
    500: "Terjadi kesalahan di server. Coba lagi atau hubungi admin.",
}


def _minta_json():
    return request.path.startswith("/api/") or request.headers.get("X-Requested-With") == "fetch"


def pasang_cache_static(app):
    """File statis di-cache 1 tahun; URL diberi ?v=<waktu ubah file> sehingga update langsung terbaca."""
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = SATU_TAHUN

    @app.url_defaults
    def versi_static(endpoint, values):
        if endpoint != "static" or "filename" not in values:
            return
        try:
            values["v"] = int(os.stat(os.path.join(app.static_folder, values["filename"])).st_mtime)
        except OSError:
            pass


def pasang_header_cache(app):
    """Halaman & API berisi data operasional: jangan disimpan browser / proxy."""
    @app.after_request
    def header_cache(resp):
        if not request.path.startswith(("/static/", "/berkas/")):
            resp.headers["Cache-Control"] = "no-store"
        return resp


def pasang_kompresi(app):
    try:
        from flask_compress import Compress
    except ImportError:
        log.warning("flask-compress belum terpasang, respons tidak dikompres (pip install -r requirements.txt)")
        return
    app.config.setdefault("COMPRESS_MIMETYPES", ["text/html", "text/css", "application/javascript",
                                                 "text/javascript", "application/json", "image/svg+xml"])
    app.config.setdefault("COMPRESS_MIN_SIZE", 1024)
    Compress(app)


def pasang_error_handler(app):
    """API -> JSON { error }, halaman -> templates/error.html. Tidak ada lagi halaman error bawaan / JSON mentah."""
    from utils.face_cache import ServerSibuk

    @app.errorhandler(ServerSibuk)
    def server_sibuk(e):
        return jsonify({"error": "Server sedang memproses wajah lain. Coba lagi beberapa detik."}), 503

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def csrf_gagal(e):
        from utils.keamanan import log_keamanan
        log_keamanan("CSRF_GAGAL", request.path)
        pesan = "Sesi form kedaluwarsa. Muat ulang halaman (F5) lalu coba lagi."
        if _minta_json():
            return jsonify({"error": pesan}), 400
        return render_template("error.html", kode=400, pesan=pesan), 400
    @app.errorhandler(HTTPException)
    def http_error(e):
        pesan = PESAN_ERROR.get(e.code, e.description)
        if _minta_json():
            return jsonify({"error": pesan}), e.code
        return render_template("error.html", kode=e.code, pesan=pesan), e.code

    @app.errorhandler(Exception)
    def server_error(e):
        # Kode rujukan unik: operator melapor kode ini, IT mencarinya di logs/error_app.log (traceback lengkap)
        kode = kode_error()
        log.exception("%s Error tak tertangani di %s %s (user=%s, ip=%s)", kode, request.method, request.path,
                      _username(), request.remote_addr)
        pesan = f"Terjadi kesalahan sistem. Kode error: {kode}. Catat kode ini & No. Tiket, lalu hubungi IT site."
        if _minta_json():
            return jsonify({"error": pesan, "kode_error": kode}), 500
        return render_template("error.html", kode=500, pesan=pesan), 500


def kode_error():
    """Mis. ERR-1010-1415-A7F3 (bulan-tanggal, jam-menit, acak) supaya mudah dicari di log."""
    return f"ERR-{datetime.now():%m%d-%H%M}-{secrets.token_hex(2).upper()}"


def _username():
    try:
        from flask_login import current_user
        return current_user.username if current_user.is_authenticated else "-"
    except Exception:       # noqa: BLE001 - jangan sampai pencatatan error membuat error baru
        return "-"


def pasang_log_error(app):
    """Semua log WARNING ke atas (termasuk traceback error) ke logs/error_app.log, diputar 5 MB x 10 file."""
    from extensions import BASE_DIR
    akar = logging.getLogger()
    if any(getattr(h, "_error_app", False) for h in akar.handlers):
        return
    os.makedirs(os.path.join(BASE_DIR, "logs"), exist_ok=True)
    h = RotatingFileHandler(os.path.join(BASE_DIR, "logs", "error_app.log"),
                            maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8")
    h._error_app = True
    h.setLevel(logging.WARNING)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    akar.addHandler(h)


def pasang_log_lambat(app):
    """Catat request yang lebih lambat dari BATAS_LAMBAT_MS (default 1 detik) ke log."""
    @app.before_request
    def mulai_timer():
        g._mulai = time.perf_counter()

    @app.after_request
    def catat(resp):
        mulai = getattr(g, "_mulai", None)
        if mulai is not None and not request.path.startswith("/static/"):
            ms = (time.perf_counter() - mulai) * 1000
            resp.headers["Server-Timing"] = f"app;dur={ms:.0f}"
            if ms >= BATAS_LAMBAT_MS:
                # db: jumlah koneksi dibuka & total waktu membuka koneksi. Buka koneksi lama = jaringan / login SQL lambat;
                # buka cepat tapi total lama = query lambat / tertahan lock di SQL Server (cek: EXEC sp_who2 di SSMS).
                log.warning("LAMBAT %.0f ms  %s %s -> %s  (db: %d koneksi, buka %.0f ms)", ms, request.method,
                            request.full_path.rstrip("?"), resp.status_code,
                            getattr(g, "db_koneksi", 0), getattr(g, "db_buka_ms", 0))
        return resp


def pasang_semua(app):
    pasang_log_error(app)
    pasang_cache_static(app)
    pasang_header_cache(app)
    pasang_kompresi(app)
    pasang_error_handler(app)
    pasang_log_lambat(app)
