"""Menu Data Master: Driver (personel kategori DRIVER), Kendaraan, Supplier, Produk, Mata Uang & Bank, dan tabel referensi
(utils/db_referensi.py). Aksi sesuai Admin › Hak Akses."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from utils import db_master as db, db_admin, alur, log_aktivitas, kolom_wajib, db_referensi as ref
from utils.plat_utils import normalisasi_plat
from utils.hak_akses import izin, boleh, boleh_lihat, halaman as lihat_halaman
from utils.db_personel import daftar_jenis_sim, daftar_kategori
from utils.db_organisasi import daftar_company

master_bp = Blueprint("master", __name__)

@master_bp.route("/master")
@login_required
@lihat_halaman("MASTER")
def master_halaman():
    return render_template("master/master.html", halaman="master", kategori_tetap="DRIVER",
                           boleh_ubah=boleh("MASTER_DRIVER"), boleh_kendaraan=boleh("MASTER_KENDARAAN"),
                           hak={k: {a: boleh(f"MASTER_{k.upper()}", a) for a in ("tambah", "ubah")} for k in ("mitra", "produk", "keuangan")},
                           grup_supplier_list=ref.opsi("grup_supplier"), rekening_list=ref.opsi("rekening"),
                           driver_list=db.daftar_driver_aktif(), jenis_sim_list=daftar_jenis_sim(),
                           kategori_list=list(daftar_kategori().values()), boleh_kode=boleh("PERSONEL", "ubah"),
                           jenis_kendaraan_list=db.daftar_jenis_kendaraan(),
                           company_list=[c for c in daftar_company() if c["is_active"]],
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
    try:
        kolom_wajib.cek("KENDARAAN", f)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    teks_supir = (f.get("id_supir_utama") or "").strip()
    id_supir = int(teks_supir) if teks_supir.isdigit() else None
    if id_supir and id_supir not in {d["id_personel"] for d in db.daftar_driver_aktif()}:
        return jsonify({"error": "Supir utama harus supir aktif yang tidak diblacklist"}), 400
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
            return jsonify({"error": f"Masih ada tiket aktif {tiket}. Selesaikan tiket tersebut terlebih dahulu"}), 400
    db.set_aktif_kendaraan(id_kendaraan, aktif)
    return jsonify({"message": f"Kendaraan {k['no_plat']} berhasil {'diaktifkan' if aktif else 'dinonaktifkan'}"})


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
            return jsonify({"error": "Level Anda tidak memiliki akses untuk tindakan ini"}), 403
        kode, nama = _teks("kode_supplier", "Kode", maks=20).upper(), _teks("nama_supplier", "Nama")
        peran = [p for p, f in zip(db_admin.PERAN_SUPPLIER, ("is_customer", "is_angkutan")) if request.form.get(f)]
        if not peran:
            raise ValueError("Pilih minimal satu peran: customer / pengangkutan")
        if db_admin.kode_supplier_dipakai(kode, kecuali=id_supplier):
            raise ValueError(f"Kode {kode} sudah dipakai")
        kolom_wajib.cek("SUPPLIER", request.form)
        alamat = (request.form.get("alamat") or "").strip() or None
        if alamat and len(alamat) > 255:
            raise ValueError("Alamat maksimal 255 karakter")
        semua = {c["id_company"] for c in daftar_company()}
        pt = {v.strip().upper() for v in request.form.getlist("company") if v.strip()}
        if pt - semua:
            raise ValueError("Pilih perusahaan dari daftar")
        id_grup, id_rekening = (_pilih_opsional(k, ref.opsi(sumber), label) for k, sumber, label in
                                (("id_grup", "grup_supplier", "grup supplier"), ("id_rekening", "rekening", "rekening")))
        db_admin.simpan_supplier(id_supplier, kode, nama, peran, alamat, pt, id_grup, id_rekening)
        _catat("MITRA_UBAH" if id_supplier else "MITRA_TAMBAH", kode, nama)
        return jsonify({"message": f"Supplier {nama} berhasil disimpan."})
    return _jalankan(aksi)


def _pilih_opsional(nama, opsi, label):
    """id pilihan opsional dari form; kosong = None. ValueError bila tidak ada di daftar."""
    teks = (request.form.get(nama) or "").strip()
    if not teks:
        return None
    if not teks.isdigit() or int(teks) not in {o["id"] for o in opsi}:
        raise ValueError(f"Pilih {label} dari daftar")
    return int(teks)


@master_bp.route("/api/master/mitra/<int:id_supplier>/aktif", methods=["POST"])
@login_required
@izin('MASTER_MITRA', 'ubah')
def mitra_aktif(id_supplier):
    aktif = request.form.get("aktif") in ("1", "true")
    db_admin.set_aktif_supplier(id_supplier, aktif)
    _catat("MITRA_AKTIF" if aktif else "MITRA_NONAKTIF", id_supplier)
    return jsonify({"message": "Supplier berhasil " + ("diaktifkan." if aktif else "dinonaktifkan.")})


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
            return jsonify({"error": "Level Anda tidak memiliki akses untuk tindakan ini"}), 403
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
        return jsonify({"message": f"Produk {nama} berhasil disimpan"})
    return _jalankan(aksi)


@master_bp.route("/api/master/produk/<int:id_produk>/aktif", methods=["POST"])
@login_required
@izin('MASTER_PRODUK', 'ubah')
def produk_aktif(id_produk):
    aktif = request.form.get("aktif") in ("1", "true")
    db_admin.set_aktif_produk(id_produk, aktif)
    _catat("PRODUK_AKTIF" if aktif else "PRODUK_NONAKTIF", id_produk)
    return jsonify({"message": "Produk berhasil " + ("diaktifkan" if aktif else "dinonaktifkan")})


# ===== JENIS KENDARAAN (kapasitas, migrasi 032) =====
@master_bp.route("/api/master/jenis-kendaraan")
@login_required
def jenis_kendaraan_daftar():
    return jsonify(db.daftar_jenis_kendaraan(semua=True))


def _angka_opsional(nama, label, maks):
    teks = (request.form.get(nama) or "").strip().replace(",", ".")
    if not teks:
        return None
    try:
        nilai = float(teks)
    except ValueError:
        raise ValueError(f"{label} harus berupa angka")
    if nilai < 0 or nilai > maks:
        raise ValueError(f"{label} 0 sampai {maks:,.0f}".replace(",", "."))
    return nilai


@master_bp.route("/api/master/jenis-kendaraan/simpan", methods=["POST"])
@login_required
@izin('MASTER_KENDARAAN', 'tambah', 'ubah')
def jenis_kendaraan_simpan():
    def aksi():
        teks_id = (request.form.get("id_jenis_kendaraan") or "").strip()
        id_jenis = int(teks_id) if teks_id.isdigit() else None
        if not boleh("MASTER_KENDARAAN", "ubah" if id_jenis else "tambah"):
            return jsonify({"error": "Level Anda tidak memiliki akses untuk tindakan ini"}), 403
        kode = _teks("kode", "Kode", maks=20).upper().replace(" ", "_")
        nama = _teks("nama", "Nama", maks=50)
        berat_kosong = _angka_opsional("berat_kosong_kg", "Berat kosong", 100000)
        muatan = _angka_opsional("muatan_maks_kg", "Muatan maksimal", 200000)
        kursi = _angka_opsional("kursi", "Jumlah kursi", 99)
        db.simpan_jenis_kendaraan(id_jenis, kode, nama, berat_kosong, muatan, int(kursi) if kursi is not None else None)
        _catat("JENIS_KENDARAAN_UBAH" if id_jenis else "JENIS_KENDARAAN_TAMBAH", kode, nama)
        return jsonify({"message": f"Jenis kendaraan {nama} berhasil disimpan."})
    return _jalankan(aksi)


@master_bp.route("/api/master/jenis-kendaraan/<int:id_jenis>/aktif", methods=["POST"])
@login_required
@izin('MASTER_KENDARAAN', 'ubah')
def jenis_kendaraan_aktif(id_jenis):
    def aksi():
        aktif = request.form.get("aktif") in ("1", "true")
        db.set_aktif_jenis_kendaraan(id_jenis, aktif)
        _catat("JENIS_KENDARAAN_AKTIF" if aktif else "JENIS_KENDARAAN_NONAKTIF", id_jenis)
        return jsonify({"message": "Jenis kendaraan berhasil " + ("diaktifkan." if aktif else "dinonaktifkan.")})
    return _jalankan(aksi)


# ===== TABEL REFERENSI (Mata Uang, Bank, Rekening, Jenis & Grup Supplier, Jenis & Harga Produk) =====
def _ref(jenis, *aksi):
    """Konfigurasi jenis + cek hak menu-nya. (None, respons error) bila tidak boleh."""
    if jenis not in ref.REF:
        return None, (jsonify({"error": "Data tidak dikenal"}), 404)
    menu = ref.REF[jenis]["menu"]
    if not (boleh(menu, *aksi) if aksi else boleh_lihat(menu)):
        return None, (jsonify({"error": "Level Anda tidak memiliki akses untuk tindakan ini"}), 403)
    return ref.REF[jenis], None


@master_bp.route("/api/master/ref/<jenis>")
@login_required
def ref_daftar(jenis):
    _, gagal = _ref(jenis)
    if gagal:
        return gagal
    return jsonify({**ref.info(jenis), "data": ref.daftar(jenis), "pilihan": ref.pilihan(jenis),
                    "boleh_tambah": boleh(ref.REF[jenis]["menu"], "tambah"), "boleh_ubah": boleh(ref.REF[jenis]["menu"], "ubah")})


@master_bp.route("/api/master/ref/<jenis>/simpan", methods=["POST"])
@login_required
def ref_simpan(jenis):
    id_baris = request.form.get("id", type=int)
    c, gagal = _ref(jenis, "ubah" if id_baris else "tambah")
    if gagal:
        return gagal
    def aksi():
        id_baru = ref.simpan(jenis, id_baris, request.form, current_user.id)
        _catat(f"REF_{'UBAH' if id_baris else 'TAMBAH'}", f"{c['tabel']}:{id_baru}")
        return jsonify({"message": f"{c['judul']} berhasil disimpan", "id": id_baru})
    return _jalankan(aksi)


@master_bp.route("/api/master/ref/<jenis>/<int:id_baris>/aktif", methods=["POST"])
@login_required
def ref_aktif(jenis, id_baris):
    c, gagal = _ref(jenis, "ubah")
    if gagal:
        return gagal
    aktif = request.form.get("aktif") in ("1", "true")
    def aksi():
        ref.set_aktif(jenis, id_baris, aktif)
        _catat("REF_AKTIF" if aktif else "REF_NONAKTIF", f"{c['tabel']}:{id_baris}")
        return jsonify({"message": f"{c['judul']} berhasil " + ("diaktifkan." if aktif else "dinonaktifkan.")})
    return _jalankan(aksi)


@master_bp.route("/api/master/ref/<jenis>/<int:id_baris>/void", methods=["POST"])
@login_required
def ref_void(jenis, id_baris):
    c, gagal = _ref(jenis, "ubah")
    if gagal:
        return gagal
    def aksi():
        ref.batalkan(jenis, id_baris, current_user.id)
        _catat("REF_VOID", f"{c['tabel']}:{id_baris}")
        return jsonify({"message": f"{c['judul']} dibatalkan"})
    return _jalankan(aksi)
