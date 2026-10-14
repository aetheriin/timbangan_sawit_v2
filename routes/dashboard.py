"""Dashboard harga: semua role non-admin melihat, HO mengisi."""
from datetime import date

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from utils import pengaturan
from utils.area import area_data
from utils.db_dashboard import KOLOM, riwayat_harga, simpan_harga, arus_hari_ini
from utils.db_jembatan import daftar_jembatan
from utils.db_organisasi import daftar_area
from utils.serial_reader import baca_status
from utils.hak_akses import izin, boleh

dashboard_bp = Blueprint("dashboard", __name__)
BATAS = {"harga_cpo": (0, 1_000_000), "harga_kernel": (0, 1_000_000), "oer_cpo": (0, 100), "biaya_olah": (0, 1_000_000)}


@dashboard_bp.route("/dashboard")
@login_required
def dashboard_halaman():
    """HO (area pusat) bisa memilih site untuk Arus Penimbangan & Status Jembatan; akun site hanya site-nya."""
    id_area = area_data(current_user.id)
    if id_area is None:
        pusat = str(pengaturan.nilai("AREA_PUSAT") or "")
        area_list = [a for a in daftar_area() if a["is_active"] and str(a["id_comp_area"]) != pusat]   # kantor pusat bukan site
        area_saya = None
    else:
        area_list = []
        area_saya = next((a["nama"] for a in daftar_area() if a["id_comp_area"] == id_area), "")
    return render_template("dashboard/dashboard.html", halaman="dashboard", boleh_ubah=boleh("DASHBOARD", "ubah"),
                           area_list=area_list, area_saya=area_saya)


@dashboard_bp.route("/api/dashboard/harga")
@login_required
def dashboard_harga():
    hari = min(max(request.args.get("hari", 30, type=int), 7), 365)
    return jsonify([{**{k: (float(r[k]) if r[k] is not None else None) for k in KOLOM},
                     "tanggal": r["tanggal"].strftime("%Y-%m-%d"), "oleh": r["oleh"]} for r in riwayat_harga(hari)])


@dashboard_bp.route("/api/dashboard/harga/simpan", methods=["POST"])
@login_required
@izin('DASHBOARD', 'ubah')
def dashboard_harga_simpan():
    try:
        tanggal = date.fromisoformat(request.form.get("tanggal", ""))
        nilai = []
        for k in KOLOM:
            v = float(request.form.get(k, "").replace(",", "."))
            if not BATAS[k][0] <= v <= BATAS[k][1]:
                raise ValueError
            nilai.append(v)
    except ValueError:
        return jsonify({"error": "Tanggal dan semua nilai wajib diisi angka yang wajar (OER 0 - 100 %)"}), 400
    if tanggal > date.today():
        return jsonify({"error": "Tanggal tidak boleh setelah hari ini"}), 400
    simpan_harga(tanggal, nilai, current_user.id)
    return jsonify({"message": f"Harga {tanggal:%d-%m-%Y} berhasil disimpan"})


def _angka(v):
    return float(v) if v is not None else None


@dashboard_bp.route("/api/dashboard/arus")
@login_required
def dashboard_arus():
    """Arus penimbangan hari ini + status jembatan timbang.
    Akun site: selalu area sendiri. HO (area pusat): ?area=<id> untuk satu site, kosong = semua site."""
    id_area = area_data(current_user.id)
    if id_area is None:
        id_area = request.args.get("area", type=int) or None
    ringkas, distribusi, per_jam, posisi = arus_hari_ini(id_area)
    try:
        jembatan = [j for j in daftar_jembatan() if j["is_active"] and (id_area is None or j["id_comp_area"] == id_area)]
    except Exception:       # noqa: BLE001 - tabel jembatan belum ada
        jembatan = []
    status = []
    for j in jembatan:
        st = baca_status(j["id_jembatan"])
        status.append({"kode": j["kode"], "nama": j["nama"], "area": j["area"], "terhubung": bool(st.get("terhubung")),
                       "berat": st.get("berat"), "stabil": bool(st.get("stabil")), "error": st.get("error")})
    return jsonify({
        "ringkas": {k: _angka(v) for k, v in ringkas.items()},
        "distribusi": [{"produk": r["produk"], "netto": _angka(r["netto"])} for r in distribusi],
        "per_jam": per_jam,
        "posisi": posisi,
        "jembatan": status,
    })
