import os
import pyodbc
import hashlib
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config import get_connection_string

load_dotenv()

def get_connection():
    return pyodbc.connect(get_connection_string())

# ===== USERS =====

def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_user, username, password, nama, role FROM users WHERE username = ? AND is_active = 1", username)
    row = cursor.fetchone()
    conn.close()
    return row

def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_user, username, nama, role FROM users WHERE id_user = ?", user_id)
    row = cursor.fetchone()
    conn.close()
    return row

def insert_user(username, password_hash, nama, role):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (nama, username, password, role) VALUES (?, ?, ?, ?)", nama, username, password_hash, role)
    conn.commit()
    conn.close()

# ===== SUPPLIER / PRODUK =====

def get_semua_supplier():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_supplier, nama_supplier FROM supplier WHERE is_active = 1 ORDER BY nama_supplier")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_semua_produk():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_produk, nama_produk, kategori FROM produk WHERE is_active = 1 ORDER BY nama_produk")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ===== KENDARAAN =====

def get_or_create_kendaraan(no_plat, no_stnk=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_kendaraan FROM kendaraan WHERE no_plat = ?", no_plat)
    row = cursor.fetchone()
    if row:
        if no_stnk:
            cursor.execute("UPDATE kendaraan SET no_stnk = ? WHERE id_kendaraan = ?", no_stnk, row.id_kendaraan)
            conn.commit()
        conn.close()
        return row.id_kendaraan
    cursor.execute("INSERT INTO kendaraan (no_plat, no_stnk) VALUES (?, ?)", no_plat, no_stnk)
    conn.commit()
    cursor.execute("SELECT id_kendaraan FROM kendaraan WHERE no_plat = ?", no_plat)
    kendaraan_id = cursor.fetchone().id_kendaraan
    conn.close()
    return kendaraan_id

# ===== DRIVER =====

def get_all_driver_embeddings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_driver, nama_driver, face_embedding_data FROM driver WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_driver_by_id(driver_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_driver, nik, nama_driver, no_sim, is_updated, foto_path FROM driver WHERE id_driver = ?", driver_id)
    row = cursor.fetchone()
    conn.close()
    return row

def cek_nik_ada(nik, exclude_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    if exclude_id:
        cursor.execute("SELECT id_driver FROM driver WHERE nik = ? AND id_driver != ?", nik, exclude_id)
    else:
        cursor.execute("SELECT id_driver FROM driver WHERE nik = ?", nik)
    row = cursor.fetchone()
    conn.close()
    return row is not None

def cari_wajah_mirip_driver(embedding_baru, threshold=0.55, exclude_id=None):
    from utils.face_utils import binary_to_embedding, compare_faces
    driver_list = get_all_driver_embeddings()
    for row in driver_list:
        driver_id, nama, embedding_binary = row
        if exclude_id and driver_id == exclude_id:
            continue
        if embedding_binary is None:
            continue
        embedding_tersimpan = binary_to_embedding(embedding_binary)
        is_match, _ = compare_faces(embedding_tersimpan, embedding_baru, threshold)
        if is_match:
            return (driver_id, nama)
    return None

def insert_driver(nik, nama, no_sim, embedding_binary, foto_path=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO driver (nik, nama_driver, no_sim, face_embedding_data, foto_path) VALUES (?, ?, ?, ?, ?)",
        nik, nama, no_sim, embedding_binary, foto_path
    )
    conn.commit()
    cursor.execute("SELECT id_driver FROM driver WHERE nik = ?", nik)
    driver_id = cursor.fetchone().id_driver
    conn.close()
    return driver_id

def hitung_hash_driver(nik, nama, no_sim, timestamp, secret_key=None):
    if secret_key is None:
        secret_key = os.getenv("HASH_SECRET_KEY")
    data = f"{nik}{nama}{no_sim}{timestamp}{secret_key}"
    return hashlib.sha256(data.encode()).hexdigest()

def update_driver_dengan_audit(driver_id, nik_baru, nama_baru, sim_baru, updated_by, embedding_binary=None, foto_path=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT nik, nama_driver, no_sim FROM driver WHERE id_driver = ?", driver_id)
    lama = cursor.fetchone()

    timestamp = datetime.now()
    hash_baru = hitung_hash_driver(nik_baru, nama_baru, sim_baru, timestamp)

    if embedding_binary is not None:
        cursor.execute(
            "UPDATE driver SET nik=?, nama_driver=?, no_sim=?, face_embedding_data=?, foto_path=?, is_updated=1, current_hash=?, updated_at=GETDATE() WHERE id_driver=?",
            nik_baru, nama_baru, sim_baru, embedding_binary, foto_path, hash_baru, driver_id
        )
    else:
        cursor.execute(
            "UPDATE driver SET nik=?, nama_driver=?, no_sim=?, is_updated=1, current_hash=?, updated_at=GETDATE() WHERE id_driver=?",
            nik_baru, nama_baru, sim_baru, hash_baru, driver_id
        )

    cursor.execute(
        """INSERT INTO driver_audit_logs
           (id_driver, nik_lama, nik_baru, nama_lama, nama_baru, no_sim_lama, no_sim_baru, hash_audit, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        driver_id, lama.nik, nik_baru, lama.nama_driver, nama_baru, lama.no_sim, sim_baru, hash_baru, updated_by
    )
    conn.commit()
    conn.close()

def cari_riwayat_driver_by_plat(no_plat):
    """Cari transaksi TERAKHIR untuk plat ini (apapun statusnya) untuk menyarankan supir & foto."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP 1 d.id_driver, d.nik, d.nama_driver, d.no_sim, d.foto_path, d.is_updated,
               k.id_kendaraan, k.no_stnk
        FROM transaksi t
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN driver d ON t.id_driver = d.id_driver
        WHERE k.no_plat = ?
        ORDER BY t.created_at DESC
    """, no_plat)
    row = cursor.fetchone()
    conn.close()
    return row

def cari_driver_by_nik(nik):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_driver, nik, nama_driver, no_sim, foto_path, is_updated FROM driver WHERE nik = ? AND is_active = 1", nik)
    row = cursor.fetchone()
    conn.close()
    return row

# ===== TRANSAKSI (INTI) =====

def generate_no_tiket(no_plat):
    plat_bersih = no_plat.replace(" ", "").upper()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"TKT-{plat_bersih}-{timestamp}"

def cari_transaksi_aktif(no_plat=None, no_tiket=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.no_tiket, t.jenis_transaksi, t.no_do, t.status_alur, t.qr_expired_at,
               t.id_supplier, t.id_produk, s.nama_supplier, p.nama_produk, p.kategori,
               k.no_plat, k.no_stnk,
               d.id_driver, d.nik, d.nama_driver, d.no_sim, d.is_updated, d.foto_path
        FROM transaksi t
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN supplier s ON t.id_supplier = s.id_supplier
        JOIN produk p ON t.id_produk = p.id_produk
        JOIN driver d ON t.id_driver = d.id_driver
        WHERE t.status_alur NOT IN ('SELESAI', 'REJECTED')
          AND (k.no_plat = ? OR t.no_tiket = ?)
        ORDER BY t.created_at DESC
    """, no_plat or '', no_tiket or '')
    row = cursor.fetchone()
    conn.close()
    return row

def cari_transaksi_aktif_by_plat(no_plat):
    return cari_transaksi_aktif(no_plat=no_plat)

def buat_transaksi_full(no_tiket, no_plat, no_stnk, jenis_transaksi, id_supplier, id_produk, id_driver, no_do, security_id):
    """INSERT sungguhan, dipanggil saat 'Mulai Validasi Awal' diklik (bukan saat Tab di base bar)."""
    kendaraan_id = get_or_create_kendaraan(no_plat, no_stnk)
    qr_expired = datetime.now() + timedelta(hours=24)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO transaksi
           (no_tiket, jenis_transaksi, id_supplier, id_produk, id_kendaraan, id_driver, no_do, qr_expired_at, security_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        no_tiket, jenis_transaksi, id_supplier, id_produk, kendaraan_id, id_driver, no_do, qr_expired, security_id
    )
    cursor.execute("INSERT INTO timbangan (no_tiket) VALUES (?)", no_tiket)
    cursor.execute("INSERT INTO timeline_monitoring (no_tiket, stage, processed_by) VALUES (?, 'SECURITY_INIT', ?)", no_tiket, security_id)
    conn.commit()
    conn.close()
    return no_tiket

def catat_timeline(no_tiket, stage, processed_by):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO timeline_monitoring (no_tiket, stage, processed_by) VALUES (?, ?, ?)",
        no_tiket, stage, processed_by
    )
    conn.commit()
    conn.close()

# ===== TIMBANGAN =====

def get_data_timbangan(no_tiket):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM timbangan WHERE no_tiket = ?", no_tiket)
    row = cursor.fetchone()
    conn.close()
    return row

def hitung_hash_timbang(no_tiket, bruto, tara, secret_key=None):
    if secret_key is None:
        secret_key = os.getenv("HASH_SECRET_KEY")
    data = f"{no_tiket}{bruto}{tara}{secret_key}"
    return hashlib.sha256(data.encode()).hexdigest()

def simpan_timbang_pertama(no_tiket, berat, operator_id):
    """Untuk PEMBELIAN: ini bruto. Untuk PENJUALAN: ini tara. Untuk PENIMBANGAN_SAJA: ini bruto (jadi netto langsung)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT jenis_transaksi FROM transaksi WHERE no_tiket = ?", no_tiket)
    jenis = cursor.fetchone().jenis_transaksi

    if jenis == 'PENJUALAN':
        cursor.execute("UPDATE timbangan SET berat_tara = ?, waktu_tara = GETDATE(), operator_timbang_id = ? WHERE no_tiket = ?", berat, operator_id, no_tiket)
    else:
        cursor.execute("UPDATE timbangan SET berat_bruto = ?, waktu_bruto = GETDATE(), operator_timbang_id = ? WHERE no_tiket = ?", berat, operator_id, no_tiket)

    if jenis == 'PENIMBANGAN_SAJA':
        cursor.execute("UPDATE timbangan SET berat_netto = ? WHERE no_tiket = ?", berat, no_tiket)
        cursor.execute("UPDATE transaksi SET status_alur = 'SELESAI' WHERE no_tiket = ?", no_tiket)
    else:
        cursor.execute("UPDATE transaksi SET status_alur = 'TIMBANG_1' WHERE no_tiket = ?", no_tiket)

    conn.commit()
    conn.close()
    return jenis

def simpan_timbang_kedua(no_tiket, berat, operator_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT jenis_transaksi FROM transaksi WHERE no_tiket = ?", no_tiket)
    jenis = cursor.fetchone().jenis_transaksi

    cursor.execute("SELECT berat_bruto, berat_tara FROM timbangan WHERE no_tiket = ?", no_tiket)
    existing = cursor.fetchone()

    if jenis == 'PENJUALAN':
        bruto = berat
        tara = existing.berat_tara
        cursor.execute("UPDATE timbangan SET berat_bruto = ?, waktu_bruto = GETDATE() WHERE no_tiket = ?", berat, no_tiket)
    else:
        bruto = existing.berat_bruto
        tara = berat
        cursor.execute("UPDATE timbangan SET berat_tara = ?, waktu_tara = GETDATE() WHERE no_tiket = ?", berat, no_tiket)

    netto = round(abs(bruto - tara), 2)
    hash_val = hitung_hash_timbang(no_tiket, bruto, tara)

    cursor.execute(
        "UPDATE timbangan SET berat_netto = ?, hash_keamanan = ?, operator_timbang_id = ? WHERE no_tiket = ?",
        netto, hash_val, operator_id, no_tiket
    )
    cursor.execute("UPDATE transaksi SET status_alur = 'SELESAI' WHERE no_tiket = ?", no_tiket)
    conn.commit()
    conn.close()
    return netto

def get_history_timbangan_by_supplier(id_supplier, hari=7):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.nama_supplier, k.no_plat, tb.berat_bruto, tb.berat_tara, tb.berat_netto, t.created_at
        FROM transaksi t
        JOIN supplier s ON t.id_supplier = s.id_supplier
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN timbangan tb ON t.no_tiket = tb.no_tiket
        WHERE t.id_supplier = ? AND t.created_at >= DATEADD(day, ?, GETDATE())
        ORDER BY t.created_at DESC
    """, id_supplier, -hari)
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data

def get_list_tiket_aktif():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.no_tiket, k.no_plat, s.nama_supplier AS supplier, t.status_alur
        FROM transaksi t
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN supplier s ON t.id_supplier = s.id_supplier
        WHERE t.status_alur NOT IN ('SELESAI', 'REJECTED')
        ORDER BY t.created_at DESC
    """)
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data

def get_history_driver(limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT TOP {int(limit)} k.no_plat, d.nama_driver, d.nik, d.no_sim
        FROM transaksi t
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN driver d ON t.id_driver = d.id_driver
        ORDER BY t.created_at DESC
    """)
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data

# ===== SORTASI & LAB =====
def get_data_sortasi(no_tiket):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sortasi WHERE no_tiket = ?", no_tiket)
    row = cursor.fetchone()
    conn.close()
    return row

def simpan_sortasi(no_tiket, mentah, busuk, tangkai, sampah, matang, brondolan, catatan, operator_id):
    data_tb = get_data_timbangan(no_tiket)
    berat_acuan = data_tb.berat_bruto or data_tb.berat_netto or 0
    total_persen_potongan = (mentah or 0) + (tangkai or 0) + (sampah or 0)
    total_potongan_kg = round(berat_acuan * total_persen_potongan / 100, 2)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_sortasi FROM sortasi WHERE no_tiket = ?", no_tiket)
    if cursor.fetchone():
        cursor.execute("""UPDATE sortasi SET persen_buah_mentah=?, persen_buah_busuk=?, persen_tangkai_panjang=?,
                           persen_sampah_kotoran=?, persen_buah_matang=?, persen_brondolan=?, total_potongan_kg=?,
                           catatan=?, operator_sortasi_id=?, waktu_sortasi=GETDATE() WHERE no_tiket=?""",
                       mentah, busuk, tangkai, sampah, matang, brondolan, total_potongan_kg, catatan, operator_id, no_tiket)
    else:
        cursor.execute("""INSERT INTO sortasi (no_tiket, persen_buah_mentah, persen_buah_busuk, persen_tangkai_panjang,
                           persen_sampah_kotoran, persen_buah_matang, persen_brondolan, total_potongan_kg, catatan,
                           operator_sortasi_id, waktu_sortasi) VALUES (?,?,?,?,?,?,?,?,?,?,GETDATE())""",
                       no_tiket, mentah, busuk, tangkai, sampah, matang, brondolan, total_potongan_kg, catatan, operator_id)
    cursor.execute("UPDATE transaksi SET status_alur = 'TIMBANG_2' WHERE no_tiket = ?", no_tiket)
    conn.commit()
    conn.close()
    return total_potongan_kg

def get_standar_mutu(id_produk):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM standar_mutu WHERE id_produk = ?", id_produk)
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO standar_mutu (id_produk) VALUES (?)", id_produk)
        conn.commit()
        cursor.execute("SELECT * FROM standar_mutu WHERE id_produk = ?", id_produk)
        row = cursor.fetchone()
    conn.close()
    return row

def update_standar_mutu(id_produk, maks_ffa, maks_air, maks_kotoran):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE standar_mutu SET maks_ffa=?, maks_air=?, maks_kotoran=? WHERE id_produk=?",
                   maks_ffa, maks_air, maks_kotoran, id_produk)
    conn.commit()
    conn.close()

