import os
import uuid
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import role_required, UPLOAD_FOLDER, camera_trigger_state
from utils.face_utils import (extract_embedding, extract_embedding_tunggal, embedding_to_binary,
                              verifikasi_liveness)
from utils.plat_utils import normalisasi_plat
from utils.verifikasi_state import set_terverifikasi, get_verifikasi, reset_verifikasi
from utils.db_utils import (
    cari_transaksi_aktif, buat_transaksi_full, get_list_tiket_aktif, get_history_driver,
    get_driver_by_id, cari_driver_by_nik, cek_nik_ada, cari_wajah_mirip_driver,
    insert_driver, update_driver_dengan_audit, get_kendaraan_by_plat
)
from utils.serializers import serialisasi_driver
from utils.audit_utils import catat_security_audit
from utils.personel_utils import format_nama_personel
from utils.face_cache import slot_proses_wajah, cari_terdekat

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
    no_plat, error_plat = normalisasi_plat(f.get("no_plat"))
    jenis = f.get("jenis_transaksi", "").strip()
    id_supplier, id_produk, id_driver = f.get("id_supplier"), f.get("id_produk"), f.get("id_driver")

    if error_plat:
        return jsonify({"error": error_plat}), 400
    if not all([no_tiket, jenis, id_supplier, id_produk, id_driver]):
        return jsonify({"error": "Semua field wajib diisi"}), 400

    existing = cari_transaksi_aktif(no_plat=no_plat)
    if existing:
        return jsonify({"error": f"Plat ini sudah punya tiket aktif: {existing.no_tiket}"}), 400

    # Blacklist dicek di server, bukan hanya di tampilan
    ip = request.remote_addr
    kendaraan = get_kendaraan_by_plat(no_plat)
    if kendaraan and kendaraan.is_blacklisted:
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=ip,
                             details={"keterangan": f"Submit tiket ditolak: plat {no_plat} blacklist", "no_plat": no_plat})
        return jsonify({"error": f"Kendaraan {no_plat} masuk BLACKLIST. Tiket tidak dapat dibuat."}), 403
    driver = get_driver_by_id(id_driver) if str(id_driver).isdigit() else None
    if not driver:
        return jsonify({"error": "Supir tidak ditemukan"}), 404
    nama_driver = format_nama_personel(driver.kode_personel, driver.id_driver, driver.nama_driver)
    if driver.is_blacklisted:
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=ip,
                             details={"keterangan": f"Submit tiket ditolak: supir {nama_driver} blacklist",
                                      "no_plat": no_plat, "id_personel": driver.id_driver})
        return jsonify({"error": f"Supir {nama_driver} masuk BLACKLIST. Tiket tidak dapat dibuat."}), 403
    if driver.kategori != 'DRIVER':
        return jsonify({"error": f"{nama_driver} terdaftar sebagai {driver.kategori}, bukan supir"}), 400

    v = get_verifikasi()
    terverifikasi = bool(v) and str(v["id_driver"]) == str(id_driver)
    if os.getenv("WAJIB_SCAN_WAJAH", "true").lower() == "true" and not terverifikasi:
        return jsonify({"error": "Supir belum terverifikasi wajah. Lakukan Scan Wajah dulu."}), 400

    # Supir berbeda dari saran (supir utama / terakhir truk ini) -> dicatat
    saran = f.get("id_driver_saran", "").strip()
    prev_driver_id = int(saran) if saran.isdigit() and saran != str(id_driver) else None

    buat_transaksi_full(no_tiket, no_plat, f.get("no_stnk", "").strip() or None, jenis,
                        id_supplier, id_produk, id_driver, f.get("no_do", "").strip() or None,
                        current_user.id, prev_driver_id)

    if prev_driver_id:
        lama = get_driver_by_id(prev_driver_id)
        nama_lama = format_nama_personel(lama.kode_personel, lama.id_driver, lama.nama_driver) if lama else prev_driver_id
        catat_security_audit(current_user.id, "OVERRIDE_DRIVER", no_tiket, ip_address=ip,
                             details={"keterangan": f"Supir diganti: {nama_lama} → {nama_driver}",
                                      "prev_driver_id": prev_driver_id, "id_driver": driver.id_driver})
    if not terverifikasi:
        catat_security_audit(current_user.id, "MANUAL_INPUT", no_tiket, ip_address=ip,
                             details={"keterangan": f"Tiket dibuat tanpa scan wajah (supir {nama_driver})"})

    reset_verifikasi()
    return jsonify({"message": "Tiket berhasil dibuat & tervalidasi", "no_tiket": no_tiket}), 200

