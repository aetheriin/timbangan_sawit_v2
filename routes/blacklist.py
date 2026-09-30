"""Menu Face Recognition > Blacklist: riwayat & tambah. Permanen, tidak ada update / hapus."""
from datetime import date
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import role_required
from utils.db_blacklist import TIPE_VALID, get_riwayat_blacklist, cari_target, tambah_blacklist
from utils.upload_utils import simpan_upload, hapus_file, SURAT_EKSTENSI

blacklist_bp = Blueprint('blacklist', __name__)


@blacklist_bp.route("/api/blacklist")
@login_required
def blacklist_riwayat():
    tipe = request.args.get("tipe", "").upper()
    return jsonify(get_riwayat_blacklist(tipe if tipe in TIPE_VALID else None,
                                         request.args.get("cari", "").strip() or None))


@blacklist_bp.route("/api/blacklist/cari-target")
@login_required
def blacklist_cari_target():
    tipe = request.args.get("tipe", "PERSONEL").upper()
    kata = request.args.get("q", "").strip()
    if tipe not in TIPE_VALID or len(kata) < 2:
        return jsonify([])
    return jsonify(cari_target(tipe, kata))


@blacklist_bp.route("/api/blacklist/tambah", methods=["POST"])
@login_required
@role_required('HO')
def blacklist_tambah():
    f = request.form
    tipe = f.get("tipe_entitas", "").upper()
    id_target = f.get("id_target", type=int)
    no_surat, alasan = f.get("no_surat", "").strip(), f.get("alasan", "").strip()
    if tipe not in TIPE_VALID or not id_target:
        return jsonify({"error": "Pilih target blacklist dulu"}), 400
    if not no_surat or not alasan:
        return jsonify({"error": "No. surat dan alasan wajib diisi"}), 400
    try:
        tgl = date.fromisoformat(f.get("tgl_blacklist", "").strip())
    except ValueError:
        return jsonify({"error": "Tanggal surat tidak valid"}), 400
    if tgl > date.today():
        return jsonify({"error": "Tanggal surat tidak boleh setelah hari ini"}), 400

    try:
        path_disk, relatif = simpan_upload(request.files.get("file_surat"), "surat_blacklist", SURAT_EKSTENSI)
    except ValueError as e:
        return jsonify({"error": f"Surat: {e}"}), 400

    try:
        tambah_blacklist(tipe, id_target, no_surat, alasan, relatif, tgl, current_user.id)
    except ValueError as e:
        hapus_file(path_disk)
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "Blacklist ditetapkan (permanen)"})