def simpan_lab(no_tiket, ffa, air, kotoran, warna, keputusan, no_coa, operator_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_lab FROM lab_hasil WHERE no_tiket = ?", no_tiket)
    if cursor.fetchone():
        cursor.execute("""UPDATE lab_hasil SET ffa=?, kadar_air=?, kadar_kotoran=?, warna_locis=?,
                           keputusan=?, no_dokumen_coa=?, operator_lab_id=?, waktu_pemeriksaan=GETDATE() WHERE no_tiket=?""",
                       ffa, air, kotoran, warna, keputusan, no_coa, operator_id, no_tiket)
    else:
        cursor.execute("""INSERT INTO lab_hasil (no_tiket, ffa, kadar_air, kadar_kotoran, warna_locis, keputusan,
                           no_dokumen_coa, operator_lab_id, waktu_pemeriksaan) VALUES (?,?,?,?,?,?,?,?,GETDATE())""",
                       no_tiket, ffa, air, kotoran, warna, keputusan, no_coa, operator_id)

    status_baru = 'SELESAI' if keputusan == 'APPROVE' else 'REJECTED'
    if keputusan == 'REJECT':
        cursor.execute("UPDATE transaksi SET status_alur=?, alasan_reject=? WHERE no_tiket=?", status_baru, 'Ditolak Lab', no_tiket)
    else:
        cursor.execute("UPDATE transaksi SET status_alur=? WHERE no_tiket=?", status_baru, no_tiket)
    conn.commit()
    conn.close()

def get_history_umum(tabel, limit=10):
    conn = get_connection()
    cursor = conn.cursor()
    kolom_status = "sr.keputusan" if tabel == 'lab_hasil' else "t.status_alur"
    cursor.execute(f"""
        SELECT TOP {limit} k.no_plat, p.nama_produk, s.nama_supplier, {kolom_status} AS status_val
        FROM {tabel} sr
        JOIN transaksi t ON sr.no_tiket = t.no_tiket
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN produk p ON t.id_produk = p.id_produk
        JOIN supplier s ON t.id_supplier = s.id_supplier
        ORDER BY t.created_at DESC
    """)
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data