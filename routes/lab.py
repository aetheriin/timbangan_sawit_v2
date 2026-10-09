from flask import Blueprint, request, jsonify
from utils.db_kunjungan import area_akun
from flask_login import login_required, current_user
from utils.db_utils import (get_standar_mutu, update_standar_mutu, simpan_lab, get_history_umum, cari_transaksi_aktif,
                            get_history_standar)
from utils.hak_akses import izin
from utils import alur


def _tahap_ada(trx, kode):
    """Tahap ini ada di alur mill tiket; tiket lama tanpa mill memakai kategori produk."""
    if trx.id_alur:
        return alur.punya_tahap(trx.id_alur, kode)
    return trx.kategori == ("TBS" if kode == "SORTASI" else "PRODUK_PKS")

lab_bp = Blueprint('lab', __name__)

@lab_bp.route("/api/lab/standar/<int:id_produk>")
@login_required
def lab_standar(id_produk):
    row = get_standar_mutu(id_produk)
    return jsonify({"maks_ffa": row.maks_ffa, "maks_air": row.maks_air, "maks_kotoran": row.maks_kotoran})

@lab_bp.route("/api/lab/standar/update", methods=["POST"])
@login_required
@izin('FORM_LAB', 'ubah')
def lab_standar_update():
    f = request.form
    try:
        nilai = [float(f.get(k, "")) for k in ("maks_ffa", "maks_air", "maks_kotoran")]
        id_produk = int(f.get("id_produk", ""))
    except ValueError:
        return jsonify({"error": "Produk dan semua batas standar wajib diisi angka"}), 400
    if any(v < 0 or v > 100 for v in nilai):
        return jsonify({"error": "Batas standar harus 0 - 100 %"}), 400
    update_standar_mutu(id_produk, *nilai, user_id=current_user.id)
    return jsonify({"message": "Standar mutu diperbarui"}), 200


@lab_bp.route("/api/lab/standar/history")
@login_required
def lab_standar_history():
    return jsonify([{**r, "updated_at": r["updated_at"].strftime("%Y-%m-%d %H:%M")} for r in get_history_standar(2)])

@lab_bp.route("/api/lab/simpan", methods=["POST"])
@login_required
@izin('FORM_LAB', 'tambah')
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
    if not _tahap_ada(trx, "LAB"):
        return jsonify({"error": "Pemeriksaan lab tidak ada di alur tiket ini (lihat Admin › Organisasi › Mill)"}), 400
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
    return jsonify(get_history_umum('lab_hasil', id_area=area_akun(current_user.id)))