from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import role_required
from utils.db_utils import simpan_sortasi, get_history_umum, cari_transaksi_aktif

sortasi_bp = Blueprint('sortasi', __name__)

@sortasi_bp.route("/api/sortasi/simpan", methods=["POST"])
@login_required
@role_required('SORTASI')
def sortasi_simpan():
    no_tiket = request.form.get("no_tiket")
    if not no_tiket:
        return jsonify({"error": "Tiket belum dipilih"}), 400
    trx = cari_transaksi_aktif(no_tiket=no_tiket)
    if trx is None:
        return jsonify({"error": "Tiket tidak ditemukan / sudah selesai / ditolak"}), 404
    if trx.kategori != 'TBS':
        return jsonify({"error": "Sortasi hanya untuk produk TBS"}), 400
    if trx.status_alur not in ('TIMBANG_1', 'TIMBANG_2'):
        return jsonify({"error": "Sortasi dilakukan setelah timbang pertama"}), 400
    v = {k: float(request.form.get(k) or 0) for k in ['mentah', 'busuk', 'tangkai', 'sampah', 'matang', 'brondolan']}
    persen, kg = simpan_sortasi(no_tiket, v['mentah'], v['busuk'], v['tangkai'], v['sampah'],
                                v['matang'], v['brondolan'], request.form.get("catatan", ""), current_user.id)
    rincian = f"{kg} kg" if kg is not None else "kg dihitung dari netto saat timbang kedua"
    return jsonify({"message": f"Sortasi tersimpan. Potongan {persen}% ({rincian})",
                    "total_persen_potongan": persen, "total_potongan_kg": kg}), 200

@sortasi_bp.route("/api/history/sortasi")
@login_required
def history_sortasi():
    return jsonify(get_history_umum('sortasi'))