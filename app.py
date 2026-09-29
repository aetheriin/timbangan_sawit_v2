import os
from flask import Flask
from dotenv import load_dotenv

from extensions import login_manager
from utils.auth import User
from utils.db_utils import get_user_by_id
from utils.serial_reader import mulai_pembacaan_serial
from routes.auth import auth_bp
from routes.main import main_bp
from routes.security import security_bp
from routes.timbangan import timbangan_bp
from routes.sortasi import sortasi_bp
from routes.lab import lab_bp

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    row = get_user_by_id(user_id)
    return User(row.id_user, row.username, row.nama, row.role) if row else None

for bp in (auth_bp, main_bp, security_bp, timbangan_bp, sortasi_bp, lab_bp):
    app.register_blueprint(bp)

if __name__ == "__main__":
    DEBUG = True
    # Mode debug menjalankan app 2x (proses induk + anak). Port COM hanya bisa dibuka 1 proses,
    # jadi serial reader dinyalakan hanya di proses yang benar-benar melayani request.
    if not DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        mulai_pembacaan_serial()
    app.run(debug=DEBUG, port=5000)