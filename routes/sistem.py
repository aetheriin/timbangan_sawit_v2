"""Endpoint sistem: /health untuk memantau database, timbangan (serial), dan cache wajah."""
import time
from flask import Blueprint, jsonify
from utils.db_utils import cek_koneksi_db
from utils.serial_reader import baca_status_asli
from utils import face_cache

sistem_bp = Blueprint('sistem', __name__)
_MULAI = time.time()


@sistem_bp.route("/health")
def health():
    try:
        db_ok, db_pesan = cek_koneksi_db(), "ok"
    except Exception as e:      # noqa: BLE001 - laporkan, jangan crash
        db_ok, db_pesan = False, type(e).__name__
    serial = baca_status_asli()
    data = {
        "status": "ok" if db_ok else "gangguan",
        "database": {"ok": db_ok, "pesan": db_pesan},
        "timbangan_serial": {"terhubung": bool(serial.get("terhubung"))},
        "cache_wajah": {"dimuat": face_cache._data is not None,
                        "jumlah": len(face_cache._data) if face_cache._data is not None else 0},
        "uptime_detik": int(time.time() - _MULAI),
    }
    return jsonify(data), (200 if db_ok else 503)
