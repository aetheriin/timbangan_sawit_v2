from flask import Blueprint, request, jsonify, g
from flask_login import login_required, current_user
from extensions import role_required, UPLOAD_FOLDER
from utils.face_utils import (extract_embedding, extract_embedding_tunggal, embedding_to_binary,
                              verifikasi_liveness)
from utils.plat_utils import normalisasi_plat
from utils import pengaturan
from utils.db_kontrak import get_do
from utils import verifikasi_state as verif
from utils.keamanan import perangkat_atau_login, id_pos
from utils.upload_utils import simpan_upload, simpan_frames, hapus_file
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
    id_driver = f.get("id_driver")

    if error_plat:
        return jsonify({"error": error_plat}), 400
    if not all([no_tiket, f.get("no_do", "").strip(), id_driver]):
        return jsonify({"error": "No tiket, No DO, dan supir wajib diisi"}), 400
    # Jenis transaksi, customer, produk, pengangkutan SELALU dari DO (diisi HO), bukan dari isian browser
    do = get_do(f.get("no_do").strip().upper())
    if not do:
        return jsonify({"error": "DO belum terdaftar / tidak aktif. Hubungi HO."}), 400
    jenis, id_supplier, id_produk = do["jenis_transaksi"], do["id_customer"], do["id_produk"]

    existing = cari_transaksi_aktif(no_plat=no_plat)
    if existing:
        return jsonify({"error": f"Plat ini sudah punya tiket aktif: {existing.no_tiket}"}), 400

    ip = request.remote_addr
    driver = get_driver_by_id(id_driver) if str(id_driver).isdigit() else None
    if not driver:
        return jsonify({"error": "Supir tidak ditemukan"}), 404
    nama_driver = format_nama_personel(driver.kode_personel, driver.id_driver, driver.nama_driver)
    if driver.kategori != 'DRIVER':
        return jsonify({"error": f"{nama_driver} terdaftar sebagai {driver.kategori}, bukan supir"}), 400

    # Blacklist = PERINGATAN: tiket tetap boleh dibuat, tetapi selalu tercatat di Audit Log untuk HO
    kendaraan = get_kendaraan_by_plat(no_plat)
    peringatan = []
    if kendaraan and kendaraan.is_blacklisted:
        peringatan.append(f"kendaraan {no_plat}")
    if driver.is_blacklisted:
        peringatan.append(f"supir {nama_driver}")

    v = verif.ambil(id_pos(), current_user.id)
    terverifikasi = bool(v) and str(v["id_driver"]) == str(id_driver)
    if pengaturan.nilai("WAJIB_SCAN_WAJAH") and not terverifikasi:
        return jsonify({"error": "Supir belum terverifikasi wajah. Lakukan Scan Wajah dulu."}), 400

    # Supir berbeda dari saran (supir utama / terakhir truk ini) -> dicatat
    saran = f.get("id_driver_saran", "").strip()
    prev_driver_id = int(saran) if saran.isdigit() and saran != str(id_driver) else None

    buat_transaksi_full(no_tiket, no_plat, f.get("no_stnk", "").strip() or None, jenis,
                        id_supplier, id_produk, id_driver, do["no_do"],
                        current_user.id, prev_driver_id, do["id_pengangkutan"])

    if prev_driver_id:
        lama = get_driver_by_id(prev_driver_id)
        nama_lama = format_nama_personel(lama.kode_personel, lama.id_driver, lama.nama_driver) if lama else prev_driver_id
        catat_security_audit(current_user.id, "OVERRIDE_DRIVER", no_tiket, ip_address=ip,
                             details={"keterangan": f"Supir diganti: {nama_lama} → {nama_driver}",
                                      "prev_driver_id": prev_driver_id, "id_driver": driver.id_driver})
    if not terverifikasi:
        catat_security_audit(current_user.id, "MANUAL_INPUT", no_tiket, ip_address=ip,
                             details={"keterangan": f"Tiket dibuat tanpa scan wajah (supir {nama_driver})"})
    if peringatan:
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", no_tiket, ip_address=ip,
                             details={"keterangan": f"Tiket dibuat walau {' & '.join(peringatan)} masuk blacklist",
                                      "no_plat": no_plat, "id_personel": driver.id_driver})

    verif.hapus(id_pos(), current_user.id)
    pesan = "Tiket berhasil dibuat & tervalidasi"
    if peringatan:
        pesan += f". Perhatian: {' & '.join(peringatan)} masuk blacklist (tercatat di Audit Log)"
    return jsonify({"message": pesan, "no_tiket": no_tiket, "blacklist": bool(peringatan)}), 200

