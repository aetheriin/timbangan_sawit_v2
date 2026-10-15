"""Halaman Persetujuan: pengajuan yang menunggu saya, pengajuan saya, dan riwayat (utils/persetujuan.py)."""
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from utils import persetujuan
from utils.hak_akses import halaman as lihat_halaman

persetujuan_bp = Blueprint("persetujuan", __name__)


@persetujuan_bp.route("/persetujuan")
@login_required
@lihat_halaman("PERSETUJUAN")
def halaman():
    return render_template("persetujuan/persetujuan.html", halaman="persetujuan")


@persetujuan_bp.route("/api/persetujuan")
@login_required
def daftar():
    mode = request.args.get("mode", "menunggu")
    if mode not in ("menunggu", "saya", "semua"):
        mode = "menunggu"
    return jsonify(persetujuan.daftar(current_user, mode))


def _jalankan(fn):
    try:
        return jsonify({"message": fn()})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@persetujuan_bp.route("/api/persetujuan/<int:id_pengajuan>/setujui", methods=["POST"])
@login_required
def setujui(id_pengajuan):
    catatan = (request.form.get("catatan") or "").strip()[:500] or None
    return _jalankan(lambda: persetujuan.setujui(id_pengajuan, current_user, catatan))


@persetujuan_bp.route("/api/persetujuan/<int:id_pengajuan>/tolak", methods=["POST"])
@login_required
def tolak(id_pengajuan):
    catatan = (request.form.get("catatan") or "").strip()[:500]
    if not catatan:
        return jsonify({"error": "Alasan penolakan wajib diisi"}), 400
    return _jalankan(lambda: persetujuan.tolak(id_pengajuan, current_user, catatan))


@persetujuan_bp.route("/api/persetujuan/<int:id_pengajuan>/batalkan", methods=["POST"])
@login_required
def batalkan(id_pengajuan):
    return _jalankan(lambda: persetujuan.batalkan(id_pengajuan, current_user))
