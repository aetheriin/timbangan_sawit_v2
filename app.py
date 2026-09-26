import os
import json
import uuid
from flask import Flask, request, jsonify, render_template, redirect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from dotenv import load_dotenv

from utils.face_utils import extract_embedding, embedding_to_binary, binary_to_embedding, compare_faces
from utils.auth import User
from utils.db_utils import (
    get_user_by_username, get_user_by_id, insert_user,
    get_semua_supplier, get_semua_produk,
    cari_transaksi_aktif_by_plat, buat_transaksi_full, catat_timeline,
    cari_riwayat_driver_by_plat, generate_no_tiket, cari_driver_by_nik,
    get_history_timbangan_by_supplier,
    get_driver_by_id, cek_nik_ada, cari_wajah_mirip_driver, insert_driver, update_driver_dengan_audit,
    get_data_timbangan, simpan_timbang_pertama, simpan_timbang_kedua, 
    get_data_sortasi, simpan_sortasi, get_standar_mutu, update_standar_mutu,
    simpan_lab, get_history_umum
)
from utils.serial_reader import mulai_pembacaan_serial, baca_status_asli, reset_deteksi_stabil

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

mulai_pembacaan_serial()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    row = get_user_by_id(user_id)
    if row is None:
        return None
    return User(row.id_user, row.username, row.nama, row.role)

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles and 'ADMIN' not in [current_user.role]:
                return jsonify({"error": "Akses ditolak untuk role Anda"}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator

# ===== LOGIN =====

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = get_user_by_username(username)
        if row is None or not check_password_hash(row.password, password):
            return render_template("login.html", error="Username atau password salah")
        user = User(row.id_user, row.username, row.nama, row.role)
        login_user(user)

        tab_default = {
            'SECURITY': 'security', 'OPERATOR_TIMBANG': 'timbangan',
            'SORTASI': 'sortasi', 'LAB': 'lab', 'ADMIN': 'security'
        }
        return redirect(f"/weighbridge?tab={tab_default.get(row.role, 'security')}")
    return render_template("login.html", error=None)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

@app.route("/")
def index():
    return redirect("/login")

# ===== HALAMAN UTAMA (SATU HALAMAN, 4 TAB) =====

@app.route("/weighbridge")
@login_required
def weighbridge():
    tab_aktif = request.args.get("tab", "security")
    supplier_list = get_semua_supplier()
    produk_list = get_semua_produk()
    return render_template("weighbridge.html", tab_aktif=tab_aktif, supplier_list=supplier_list, produk_list=produk_list)

# ===== API: LOOKUP / GENERATE TIKET BERDASARKAN PLAT =====

@app.route("/api/plat/lookup", methods=["POST"])
@login_required
def api_plat_lookup():
    no_plat = request.form.get("no_plat", "").strip().upper()
    if not no_plat:
        return jsonify({"error": "Nomor plat kosong"}), 400

    row = cari_transaksi_aktif_by_plat(no_plat)
    if row:
        return jsonify({
            "status": "ADA_TIKET", "no_tiket": row.no_tiket, "jenis_transaksi": row.jenis_transaksi,
            "no_do": row.no_do, "status_alur": row.status_alur, "supplier": row.nama_supplier,
            "id_supplier": None, "produk": row.nama_produk, "kategori_produk": row.kategori,
            "no_plat": row.no_plat, "no_stnk": row.no_stnk,
            "driver": {"id_driver": row.id_driver, "nik": row.nik, "nama": row.nama_driver,
                       "no_sim": row.no_sim, "is_updated": bool(row.is_updated), "foto_path": None}
        }), 200

    # TIDAK ADA tiket aktif -> siapkan draft (TIDAK di-insert dulu)
    no_tiket_reserved = generate_no_tiket(no_plat)
    riwayat = cari_riwayat_driver_by_plat(no_plat)

    driver_info = None
    if riwayat:
        driver_info = {
            "id_driver": riwayat.id_driver, "nik": riwayat.nik, "nama": riwayat.nama_driver,
            "no_sim": riwayat.no_sim, "is_updated": bool(riwayat.is_updated),
            "foto_path": riwayat.foto_path
        }

    return jsonify({
        "status": "DRAFT",
        "no_tiket_reserved": no_tiket_reserved,
        "no_stnk": riwayat.no_stnk if riwayat else None,
        "driver": driver_info
    }), 200

# ===== SECURITY: BUAT TIKET BARU =====

@app.route("/api/security/buat-tiket", methods=["POST"])
@login_required
@role_required('SECURITY', 'ADMIN')
def api_buat_tiket():
    no_tiket = request.form.get("no_tiket", "").strip()
    no_plat = request.form.get("no_plat", "").strip().upper()
    no_stnk = request.form.get("no_stnk", "").strip() or None
    no_do = request.form.get("no_do", "").strip() or None
    jenis_transaksi = request.form.get("jenis_transaksi", "").strip()
    id_supplier = request.form.get("id_supplier", "").strip()
    id_produk = request.form.get("id_produk", "").strip()
    id_driver = request.form.get("id_driver", "").strip()

    if not all([no_tiket, no_plat, jenis_transaksi, id_supplier, id_produk, id_driver]):
        return jsonify({"error": "Semua field wajib diisi"}), 400

    existing = cari_transaksi_aktif_by_plat(no_plat)
    if existing:
        return jsonify({"error": f"Plat ini sudah punya tiket aktif: {existing.no_tiket}"}), 400

    buat_transaksi_full(no_tiket, no_plat, no_stnk, jenis_transaksi, id_supplier, id_produk, id_driver, no_do, current_user.id)
    return jsonify({"message": "Tiket berhasil dibuat & tervalidasi", "no_tiket": no_tiket}), 200

@app.route("/api/security/list-tiket-aktif")
@login_required
def api_list_tiket_aktif():
    from utils.db_utils import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.no_tiket, k.no_plat, s.nama_supplier, t.status_alur
        FROM transaksi t
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN supplier s ON t.id_supplier = s.id_supplier
        WHERE t.status_alur NOT IN ('SELESAI', 'REJECTED')
        ORDER BY t.created_at DESC
    """)
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return jsonify(data)

# ===== DRIVER: TAMBAH, UPDATE (2 MODE) =====

@app.route("/api/driver/tambah", methods=["POST"])
@login_required
@role_required('SECURITY', 'ADMIN')
def api_driver_tambah():
    nik = request.form.get("nik", "").strip()
    nama = request.form.get("nama", "").strip()
    no_sim = request.form.get("no_sim", "").strip()
    file = request.files.get("foto")

    if not all([nik, nama, no_sim, file]):
        return jsonify({"error": "Semua field wajib diisi"}), 400
    if cek_nik_ada(nik):
        return jsonify({"error": f"NIK '{nik}' sudah terdaftar"}), 400

    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    embedding = extract_embedding(filepath)
    if embedding is None:
        os.remove(filepath)
        return jsonify({"error": "Wajah tidak terdeteksi"}), 400

    mirip = cari_wajah_mirip_driver(embedding)
    if mirip:
        os.remove(filepath)
        return jsonify({"error": f"Wajah sudah terdaftar sebagai '{mirip[1]}'"}), 400

    binary_data = embedding_to_binary(embedding)
    driver_id = insert_driver(nik, nama, no_sim, binary_data, f"uploads/{filename}")
    return jsonify({"message": f"Supir '{nama}' berhasil ditambahkan", "id_driver": driver_id}), 200

@app.route("/api/driver/update-mutasi", methods=["POST"])
@login_required
@role_required('SECURITY', 'ADMIN')
def api_driver_update_mutasi():
    """Mode default popup Update: cuma ganti plat truk, TIDAK ubah data driver."""
    id_driver = request.form.get("id_driver", "").strip()
    no_plat_baru = request.form.get("no_plat_baru", "").strip().upper()
    no_tiket = request.form.get("no_tiket", "").strip()

    if not all([id_driver, no_plat_baru, no_tiket]):
        return jsonify({"error": "Data tidak lengkap"}), 400

    kendaraan_id = get_or_create_kendaraan_wrapper(no_plat_baru)
    from utils.db_utils import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE transaksi SET id_kendaraan = ? WHERE no_tiket = ?", kendaraan_id, no_tiket)
    conn.commit()
    conn.close()

    return jsonify({"message": "Truk berhasil dimutasikan"}), 200

def get_or_create_kendaraan_wrapper(no_plat):
    from utils.db_utils import get_or_create_kendaraan
    return get_or_create_kendaraan(no_plat)

@app.route("/api/driver/update-identitas", methods=["POST"])
@login_required
@role_required('SECURITY', 'ADMIN')
def api_driver_update_identitas():
    """Mode edit: ubah NIK/Nama/SIM, WAJIB audit log."""
    id_driver = request.form.get("id_driver", "").strip()
    nik = request.form.get("nik", "").strip()
    nama = request.form.get("nama", "").strip()
    no_sim = request.form.get("no_sim", "").strip()
    file = request.files.get("foto")

    if not all([id_driver, nik, nama, no_sim]):
        return jsonify({"error": "Semua field wajib diisi"}), 400
    if cek_nik_ada(nik, exclude_id=int(id_driver)):
        return jsonify({"error": f"NIK '{nik}' sudah dipakai supir lain"}), 400

    embedding_binary = None
    foto_path = None
    if file and file.filename != "":
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        embedding = extract_embedding(filepath)
        if embedding is None:
            os.remove(filepath)
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400
        embedding_binary = embedding_to_binary(embedding)
        foto_path = f"uploads/{filename}"

    update_driver_dengan_audit(int(id_driver), nik, nama, no_sim, current_user.id, embedding_binary, foto_path)
    return jsonify({"message": f"Data '{nama}' berhasil diperbarui, tercatat di audit log"}), 200

@app.route("/api/driver/cari-by-nik", methods=["POST"])
@login_required
def api_driver_cari_nik():
    nik = request.form.get("nik", "").strip()
    row = cari_driver_by_nik(nik)
    if not row:
        return jsonify({"status": "TIDAK_DITEMUKAN"}), 200
    return jsonify({
        "status": "DITEMUKAN", "id_driver": row.id_driver, "nik": row.nik,
        "nama": row.nama_driver, "no_sim": row.no_sim, "is_updated": bool(row.is_updated)
    }), 200

# ===== VERIFIKASI WAJAH (SAMA POLA DENGAN PROJECT SEBELUMNYA) =====

@app.route("/api/kamera/start", methods=["POST"])
def api_kamera_start():
    from utils.verifikasi_state import reset_verifikasi
    global camera_trigger_state
    camera_trigger_state["is_active"] = True
    reset_verifikasi()
    return jsonify({"status": "SUCCESS"}), 200

camera_trigger_state = {"is_active": False}

@app.route("/api/kamera/status", methods=["GET"])
def api_kamera_status():
    return jsonify({"is_active": camera_trigger_state["is_active"]}), 200

@app.route("/api/kamera/batal", methods=["POST"])
def api_kamera_batal():
    from utils.verifikasi_state import reset_verifikasi
    camera_trigger_state["is_active"] = False
    reset_verifikasi()
    return jsonify({"status": "SUCCESS"}), 200

@app.route("/api/verifikasi-wajah", methods=["POST"])
def api_verifikasi_wajah():
    from utils.face_utils import verifikasi_liveness
    from utils.verifikasi_state import set_terverifikasi
    from utils.db_utils import get_all_driver_embeddings

    files = request.files.getlist("frames")
    tantangan = request.form.get("tantangan", "KEDIP")

    if not files or len(files) < 3:
        return jsonify({"error": "Frame tidak cukup"}), 400

    filepaths = []
    try:
        for f in files:
            filepath = os.path.join(UPLOAD_FOLDER, f"tmp_{uuid.uuid4().hex}.jpg")
            f.save(filepath)
            filepaths.append(filepath)

        if not verifikasi_liveness(filepaths, tantangan):
            return jsonify({"error": "Liveness tidak terverifikasi"}), 400

        embedding_baru = extract_embedding(filepaths[len(filepaths) // 2])
        if embedding_baru is None:
            return jsonify({"error": "Wajah tidak terdeteksi"}), 400

        driver_list = get_all_driver_embeddings()
        match_found = None
        for row in driver_list:
            driver_id, nama, embedding_binary = row
            if embedding_binary is None:
                continue
            embedding_tersimpan = binary_to_embedding(embedding_binary)
            is_match, _ = compare_faces(embedding_tersimpan, embedding_baru, threshold=0.55)
            if is_match:
                match_found = (driver_id, nama)
                break

        if not match_found:
            return jsonify({"error": "Supir tidak dikenali, silakan Tambah Data Baru"}), 404

        driver_id, nama = match_found
        detail = get_driver_by_id(driver_id)
        set_terverifikasi(driver_id, nama, detail.nik, detail.no_sim, bool(detail.is_updated))
        camera_trigger_state["is_active"] = False

        return jsonify({"message": f"Terverifikasi: {nama}", "id_driver": driver_id}), 200
    finally:
        for path in filepaths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

@app.route("/api/status-verifikasi")
def api_status_verifikasi():
    from utils.verifikasi_state import get_verifikasi
    v = get_verifikasi()
    if v is None:
        return jsonify({"terverifikasi": False})
    return jsonify({"terverifikasi": True, **v})

# ===== TIMBANGAN =====

@app.route("/api/timbang/status")
def api_timbang_status():
    return jsonify(baca_status_asli())

@app.route("/api/timbang/reset-baseline", methods=["POST"])
@login_required
def api_timbang_reset_baseline():
    reset_deteksi_stabil()
    return jsonify({"message": "Baseline direset"}), 200

@app.route("/api/timbang/simpan", methods=["POST"])
@login_required
@role_required('OPERATOR_TIMBANG', 'ADMIN')
def api_timbang_simpan():
    no_tiket = request.form.get("no_tiket", "").strip()
    if not no_tiket:
        return jsonify({"error": "No. Tiket wajib ada"}), 400

    status = baca_status_asli()
    if not status.get("siap_kunci"):
        return jsonify({"error": "Berat belum stabil"}), 400

    berat = status["berat"]
    data_lama = get_data_timbangan(no_tiket)

    sudah_ada_bruto = data_lama.berat_bruto is not None
    sudah_ada_tara = data_lama.berat_tara is not None

    if not sudah_ada_bruto and not sudah_ada_tara:
        jenis = simpan_timbang_pertama(no_tiket, berat, current_user.id)
        reset_deteksi_stabil()
        if jenis == 'PENIMBANGAN_SAJA':
            catat_timeline(no_tiket, 'TIMBANG_MASUK', current_user.id)
            return jsonify({"message": f"Berhasil, langsung SELESAI (Penimbangan). Netto: {berat} kg"}), 200
        catat_timeline(no_tiket, 'TIMBANG_MASUK', current_user.id)
        label = "Tara" if jenis == 'PENJUALAN' else "Bruto"
        return jsonify({"message": f"{label} tersimpan: {berat} kg. Tunggu truk kembali untuk timbang kedua."}), 200
    else:
        netto = simpan_timbang_kedua(no_tiket, berat, current_user.id)
        reset_deteksi_stabil()
        catat_timeline(no_tiket, 'TIMBANG_KELUAR', current_user.id)
        return jsonify({"message": f"Selesai! Netto: {netto} kg"}), 200

@app.route("/api/timbang/data/<no_tiket>")
@login_required
def api_timbang_data(no_tiket):
    row = get_data_timbangan(no_tiket)
    return jsonify({"berat_bruto": row.berat_bruto, "berat_tara": row.berat_tara, "berat_netto": row.berat_netto})

@app.route("/api/timbang/scan-qr", methods=["POST"])
@login_required
def api_timbang_scan_qr():
    no_tiket = request.form.get("no_tiket", "").strip()
    row = cari_transaksi_aktif_by_plat_or_tiket(no_tiket)  
    if not row:
        return jsonify({"error": "Tiket tidak ditemukan / sudah selesai"}), 404
    return jsonify({"status": "ADA_TIKET", "no_tiket": row.no_tiket, "jenis_transaksi": row.jenis_transaksi,
                     "id_supplier": row.id_supplier, "supplier": row.nama_supplier, "produk": row.nama_produk}), 200

@app.route("/api/history-timbangan-supplier")
@login_required
def api_history_timbangan_supplier():
    id_supplier = request.args.get("id_supplier")
    if not id_supplier:
        return jsonify([])
    data = get_history_timbangan_by_supplier(id_supplier)
    return jsonify(data)

# ==== SORTASI =====

@app.route("/api/sortasi/simpan", methods=["POST"])
@login_required
@role_required('SORTASI', 'ADMIN')
def api_sortasi_simpan():
    no_tiket = request.form.get("no_tiket")
    if not no_tiket:
        return jsonify({"error": "Tiket belum dipilih"}), 400
    vals = {k: float(request.form.get(k) or 0) for k in ['mentah', 'busuk', 'tangkai', 'sampah', 'matang', 'brondolan']}
    catatan = request.form.get("catatan", "")
    total = simpan_sortasi(no_tiket, vals['mentah'], vals['busuk'], vals['tangkai'], vals['sampah'],
                            vals['matang'], vals['brondolan'], catatan, current_user.id)
    return jsonify({"message": f"Sortasi tersimpan. Total potongan: {total} kg", "total_potongan_kg": total}), 200

# === LAB =====

@app.route("/api/lab/standar/<int:id_produk>")
@login_required
def api_lab_standar(id_produk):
    row = get_standar_mutu(id_produk)
    return jsonify({"maks_ffa": row.maks_ffa, "maks_air": row.maks_air, "maks_kotoran": row.maks_kotoran})

@app.route("/api/lab/standar/update", methods=["POST"])
@login_required
@role_required('LAB', 'ADMIN')
def api_lab_standar_update():
    id_produk = request.form.get("id_produk")
    update_standar_mutu(id_produk, request.form.get("maks_ffa"), request.form.get("maks_air"), request.form.get("maks_kotoran"))
    return jsonify({"message": "Standar mutu diperbarui"}), 200

@app.route("/api/lab/simpan", methods=["POST"])
@login_required
@role_required('LAB', 'ADMIN')
def api_lab_simpan():
    no_tiket = request.form.get("no_tiket")
    if not no_tiket:
        return jsonify({"error": "Tiket belum dipilih"}), 400
    keputusan = request.form.get("keputusan")
    no_coa = f"COA-{no_tiket}" if keputusan == 'APPROVE' else None
    simpan_lab(no_tiket, request.form.get("ffa"), request.form.get("kadar_air"),
               request.form.get("kadar_kotoran"), request.form.get("warna_locis"), keputusan, no_coa, current_user.id)
    return jsonify({"message": f"Hasil lab tersimpan ({keputusan})", "no_dokumen_coa": no_coa}), 200

@app.route("/api/history/sortasi")
@login_required
def api_history_sortasi():
    return jsonify(get_history_umum('sortasi'))

@app.route("/api/history/lab")
@login_required
def api_history_lab():
    return jsonify(get_history_umum('lab_hasil'))

if __name__ == "__main__":
    app.run(debug=True, port=5000)