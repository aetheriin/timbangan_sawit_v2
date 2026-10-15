"""API persetujuan (utils/persetujuan.py). Antrean ditampilkan sebagai tab di halaman menunya (mis. Blacklist ›
Persetujuan); alamat lama /persetujuan dialihkan ke sana."""
from flask import Blueprint, jsonify, redirect, request
from flask_login import current_user, login_required

from utils import persetujuan

persetujuan_bp = Blueprint("persetujuan", __name__)


@persetujuan_bp.route("/persetujuan")
@login_required
def halaman_lama():
    id_p = request.args.get("id", type=int)
    return redirect("/blacklist?tab=persetujuan" + (f"&id={id_p}" if id_p else ""))


@persetujuan_bp.route("/api/persetujuan")
@login_required
def daftar():
    mode = request.args.get("mode", "menunggu")
    if mode not in ("menunggu", "saya", "semua"):
        mode = "menunggu"
    menu = (request.args.get("menu") or "").upper() or None
    return jsonify(persetujuan.daftar(current_user, mode, menu=menu))


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
