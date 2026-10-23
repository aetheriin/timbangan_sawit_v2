"""Menu Kontrak & DO (role HO) + pencarian DO untuk Form Security."""
from datetime import date

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from utils import db_kontrak as db, kolom_wajib
from utils.db_utils import get_semua_produk
from utils.hak_akses import izin, boleh, halaman as lihat_halaman
from utils.area import company_user
from utils.db_organisasi import daftar_company
from utils.db_admin import supplier_boleh
from utils.db_blacklist import supplier_diblacklist

kontrak_bp = Blueprint("kontrak", __name__)


def _tgl(d):
    return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else d


def _angka(v):
    return float(v) if v is not None else None


def _json_do(d):
    return {**d, "tanggal_do": _tgl(d["tanggal_do"]), "berlaku_sampai": _tgl(d["berlaku_sampai"]),
            "tanggal_kontrak": _tgl(d["tanggal_kontrak"]), "created_at": _tgl(d["created_at"]),
            "qty_kg": _angka(d["qty_kg"]), "harga_per_kg": _angka(d["harga_per_kg"]), "realisasi_kg": _angka(d.get("realisasi_kg")),
            "angkutan": [{**a, "qty_kg": _angka(a["qty_kg"]), "ongkos_per_kg": _angka(a.get("ongkos_per_kg"))} for a in d["angkutan"]],
            "ppn": bool(d.get("ppn")), "harga_termasuk_ppn": bool(d.get("harga_termasuk_ppn"))}


@kontrak_bp.route("/kontrak")
@login_required
@lihat_halaman("KONTRAK_DO")
def kontrak_halaman():
    """Semua level bisa melihat; tambah / ubah sesuai Admin › Hak Akses (dicek juga di API)."""
    pt = company_user(current_user.id)
    mitra = [m for m in db.daftar_mitra() if supplier_boleh(m["id_supplier"], pt)]
    return render_template("kontrak/kontrak.html", halaman="kontrak", jenis_list=db.JENIS_VALID,
                           boleh_ubah=boleh("KONTRAK_DO"),
                           customer_list=[m for m in mitra if m["peran"] == "CUSTOMER"],
                           angkutan_list=[m for m in mitra if m["peran"] == "PENGANGKUTAN"],
                           company_list=_company_user(),
                           produk_list=get_semua_produk())


@kontrak_bp.route("/api/kontrak/do")
@login_required
def do_daftar():
    return jsonify([_json_do(d) for d in db.daftar_do(request.args.get("cari", ""))])


def _company_user():
    """PT yang boleh dipilih sebagai pemilik kontrak: kantor pusat = semua PT aktif, selain itu PT sendiri."""
    pt = company_user(current_user.id)
    return [c for c in daftar_company() if c["is_active"] and (pt is None or c["id_company"] in pt)]


def _tanggal(nama, wajib, label="Tanggal DO"):
    teks = (request.form.get(nama) or "").strip()
    if not teks:
        if wajib:
            raise ValueError(f"{label} wajib diisi")
        return None
    try:
        return date.fromisoformat(teks)
    except ValueError:
        raise ValueError("Format tanggal tidak valid")


def _id(nama, wajib=True):
    teks = (request.form.get(nama) or "").strip()
    if not teks.isdigit():
        if wajib:
            raise ValueError("Perusahaan wajib dipilih" if nama == "id_company" else f"{nama.replace('id_', '').capitalize()} wajib dipilih")
        return None
    return int(teks)


def _desimal(teks, label):
    teks = (teks or "").strip().replace(",", ".")
    if not teks:
        return None
    try:
        nilai = round(float(teks), 2)
    except ValueError:
        raise ValueError(f"{label} harus angka")
    if not 0 < nilai < 1e12:
        raise ValueError(f"{label} harus lebih dari 0")
    return nilai


def _angkutan_form(qty_kontrak):
    """Baris pengangkutan dari form (angkut_cara[], angkut_nama[], angkut_qty[])."""
    f = request.form
    hasil, kunci = [], set()
    ongkos = f.getlist("angkut_ongkos") or [""] * len(f.getlist("angkut_cara"))
    for cara, nama, qty, biaya in zip(f.getlist("angkut_cara"), f.getlist("angkut_nama"), f.getlist("angkut_qty"), ongkos):
        cara = (cara or "").strip().upper()
        if cara not in db.CARA_ANGKUT:
            raise ValueError("Cara angkut tidak dikenal")
        id_angkut = None
        if cara == "PIHAK_KETIGA":
            if len(nama.strip()) < 3:
                raise ValueError("Nama pengangkutan pihak ketiga wajib diisi")
            id_angkut = db.id_pengangkutan_dari_nama(nama)
        if (cara, id_angkut) in kunci:
            raise ValueError("Pengangkutan yang sama dipilih dua kali")
        kunci.add((cara, id_angkut))
        hasil.append({"cara_angkut": cara, "id_pengangkutan": id_angkut, "qty_kg": _desimal(qty, "Alokasi qty"),
                      "ongkos_per_kg": _desimal(biaya, "Ongkos angkut")})
    if not hasil:
        raise ValueError("Tambahkan minimal satu pengangkutan")
    total = sum(a["qty_kg"] or 0 for a in hasil)
    if qty_kontrak and total > qty_kontrak:
        raise ValueError(f"Total alokasi pengangkutan ({total:,.0f} kg) melebihi qty kontrak ({qty_kontrak:,.0f} kg)")
    return hasil


