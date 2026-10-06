"""API untuk agen_timbang.py di PC jembatan (mode AGEN): ambil pengaturan port, kirim data mentah indikator.
Dilindungi token perangkat (Admin › Perangkat / Kiosk), sama seperti kiosk kamera."""
from flask import Blueprint, request, jsonify

from utils.keamanan import perangkat_atau_login
from utils.db_jembatan import get_jembatan
from utils.serial_reader import terima_dari_agen, konfigurasi

agen_bp = Blueprint("agen", __name__)
MAKS_TEKS = 8000


def _jembatan_agen(id_jembatan):
    j = get_jembatan(id_jembatan)
    if j is None or not j["is_active"]:
        return None, (jsonify({"error": f"Jembatan id {id_jembatan} tidak ada / nonaktif"}), 404)
    if j["mode"] != "AGEN":
        return None, (jsonify({"error": f"Jembatan {j['kode']} memakai mode Lokal. Ubah sumber data ke "
                                        "'Agen di PC jembatan' di Admin › Perangkat / Kiosk."}), 409)
    return j, None


@agen_bp.route("/api/agen/jembatan/<int:id_jembatan>/konfigurasi")
@perangkat_atau_login
def agen_konfigurasi(id_jembatan):
    j, salah = _jembatan_agen(id_jembatan)
    if salah:
        return salah
    cfg = konfigurasi(id_jembatan)
    if cfg is None:
        return jsonify({"error": "Pembaca jembatan belum siap, coba lagi"}), 503
    return jsonify({**cfg, "kode": j["kode"], "nama": j["nama"]})


@agen_bp.route("/api/agen/jembatan/<int:id_jembatan>/data", methods=["POST"])
@perangkat_atau_login
def agen_data(id_jembatan):
    j, salah = _jembatan_agen(id_jembatan)
    if salah:
        return salah
    isi = request.get_json(silent=True) or {}
    teks = str(isi.get("teks") or "")[-MAKS_TEKS:]
    versi = terima_dari_agen(id_jembatan, teks, bool(isi.get("terhubung", True)), isi.get("error"))
    if versi is None:
        return jsonify({"error": "Pembaca jembatan belum siap"}), 503
    return jsonify({"versi": versi})
