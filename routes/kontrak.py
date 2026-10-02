"""Menu Kontrak & DO (role HO) + pencarian DO untuk Form Security."""
from datetime import date

from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user

from extensions import role_required
from utils import db_kontrak as db
from utils.db_utils import get_semua_produk

kontrak_bp = Blueprint("kontrak", __name__)


def _tgl(d):
    return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else d


def _json_do(d):
    return {**d, "tanggal_do": _tgl(d["tanggal_do"]), "berlaku_sampai": _tgl(d["berlaku_sampai"]),
            "created_at": _tgl(d["created_at"]), "nama_pengangkutan": d["nama_pengangkutan"] or "Kendaraan sendiri"}


@kontrak_bp.route("/kontrak")
@login_required
def kontrak_halaman():
    if current_user.role != "HO":
        abort(403)
    mitra = db.daftar_mitra()
    return render_template("kontrak/kontrak.html", halaman="kontrak", jenis_list=db.JENIS_VALID,
                           customer_list=[m for m in mitra if m["tipe"] == "CUSTOMER"],
                           angkutan_list=[m for m in mitra if m["tipe"] == "PENGANGKUTAN"],
                           produk_list=get_semua_produk())


@kontrak_bp.route("/api/kontrak/do")
@login_required
@role_required("HO")
def do_daftar():
    return jsonify([_json_do(d) for d in db.daftar_do(request.args.get("cari", ""))])


@kontrak_bp.route("/api/kontrak/terakhir")
@login_required
@role_required("HO")
def do_kontrak_terakhir():
    d = db.kontrak_terakhir((request.args.get("no_kontrak") or "").strip().upper())
    return jsonify(_json_do(d) if d else {})


def _tanggal(nama, wajib):
    teks = (request.form.get(nama) or "").strip()
    if not teks:
        if wajib:
            raise ValueError("Tanggal DO wajib diisi")
        return None
    try:
        return date.fromisoformat(teks)
    except ValueError:
        raise ValueError("Format tanggal tidak valid")


def _id(nama, wajib=True):
    teks = (request.form.get(nama) or "").strip()
    if not teks.isdigit():
        if wajib:
            raise ValueError(f"{nama.replace('id_', '').capitalize()} wajib dipilih")
        return None
    return int(teks)


@kontrak_bp.route("/api/kontrak/do/simpan", methods=["POST"])
@login_required
@role_required("HO")
def do_simpan():
    f = request.form
    try:
        id_do = _id("id_do", wajib=False)
        d = {"no_do": (f.get("no_do") or "").strip().upper(), "no_kontrak": (f.get("no_kontrak") or "").strip().upper(),
             "jenis_transaksi": (f.get("jenis_transaksi") or "").strip().upper(),
             "id_customer": _id("id_customer"), "id_produk": _id("id_produk"), "id_pengangkutan": _id("id_pengangkutan", False),
             "tanggal_do": _tanggal("tanggal_do", True), "berlaku_sampai": _tanggal("berlaku_sampai", False),
             "keterangan": (f.get("keterangan") or "").strip()[:200] or None}
        if not d["no_do"] or not d["no_kontrak"]:
            raise ValueError("No DO dan No Kontrak wajib diisi")
        if len(d["no_do"]) > 50 or len(d["no_kontrak"]) > 50:
            raise ValueError("No DO / No Kontrak maksimal 50 karakter")
        if d["jenis_transaksi"] not in db.JENIS_VALID:
            raise ValueError("Jenis transaksi tidak dikenal")
        if d["berlaku_sampai"] and d["berlaku_sampai"] < d["tanggal_do"]:
            raise ValueError("Berlaku sampai tidak boleh sebelum tanggal DO")
        if db.no_do_dipakai(d["no_do"], kecuali=id_do):
            raise ValueError(f"No DO {d['no_do']} sudah terdaftar")
        db.simpan_do(id_do, d, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": f"DO {d['no_do']} disimpan"})


@kontrak_bp.route("/api/kontrak/do/<int:id_do>/aktif", methods=["POST"])
@login_required
@role_required("HO")
def do_aktif(id_do):
    aktif = request.form.get("aktif") in ("1", "true")
    try:
        db.set_aktif_do(id_do, aktif)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"message": "DO " + ("diaktifkan" if aktif else "dinonaktifkan")})


@kontrak_bp.route("/api/do/<path:no_do>")
@login_required
def do_cari(no_do):
    """Form Security: ketik No DO -> data transaksi terisi otomatis."""
    d = db.get_do(no_do.strip().upper())
    if not d:
        return jsonify({"error": f"DO {no_do.upper()} belum terdaftar / tidak aktif / sudah lewat masa berlaku. Hubungi HO."}), 404
    return jsonify(_json_do(d))
