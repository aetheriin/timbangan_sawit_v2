import logging
import os
from flask import Flask, jsonify, request, redirect, session
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from extensions import login_manager
from utils.auth import User
from utils.db_utils import get_user_by_id
from utils.serial_reader import mulai_pembacaan_serial
from utils.maintenance import mulai_pembersihan_berkala, pindahkan_upload_lama
from utils.web_setup import pasang_semua
from utils.keamanan import pasang_keamanan, log_keamanan
from utils import sesi_aktif
from routes.auth import auth_bp
from routes.main import main_bp
from routes.security import security_bp
from routes.timbangan import timbangan_bp
from routes.sortasi import sortasi_bp
from routes.lab import lab_bp
from routes.kendaraan import kendaraan_bp
from routes.personel import personel_bp
from routes.blacklist import blacklist_bp
from routes.absensi import absensi_bp
from routes.audit import audit_bp
from routes.sistem import sistem_bp
from routes.admin import admin_bp
from routes.kontrak import kontrak_bp
from routes.master import master_bp
from routes.dashboard import dashboard_bp

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024       # batas upload (foto, surat, frame absensi)
if os.getenv("BEHIND_PROXY", "0") == "1":                # di belakang reverse proxy HTTPS (Caddy / IIS)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
pasang_keamanan(app)                                      # secret key, cookie, sesi idle, header keamanan
csrf = CSRFProtect(app)                                   # token CSRF wajib untuk semua POST dari browser
login_manager.init_app(app)
pasang_semua(app)

@login_manager.user_loader
def load_user(user_id):
    row = get_user_by_id(user_id)
    if row is None:
        return None
    # Admin menekan "Paksa keluar" / reset password / ubah role -> sesi_versi naik, sesi lama ditolak
    if (row.sesi_versi or 0) != session.get("_versi", 0):
        log_keamanan("SESI_DICABUT", f"username={row.username}")
        return None
    return User.dari_row(row)

@login_manager.unauthorized_handler
def belum_login():
    # Sesi dicabut (perangkat lain / paksa keluar / reset password): alasannya ditampilkan di halaman login
    sid = session.get("_sid")
    if sid:
        kode = sesi_aktif.alasan_berakhir(sid) or "DICABUT"
        sesi_aktif.hapus(sid, kode)
        session.clear()
        session["_keluar"] = kode
    # API dipanggil lewat fetch -> JSON 401 (ditangani api.js), halaman -> redirect ke login
    if request.path.startswith("/api/"):
        log_keamanan("TANPA_LOGIN", request.path)
        return jsonify({"error": "Sesi Anda berakhir. Silakan login ulang."}), 401
    return redirect("/login")

for bp in (auth_bp, main_bp, security_bp, timbangan_bp, sortasi_bp, lab_bp, kendaraan_bp,
           personel_bp, blacklist_bp, absensi_bp, audit_bp, sistem_bp, admin_bp, kontrak_bp, dashboard_bp, master_bp):
    app.register_blueprint(bp)

# Endpoint yang dipanggil kiosk kamera (tanpa sesi browser) dilindungi token perangkat, bukan CSRF
for endpoint in ("security.verifikasi_wajah", "security.kamera_batal"):
    csrf.exempt(app.view_functions[endpoint])


def jalankan_layanan_latar():
    """Serial timbangan & pembersihan uploads. Dipanggil sekali oleh proses yang melayani request."""
    pindahkan_upload_lama()
    mulai_pembacaan_serial()
    mulai_pembersihan_berkala()


if __name__ == "__main__":
    # Mode development. Untuk dipakai di site gunakan: python serve.py (waitress, tanpa debug)
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
    # Mode debug menjalankan app 2x (proses induk + anak). Port COM hanya bisa dibuka 1 proses,
    # jadi layanan latar dinyalakan hanya di proses yang benar-benar melayani request.
    if not DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        jalankan_layanan_latar()
    # Development hanya bisa dibuka dari PC ini. Untuk PC lain di LAN gunakan serve.py
    app.run(debug=DEBUG, host="127.0.0.1", port=int(os.getenv("PORT", "5000")), threaded=True)
