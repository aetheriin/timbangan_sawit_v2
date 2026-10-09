import logging
from datetime import date, datetime
from flask import Blueprint, request, jsonify
from utils.area import area_data
from flask_login import login_required, current_user
from utils.serial_reader import baca_status, reset_deteksi_stabil
from utils.db_utils import (
    get_data_timbangan, simpan_timbang_pertama, simpan_timbang_kedua, catat_timeline,
    cari_transaksi_aktif, get_history_timbangan_by_supplier
)
from utils.serializers import serialisasi_tiket
from utils.hak_akses import izin
from utils.db_jembatan import jembatan_dipilih
from utils import alur, db_kelebihan_do

timbangan_bp = Blueprint('timbangan', __name__)

@timbangan_bp.route("/api/timbang/status")
@login_required
def timbang_status():
    """Berat live jembatan yang dipilih PC ini (dibaca terus, walau belum ada tiket)."""
    j = jembatan_dipilih(request)
    if j is None:
        return jsonify({"berat": 0, "stabil": False, "terhubung": False, "siap_kunci": False, "jembatan": None,
                        "error": "Pilih jembatan timbang untuk PC ini"})
    return jsonify({**baca_status(j["id_jembatan"]), "jembatan": j["kode"]})

@timbangan_bp.route("/api/timbang/reset-baseline", methods=["POST"])
@login_required
def timbang_reset():
    j = jembatan_dipilih(request)
    if j:
        reset_deteksi_stabil(j["id_jembatan"])
    return jsonify({"message": "Baseline direset"}), 200

@timbangan_bp.route("/api/timbang/data/<no_tiket>")
@login_required
def timbang_data(no_tiket):
    row = get_data_timbangan(no_tiket)
    if not row:
        return jsonify({"berat_bruto": None, "berat_tara": None, "berat_netto": None,
                        "potongan_kg": None, "netto_akhir": None})
    return jsonify({"berat_bruto": row.berat_bruto, "berat_tara": row.berat_tara, "berat_netto": row.berat_netto,
                    "potongan_kg": row.total_potongan_kg, "netto_akhir": _netto_akhir(row),
                    "jembatan_masuk": row.kode_jembatan})

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

HARI_HISTORY_MAKS = 30


@timbangan_bp.route("/api/history-timbangan-supplier")
@login_required
def history_supplier():
    id_supplier = request.args.get("id_supplier")
    tanggal = None
    if request.args.get("tanggal"):            # filter per hari, hanya 30 hari terakhir
        try:
            tanggal = datetime.strptime(request.args["tanggal"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Format tanggal salah"}), 400
        if not 0 <= (date.today() - tanggal).days < HARI_HISTORY_MAKS:
            return jsonify({"error": f"Tanggal hanya bisa dipilih {HARI_HISTORY_MAKS} hari terakhir"}), 400
    rows = (get_history_timbangan_by_supplier(id_supplier, tanggal=tanggal, id_area=area_data(current_user.id))
            if id_supplier else [])
    return jsonify([{**r, "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M") if r["created_at"] else None} for r in rows])

@timbangan_bp.route("/api/timbang/simpan", methods=["POST"])
@login_required
@izin('FORM_TIMBANGAN', 'tambah')
def timbang_simpan():
    no_tiket = request.form.get("no_tiket", "").strip()
    if not no_tiket:
        return jsonify({"error": "No. Tiket wajib ada"}), 400

    jembatan = jembatan_dipilih(request)
    if jembatan is None:
        return jsonify({"error": "Pilih jembatan timbang untuk PC ini dulu (di atas tampilan berat)"}), 400
    status = baca_status(jembatan["id_jembatan"])
    if not status.get("terhubung"):
        return jsonify({"error": f"Timbangan {jembatan['kode']} tidak terhubung: {status.get('error') or '-'}"}), 400
    if not status.get("siap_kunci"):
        return jsonify({"error": "Berat belum stabil"}), 400
    if status["berat"] < jembatan.get("berat_min_kg", 0):
        return jsonify({"error": f"Berat {status['berat']:g} kg di bawah minimum {jembatan['berat_min_kg']:g} kg "
                                 f"(timbangan kosong / truk belum naik penuh)"}), 400

    trx = cari_transaksi_aktif(no_tiket=no_tiket)
    data_lama = get_data_timbangan(no_tiket)
    if trx is None or data_lama is None:
        return jsonify({"error": "Tiket tidak ditemukan / sudah selesai / ditolak"}), 404
    if data_lama.berat_netto is not None:
        return jsonify({"error": "Tiket ini sudah selesai ditimbang"}), 400

    berat = status["berat"]
    if data_lama.berat_bruto is None and data_lama.berat_tara is None:
        jenis = simpan_timbang_pertama(no_tiket, berat, current_user.id, jembatan["id_jembatan"])
        reset_deteksi_stabil(jembatan["id_jembatan"])
        catat_timeline(no_tiket, 'TIMBANG_MASUK', current_user.id)
        if jenis == 'PENIMBANGAN_SAJA':
            return jsonify({"message": f"Selesai (Penimbangan). Netto: {berat} kg",
                            "kelebihan_do": _cek_kelebihan(no_tiket)}), 200
        label = "Tara" if jenis == 'PENJUALAN' else "Bruto"
        return jsonify({"message": f"{label} tersimpan di {jembatan['kode']}: {berat} kg. "
                                   f"Timbang keluar juga harus di {jembatan['kode']}."}), 200

    # Timbang kedua hanya setelah inspeksi: sortasi (TBS) atau lab APPROVE (produk PKS)
    if trx.status_alur != 'TIMBANG_2':
        menunggu = (alur.menunggu(trx.id_alur, trx.status_alur) if trx.id_alur
                    else "sortasi" if trx.kategori == 'TBS' else "hasil lab (Approve)")
        return jsonify({"error": f"Belum bisa timbang kedua, tiket masih menunggu {menunggu}"}), 400

    if data_lama.id_jembatan != jembatan["id_jembatan"]:
        return jsonify({"error": f"Tiket ini masuk di {data_lama.kode_jembatan}. Timbang keluar harus di "
                                 f"{data_lama.kode_jembatan}, bukan {jembatan['kode']}."}), 400
    try:
        netto = simpan_timbang_kedua(no_tiket, berat, current_user.id, jembatan["id_jembatan"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    reset_deteksi_stabil(jembatan["id_jembatan"])
    catat_timeline(no_tiket, 'TIMBANG_KELUAR', current_user.id)
    hasil = get_data_timbangan(no_tiket)
    pesan = f"Selesai! Netto: {netto} kg"
    if hasil.total_potongan_kg is not None:
        pesan += f", potongan sortasi: {hasil.total_potongan_kg} kg, netto akhir: {_netto_akhir(hasil)} kg"
    return jsonify({"message": pesan, "kelebihan_do": _cek_kelebihan(no_tiket)}), 200


def _cek_kelebihan(no_tiket):
    """DO tiket ini lewat kuota -> tiket split + notifikasi KTU / HO. Gagal di sini tidak membatalkan timbangan."""
    try:
        return db_kelebihan_do.proses_tiket_selesai(no_tiket, current_user.id)
    except Exception:       # noqa: BLE001
        logging.getLogger("weighbridge").exception("Gagal memproses kelebihan DO %s", no_tiket)
        return None