@kontrak_bp.route("/api/kontrak/do/simpan", methods=["POST"])
@login_required
@izin('KONTRAK_DO', 'tambah', 'ubah')
def do_simpan():
    f = request.form
    try:
        id_do = _id("id_do", wajib=False)
        kolom_wajib.cek("KONTRAK_DO", f)
        d = {"no_do": (f.get("no_do") or "").strip().upper(), "no_kontrak": (f.get("no_kontrak") or "").strip().upper(),
             "jenis_transaksi": (f.get("jenis_transaksi") or "").strip().upper(),
             "id_customer": _id("id_customer"), "id_produk": _id("id_produk"),
             "tanggal_kontrak": _tanggal("tanggal_kontrak", True, "Tanggal kontrak"),
             "qty_kg": _desimal(f.get("qty_kg"), "Qty kontrak"), "harga_per_kg": _desimal(f.get("harga_per_kg"), "Harga"),
             "tanggal_do": _tanggal("tanggal_do", True), "berlaku_sampai": _tanggal("berlaku_sampai", False),
             "keterangan": (f.get("keterangan") or "").strip()[:200] or None,
             "ppn": f.get("ppn") == "1", "harga_termasuk_ppn": f.get("harga_termasuk_ppn") == "1",
             "id_company": (request.form.get("id_company") or "").strip().upper()}
        if d["id_company"] not in {c["id_company"] for c in _company_user()}:
            raise ValueError("Pilih perusahaan pemilik kontrak dari daftar")
        if not d["ppn"]:
            d["harga_termasuk_ppn"] = False
        if not d["no_do"] or not d["no_kontrak"]:
            raise ValueError("No DO dan No Kontrak wajib diisi")
        if len(d["no_do"]) > 50 or len(d["no_kontrak"]) > 50:
            raise ValueError("No DO / No Kontrak maksimal 50 karakter")
        if d["jenis_transaksi"] not in db.JENIS_VALID:
            raise ValueError("Jenis transaksi tidak dikenal")
        if d["berlaku_sampai"] and d["berlaku_sampai"] < d["tanggal_do"]:
            raise ValueError("Berlaku sampai tidak boleh sebelum tanggal DO")
        if (d["id_customer"] not in {m["id_supplier"] for m in db.daftar_mitra() if m["peran"] == "CUSTOMER"}
                or not supplier_boleh(d["id_customer"], company_user(current_user.id))):
            raise ValueError("Pilih customer dari daftar (mitra berperan customer)")
        if d["id_produk"] not in {p.id_produk for p in get_semua_produk()}:
            raise ValueError("Pilih produk dari daftar")
        if db.no_do_dipakai(d["no_do"], kecuali=id_do):
            raise ValueError(f"No DO {d['no_do']} sudah terdaftar")
        if db.no_kontrak_dipakai(d["no_kontrak"], kecuali_do=id_do):
            raise ValueError(f"No Kontrak {d['no_kontrak']} sudah punya DO (1 kontrak = 1 DO)")
        angkutan = _angkutan_form(d["qty_kg"])
        # Supplier Blacklist: tidak boleh dibuatkan kontrak / DO baru (customer maupun pengangkutan)
        for id_s in [d["id_customer"], *[a["id_pengangkutan"] for a in angkutan if a["id_pengangkutan"]]]:
            nama_bl = supplier_diblacklist(id_s)
            if nama_bl:
                raise ValueError(f"{nama_bl} sedang diblacklist (Blacklist › Supplier). Kontrak / DO tidak bisa disimpan.")
        db.simpan_do(id_do, d, angkutan, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": f"DO {d['no_do']} berhasil disimpan"})


@kontrak_bp.route("/api/kontrak/do/<int:id_do>/aktif", methods=["POST"])
@login_required
@izin('KONTRAK_DO', 'ubah')
def do_aktif(id_do):
    aktif = request.form.get("aktif") in ("1", "true")
    try:
        db.set_aktif_do(id_do, aktif)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "DO berhasil " + ("diaktifkan" if aktif else "dinonaktifkan")})


@kontrak_bp.route("/api/do/<path:no_do>")
@login_required
def do_cari(no_do):
    """Form Security: ketik No DO -> data transaksi terisi otomatis."""
    d = db.get_do(no_do.strip().upper())
    if not d:
        return jsonify({"error": f"DO {no_do.upper()} belum terdaftar / tidak aktif / sudah lewat masa berlaku. Hubungi HO."}), 404
    return jsonify(_json_do(d))
