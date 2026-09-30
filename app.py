import logging
import os
from flask import Flask, jsonify, request, redirect
from dotenv import load_dotenv

from extensions import login_manager
from utils.auth import User
from utils.db_utils import get_user_by_id
from utils.serial_reader import mulai_pembacaan_serial
from utils.maintenance import mulai_pembersihan_berkala
from utils.web_setup import pasang_semua
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

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024       # batas upload (foto, surat, frame absensi)
login_manager.init_app(app)
pasang_semua(app)

@login_manager.user_loader
def load_user(user_id):
    row = get_user_by_id(user_id)
    return User(row.id_user, row.username, row.nama, row.role) if row else None

@login_manager.unauthorized_handler
def belum_login():
    # API dipanggil lewat fetch -> JSON 401 (ditangani api.js), halaman -> redirect ke login
    if request.path.startswith("/api/"):
        return jsonify({"error": "Sesi Anda berakhir. Silakan login ulang."}), 401
    return redirect("/login")

for bp in (auth_bp, main_bp, security_bp, timbangan_bp, sortasi_bp, lab_bp, kendaraan_bp,
           personel_bp, blacklist_bp, absensi_bp, audit_bp, sistem_bp):
    app.register_blueprint(bp)


def jalankan_layanan_latar():
    """Serial timbangan & pembersihan uploads. Dipanggil sekali oleh proses yang melayani request."""
    mulai_pembacaan_serial()
    mulai_pembersihan_berkala()


if __name__ == "__main__":
    # Mode development. Untuk dipakai di site gunakan: python serve.py (waitress, tanpa debug)
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"
    # Mode debug menjalankan app 2x (proses induk + anak). Port COM hanya bisa dibuka 1 proses,
    # jadi layanan latar dinyalakan hanya di proses yang benar-benar melayani request.
    if not DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        jalankan_layanan_latar()
    app.run(debug=DEBUG, port=int(os.getenv("PORT", "5000")), threaded=True)
