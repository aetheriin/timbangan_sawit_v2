import io
from datetime import datetime
import qrcode
import qrcode.image.svg
from flask import Blueprint, request, jsonify, render_template, Response, abort
from flask_login import login_required, current_user
from utils.db_utils import (
    get_semua_supplier, get_semua_produk, get_history_produk, cari_transaksi_aktif,
    cari_riwayat_driver_by_plat, generate_no_tiket,
    get_kendaraan_by_plat, get_supir_kendaraan, get_kontrak_kendaraan, catat_cetak_qr
)
from utils.serializers import serialisasi_tiket, serialisasi_driver
from utils.db_blacklist import get_surat_blacklist
from utils.audit_utils import catat_security_audit
from utils.plat_utils import normalisasi_plat
from utils import pengaturan

main_bp = Blueprint('main', __name__)

# Tahap yang ditangani tiap role: halaman List default ke tahap ini, Form default ke tab ini
TAHAP_ROLE = {"SECURITY": "security", "OPERATOR_TIMBANG": "timbangan", "SORTASI": "sortasi", "LAB": "lab"}


@main_bp.route("/weighbridge")
@login_required
def weighbridge():
    """List = daftar tiket aktif per tahap (tanpa info bar & tab). Form = info bar + tab Security..Lab."""
    if request.args.get("view") != "form":
        return render_template("site/list.html", halaman="site", view="list", produk_list=get_semua_produk(),
                               tahap_awal=TAHAP_ROLE.get(current_user.role, ""))
    return render_template("site/weighbridge.html", halaman="site", view="form",
                           tab_awal=TAHAP_ROLE.get(current_user.role, "security"),
                           supplier_list=get_semua_supplier(), produk_list=get_semua_produk(),
                           wajib_scan_wajah=pengaturan.nilai("WAJIB_SCAN_WAJAH"))

@main_bp.route("/api/list/history-produk")
@login_required
def history_produk():
    id_produk = request.args.get("id_produk", "")
    rows = get_history_produk(int(id_produk) if id_produk.isdigit() else None)
    return jsonify([{**r, "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M")} for r in rows])


@main_bp.route("/face-recognition")
@login_required
def face_recognition():
    """Satu halaman, tab Absensi | Personel | Blacklist | Audit Log (tanpa info bar)."""
    return render_template("face_recognition/face_recognition.html", halaman="face")

@main_bp.route("/api/plat/lookup", methods=["POST"])
@login_required
def api_plat_lookup():
    no_plat, error = normalisasi_plat(request.form.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400

    kendaraan = get_kendaraan_by_plat(no_plat)
    blacklist = (get_surat_blacklist("KENDARAAN", kendaraan.id_kendaraan)
                 if kendaraan and kendaraan.is_blacklisted else None)

    row = cari_transaksi_aktif(no_plat=no_plat)
    if row:
        return jsonify({**serialisasi_tiket(row), "kendaraan_blacklist": blacklist}), 200

    # Belum ada tiket aktif: nomor tiket cuma "dipesan", belum di-INSERT
    riwayat = cari_riwayat_driver_by_plat(no_plat)
    driver_info = serialisasi_driver(riwayat)

    if blacklist:      # truk diblacklist HO: hanya PERINGATAN (tiket tetap bisa dibuat), tercatat untuk HO
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST",
                             details={"keterangan": f"Plat {no_plat} terdeteksi blacklist (peringatan)",
                                      "no_plat": no_plat, "no_surat": blacklist["no_surat_blacklist"]},
                             ip_address=request.remote_addr)

    # Data dari menu Update: supir terdaftar & kontrak aktif truk ini
    supir_terdaftar = get_supir_kendaraan(kendaraan.id_kendaraan) if kendaraan else []
    kontrak_aktif = get_kontrak_kendaraan(kendaraan.id_kendaraan, hanya_aktif=True) if kendaraan else []
    utama = next((s for s in supir_terdaftar if s["is_utama"]), None)
    driver_utama = None
    if utama:
        driver_utama = {"id_driver": utama["id_driver"], "kode_personel": utama["kode_personel"],
                        "nik": utama["nik"], "nama": utama["nama_driver"], "no_sim": utama["no_sim"],
                        "kategori": "DRIVER", "is_blacklisted": utama["is_blacklisted"],
                        "is_updated": utama["is_updated"], "foto_path": utama["foto_path"]}

    return jsonify({
        "status": "DRAFT",
        "no_plat": no_plat,
        "no_tiket_reserved": generate_no_tiket(no_plat),
        "no_stnk": (kendaraan.no_stnk if kendaraan and kendaraan.no_stnk else None)
                   or (riwayat.no_stnk if riwayat else None),
        "driver": driver_info,             # supir transaksi terakhir
        "driver_utama": driver_utama,      # supir utama dari menu Update
        "supir_terdaftar": supir_terdaftar,
        "kontrak_aktif": kontrak_aktif,
        "kendaraan_blacklist": blacklist,  # None = tidak blacklist
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
    return render_template("site/cetak_tiket.html", t=row, qr_svg=_svg_qr(row.no_tiket), cetakan_ke=cetakan_ke,
                           now=datetime.now().strftime("%d-%m-%Y %H:%M"))