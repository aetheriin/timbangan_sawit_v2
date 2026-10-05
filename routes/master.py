"""Menu Data Master: Driver (personel kategori DRIVER) & Kendaraan. Tambah / ubah oleh SECURITY dan HO."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from extensions import role_required
from utils import db_master as db
from utils.plat_utils import normalisasi_plat

master_bp = Blueprint("master", __name__)

ROLE_UBAH = ("SECURITY", "HO")


@master_bp.route("/master")
@login_required
def master_halaman():
    return render_template("master/master.html", halaman="master", kategori_tetap="DRIVER",
                           boleh_ubah=current_user.role in ROLE_UBAH, driver_list=db.daftar_driver_aktif())


@master_bp.route("/api/master/kendaraan")
@login_required
def kendaraan_daftar():
    return jsonify(db.daftar_kendaraan((request.args.get("cari") or "").strip().upper()[:20]))


@master_bp.route("/api/master/kendaraan/simpan", methods=["POST"])
@login_required
@role_required(*ROLE_UBAH)
def kendaraan_simpan():
    f = request.form
    id_kendaraan = int(f["id_kendaraan"]) if (f.get("id_kendaraan") or "").isdigit() else None
    no_plat, error = normalisasi_plat(f.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400
    no_stnk = (f.get("no_stnk") or "").strip().upper() or None
    if no_stnk and len(no_stnk) > 50:
        return jsonify({"error": "No. STNK maksimal 50 karakter"}), 400
    teks_supir = (f.get("id_supir_utama") or "").strip()
    id_supir = int(teks_supir) if teks_supir.isdigit() else None
    if id_supir and id_supir not in {d["id_personel"] for d in db.daftar_driver_aktif()}:
        return jsonify({"error": "Supir utama harus driver aktif yang tidak diblacklist"}), 400
    if db.plat_dipakai(no_plat, kecuali=id_kendaraan):
        return jsonify({"error": f"Plat {no_plat} sudah terdaftar"}), 400
    if id_kendaraan is not None:
        lama = db.get_kendaraan(id_kendaraan)
        if not lama:
            return jsonify({"error": "Kendaraan tidak ditemukan"}), 404
        tiket = db.ada_tiket_aktif(id_kendaraan)
        if lama["no_plat"] != no_plat and tiket:
            return jsonify({"error": f"Plat tidak bisa diubah: masih ada tiket aktif {tiket}"}), 400
    db.simpan_kendaraan(id_kendaraan, no_plat, no_stnk, id_supir, current_user.id)
    return jsonify({"message": f"Kendaraan {no_plat} {'diperbarui' if id_kendaraan else 'ditambahkan'}"})


@master_bp.route("/api/master/kendaraan/<int:id_kendaraan>/aktif", methods=["POST"])
@login_required
@role_required(*ROLE_UBAH)
def kendaraan_aktif(id_kendaraan):
    aktif = request.form.get("aktif") in ("1", "true")
    k = db.get_kendaraan(id_kendaraan)
    if not k:
        return jsonify({"error": "Kendaraan tidak ditemukan"}), 404
    if not aktif:
        tiket = db.ada_tiket_aktif(id_kendaraan)
        if tiket:
            return jsonify({"error": f"Masih ada tiket aktif {tiket}, selesaikan dulu"}), 400
    db.set_aktif_kendaraan(id_kendaraan, aktif)
    return jsonify({"message": f"Kendaraan {k['no_plat']} {'diaktifkan' if aktif else 'dinonaktifkan'}"})
