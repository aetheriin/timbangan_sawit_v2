from flask import Blueprint, request, render_template, redirect
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from utils.auth import User
from utils.db_utils import get_user_by_username

auth_bp = Blueprint('auth', __name__)

TAB_DEFAULT = {'SECURITY': 'security', 'OPERATOR_TIMBANG': 'timbangan',
               'SORTASI': 'sortasi', 'LAB': 'lab', 'ADMIN': 'security', 'HO': 'security'}

@auth_bp.route("/")
def index():
    return redirect("/login")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        row = get_user_by_username(request.form.get("username", "").strip())
        if row is None or not check_password_hash(row.password, request.form.get("password", "")):
            return render_template("login.html", error="Username atau password salah")
        login_user(User(row.id_user, row.username, row.nama, row.role))
        return redirect(f"/weighbridge?tab={TAB_DEFAULT.get(row.role, 'security')}")
    return render_template("login.html", error=None)

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")