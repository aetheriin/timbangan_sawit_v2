import os
import pyodbc
import hashlib
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from config import get_connection_string
from utils.cache import cache_ttl

load_dotenv()

# Connection pooling ODBC: koneksi yang di-close() dikembalikan ke pool, bukan diputus.
# Harus di-set sebelum koneksi pertama dibuat.
pyodbc.pooling = True

def get_connection():
    return pyodbc.connect(get_connection_string(), timeout=10)

def cek_koneksi_db():
    """Dipakai /health: True bila database bisa dijangkau."""
    conn = get_connection()
    try:
        conn.cursor().execute("SELECT 1").fetchone()
        return True
    finally:
        conn.close()

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

@cache_ttl(300)
def get_semua_supplier():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_supplier, nama_supplier FROM supplier WHERE is_active = 1 ORDER BY nama_supplier")
    rows = cursor.fetchall()
    conn.close()
    return rows

@cache_ttl(300)
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

def get_kendaraan_by_plat(no_plat):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_kendaraan, no_plat, no_stnk, is_blacklisted FROM kendaraan WHERE no_plat = ?", no_plat)
    row = cursor.fetchone()
    conn.close()
    return row

def _rows_to_dicts(cursor):
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

# ----- Truk <-> Supir (tabel kendaraan_driver) -----

def get_supir_kendaraan(id_kendaraan):
    """Supir terdaftar untuk truk ini, supir utama paling atas."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id_personel AS id_driver, d.kode_personel, d.nik, d.nama_personel AS nama_driver, d.no_sim,
               d.foto_path, d.is_updated, d.is_blacklisted, kd.is_utama
        FROM kendaraan_driver kd
        JOIN personel d ON kd.id_driver = d.id_personel
        WHERE kd.id_kendaraan = ? AND kd.is_active = 1 AND d.is_active = 1
        ORDER BY kd.is_utama DESC, d.nama_personel
    """, id_kendaraan)
    data = _rows_to_dicts(cursor)
    conn.close()
    for r in data:
        r["is_utama"], r["is_updated"] = bool(r["is_utama"]), bool(r["is_updated"])
        r["is_blacklisted"] = bool(r["is_blacklisted"])
    return data

def _daftarkan_supir(cursor, id_kendaraan, id_driver, is_utama, user_id):
    """Tambah / aktifkan ulang relasi truk-supir. Kalau is_utama, supir lain di truk ini jadi bukan utama."""
    if is_utama:
        cursor.execute("UPDATE kendaraan_driver SET is_utama = 0, updated_at = GETDATE() WHERE id_kendaraan = ?",
                       id_kendaraan)
    cursor.execute("SELECT id_kendaraan_driver FROM kendaraan_driver WHERE id_kendaraan = ? AND id_driver = ?",
                   id_kendaraan, id_driver)
    if cursor.fetchone():
        cursor.execute("""UPDATE kendaraan_driver SET is_active = 1, is_utama = ?, updated_at = GETDATE()
                          WHERE id_kendaraan = ? AND id_driver = ?""", 1 if is_utama else 0, id_kendaraan, id_driver)
    else:
        cursor.execute("""INSERT INTO kendaraan_driver (id_kendaraan, id_driver, is_utama, created_by)
                          VALUES (?, ?, ?, ?)""", id_kendaraan, id_driver, 1 if is_utama else 0, user_id)

