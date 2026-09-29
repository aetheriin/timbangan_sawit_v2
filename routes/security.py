import os
import uuid
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import role_required, UPLOAD_FOLDER, camera_trigger_state
from utils.face_utils import (extract_embedding, embedding_to_binary, binary_to_embedding,
                              compare_faces, verifikasi_liveness)
from utils.verifikasi_state import set_terverifikasi, get_verifikasi, reset_verifikasi
from utils.db_utils import (
    cari_transaksi_aktif, buat_transaksi_full, get_list_tiket_aktif, get_history_driver,
    get_driver_by_id, cari_driver_by_nik, cek_nik_ada, cari_wajah_mirip_driver,
    insert_driver, update_driver_dengan_audit, get_all_driver_embeddings
)

security_bp = Blueprint('security', __name__)

@security_bp.route("/api/security/list-tiket-aktif")
@login_required
def list_tiket_aktif():
    return jsonify(get_list_tiket_aktif())

@security_bp.route("/api/security/history-driver")
@login_required
def history_driver():
    return jsonify(get_history_driver())

@security_bp.route("/api/security/buat-tiket", methods=["POST"])
@login_required
@role_required('SECURITY')
def buat_tiket():
    f = request.form
    no_tiket = f.get("no_tiket", "").strip()
    no_plat = f.get("no_plat", "").strip().upper()
    jenis = f.get("jenis_transaksi", "").strip()
    id_supplier, id_produk, id_driver = f.get("id_supplier"), f.get("id_produk"), f.get("id_driver")

    if not all([no_tiket, no_plat, jenis, id_supplier, id_produk, id_driver]):
        return jsonify({"error": "Semua field wajib diisi"}), 400

    existing = cari_transaksi_aktif(no_plat=no_plat)
    if existing:
        return jsonify({"error": f"Plat ini sudah punya tiket aktif: {existing.no_tiket}"}), 400

    if os.getenv("WAJIB_SCAN_WAJAH", "true").lower() == "true":
        v = get_verifikasi()
        if not v or str(v["id_driver"]) != str(id_driver):
            return jsonify({"error": "Supir belum terverifikasi wajah. Lakukan Scan Wajah dulu."}), 400

    buat_transaksi_full(no_tiket, no_plat, f.get("no_stnk", "").strip() or None, jenis,
                        id_supplier, id_produk, id_driver, f.get("no_do", "").strip() or None,
                        current_user.id)

    reset_verifikasi()
    return jsonify({"message": "Tiket berhasil dibuat & tervalidasi", "no_tiket": no_tiket}), 200

# ===== DRIVER =====

@security_bp.route("/api/driver/cari-by-nik", methods=["POST"])
@login_required
def driver_cari_nik():
    row = cari_driver_by_nik(request.form.get("nik", "").strip())
    if not row:
        return jsonify({"status": "TIDAK_DITEMUKAN"}), 200
    return jsonify({"status": "DITEMUKAN", "id_driver": row.id_driver, "nik": row.nik,
                    "nama": row.nama_driver, "no_sim": row.no_sim,
                    "is_updated": bool(row.is_updated), "foto_path": row.foto_path}), 200

def _simpan_foto(file):
    filename = f"{uuid.uuid4().hex}{os.path.splitext(file.filename)[1]}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return filepath, filename

@security_bp.route("/api/driver/tambah", methods=["POST"])
@login_required
@role_required('SECURITY')
def driver_tambah():
    nik = request.form.get("nik", "").strip()
    nama = request.form.get("nama", "").strip()
    no_sim = request.form.get("no_sim", "").strip()
    file = request.files.get("foto")

    if not all([nik, nama, no_sim, file]):
        return jsonify({"error": "Semua field wajib diisi, termasuk foto wajah"}), 400
    if cek_nik_ada(nik):
        return jsonify({"error": f"NIK '{nik}' sudah terdaftar"}), 400

    filepath, filename = _simpan_foto(file)
    embedding = extract_embedding(filepath)
    if embedding is None:
        os.remove(filepath)
        return jsonify({"error": "Wajah tidak terdeteksi"}), 400
    mirip = cari_wajah_mirip_driver(embedding)
    if mirip:
        os.remove(filepath)
        return jsonify({"error": f"Wajah sudah terdaftar sebagai '{mirip[1]}'"}), 400

    foto_path = f"uploads/{filename}"
    driver_id = insert_driver(nik, nama, no_sim, embedding_to_binary(embedding), foto_path)
    set_terverifikasi(driver_id, nama, nik, no_sim, False, foto_path)  
    return jsonify({"message": f"Supir '{nama}' berhasil ditambahkan",
                    "id_driver": driver_id, "foto_path": foto_path}), 200

