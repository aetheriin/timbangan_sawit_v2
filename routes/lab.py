from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import role_required
from utils.db_utils import get_standar_mutu, update_standar_mutu, simpan_lab, get_history_umum, cari_transaksi_aktif

lab_bp = Blueprint('lab', __name__)

@lab_bp.route("/api/lab/standar/<int:id_produk>")
@login_required
def lab_standar(id_produk):
    row = get_standar_mutu(id_produk)
    return jsonify({"maks_ffa": row.maks_ffa, "maks_air": row.maks_air, "maks_kotoran": row.maks_kotoran})

@lab_bp.route("/api/lab/standar/update", methods=["POST"])
@login_required
@role_required('LAB')
def lab_standar_update():
    f = request.form
    update_standar_mutu(f.get("id_produk"), f.get("maks_ffa"), f.get("maks_air"), f.get("maks_kotoran"))
    return jsonify({"message": "Standar mutu diperbarui"}), 200

@lab_bp.route("/api/lab/simpan", methods=["POST"])
@login_required
@role_required('LAB')
def lab_simpan():
    f = request.form
    no_tiket, keputusan = f.get("no_tiket"), f.get("keputusan")
    if not no_tiket:
        return jsonify({"error": "Tiket belum dipilih"}), 400
    if keputusan not in ('APPROVE', 'REJECT'):
        return jsonify({"error": "Keputusan harus APPROVE atau REJECT"}), 400
    trx = cari_transaksi_aktif(no_tiket=no_tiket)
    if trx is None:
        return jsonify({"error": "Tiket tidak ditemukan / sudah selesai / ditolak"}), 404
    if trx.kategori != 'PRODUK_PKS':
        return jsonify({"error": "Pemeriksaan lab hanya untuk produk PKS"}), 400
    if trx.status_alur not in ('TIMBANG_1', 'TIMBANG_2'):
        return jsonify({"error": "Pemeriksaan lab dilakukan setelah timbang pertama"}), 400
    no_coa = f"COA-{no_tiket}" if keputusan == 'APPROVE' else None
    simpan_lab(no_tiket, f.get("ffa"), f.get("kadar_air"), f.get("kadar_kotoran"),
               f.get("warna_locis"), keputusan, no_coa, current_user.id)
    lanjut = "lanjut timbang kedua" if keputusan == 'APPROVE' else "tiket ditolak"
    return jsonify({"message": f"Hasil lab tersimpan ({keputusan}), {lanjut}", "no_dokumen_coa": no_coa}), 200

@lab_bp.route("/api/history/lab")
@login_required
def history_lab():
    return jsonify(get_history_umum('lab_hasil'))