def tambah_supir_kendaraan(id_kendaraan, id_driver, is_utama, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    _daftarkan_supir(cursor, id_kendaraan, id_driver, is_utama, user_id)
    conn.commit()
    conn.close()

def nonaktifkan_supir_kendaraan(id_kendaraan, id_driver):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""UPDATE kendaraan_driver SET is_active = 0, is_utama = 0, updated_at = GETDATE()
                      WHERE id_kendaraan = ? AND id_driver = ?""", id_kendaraan, id_driver)
    conn.commit()
    conn.close()

# ----- Truk <-> Supplier (tabel kontrak_kendaraan) -----

def _status_kontrak(k, hari_ini):
    if not k["is_active"]:
        return "NONAKTIF"
    if k["tanggal_mulai"] > hari_ini:
        return "BELUM_MULAI"
    if k["tanggal_selesai"] is not None and k["tanggal_selesai"] < hari_ini:
        return "BERAKHIR"
    return "AKTIF"

def _ke_tanggal(v):
    """Kolom DATE dari pyodbc sudah berupa date; jaga-jaga kalau driver mengembalikan datetime / string."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])

def get_kontrak_kendaraan(id_kendaraan, hanya_aktif=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT kk.id_kontrak, kk.no_kontrak, kk.id_supplier, s.nama_supplier, kk.id_produk, p.nama_produk,
               kk.jenis_transaksi, kk.tanggal_mulai, kk.tanggal_selesai, kk.is_active, kk.keterangan
        FROM kontrak_kendaraan kk
        JOIN supplier s ON kk.id_supplier = s.id_supplier
        LEFT JOIN produk p ON kk.id_produk = p.id_produk
        WHERE kk.id_kendaraan = ?
        ORDER BY kk.is_active DESC, kk.tanggal_mulai DESC
    """, id_kendaraan)
    data = _rows_to_dicts(cursor)
    conn.close()
    hari_ini = date.today()
    for k in data:
        k["tanggal_mulai"], k["tanggal_selesai"] = _ke_tanggal(k["tanggal_mulai"]), _ke_tanggal(k["tanggal_selesai"])
        k["status"] = _status_kontrak(k, hari_ini)
        k["is_active"] = bool(k["is_active"])
        k["tanggal_mulai"] = k["tanggal_mulai"].isoformat()
        k["tanggal_selesai"] = k["tanggal_selesai"].isoformat() if k["tanggal_selesai"] else None
    if hanya_aktif:
        data = [k for k in data if k["status"] == "AKTIF"]
    return data

def _sql_kontrak_berlaku():
    return "is_active = 1 AND tanggal_mulai <= ? AND (tanggal_selesai IS NULL OR tanggal_selesai >= ?)"

def cari_kontrak_aktif(id_kendaraan, id_supplier, cursor=None):
    """id_kontrak yang berlaku hari ini untuk pasangan truk + supplier, atau None."""
    tutup = cursor is None
    if tutup:
        conn = get_connection()
        cursor = conn.cursor()
    hari_ini = date.today()
    cursor.execute(f"""SELECT TOP 1 id_kontrak FROM kontrak_kendaraan
                       WHERE id_kendaraan = ? AND id_supplier = ? AND {_sql_kontrak_berlaku()}
                       ORDER BY tanggal_mulai DESC""", id_kendaraan, id_supplier, hari_ini, hari_ini)
    row = cursor.fetchone()
    if tutup:
        conn.close()
    return row.id_kontrak if row else None

def tambah_kontrak(id_kendaraan, id_supplier, id_produk, jenis_transaksi, no_kontrak,
                   tanggal_mulai, tanggal_selesai, keterangan, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO kontrak_kendaraan
                      (no_kontrak, id_kendaraan, id_supplier, id_produk, jenis_transaksi,
                       tanggal_mulai, tanggal_selesai, keterangan, created_by)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   no_kontrak, id_kendaraan, id_supplier, id_produk, jenis_transaksi,
                   tanggal_mulai, tanggal_selesai, keterangan, user_id)
    conn.commit()
    conn.close()

def akhiri_kontrak(id_kontrak):
    """Nonaktifkan kontrak. Tanggal selesai diisi hari ini kalau masih kosong / lebih lambat."""
    conn = get_connection()
    cursor = conn.cursor()
    hari_ini = date.today()
    cursor.execute("""UPDATE kontrak_kendaraan SET is_active = 0,
                      tanggal_selesai = CASE WHEN tanggal_selesai IS NULL OR tanggal_selesai > ? THEN ?
                                             ELSE tanggal_selesai END
                      WHERE id_kontrak = ? AND tanggal_mulai <= ?""", hari_ini, hari_ini, id_kontrak, hari_ini)
    if cursor.rowcount == 0:   # kontrak yang belum mulai: cukup dinonaktifkan
        cursor.execute("UPDATE kontrak_kendaraan SET is_active = 0 WHERE id_kontrak = ?", id_kontrak)
    conn.commit()
    conn.close()

# ===== DRIVER (tabel personel, migrasi 002) =====
# Supir adalah personel berkategori DRIVER. Kolom dialias ke nama lama (id_driver, nama_driver)
# supaya kode & JSON tab Security / Timbangan / Sortasi / Lab tidak perlu berubah.

SQL_KOLOM_DRIVER = """d.id_personel AS id_driver, d.kode_personel, d.nik, d.nama_personel AS nama_driver, d.no_sim,
                      d.kategori, d.is_blacklisted, d.is_updated, d.foto_path"""

def get_all_driver_embeddings():
    """Semua personel aktif (bukan hanya DRIVER), supaya wajah security/karyawan tidak terbaca sebagai supir lain."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_personel, nama_personel, face_embedding_data FROM personel WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_driver_by_id(driver_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {SQL_KOLOM_DRIVER} FROM personel d WHERE d.id_personel = ?", driver_id)
    row = cursor.fetchone()
    conn.close()
    return row

def cek_nik_ada(nik, exclude_id=None):
    """NIK unik untuk semua personel, termasuk yang sudah dihapus (is_active = 0)."""
    conn = get_connection()
    cursor = conn.cursor()
    if exclude_id:
        cursor.execute("SELECT id_personel FROM personel WHERE nik = ? AND id_personel != ?", nik, exclude_id)
    else:
        cursor.execute("SELECT id_personel FROM personel WHERE nik = ?", nik)
    row = cursor.fetchone()
    conn.close()
    return row is not None

def cari_wajah_mirip_driver(embedding_baru, threshold=0.55, exclude_id=None):
    """Personel aktif paling mirip (dari cache embedding di memori), atau None."""
    from utils.face_cache import cari_terdekat
    id_personel, nama, _ = cari_terdekat(embedding_baru, threshold, exclude_id)
    return (id_personel, nama) if id_personel is not None else None

def insert_driver(nik, nama, no_sim, embedding_binary, foto_path=None, user_id=None, foto_sumber='KAMERA'):
    """Supir baru dari modal Tambah di Form Create Ticket = personel kategori DRIVER."""
    from utils.db_personel import insert_personel
    return insert_personel(nik, nama, no_sim, 'DRIVER', None, embedding_binary, foto_path, foto_sumber, user_id)

def hitung_hash_driver(nik, nama, no_sim, timestamp, secret_key=None):
    if secret_key is None:
        secret_key = os.getenv("HASH_SECRET_KEY")
    data = f"{nik}{nama}{no_sim}{timestamp}{secret_key}"
    return hashlib.sha256(data.encode()).hexdigest()

def update_driver_dengan_audit(driver_id, nik_baru, nama_baru, sim_baru, updated_by, embedding_binary=None, foto_path=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT nik, nama_personel, no_sim, kode_personel FROM personel WHERE id_personel = ?", driver_id)
    lama = cursor.fetchone()

    timestamp = datetime.now()
    hash_baru = hitung_hash_driver(nik_baru, nama_baru, sim_baru, timestamp)

    if embedding_binary is not None:
        cursor.execute(
            "UPDATE personel SET nik=?, nama_personel=?, no_sim=?, face_embedding_data=?, foto_path=?, is_updated=1, current_hash=?, updated_at=GETDATE() WHERE id_personel=?",
            nik_baru, nama_baru, sim_baru, embedding_binary, foto_path, hash_baru, driver_id
        )
    else:
        cursor.execute(
            "UPDATE personel SET nik=?, nama_personel=?, no_sim=?, is_updated=1, current_hash=?, updated_at=GETDATE() WHERE id_personel=?",
            nik_baru, nama_baru, sim_baru, hash_baru, driver_id
        )

    if embedding_binary is not None:
        from utils.face_cache import invalidate
        invalidate()
    cursor.execute(
        """INSERT INTO personel_audit_logs
           (id_personel, aksi, kode_personel_lama, kode_personel_baru, nik_lama, nik_baru, nama_lama, nama_baru,
            no_sim_lama, no_sim_baru, hash_audit, updated_by)
           VALUES (?, 'UPDATE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        driver_id, lama.kode_personel, lama.kode_personel, lama.nik, nik_baru, lama.nama_personel, nama_baru,
        lama.no_sim, sim_baru, hash_baru, updated_by
    )
    conn.commit()
    conn.close()

def cari_riwayat_driver_by_plat(no_plat):
    """Cari transaksi TERAKHIR untuk plat ini (apapun statusnya) untuk menyarankan supir & foto."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT TOP 1 {SQL_KOLOM_DRIVER}, k.id_kendaraan, k.no_stnk
        FROM transaksi t
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN personel d ON t.id_driver = d.id_personel
        WHERE k.no_plat = ?
        ORDER BY t.created_at DESC
    """, no_plat)
    row = cursor.fetchone()
    conn.close()
    return row

def cari_driver_by_nik(nik):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {SQL_KOLOM_DRIVER} FROM personel d WHERE d.nik = ? AND d.is_active = 1", nik)
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
               t.created_at, t.qr_reprint_count, t.id_supplier, t.id_produk, s.nama_supplier, p.nama_produk, p.kategori,
               k.no_plat, k.no_stnk,
               d.id_personel AS id_driver, d.kode_personel, d.nik, d.nama_personel AS nama_driver, d.no_sim,
               d.is_updated, d.is_blacklisted, d.foto_path
        FROM transaksi t
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN supplier s ON t.id_supplier = s.id_supplier
        JOIN produk p ON t.id_produk = p.id_produk
        JOIN personel d ON t.id_driver = d.id_personel
        WHERE t.status_alur NOT IN ('SELESAI', 'REJECTED')
          AND (k.no_plat = ? OR t.no_tiket = ?)
        ORDER BY t.created_at DESC
    """, no_plat or '', no_tiket or '')
    row = cursor.fetchone()
    conn.close()
    return row

def cari_transaksi_aktif_by_plat(no_plat):
    return cari_transaksi_aktif(no_plat=no_plat)

def catat_cetak_qr(no_tiket):
    """Naikkan hitungan cetak QR, kembalikan jumlah cetak sebelumnya (0 = cetakan pertama)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT qr_reprint_count FROM transaksi WHERE no_tiket = ?", no_tiket)
    sebelumnya = cursor.fetchone()[0] or 0
    cursor.execute("UPDATE transaksi SET qr_reprint_count = qr_reprint_count + 1 WHERE no_tiket = ?", no_tiket)
    conn.commit()
    conn.close()
    return sebelumnya

def buat_transaksi_full(no_tiket, no_plat, no_stnk, jenis_transaksi, id_supplier, id_produk, id_driver, no_do, security_id,
                        prev_driver_id=None):
    """INSERT sungguhan, dipanggil saat 'Mulai Validasi Awal' diklik (bukan saat Tab di base bar)."""
    kendaraan_id = get_or_create_kendaraan(no_plat, no_stnk)
    qr_expired = datetime.now() + timedelta(hours=24)

    conn = get_connection()
    cursor = conn.cursor()
    id_kontrak = cari_kontrak_aktif(kendaraan_id, id_supplier, cursor)
    cursor.execute(
        """INSERT INTO transaksi
           (no_tiket, jenis_transaksi, id_supplier, id_produk, id_kendaraan, id_driver, no_do, qr_expired_at,
            security_id, id_kontrak, is_driver_changed, prev_driver_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        no_tiket, jenis_transaksi, id_supplier, id_produk, kendaraan_id, id_driver, no_do, qr_expired,
        security_id, id_kontrak, 1 if prev_driver_id else 0, prev_driver_id
    )
    # Supir yang membawa truk ini otomatis tercatat di daftar supir truk.
    # Kalau truk belum punya supir sama sekali, supir ini jadi supir utama.
    cursor.execute("SELECT id_driver FROM kendaraan_driver WHERE id_kendaraan = ? AND id_driver = ? AND is_active = 1",
                   kendaraan_id, id_driver)
    if not cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM kendaraan_driver WHERE id_kendaraan = ? AND is_active = 1", kendaraan_id)
        _daftarkan_supir(cursor, kendaraan_id, id_driver, cursor.fetchone()[0] == 0, security_id)
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
    cursor.execute("""
        SELECT tb.no_tiket, tb.berat_bruto, tb.waktu_bruto, tb.berat_tara, tb.waktu_tara, tb.berat_netto,
               tb.operator_timbang_id, s.total_potongan_kg
        FROM timbangan tb
        LEFT JOIN sortasi s ON s.no_tiket = tb.no_tiket
        WHERE tb.no_tiket = ?
    """, no_tiket)
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
    # Potongan sortasi = persen potongan x NETTO (berat buah saja, tanpa truk)
    cursor.execute(f"UPDATE sortasi SET total_potongan_kg = ROUND(? * {SQL_PERSEN_POTONGAN} / 100, 2) WHERE no_tiket = ?",
                   netto, no_tiket)
    conn.commit()
    conn.close()
    return netto

def get_history_timbangan_by_supplier(id_supplier, hari=7):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP 200 s.nama_supplier, k.no_plat, tb.berat_bruto, tb.berat_tara, tb.berat_netto, t.created_at
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
        SELECT TOP {int(limit)} k.no_plat, d.id_personel AS id_driver, d.kode_personel,
               d.nama_personel AS nama_driver, d.nik, d.no_sim, d.is_blacklisted
        FROM transaksi t
        JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
        JOIN personel d ON t.id_driver = d.id_personel
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
    cursor.execute("""SELECT no_tiket, persen_buah_mentah, persen_buah_busuk, persen_tangkai_panjang,
                             persen_sampah_kotoran, persen_buah_matang, persen_brondolan, total_potongan_kg,
                             catatan, waktu_sortasi
                      FROM sortasi WHERE no_tiket = ?""", no_tiket)
    row = cursor.fetchone()
    conn.close()
    return row

# Komponen yang memotong berat: buah mentah + tangkai panjang + sampah/kotoran
SQL_PERSEN_POTONGAN = ("(COALESCE(persen_buah_mentah, 0) + COALESCE(persen_tangkai_panjang, 0)"
                       " + COALESCE(persen_sampah_kotoran, 0))")

def hitung_persen_potongan(mentah, tangkai, sampah):
    return round((mentah or 0) + (tangkai or 0) + (sampah or 0), 2)

def simpan_sortasi(no_tiket, mentah, busuk, tangkai, sampah, matang, brondolan, catatan, operator_id):
    """Potongan kg dihitung dari NETTO. Netto baru ada setelah timbang keluar, jadi sebelum itu
    total_potongan_kg = NULL dan akan diisi otomatis oleh simpan_timbang_kedua."""
    data_tb = get_data_timbangan(no_tiket)
    total_persen_potongan = hitung_persen_potongan(mentah, tangkai, sampah)
    total_potongan_kg = (round(data_tb.berat_netto * total_persen_potongan / 100, 2)
                         if data_tb.berat_netto is not None else None)

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
    return total_persen_potongan, total_potongan_kg

SQL_STANDAR = "SELECT id_produk, maks_ffa, maks_air, maks_kotoran FROM standar_mutu WHERE id_produk = ?"

@cache_ttl(300)
def get_standar_mutu(id_produk):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(SQL_STANDAR, id_produk)
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO standar_mutu (id_produk) VALUES (?)", id_produk)
        conn.commit()
        cursor.execute(SQL_STANDAR, id_produk)
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
    get_standar_mutu.hapus()

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

    # APPROVE -> lanjut timbang kedua (bukan langsung SELESAI, supaya netto tetap tercatat)
    if keputusan == 'REJECT':
        cursor.execute("UPDATE transaksi SET status_alur='REJECTED', alasan_reject=?, rejected_by=? WHERE no_tiket=?",
                       'Ditolak Lab', operator_id, no_tiket)
    else:
        cursor.execute("UPDATE transaksi SET status_alur='TIMBANG_2' WHERE no_tiket=?", no_tiket)
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