@security_bp.route("/api/driver/update-identitas", methods=["POST"])
@login_required
@role_required('SECURITY')
def driver_update_identitas():
    f = request.form
    id_driver, nik, nama, no_sim = f.get("id_driver", "").strip(), f.get("nik", "").strip(), \
        f.get("nama", "").strip(), f.get("no_sim", "").strip()
    file = request.files.get("foto")

    if not all([id_driver, nik, nama, no_sim]):
        return jsonify({"error": "Semua field wajib diisi"}), 400
    if cek_nik_ada(nik, exclude_id=int(id_driver)):
        return jsonify({"error": f"NIK '{nik}' sudah dipakai supir lain"}), 400

    embedding_binary, foto_path = None, None
    if file and file.filename:
        filepath, filename = _simpan_foto(file)
        embedding = extract_embedding(filepath)
        if embedding is None:
            os.remove(filepath)
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400
        embedding_binary, foto_path = embedding_to_binary(embedding), f"uploads/{filename}"

    update_driver_dengan_audit(int(id_driver), nik, nama, no_sim, current_user.id, embedding_binary, foto_path)
    d = get_driver_by_id(int(id_driver))
    v = get_verifikasi()
    if v and str(v["id_driver"]) == str(id_driver):
        set_terverifikasi(d.id_driver, d.nama_driver, d.nik, d.no_sim, True, d.foto_path)
    return jsonify({
        "message": f"Data '{nama}' diperbarui, tercatat di audit log",
        "driver": {"id_driver": d.id_driver, "nik": d.nik, "nama": d.nama_driver,
                   "no_sim": d.no_sim, "is_updated": True, "foto_path": d.foto_path}
    }), 200

# ===== KAMERA KIOSK & VERIFIKASI WAJAH =====

@security_bp.route("/api/kamera/start", methods=["POST"])
def kamera_start():
    camera_trigger_state["is_active"] = True
    reset_verifikasi()
    return jsonify({"status": "SUCCESS"}), 200

@security_bp.route("/api/kamera/status")
def kamera_status():
    return jsonify({"is_active": camera_trigger_state["is_active"]}), 200

@security_bp.route("/api/kamera/batal", methods=["POST"])
def kamera_batal():
    camera_trigger_state["is_active"] = False
    reset_verifikasi()
    return jsonify({"status": "SUCCESS"}), 200

@security_bp.route("/api/verifikasi-wajah", methods=["POST"])
def verifikasi_wajah():
    files = request.files.getlist("frames")
    tantangan = request.form.get("tantangan", "KEDIP")
    if not files or len(files) < 3:
        return jsonify({"error": "Frame tidak cukup"}), 400

    filepaths = []
    try:
        for file in files:
            path = os.path.join(UPLOAD_FOLDER, f"tmp_{uuid.uuid4().hex}.jpg")
            file.save(path)
            filepaths.append(path)

        if not verifikasi_liveness(filepaths, tantangan):
            return jsonify({"error": "Liveness tidak terverifikasi"}), 400

        embedding_baru = extract_embedding(filepaths[len(filepaths) // 2])
        if embedding_baru is None:
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400

        match = None
        for driver_id, nama, emb_bin in get_all_driver_embeddings():
            if emb_bin is None:
                continue
            ok, _ = compare_faces(binary_to_embedding(emb_bin), embedding_baru, threshold=0.55)
            if ok:
                match = (driver_id, nama)
                break
        if not match:
            return jsonify({"error": "Supir tidak dikenali, silakan Tambah Data Baru"}), 404

        detail = get_driver_by_id(match[0])
        set_terverifikasi(match[0], match[1], detail.nik, detail.no_sim, bool(detail.is_updated))
        camera_trigger_state["is_active"] = False
        return jsonify({"message": f"Terverifikasi: {match[1]}", "id_driver": match[0]}), 200
    finally:
        for path in filepaths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

@security_bp.route("/api/status-verifikasi")
def status_verifikasi():
    v = get_verifikasi()
    if v is None:
        return jsonify({"terverifikasi": False})
    return jsonify({"terverifikasi": True, **v})