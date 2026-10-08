"""Menu Data Master: Driver (personel kategori DRIVER), Kendaraan, Mitra, Produk. Aksi sesuai Admin › Hak Akses."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from utils import db_master as db, db_admin, alur, log_aktivitas
from utils.plat_utils import normalisasi_plat
from utils.hak_akses import izin, boleh
from utils.db_personel import daftar_jenis_sim, daftar_kategori

master_bp = Blueprint("master", __name__)

@master_bp.route("/master")
@login_required
def master_halaman():
    return render_template("master/master.html", halaman="master", kategori_tetap="DRIVER",
                           boleh_ubah=boleh("MASTER_DRIVER"), boleh_kendaraan=boleh("MASTER_KENDARAAN"),
                           hak={k: {a: boleh(f"MASTER_{k.upper()}", a) for a in ("tambah", "ubah")} for k in ("mitra", "produk")},
                           driver_list=db.daftar_driver_aktif(), jenis_sim_list=daftar_jenis_sim(),
                           kategori_list=list(daftar_kategori().values()), boleh_kode=boleh("PERSONEL", "ubah"),
                           jenis_kendaraan_list=db.daftar_jenis_kendaraan(),
                           alur_list=alur.daftar_alur(), kategori_produk=db_admin.KATEGORI_PRODUK)


@master_bp.route("/api/master/kendaraan")
@login_required
def kendaraan_daftar():
    return jsonify(db.daftar_kendaraan((request.args.get("cari") or "").strip().upper()[:20]))


@master_bp.route("/api/master/kendaraan/simpan", methods=["POST"])
@login_required
@izin('MASTER_KENDARAAN', 'tambah', 'ubah')
def kendaraan_simpan():
    f = request.form
    id_kendaraan = int(f["id_kendaraan"]) if (f.get("id_kendaraan") or "").isdigit() else None
    no_plat, error = normalisasi_plat(f.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400
    no_stnk = (f.get("no_stnk") or "").strip().upper()
    if not no_stnk:
        return jsonify({"error": "No. STNK wajib diisi"}), 400
    if len(no_stnk) > 50:
        return jsonify({"error": "No. STNK maksimal 50 karakter"}), 400
    teks_jenis = (f.get("id_jenis_kendaraan") or "").strip()
    if not teks_jenis.isdigit() or int(teks_jenis) not in {j["id_jenis_kendaraan"] for j in db.daftar_jenis_kendaraan()}:
        return jsonify({"error": "Pilih jenis kendaraan"}), 400
    teks_supir = (f.get("id_supir_utama") or "").strip()
    id_supir = int(teks_supir) if teks_supir.isdigit() else None
    if id_supir and id_supir not in {d["id_personel"] for d in db.daftar_driver_aktif()}:
        return jsonify({"error": "Supir utama harus driver aktif yang tidak diblacklist"}), 400
    if db.plat_dipakai(no_plat, kecuali=id_kendaraan):
        return jsonify({"error": f"Plat {no_plat} sudah terdaftar"}), 400
    plat_stnk = db.stnk_dipakai(no_stnk, kecuali=id_kendaraan)
    if plat_stnk:
        return jsonify({"error": f"No. STNK {no_stnk} sudah dipakai kendaraan {plat_stnk}"}), 400
    if id_kendaraan is not None:
        lama = db.get_kendaraan(id_kendaraan)
        if not lama:
            return jsonify({"error": "Kendaraan tidak ditemukan"}), 404
        tiket = db.ada_tiket_aktif(id_kendaraan)
        if lama["no_plat"] != no_plat and tiket:
            return jsonify({"error": f"Plat tidak bisa diubah: masih ada tiket aktif {tiket}"}), 400
    db.simpan_kendaraan(id_kendaraan, no_plat, no_stnk, id_supir, current_user.id, int(teks_jenis))
    return jsonify({"message": f"Kendaraan {no_plat} {'diperbarui' if id_kendaraan else 'ditambahkan'}"})


@master_bp.route("/api/master/kendaraan/<int:id_kendaraan>/aktif", methods=["POST"])
@login_required
@izin('MASTER_KENDARAAN', 'ubah')
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


# ===== MITRA (customer / pengangkutan) & PRODUK =====
def _teks(nama, label, maks=100):
    nilai = (request.form.get(nama) or "").strip()
    if not nilai:
        raise ValueError(f"{label} wajib diisi")
    if len(nilai) > maks:
        raise ValueError(f"{label} maksimal {maks} karakter")
    return nilai


def _jalankan(fn):
    try:
        return fn()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


def _catat(aksi, target, detail=None):
    log_aktivitas.catat("MASTER", aksi, id_baris=str(target)[:100], baru={"detail": detail} if detail else None,
                        user_id=current_user.id, ip=request.remote_addr)


@master_bp.route("/api/master/mitra")
@login_required
def mitra_daftar():
    return jsonify([{**s, "created_at": s["created_at"].strftime("%Y-%m-%d") if s["created_at"] else None}
                    for s in db_admin.daftar_supplier()])


@master_bp.route("/api/master/mitra/simpan", methods=["POST"])
@login_required
@izin('MASTER_MITRA', 'tambah', 'ubah')
def mitra_simpan():
    def aksi():
        id_supplier = int(request.form.get("id_supplier") or 0) or None
        if not boleh("MASTER_MITRA", "ubah" if id_supplier else "tambah"):
            return jsonify({"error": "Level Anda tidak punya akses untuk aksi ini"}), 403
        kode, nama = _teks("kode_supplier", "Kode", maks=20).upper(), _teks("nama_supplier", "Nama")
        peran = [p for p, f in zip(db_admin.PERAN_SUPPLIER, ("is_customer", "is_angkutan")) if request.form.get(f)]
        if not peran:
            raise ValueError("Pilih minimal satu peran: customer / pengangkutan")
        if db_admin.kode_supplier_dipakai(kode, kecuali=id_supplier):
            raise ValueError(f"Kode {kode} sudah dipakai")
        db_admin.simpan_supplier(id_supplier, kode, nama, peran)
        _catat("MITRA_UBAH" if id_supplier else "MITRA_TAMBAH", kode, nama)
        return jsonify({"message": f"Mitra {nama} disimpan"})
    return _jalankan(aksi)


@master_bp.route("/api/master/mitra/<int:id_supplier>/aktif", methods=["POST"])
@login_required
@izin('MASTER_MITRA', 'ubah')
def mitra_aktif(id_supplier):
    aktif = request.form.get("aktif") in ("1", "true")
    db_admin.set_aktif_supplier(id_supplier, aktif)
    _catat("MITRA_AKTIF" if aktif else "MITRA_NONAKTIF", id_supplier)
    return jsonify({"message": "Mitra " + ("diaktifkan" if aktif else "dinonaktifkan")})


@master_bp.route("/api/master/produk")
@login_required
def produk_daftar():
    return jsonify(db_admin.daftar_produk())


@master_bp.route("/api/master/produk/simpan", methods=["POST"])
@login_required
@izin('MASTER_PRODUK', 'tambah', 'ubah')
def produk_simpan():
    def aksi():
        id_produk = int(request.form.get("id_produk") or 0) or None
        if not boleh("MASTER_PRODUK", "ubah" if id_produk else "tambah"):
            return jsonify({"error": "Level Anda tidak punya akses untuk aksi ini"}), 403
        nama, kategori = _teks("nama_produk", "Nama produk"), _teks("kategori", "Kategori").upper()
        if kategori not in db_admin.KATEGORI_PRODUK:
            raise ValueError("Kategori tidak dikenal")
        if db_admin.nama_produk_dipakai(nama, kecuali=id_produk):
            raise ValueError(f"Produk {nama} sudah ada")
        teks_alur = (request.form.get("id_alur") or "").strip()
        if not teks_alur.isdigit() or int(teks_alur) not in {a["id_alur"] for a in alur.daftar_alur()}:
            raise ValueError("Pilih alur dari daftar")
        db_admin.simpan_produk(id_produk, nama, kategori, int(teks_alur))
        _catat("PRODUK_UBAH" if id_produk else "PRODUK_TAMBAH", nama, kategori)
        return jsonify({"message": f"Produk {nama} disimpan"})
    return _jalankan(aksi)


@master_bp.route("/api/master/produk/<int:id_produk>/aktif", methods=["POST"])
@login_required
@izin('MASTER_PRODUK', 'ubah')
def produk_aktif(id_produk):
    aktif = request.form.get("aktif") in ("1", "true")
    db_admin.set_aktif_produk(id_produk, aktif)
    _catat("PRODUK_AKTIF" if aktif else "PRODUK_NONAKTIF", id_produk)
    return jsonify({"message": "Produk " + ("diaktifkan" if aktif else "dinonaktifkan")})