# ===== DRIVER =====

@security_bp.route("/api/driver/cari-by-nik", methods=["POST"])
@login_required
def driver_cari_nik():
    row = cari_driver_by_nik(request.form.get("nik", "").strip())
    if not row:
        return jsonify({"status": "TIDAK_DITEMUKAN"}), 200
    return jsonify({"status": "DITEMUKAN", **serialisasi_driver(row)}), 200

def _simpan_foto(file):
    """Foto supir: divalidasi & disimpan privat. Kembalikan (path_disk, path_relatif 'uploads/personel/...')."""
    return simpan_upload(file, "personel")

def _data_verif(d, is_updated=None):
    """Baris driver -> argumen verif.simpan_hasil_*."""
    return {"id_driver": d.id_driver, "nama": d.nama_driver, "nik": d.nik, "no_sim": d.no_sim,
            "is_updated": bool(d.is_updated) if is_updated is None else is_updated, "foto_path": d.foto_path,
            "kode_personel": d.kode_personel, "kategori": d.kategori, "is_blacklisted": bool(d.is_blacklisted)}


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

    try:
        filepath, foto_path = _simpan_foto(file)
    except ValueError as e:
        return jsonify({"error": f"Foto: {e}"}), 400
    with slot_proses_wajah():
        embedding, jumlah_wajah = extract_embedding_tunggal(filepath)
    if embedding is None:
        hapus_file(filepath)
        return jsonify({"error": "Wajah tidak terdeteksi" if jumlah_wajah == 0
                        else f"Terdeteksi {jumlah_wajah} wajah, foto harus berisi 1 orang"}), 400
    mirip = cari_wajah_mirip_driver(embedding)
    if mirip:
        hapus_file(filepath)
        lama = get_driver_by_id(mirip[0])
        nama_lama = format_nama_personel(lama.kode_personel, lama.id_driver, lama.nama_driver)
        if lama.is_blacklisted:
            catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                                 details={"keterangan": f"Tambah supir: wajah cocok dengan {nama_lama} (blacklist)",
                                          "id_personel": lama.id_driver})
            return jsonify({"error": f"Wajah sudah terdaftar sebagai {nama_lama} (BLACKLIST). "
                                     "Gunakan data supir tersebut lewat Update."}), 400
        return jsonify({"error": f"Wajah sudah terdaftar sebagai {nama_lama}"}), 400

    driver_id = insert_driver(nik, nama, no_sim, embedding_to_binary(embedding), foto_path, current_user.id)
    verif.simpan_hasil_user(id_pos(), current_user.id, id_driver=driver_id, nama=nama, nik=nik, no_sim=no_sim,
                            is_updated=False, foto_path=foto_path, kode_personel=None, kategori="DRIVER",
                            is_blacklisted=False)
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

    if not all([id_driver, nik, nama, no_sim]) or not id_driver.isdigit():
        return jsonify({"error": "Semua field wajib diisi"}), 400
    if cek_nik_ada(nik, exclude_id=int(id_driver)):
        return jsonify({"error": f"NIK '{nik}' sudah dipakai supir lain"}), 400

    embedding_binary, foto_path = None, None
    if file and file.filename:
        try:
            filepath, foto_path = _simpan_foto(file)
        except ValueError as e:
            return jsonify({"error": f"Foto: {e}"}), 400
        with slot_proses_wajah():
            embedding = extract_embedding(filepath)
        if embedding is None:
            hapus_file(filepath)
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400
        embedding_binary = embedding_to_binary(embedding)

    update_driver_dengan_audit(int(id_driver), nik, nama, no_sim, current_user.id, embedding_binary, foto_path)
    d = get_driver_by_id(int(id_driver))
    v = verif.ambil(id_pos(), current_user.id)
    if v and str(v["id_driver"]) == str(id_driver):
        verif.simpan_hasil_user(id_pos(), current_user.id, **_data_verif(d, is_updated=True))
    return jsonify({
        "message": f"Data '{nama}' diperbarui, tercatat di audit log",
        "driver": serialisasi_driver(d)
    }), 200

