"""Endpoint sistem: /health (pemantauan) dan /berkas/... (file upload privat, wajib login)."""
import os
import time
from flask import Blueprint, jsonify, request, send_file, abort
from flask_login import login_required, current_user
from utils.db_utils import cek_koneksi_db
from utils.serial_reader import semua_status
from utils.upload_utils import path_disk_dari_relatif
from utils import face_cache

sistem_bp = Blueprint('sistem', __name__)
_MULAI = time.time()


@sistem_bp.route("/health")
def health():
    try:
        db_ok, db_pesan = cek_koneksi_db(), "ok"
    except Exception as e:      # noqa: BLE001 - laporkan, jangan crash
        db_ok, db_pesan = False, type(e).__name__
    kode = 200 if db_ok else 503
    # Rincian hanya untuk user login atau PC server sendiri; publik cukup status
    if not (current_user.is_authenticated or request.remote_addr in ("127.0.0.1", "::1")):
        return jsonify({"status": "ok" if db_ok else "gangguan"}), kode
    serial = semua_status()
    return jsonify({
        "status": "ok" if db_ok else "gangguan",
        "database": {"ok": db_ok, "pesan": db_pesan},
        "timbangan_serial": {port: {"terhubung": bool(st["terhubung"])} for port, st in serial.items()},
        "cache_wajah": {"dimuat": face_cache._data is not None,
                        "jumlah": len(face_cache._data) if face_cache._data is not None else 0},
        "uptime_detik": int(time.time() - _MULAI),
    }), kode


@sistem_bp.route("/berkas/<path:relatif>")
@login_required
def berkas(relatif):
    """Foto wajah, surat blacklist, snapshot absensi. Path di DB: 'uploads/...'."""
    path = path_disk_dari_relatif(relatif)
    if not path or not os.path.isfile(path):
        abort(404)
    resp = send_file(path, max_age=3600, conditional=True)
    resp.cache_control.private = True          # boleh di-cache browser user ini saja, tidak di proxy
    resp.headers["Content-Disposition"] = "inline"
    return resp
