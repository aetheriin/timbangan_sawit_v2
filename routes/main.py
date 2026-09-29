import io
from datetime import datetime
import qrcode
import qrcode.image.svg
from flask import Blueprint, request, jsonify, render_template, Response, abort
from flask_login import login_required
from utils.db_utils import (
    get_semua_supplier, get_semua_produk, cari_transaksi_aktif,
    cari_riwayat_driver_by_plat, generate_no_tiket,
    get_kendaraan_by_plat, get_supir_kendaraan, get_kontrak_kendaraan, catat_cetak_qr
)
from utils.serializers import serialisasi_tiket
from utils.plat_utils import normalisasi_plat

main_bp = Blueprint('main', __name__)

@main_bp.route("/weighbridge")
@login_required
def weighbridge():
    return render_template("weighbridge.html",
                           supplier_list=get_semua_supplier(), produk_list=get_semua_produk())

@main_bp.route("/api/plat/lookup", methods=["POST"])
@login_required
def api_plat_lookup():
    no_plat, error = normalisasi_plat(request.form.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400

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
    # Data dari menu Update: supir terdaftar & kontrak aktif truk ini
    kendaraan = get_kendaraan_by_plat(no_plat)
    supir_terdaftar = get_supir_kendaraan(kendaraan.id_kendaraan) if kendaraan else []
    kontrak_aktif = get_kontrak_kendaraan(kendaraan.id_kendaraan, hanya_aktif=True) if kendaraan else []
    utama = next((s for s in supir_terdaftar if s["is_utama"]), None)
    driver_utama = None
    if utama:
        driver_utama = {"id_driver": utama["id_driver"], "nik": utama["nik"], "nama": utama["nama_driver"],
                        "no_sim": utama["no_sim"], "is_updated": utama["is_updated"],
                        "foto_path": utama["foto_path"]}

    return jsonify({
        "status": "DRAFT",
        "no_plat": no_plat,
        "no_tiket_reserved": generate_no_tiket(no_plat),
        "no_stnk": (kendaraan.no_stnk if kendaraan and kendaraan.no_stnk else None)
                   or (riwayat.no_stnk if riwayat else None),
        "driver": driver_info,             # supir transaksi terakhir
        "driver_utama": driver_utama,      # supir utama dari menu Update
        "supir_terdaftar": supir_terdaftar,
        "kontrak_aktif": kontrak_aktif
    }), 200

# ===== QR CODE TIKET (dibuat di server, tidak butuh internet) =====

def _svg_qr(teks):
    img = qrcode.make(teks, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    return svg[svg.index("<svg"):]     # buang deklarasi <?xml?> supaya bisa disisipkan langsung di HTML

@main_bp.route("/api/qr/<no_tiket>")
@login_required
def qr_tiket(no_tiket):
    return Response(_svg_qr(no_tiket), mimetype="image/svg+xml")

@main_bp.route("/cetak/tiket/<no_tiket>")
@login_required
def cetak_tiket(no_tiket):
    row = cari_transaksi_aktif(no_tiket=no_tiket)
    if not row:
        abort(404, "Tiket tidak ditemukan / sudah selesai")
    cetakan_ke = catat_cetak_qr(no_tiket) + 1
    return render_template("cetak_tiket.html", t=row, qr_svg=_svg_qr(row.no_tiket), cetakan_ke=cetakan_ke,
                           now=datetime.now().strftime("%d-%m-%Y %H:%M"))