# ===== DRIVER =====

@security_bp.route("/api/driver/cari-by-nik", methods=["POST"])
@login_required
def driver_cari_nik():
    row = cari_driver_by_nik(request.form.get("nik", "").strip())
    if not row:
        return jsonify({"status": "TIDAK_DITEMUKAN"}), 200
    return jsonify({"status": "DITEMUKAN", **serialisasi_driver(row)}), 200

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
    with slot_proses_wajah():
        embedding, jumlah_wajah = extract_embedding_tunggal(filepath)
    if embedding is None:
        os.remove(filepath)
        return jsonify({"error": "Wajah tidak terdeteksi" if jumlah_wajah == 0
                        else f"Terdeteksi {jumlah_wajah} wajah, foto harus berisi 1 orang"}), 400
    mirip = cari_wajah_mirip_driver(embedding)
    if mirip:
        os.remove(filepath)
        lama = get_driver_by_id(mirip[0])
        nama_lama = format_nama_personel(lama.kode_personel, lama.id_driver, lama.nama_driver)
        if lama.is_blacklisted:
            catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                                 details={"keterangan": f"Tambah supir ditolak: wajah cocok dengan {nama_lama} (blacklist)",
                                          "id_personel": lama.id_driver})
            return jsonify({"error": f"Wajah cocok dengan personel BLACKLIST: {nama_lama}"}), 403
        return jsonify({"error": f"Wajah sudah terdaftar sebagai {nama_lama}"}), 400

    foto_path = f"uploads/{filename}"
    driver_id = insert_driver(nik, nama, no_sim, embedding_to_binary(embedding), foto_path, current_user.id)
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
        with slot_proses_wajah():
            embedding = extract_embedding(filepath)
        if embedding is None:
            os.remove(filepath)
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400
        embedding_binary, foto_path = embedding_to_binary(embedding), f"uploads/{filename}"

    update_driver_dengan_audit(int(id_driver), nik, nama, no_sim, current_user.id, embedding_binary, foto_path)
    d = get_driver_by_id(int(id_driver))
    v = get_verifikasi()
    if v and str(v["id_driver"]) == str(id_driver):
        set_terverifikasi(d.id_driver, d.nama_driver, d.nik, d.no_sim, True, d.foto_path,
                          d.kode_personel, d.kategori, bool(d.is_blacklisted))
    return jsonify({
        "message": f"Data '{nama}' diperbarui, tercatat di audit log",
        "driver": serialisasi_driver(d)
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

        with slot_proses_wajah():
            if not verifikasi_liveness(filepaths, tantangan):
                return jsonify({"error": "Liveness tidak terverifikasi"}), 400
            embedding_baru = extract_embedding(filepaths[len(filepaths) // 2])
        if embedding_baru is None:
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400

        id_cocok, nama_cocok, _ = cari_terdekat(embedding_baru, 0.55)
        match = (id_cocok, nama_cocok) if id_cocok is not None else None
        if not match:
            return jsonify({"error": "Supir tidak dikenali, silakan Tambah Data Baru"}), 404

        # Status blacklist & kategori ikut disimpan; form Security yang menolak dan mencatat audit
        d = get_driver_by_id(match[0])
        set_terverifikasi(d.id_driver, d.nama_driver, d.nik, d.no_sim, bool(d.is_updated), d.foto_path,
                          d.kode_personel, d.kategori, bool(d.is_blacklisted))
        camera_trigger_state["is_active"] = False
        nama = format_nama_personel(d.kode_personel, d.id_driver, d.nama_driver)
        if d.is_blacklisted:
            return jsonify({"error": f"{nama} masuk BLACKLIST", "id_driver": d.id_driver}), 403
        if d.kategori != 'DRIVER':
            return jsonify({"error": f"{nama} terdaftar sebagai {d.kategori}, bukan supir", "id_driver": d.id_driver}), 400
        return jsonify({"message": f"Terverifikasi: {nama}", "id_driver": d.id_driver}), 200
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
    # Kiosk tidak login, jadi percobaan scan supir blacklist dicatat saat form Security membaca hasilnya
    if v["is_blacklisted"] and not v["dilog"] and current_user.is_authenticated:
        v["dilog"] = True
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                             details={"keterangan": f"Scan wajah: {format_nama_personel(v['kode_personel'], v['id_driver'], v['nama'])} blacklist",
                                      "id_personel": v["id_driver"]})
    return jsonify({"terverifikasi": True, **{k: val for k, val in v.items() if k != "dilog"}})