# ===== KAMERA KIOSK & VERIFIKASI WAJAH =====
# Browser (user login) meminta scan -> kiosk (token perangkat) membaca status, mengirim frame.
# Hasil hanya bisa dibaca user yang meminta, per pos kiosk (utils/verifikasi_state.py).

@security_bp.route("/api/kamera/start", methods=["POST"])
@login_required
@role_required('SECURITY')
def kamera_start():
    verif.mulai_scan(id_pos(), current_user.id)
    return jsonify({"status": "SUCCESS"}), 200

@security_bp.route("/api/kamera/status")
@perangkat_atau_login
def kamera_status():
    return jsonify({"is_active": verif.kamera_aktif(id_pos())}), 200

@security_bp.route("/api/kamera/batal", methods=["POST"])
@perangkat_atau_login
def kamera_batal():
    verif.batal(id_pos())
    return jsonify({"status": "SUCCESS"}), 200

MAKS_FRAME = 20

@security_bp.route("/api/verifikasi-wajah", methods=["POST"])
@perangkat_atau_login
def verifikasi_wajah():
    pos = id_pos()
    if not verif.kamera_aktif(pos):
        return jsonify({"error": "Tidak ada permintaan scan dari form Security"}), 409
    tantangan = request.form.get("tantangan", "KEDIP")
    try:
        filepaths = simpan_frames(request.files.getlist("frames"), maks=MAKS_FRAME)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        with slot_proses_wajah():
            if not verifikasi_liveness(filepaths, tantangan):
                return jsonify({"error": "Liveness tidak terverifikasi"}), 400
            embedding_baru = extract_embedding(filepaths[len(filepaths) // 2])
        if embedding_baru is None:
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400

        id_cocok, _, _ = cari_terdekat(embedding_baru, pengaturan.nilai("AMBANG_WAJAH"))
        if id_cocok is None:
            verif.batal(pos)
            return jsonify({"error": "Supir tidak dikenali, silakan Tambah Data Baru"}), 404

        # Status blacklist & kategori ikut disimpan; form Security menampilkan peringatan & mencatat audit
        d = get_driver_by_id(id_cocok)
        verif.simpan_hasil_kiosk(pos, **_data_verif(d))
        nama = format_nama_personel(d.kode_personel, d.id_driver, d.nama_driver)
        if d.kategori != 'DRIVER':
            return jsonify({"error": f"{nama} terdaftar sebagai {d.kategori}, bukan supir", "id_driver": d.id_driver}), 400
        pesan = f"Terverifikasi: {nama}" + (" (PERINGATAN: BLACKLIST)" if d.is_blacklisted else "")
        return jsonify({"message": pesan, "id_driver": d.id_driver, "blacklist": bool(d.is_blacklisted)}), 200
    finally:
        for path in filepaths:
            hapus_file(path)

@security_bp.route("/api/status-verifikasi")
@login_required
def status_verifikasi():
    v = verif.ambil(id_pos(), current_user.id)
    if v is None:
        return jsonify({"terverifikasi": False})
    # Kiosk tidak login, jadi scan supir blacklist dicatat saat form Security membaca hasilnya
    if v["is_blacklisted"] and not v["dilog"]:
        v["dilog"] = True
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                             details={"keterangan": f"Scan wajah: {format_nama_personel(v['kode_personel'], v['id_driver'], v['nama'])} blacklist",
                                      "id_personel": v["id_driver"]})
    return jsonify({"terverifikasi": True, **{k: val for k, val in v.items() if k != "dilog"}})
