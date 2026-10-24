"""Dashboard harga: semua role non-admin melihat, HO mengisi."""
from datetime import date

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from utils.area import area_data, company_user
from utils.area_filter import area_cocok
from utils.db_dashboard import KOLOM, riwayat_harga, simpan_harga, arus_hari_ini
from utils.db_jembatan import daftar_jembatan
from utils.db_organisasi import daftar_area, daftar_company
from utils.serial_reader import baca_status
from utils.hak_akses import izin, boleh, halaman as lihat_halaman

dashboard_bp = Blueprint("dashboard", __name__)
BATAS = {"harga_cpo": (0, 1_000_000), "harga_kernel": (0, 1_000_000), "oer_cpo": (0, 100), "biaya_olah": (0, 1_000_000)}


def _company_harga(user_id):
    """Perusahaan yang harganya boleh dilihat / diisi user: yang punya area operasional (bukan kantor pusat)
    dan termasuk cakupan user. [{id_company, nama}] urut nama."""
    pt = company_user(user_id)
    operasional = {a["id_company"] for a in daftar_area() if a["is_active"] and not a["is_pusat"]}
    return [{"id_company": c["id_company"], "nama": c["nama"]} for c in daftar_company()
            if c["is_active"] and c["id_company"] in operasional and (pt is None or c["id_company"] in pt)]


def _company_dipilih(user_id, kode):
    daftar = [c["id_company"] for c in _company_harga(user_id)]
    if kode and kode in daftar:
        return kode
    if kode:
        raise ValueError("Perusahaan tidak valid")
    return daftar[0] if daftar else None


@dashboard_bp.route("/dashboard")
@login_required
@lihat_halaman("DASHBOARD")
def dashboard_halaman():
    """HO (area pusat) bisa memilih site untuk Arus Penimbangan & Status Jembatan; akun site hanya site-nya."""
    id_area = area_data(current_user.id)
    if id_area is None or isinstance(id_area, tuple):      # kantor pusat: semua site, atau site PT yang dikelola
        area_list = [a for a in daftar_area() if a["is_active"] and not a["is_pusat"] and area_cocok(id_area, a["id_comp_area"])]
        area_saya = None
    else:
        area_list = []
        area_saya = next((a["label"] for a in daftar_area() if a["id_comp_area"] == id_area), "")
    return render_template("dashboard/dashboard.html", halaman="dashboard", boleh_ubah=boleh("DASHBOARD", "ubah"),
                           company_harga=_company_harga(current_user.id), is_pusat=id_area is None or isinstance(id_area, tuple), area_list=area_list, area_saya=area_saya)


@dashboard_bp.route("/api/dashboard/harga")
@login_required
def dashboard_harga():
    """?company=<kode> (kosong = perusahaan pertama yang boleh dilihat)."""
    hari = min(max(request.args.get("hari", 30, type=int), 7), 365)
    try:
        id_company = _company_dipilih(current_user.id, (request.args.get("company") or "").strip().upper())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if id_company is None:
        return jsonify([])
    return jsonify([{**{k: (float(r[k]) if r[k] is not None else None) for k in (*KOLOM, "qty_rsi")},
                     "tanggal": r["tanggal"].strftime("%Y-%m-%d"), "oleh": r["oleh"]} for r in riwayat_harga(id_company, hari)])


@dashboard_bp.route("/api/dashboard/harga/simpan", methods=["POST"])
@login_required
@izin('DASHBOARD', 'ubah')
def dashboard_harga_simpan():
    try:
        id_company = _company_dipilih(current_user.id, (request.form.get("company") or "").strip().upper())
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if id_company is None:
        return jsonify({"error": "Pilih perusahaan"}), 400
    try:
        tanggal = date.fromisoformat(request.form.get("tanggal", ""))
        teks_rsi = (request.form.get("qty_rsi") or "").strip().replace(",", ".")
        qty_rsi = float(teks_rsi) if teks_rsi else None
        if qty_rsi is not None and not 0 <= qty_rsi <= 1_000_000_000:
            raise ValueError
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
    simpan_harga(id_company, tanggal, nilai, qty_rsi, current_user.id)
    return jsonify({"message": f"Harga {id_company} {tanggal:%d-%m-%Y} berhasil disimpan"})


def _angka(v):
    return float(v) if v is not None else None


@dashboard_bp.route("/api/dashboard/arus")
@login_required
def dashboard_arus():
    """Arus penimbangan hari ini + status jembatan timbang.
    Akun site: selalu area sendiri. HO (area pusat): ?area=<id> untuk satu site, kosong = semua site."""
    id_area = area_data(current_user.id)
    if id_area is None or isinstance(id_area, tuple):      # kantor pusat memilih satu site (dalam PT yang dikelola)
        dipilih = request.args.get("area", type=int)
        id_area = dipilih if dipilih and area_cocok(id_area, dipilih) else id_area
    ringkas, distribusi, per_jam, posisi = arus_hari_ini(id_area)
    try:
        jembatan = [j for j in daftar_jembatan() if j["is_active"] and area_cocok(id_area, j["id_comp_area"])]
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
