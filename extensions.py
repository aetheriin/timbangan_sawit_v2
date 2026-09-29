import os
from functools import wraps
from flask import jsonify
from flask_login import LoginManager, current_user

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

login_manager = LoginManager()
login_manager.login_view = "auth.login"

camera_trigger_state = {"is_active": False}   # dict dipakai bersama antar blueprint

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "Belum login"}), 401
            if current_user.role != 'ADMIN' and current_user.role not in roles:
                return jsonify({"error": "Akses ditolak untuk role Anda"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator