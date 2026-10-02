"""Dashboard harga: semua role non-admin melihat, HO mengisi."""
from datetime import date

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from extensions import role_required
from utils.db_dashboard import KOLOM, riwayat_harga, simpan_harga

dashboard_bp = Blueprint("dashboard", __name__)
BATAS = {"harga_cpo": (0, 1_000_000), "harga_kernel": (0, 1_000_000), "oer_cpo": (0, 100), "biaya_olah": (0, 1_000_000)}


@dashboard_bp.route("/dashboard")
@login_required
def dashboard_halaman():
    return render_template("dashboard/dashboard.html", halaman="dashboard", boleh_ubah=current_user.role == "HO")


@dashboard_bp.route("/api/dashboard/harga")
@login_required
def dashboard_harga():
    hari = min(max(request.args.get("hari", 30, type=int), 7), 365)
    return jsonify([{**{k: (float(r[k]) if r[k] is not None else None) for k in KOLOM},
                     "tanggal": r["tanggal"].strftime("%Y-%m-%d"), "oleh": r["oleh"]} for r in riwayat_harga(hari)])


@dashboard_bp.route("/api/dashboard/harga/simpan", methods=["POST"])
@login_required
@role_required("HO")
def dashboard_harga_simpan():
    try:
        tanggal = date.fromisoformat(request.form.get("tanggal", ""))
        nilai = []
        for k in KOLOM:
            v = float(request.form.get(k, "").replace(",", "."))
            if not BATAS[k][0] <= v <= BATAS[k][1]:
                raise ValueError
            nilai.append(v)
    except ValueError:
        return jsonify({"error": "Tanggal dan semua nilai wajib diisi angka yang wajar (OER 0 - 100 %)"}), 400
    if tanggal > date.today():
        return jsonify({"error": "Tanggal tidak boleh setelah hari ini"}), 400
    simpan_harga(tanggal, nilai, current_user.id)
    return jsonify({"message": f"Harga {tanggal:%d-%m-%Y} disimpan"})
