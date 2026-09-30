from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import role_required
from utils.serial_reader import baca_status_asli, reset_deteksi_stabil
from utils.db_utils import (
    get_data_timbangan, simpan_timbang_pertama, simpan_timbang_kedua, catat_timeline,
    cari_transaksi_aktif, get_history_timbangan_by_supplier
)
from utils.serializers import serialisasi_tiket

timbangan_bp = Blueprint('timbangan', __name__)

@timbangan_bp.route("/api/timbang/status")
@login_required
def timbang_status():
    return jsonify(baca_status_asli())

@timbangan_bp.route("/api/timbang/reset-baseline", methods=["POST"])
@login_required
def timbang_reset():
    reset_deteksi_stabil()
    return jsonify({"message": "Baseline direset"}), 200

@timbangan_bp.route("/api/timbang/data/<no_tiket>")
@login_required
def timbang_data(no_tiket):
    row = get_data_timbangan(no_tiket)
    if not row:
        return jsonify({"berat_bruto": None, "berat_tara": None, "berat_netto": None,
                        "potongan_kg": None, "netto_akhir": None})
    return jsonify({"berat_bruto": row.berat_bruto, "berat_tara": row.berat_tara, "berat_netto": row.berat_netto,
                    "potongan_kg": row.total_potongan_kg, "netto_akhir": _netto_akhir(row)})

def _netto_akhir(row):
    if row.berat_netto is None:
        return None
    return round(row.berat_netto - (row.total_potongan_kg or 0), 2)

@timbangan_bp.route("/api/timbang/scan-qr", methods=["POST"])
@login_required
def timbang_scan_qr():
    row = cari_transaksi_aktif(no_tiket=request.form.get("no_tiket", "").strip())
    if not row:
        return jsonify({"error": "Tiket tidak ditemukan / sudah selesai"}), 404
    return jsonify(serialisasi_tiket(row)), 200

@timbangan_bp.route("/api/history-timbangan-supplier")
@login_required
def history_supplier():
    id_supplier = request.args.get("id_supplier")
    return jsonify(get_history_timbangan_by_supplier(id_supplier) if id_supplier else [])

@timbangan_bp.route("/api/timbang/simpan", methods=["POST"])
@login_required
@role_required('OPERATOR_TIMBANG')
def timbang_simpan():
    no_tiket = request.form.get("no_tiket", "").strip()
    if not no_tiket:
        return jsonify({"error": "No. Tiket wajib ada"}), 400

    status = baca_status_asli()
    if not status.get("siap_kunci"):
        return jsonify({"error": "Berat belum stabil"}), 400

    trx = cari_transaksi_aktif(no_tiket=no_tiket)
    data_lama = get_data_timbangan(no_tiket)
    if trx is None or data_lama is None:
        return jsonify({"error": "Tiket tidak ditemukan / sudah selesai / ditolak"}), 404
    if data_lama.berat_netto is not None:
        return jsonify({"error": "Tiket ini sudah selesai ditimbang"}), 400

    berat = status["berat"]
    if data_lama.berat_bruto is None and data_lama.berat_tara is None:
        jenis = simpan_timbang_pertama(no_tiket, berat, current_user.id)
        reset_deteksi_stabil()
        catat_timeline(no_tiket, 'TIMBANG_MASUK', current_user.id)
        if jenis == 'PENIMBANGAN_SAJA':
            return jsonify({"message": f"Selesai (Penimbangan). Netto: {berat} kg"}), 200
        label = "Tara" if jenis == 'PENJUALAN' else "Bruto"
        return jsonify({"message": f"{label} tersimpan: {berat} kg. Menunggu timbang kedua."}), 200

    # Timbang kedua hanya setelah inspeksi: sortasi (TBS) atau lab APPROVE (produk PKS)
    if trx.status_alur != 'TIMBANG_2':
        menunggu = "sortasi" if trx.kategori == 'TBS' else "hasil lab (Approve)"
        return jsonify({"error": f"Belum bisa timbang kedua, tiket masih menunggu {menunggu}"}), 400

    netto = simpan_timbang_kedua(no_tiket, berat, current_user.id)
    reset_deteksi_stabil()
    catat_timeline(no_tiket, 'TIMBANG_KELUAR', current_user.id)
    hasil = get_data_timbangan(no_tiket)
    pesan = f"Selesai! Netto: {netto} kg"
    if hasil.total_potongan_kg is not None:
        pesan += f", potongan sortasi: {hasil.total_potongan_kg} kg, netto akhir: {_netto_akhir(hasil)} kg"
    return jsonify({"message": pesan}), 200