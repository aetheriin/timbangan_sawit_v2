from datetime import date
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import role_required
from utils.plat_utils import normalisasi_plat
from utils.db_utils import (
    get_or_create_kendaraan, get_kendaraan_by_plat, get_driver_by_id,
    get_supir_kendaraan, tambah_supir_kendaraan, nonaktifkan_supir_kendaraan,
    get_kontrak_kendaraan, tambah_kontrak, akhiri_kontrak
)

kendaraan_bp = Blueprint('kendaraan', __name__)

JENIS_VALID = ('PEMBELIAN', 'PENJUALAN', 'PENIMBANGAN_SAJA')


def _data_kendaraan(no_plat):
    row = get_kendaraan_by_plat(no_plat)
    if not row:
        return {"no_plat": no_plat, "terdaftar": False, "no_stnk": None, "supir": [], "kontrak": []}
    return {"no_plat": row.no_plat, "terdaftar": True, "no_stnk": row.no_stnk,
            "supir": get_supir_kendaraan(row.id_kendaraan),
            "kontrak": get_kontrak_kendaraan(row.id_kendaraan)}


def _plat_dari_form():
    return normalisasi_plat(request.form.get("no_plat"))


def _tanggal(teks, wajib=False):
    teks = (teks or "").strip()
    if not teks:
        if wajib:
            raise ValueError("Tanggal mulai wajib diisi")
        return None
    try:
        return date.fromisoformat(teks)
    except ValueError:
        raise ValueError(f"Format tanggal '{teks}' tidak valid (YYYY-MM-DD)")


@kendaraan_bp.route("/api/kendaraan")
@login_required
def kendaraan_detail():
    no_plat, error = normalisasi_plat(request.args.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify(_data_kendaraan(no_plat))


@kendaraan_bp.route("/api/kendaraan/simpan", methods=["POST"])
@login_required
@role_required('SECURITY')
def kendaraan_simpan():
    no_plat, error = _plat_dari_form()
    if error:
        return jsonify({"error": error}), 400
    get_or_create_kendaraan(no_plat, request.form.get("no_stnk", "").strip() or None)
    return jsonify({"message": f"Data truk {no_plat} tersimpan", **_data_kendaraan(no_plat)})


# ===== SUPIR TRUK =====

@kendaraan_bp.route("/api/kendaraan/supir/tambah", methods=["POST"])
@login_required
@role_required('SECURITY')
def kendaraan_supir_tambah():
    no_plat, error = _plat_dari_form()
    if error:
        return jsonify({"error": error}), 400
    id_driver = request.form.get("id_driver", "").strip()
    driver = get_driver_by_id(id_driver) if id_driver.isdigit() else None
    if not driver:
        return jsonify({"error": "Supir tidak ditemukan"}), 404

    id_kendaraan = get_or_create_kendaraan(no_plat)
    is_utama = request.form.get("is_utama") == "1" or not get_supir_kendaraan(id_kendaraan)   # supir pertama otomatis utama
    tambah_supir_kendaraan(id_kendaraan, driver.id_driver, is_utama, current_user.id)
    return jsonify({"message": f"{driver.nama_driver} terdaftar sebagai supir {no_plat}"
                               + (" (utama)" if is_utama else ""), **_data_kendaraan(no_plat)})


@kendaraan_bp.route("/api/kendaraan/supir/utama", methods=["POST"])
@login_required
@role_required('SECURITY')
def kendaraan_supir_utama():
    no_plat, error = _plat_dari_form()
    if error:
        return jsonify({"error": error}), 400
    row = get_kendaraan_by_plat(no_plat)
    id_driver = request.form.get("id_driver", "")
    if not row or not any(str(s["id_driver"]) == id_driver for s in get_supir_kendaraan(row.id_kendaraan)):
        return jsonify({"error": "Supir belum terdaftar di truk ini"}), 404
    tambah_supir_kendaraan(row.id_kendaraan, int(id_driver), True, current_user.id)
    return jsonify({"message": "Supir utama diperbarui", **_data_kendaraan(no_plat)})


@kendaraan_bp.route("/api/kendaraan/supir/hapus", methods=["POST"])
@login_required
@role_required('SECURITY')
def kendaraan_supir_hapus():
    no_plat, error = _plat_dari_form()
    if error:
        return jsonify({"error": error}), 400
    row = get_kendaraan_by_plat(no_plat)
    if not row:
        return jsonify({"error": "Truk belum terdaftar"}), 404
    nonaktifkan_supir_kendaraan(row.id_kendaraan, request.form.get("id_driver"))
    return jsonify({"message": "Supir dilepas dari truk ini (data supir tetap ada)", **_data_kendaraan(no_plat)})


# ===== KONTRAK TRUK - SUPPLIER =====

@kendaraan_bp.route("/api/kendaraan/kontrak/tambah", methods=["POST"])
@login_required
@role_required('SECURITY')
def kendaraan_kontrak_tambah():
    f = request.form
    no_plat, error = _plat_dari_form()
    if error:
        return jsonify({"error": error}), 400
    id_supplier = f.get("id_supplier", "").strip()
    if not id_supplier:
        return jsonify({"error": "Supplier wajib dipilih"}), 400
    jenis = f.get("jenis_transaksi", "").strip() or None
    if jenis and jenis not in JENIS_VALID:
        return jsonify({"error": "Jenis transaksi tidak valid"}), 400
    try:
        mulai = _tanggal(f.get("tanggal_mulai"), wajib=True)
        selesai = _tanggal(f.get("tanggal_selesai"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if selesai and selesai < mulai:
        return jsonify({"error": "Tanggal selesai tidak boleh sebelum tanggal mulai"}), 400

    id_kendaraan = get_or_create_kendaraan(no_plat)
    bentrok = [k for k in get_kontrak_kendaraan(id_kendaraan)
               if str(k["id_supplier"]) == id_supplier and k["status"] in ("AKTIF", "BELUM_MULAI")]
    if bentrok:
        return jsonify({"error": f"Truk ini masih punya kontrak aktif dengan {bentrok[0]['nama_supplier']}. "
                                 "Akhiri dulu kontrak lama."}), 400

    tambah_kontrak(id_kendaraan, int(id_supplier), f.get("id_produk") or None, jenis,
                   f.get("no_kontrak", "").strip() or None, mulai, selesai,
                   f.get("keterangan", "").strip() or None, current_user.id)
    return jsonify({"message": "Kontrak tersimpan", **_data_kendaraan(no_plat)})


@kendaraan_bp.route("/api/kendaraan/kontrak/akhiri", methods=["POST"])
@login_required
@role_required('SECURITY')
def kendaraan_kontrak_akhiri():
    no_plat, error = _plat_dari_form()
    if error:
        return jsonify({"error": error}), 400
    row = get_kendaraan_by_plat(no_plat)
    id_kontrak = request.form.get("id_kontrak", "")
    if not row or not any(str(k["id_kontrak"]) == id_kontrak for k in get_kontrak_kendaraan(row.id_kendaraan)):
        return jsonify({"error": "Kontrak tidak ditemukan untuk truk ini"}), 404
    akhiri_kontrak(int(id_kontrak))
    return jsonify({"message": "Kontrak diakhiri", **_data_kendaraan(no_plat)})
