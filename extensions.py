import os
from flask_login import LoginManager

# File upload (foto wajah, surat blacklist, snapshot absensi) disimpan PRIVAT di luar folder static,
# hanya bisa dibuka lewat route /berkas/... yang wajib login. Path di database tetap "uploads/...".
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "data", "uploads")))
UPLOAD_LAMA = os.path.join(BASE_DIR, "static", "uploads")     # lokasi lama (publik), dipindah saat start
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

login_manager = LoginManager()
login_manager.login_view = "auth.login"

