import os
from functools import wraps
from flask import jsonify
from flask_login import LoginManager, current_user

# File upload (foto wajah, surat blacklist, snapshot absensi) disimpan PRIVAT di luar folder static,
# hanya bisa dibuka lewat route /berkas/... yang wajib login. Path di database tetap "uploads/...".
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "data", "uploads")))
UPLOAD_LAMA = os.path.join(BASE_DIR, "static", "uploads")     # lokasi lama (publik), dipindah saat start
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

login_manager = LoginManager()
login_manager.login_view = "auth.login"


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Belum login"}), 401
            if current_user.role != 'ADMIN' and current_user.role not in roles:
                from utils.keamanan import log_keamanan
                log_keamanan("AKSES_DITOLAK", f"role {current_user.role} ke {f.__name__}")
                return jsonify({"error": "Akses ditolak untuk role Anda"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator