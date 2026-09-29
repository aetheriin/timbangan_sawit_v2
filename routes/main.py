from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required
from utils.db_utils import (
    get_semua_supplier, get_semua_produk, cari_transaksi_aktif,
    cari_riwayat_driver_by_plat, generate_no_tiket
)
from utils.serializers import serialisasi_tiket

main_bp = Blueprint('main', __name__)

@main_bp.route("/weighbridge")
@login_required
def weighbridge():
    return render_template("weighbridge.html",
                           supplier_list=get_semua_supplier(), produk_list=get_semua_produk())

@main_bp.route("/api/plat/lookup", methods=["POST"])
@login_required
def api_plat_lookup():
    no_plat = request.form.get("no_plat", "").strip().upper()
    if not no_plat:
        return jsonify({"error": "Nomor plat kosong"}), 400

    row = cari_transaksi_aktif(no_plat=no_plat)
    if row:
        return jsonify(serialisasi_tiket(row)), 200

    # Belum ada tiket aktif: nomor tiket cuma "dipesan", belum di-INSERT
    riwayat = cari_riwayat_driver_by_plat(no_plat)
    driver_info = None
    if riwayat:
        driver_info = {"id_driver": riwayat.id_driver, "nik": riwayat.nik, "nama": riwayat.nama_driver,
                       "no_sim": riwayat.no_sim, "is_updated": bool(riwayat.is_updated),
                       "foto_path": riwayat.foto_path}
    return jsonify({
        "status": "DRAFT",
        "no_tiket_reserved": generate_no_tiket(no_plat),
        "no_stnk": riwayat.no_stnk if riwayat else None,
        "driver": driver_info
    }), 200