from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import role_required
from utils.db_utils import simpan_sortasi, get_history_umum

sortasi_bp = Blueprint('sortasi', __name__)

@sortasi_bp.route("/api/sortasi/simpan", methods=["POST"])
@login_required
@role_required('SORTASI')
def sortasi_simpan():
    no_tiket = request.form.get("no_tiket")
    if not no_tiket:
        return jsonify({"error": "Tiket belum dipilih"}), 400
    v = {k: float(request.form.get(k) or 0) for k in ['mentah', 'busuk', 'tangkai', 'sampah', 'matang', 'brondolan']}
    total = simpan_sortasi(no_tiket, v['mentah'], v['busuk'], v['tangkai'], v['sampah'],
                           v['matang'], v['brondolan'], request.form.get("catatan", ""), current_user.id)
    return jsonify({"message": f"Sortasi tersimpan. Total potongan: {total} kg", "total_potongan_kg": total}), 200

@sortasi_bp.route("/api/history/sortasi")
@login_required
def history_sortasi():
    return jsonify(get_history_umum('sortasi'))