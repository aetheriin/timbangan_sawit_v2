"""Pengaturan web app: cache statis, header no-store, kompresi, penanganan error, log request lambat."""
import logging
import os
import time
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
        if not request.path.startswith("/static/"):
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
    @app.errorhandler(HTTPException)
    def http_error(e):
        pesan = PESAN_ERROR.get(e.code, e.description)
        if _minta_json():
            return jsonify({"error": pesan}), e.code
        return render_template("error.html", kode=e.code, pesan=pesan), e.code

    @app.errorhandler(Exception)
    def server_error(e):
        log.exception("Error tak tertangani di %s %s", request.method, request.path)
        if _minta_json():
            return jsonify({"error": PESAN_ERROR[500]}), 500
        return render_template("error.html", kode=500, pesan=PESAN_ERROR[500]), 500


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
                log.warning("LAMBAT %.0f ms  %s %s -> %s", ms, request.method, request.full_path.rstrip("?"),
                            resp.status_code)
        return resp


def pasang_semua(app):
    pasang_cache_static(app)
    pasang_header_cache(app)
    pasang_kompresi(app)
    pasang_error_handler(app)
    pasang_log_lambat(app)
