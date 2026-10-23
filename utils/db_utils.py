import os
import pyodbc
import hashlib
import time
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
from config import get_connection_string
from utils.cache import cache_ttl

load_dotenv()

# Connection pooling ODBC: koneksi yang di-close() dikembalikan ke pool, bukan diputus.
# Harus di-set sebelum koneksi pertama dibuat.
pyodbc.pooling = True

QUERY_TIMEOUT_DETIK = int(os.getenv("DB_QUERY_TIMEOUT", "15"))


def get_connection():
    """Koneksi baru (dari pool ODBC). Waktu buka koneksi dicatat per request untuk log LAMBAT."""
    mulai = time.perf_counter()
    conn = pyodbc.connect(get_connection_string(), timeout=10)
    conn.timeout = QUERY_TIMEOUT_DETIK          # query tertahan (lock / server sibuk) -> error, bukan menunggu lama
    try:
        from flask import g, has_request_context
        if has_request_context():
            g.db_koneksi = getattr(g, "db_koneksi", 0) + 1
            g.db_buka_ms = getattr(g, "db_buka_ms", 0) + (time.perf_counter() - mulai) * 1000
            _isi_konteks(conn)
    except ImportError:
        pass
    return conn

def _isi_konteks(conn):
    """Pengguna & IP request ini untuk trigger log perubahan data (migrasi 034). Gagal -> dicatat tanpa pengguna."""
    # Hanya user yang sudah dimuat flask-login (g._login_user): memanggil current_user di sini bisa berulang
    # karena memuat user juga membuka koneksi.
    from flask import g, request
    user = g.get("_login_user")
    id_user = getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None
    if id_user is None:
        return
    try:
        conn.cursor().execute("EXEC sp_set_session_context N'id_user', ?; EXEC sp_set_session_context N'ip', ?",
                              id_user, (request.remote_addr or "")[:45] or None)
    except pyodbc.Error:
        pass

def cek_koneksi_db():
    """Dipakai /health: True bila database bisa dijangkau."""
    conn = get_connection()
    try:
        conn.cursor().execute("SELECT 1").fetchone()
        return True
    finally:
        conn.close()

# ===== USERS (ERD Ladder Desk: Users + LevelDetails = peran + PasswordManager) =====
_KOLOM_USER = """u.UserID AS id_user, u.UserName AS username, u.Nama AS nama, ld.LevelDetCode AS role,
                 ld.LevelDetName AS nama_level, u.UserLevelID AS id_level, lv.IsAdmin AS is_admin, ld.HomeUrl AS halaman_awal,
                 u.SessionVersion AS sesi_versi"""
_DARI_USER = """FROM Users u JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID JOIN Level lv ON lv.LevelID = ld.LevelID"""


def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""SELECT {_KOLOM_USER}, pm.UserPasswd AS password,
                              CASE WHEN pm.MustChange = 1 THEN NULL ELSE pm.CreateDate END AS password_changed_at
                       {_DARI_USER} JOIN PasswordManager pm ON pm.UserID = u.UserID
                       WHERE u.UserName = ? AND u.Active = 1 AND ld.Active = 1""", username)
    row = cursor.fetchone()
    conn.close()
    return row

@cache_ttl(15)
def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    # User yang dinonaktifkan langsung kehilangan sesi (flask-login memanggil ini setiap request)
    cursor.execute(f"SELECT {_KOLOM_USER} {_DARI_USER} WHERE u.UserID = ? AND u.Active = 1 AND ld.Active = 1", user_id)
    row = cursor.fetchone()
    conn.close()
    return row

def get_password_hash(user_id):
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT UserPasswd FROM PasswordManager WHERE UserID = ?", user_id).fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def ganti_password_sendiri(user_id, password_hash):
    """Password baru oleh user sendiri. Sesi lain user ini dicabut; kembalikan sesi_versi baru untuk sesi sekarang."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        simpan_password(cursor, user_id, password_hash, wajib_ganti=False)
        cursor.execute("""SET NOCOUNT ON; DECLARE @o TABLE (v INT);
                          UPDATE Users SET SessionVersion = SessionVersion + 1, UpdateDate = GETDATE()
                          OUTPUT INSERTED.SessionVersion INTO @o WHERE UserID = ?; SELECT v FROM @o""", user_id)
        versi = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    get_user_by_id.hapus()
    return versi

RIWAYAT_PASSWORD_MAKS = 12


def simpan_password(cursor, user_id, password_hash, wajib_ganti):
    """Isi / ganti password di PasswordManager; hash baru masuk paling depan History (disimpan secukupnya)."""
    import json
    row = cursor.execute("SELECT History FROM PasswordManager WITH (UPDLOCK) WHERE UserID = ?", user_id).fetchone()
    riwayat = [password_hash] + (json.loads(row[0] or "[]") if row else [])
    riwayat = json.dumps(riwayat[:RIWAYAT_PASSWORD_MAKS])
    if row:
        cursor.execute("""UPDATE PasswordManager SET UserPasswd = ?, CreateDate = GETDATE(), MustChange = ?, History = ?
                          WHERE UserID = ?""", password_hash, 1 if wajib_ganti else 0, riwayat, user_id)
    else:
        cursor.execute("INSERT INTO PasswordManager (UserID, UserPasswd, MustChange, History) VALUES (?, ?, ?, ?)",
                       user_id, password_hash, 1 if wajib_ganti else 0, riwayat)

def password_pernah_dipakai(user_id, password):
    """True bila password sama dengan salah satu dari N password terakhir (Pengaturan › PASSWORD_RIWAYAT)."""
    import json
    from werkzeug.security import check_password_hash
    from utils import pengaturan
    n = pengaturan.nilai("PASSWORD_RIWAYAT")
    if not n:
        return False
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT History FROM PasswordManager WHERE UserID = ?", user_id).fetchone()
    finally:
        conn.close()
    return any(check_password_hash(h, password) for h in (json.loads(row[0] or "[]") if row else [])[:n])

def pesan_riwayat_password():
    from utils import pengaturan
    n = pengaturan.nilai("PASSWORD_RIWAYAT")
    return (f"Password baru tidak boleh sama dengan {n} password terakhir." if n and n > 1
            else "Password baru tidak boleh sama dengan password lama.")

def naikkan_sesi_versi(user_id):
    """Cabut semua sesi lain user ini (login di perangkat baru); kembalikan sesi_versi baru."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SET NOCOUNT ON; DECLARE @o TABLE (v INT);
                          UPDATE Users SET SessionVersion = SessionVersion + 1 OUTPUT INSERTED.SessionVersion INTO @o
                          WHERE UserID = ?; SELECT v FROM @o""", user_id)
        versi = cursor.fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    get_user_by_id.hapus()
    return versi

def catat_login_terakhir(user_id):
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE Users SET LastLogin = GETDATE() WHERE UserID = ?", user_id)
        conn.commit()
    finally:
        conn.close()

def user_id_baru(cursor):
    """UserID format Ladder Desk: YYMMDD + urutan 4 digit (mis. 2601010001)."""
    cursor.execute("""SET NOCOUNT ON; DECLARE @p BIGINT = CAST(FORMAT(GETDATE(), 'yyMMdd') AS BIGINT) * 10000;
                      SELECT ISNULL(MAX(UserID), @p) + 1 FROM Users WITH (UPDLOCK, HOLDLOCK)
                      WHERE UserID > @p AND UserID < @p + 10000""")
    return cursor.fetchone()[0]

# ===== SUPPLIER / PRODUK =====

@cache_ttl(300)
def get_semua_supplier():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT s.SupplierID AS id_supplier, s.SupplierName AS nama_supplier,
                             CAST(CASE WHEN EXISTS (SELECT 1 FROM SupplierTypeDetails p WHERE p.SupplierID = s.SupplierID
                                                    AND p.TypeCode = 'CUSTOMER') THEN 1 ELSE 0 END AS BIT) AS is_customer,
                             CAST(CASE WHEN EXISTS (SELECT 1 FROM SupplierTypeDetails p WHERE p.SupplierID = s.SupplierID
                                                    AND p.TypeCode = 'PENGANGKUTAN') THEN 1 ELSE 0 END AS BIT) AS is_angkutan
                      FROM Supplier s WHERE s.Active = 1 ORDER BY s.SupplierName""")
    rows = cursor.fetchall()
    conn.close()
    return rows

@cache_ttl(300)
def get_semua_produk():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ProductID AS id_produk, ProductName AS nama_produk, Category AS kategori, FlowID AS id_alur FROM Product WHERE Active = 1 ORDER BY ProductName")
    rows = cursor.fetchall()
    conn.close()
    return rows

# ===== KENDARAAN =====

def get_or_create_kendaraan(no_plat, no_stnk=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IDVehicle AS id_kendaraan FROM DetailVehicle WHERE NoVehicle = ?", no_plat)
    row = cursor.fetchone()
    if row:
        if no_stnk:
            cursor.execute("UPDATE DetailVehicle SET NoSTNK = ? WHERE IDVehicle = ?", no_stnk, row.id_kendaraan)
            conn.commit()
        conn.close()
        return row.id_kendaraan
    cursor.execute("INSERT INTO DetailVehicle (NoVehicle, NoSTNK) VALUES (?, ?)", no_plat, no_stnk)
    conn.commit()
    cursor.execute("SELECT IDVehicle AS id_kendaraan FROM DetailVehicle WHERE NoVehicle = ?", no_plat)
    kendaraan_id = cursor.fetchone().id_kendaraan
    conn.close()
    return kendaraan_id

def get_kendaraan_by_plat(no_plat):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT IDVehicle AS id_kendaraan, NoVehicle AS no_plat, NoSTNK AS no_stnk, CAST(CASE WHEN BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted, Active AS is_active FROM DetailVehicle WHERE NoVehicle = ?", no_plat)
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
        SELECT d.UserID AS id_driver, d.UserCode AS kode_personel, d.NoKTP AS nik, d.Nama AS nama_driver, d.LicenseNumber AS no_sim,
               d.PhotoPath AS foto_path, d.IsUpload AS is_updated, d.IsBlacklisted AS is_blacklisted, kd.IsMain AS is_utama
        FROM VehicleDriver kd
        JOIN UserProfile d ON kd.UserID = d.UserID
        WHERE kd.IDVehicle = ? AND kd.Active = 1 AND d.Active = 1
        ORDER BY kd.IsMain DESC, d.Nama
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
        cursor.execute("UPDATE VehicleDriver SET IsMain = 0, UpdateDate = GETDATE() WHERE IDVehicle = ?",
                       id_kendaraan)
    cursor.execute("SELECT VehicleDriverID AS id_kendaraan_driver FROM VehicleDriver WHERE IDVehicle = ? AND UserID = ?",
                   id_kendaraan, id_driver)
    if cursor.fetchone():
        cursor.execute("""UPDATE VehicleDriver SET Active = 1, IsMain = ?, UpdateDate = GETDATE()
                          WHERE IDVehicle = ? AND UserID = ?""", 1 if is_utama else 0, id_kendaraan, id_driver)
    else:
        cursor.execute("""INSERT INTO VehicleDriver (IDVehicle, UserID, IsMain, CreateBy)
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
    cursor.execute("""UPDATE VehicleDriver SET Active = 0, IsMain = 0, UpdateDate = GETDATE()
                      WHERE IDVehicle = ? AND UserID = ?""", id_kendaraan, id_driver)
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
        SELECT kk.VehicleContractID AS id_kontrak, kk.ContractNumber AS no_kontrak, kk.SupplierID AS id_supplier, s.SupplierName AS nama_supplier, kk.ProductID AS id_produk, p.ProductName AS nama_produk,
               kk.TransactionType AS jenis_transaksi, kk.StartDate AS tanggal_mulai, kk.EndDate AS tanggal_selesai, kk.Active AS is_active, kk.Description AS keterangan
        FROM VehicleContract kk
        JOIN Supplier s ON kk.SupplierID = s.SupplierID
        LEFT JOIN Product p ON kk.ProductID = p.ProductID
        WHERE kk.IDVehicle = ?
        ORDER BY kk.Active DESC, kk.StartDate DESC
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
    return "Active = 1 AND StartDate <= ? AND (EndDate IS NULL OR EndDate >= ?)"

def cari_kontrak_aktif(id_kendaraan, id_supplier, cursor=None):
    """id_kontrak yang berlaku hari ini untuk pasangan truk + supplier, atau None."""
    tutup = cursor is None
    if tutup:
        conn = get_connection()
        cursor = conn.cursor()
    hari_ini = date.today()
    cursor.execute(f"""SELECT TOP 1 VehicleContractID AS id_kontrak FROM VehicleContract
                       WHERE IDVehicle = ? AND SupplierID = ? AND {_sql_kontrak_berlaku()}
                       ORDER BY StartDate DESC""", id_kendaraan, id_supplier, hari_ini, hari_ini)
    row = cursor.fetchone()
    if tutup:
        conn.close()
    return row.id_kontrak if row else None

def tambah_kontrak(id_kendaraan, id_supplier, id_produk, jenis_transaksi, no_kontrak,
                   tanggal_mulai, tanggal_selesai, keterangan, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO VehicleContract
                      (ContractNumber, IDVehicle, SupplierID, ProductID, TransactionType,
                       StartDate, EndDate, Description, CreateBy)
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
    cursor.execute("""UPDATE VehicleContract SET Active = 0,
                      EndDate = CASE WHEN EndDate IS NULL OR EndDate > ? THEN ?
                                             ELSE EndDate END
                      WHERE VehicleContractID = ? AND StartDate <= ?""", hari_ini, hari_ini, id_kontrak, hari_ini)
    if cursor.rowcount == 0:   # kontrak yang belum mulai: cukup dinonaktifkan
        cursor.execute("UPDATE VehicleContract SET Active = 0 WHERE VehicleContractID = ?", id_kontrak)
    conn.commit()
    conn.close()

# ===== DRIVER (tabel personel, migrasi 002) =====
# Supir adalah personel berkategori DRIVER. Kolom dialias ke nama lama (id_driver, nama_driver)
# supaya kode & JSON tab Security / Timbangan / Sortasi / Lab tidak perlu berubah.

SQL_KOLOM_DRIVER = """d.UserID AS id_driver, d.UserCode AS kode_personel, d.NoKTP AS nik, d.Nama AS nama_driver, d.LicenseNumber AS no_sim,
                      d.CategoryCode AS kategori, d.IsBlacklisted AS is_blacklisted, d.IsUpload AS is_updated, d.PhotoPath AS foto_path"""

def get_all_driver_embeddings():
    """Semua personel aktif (bukan hanya DRIVER), supaya wajah security/karyawan tidak terbaca sebagai supir lain."""
    conn = get_connection()
    cursor = conn.cursor()
    # Semua wajah aktif (personel_wajah, migrasi 009); satu personel bisa punya lebih dari satu
    cursor.execute("""SELECT p.UserID AS id_personel, p.Nama AS nama_personel, w.FaceDet AS embedding FROM FaceRecog w
                      JOIN Users p ON p.UserID = w.UserID
                      WHERE p.Active = 1 AND w.Active = 1""")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_driver_by_id(driver_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {SQL_KOLOM_DRIVER} FROM UserProfile d WHERE d.UserID = ?", driver_id)
    row = cursor.fetchone()
    conn.close()
    return row

def cek_nik_ada(nik, exclude_id=None):
    """NIK unik untuk semua personel, termasuk yang sudah dihapus (is_active = 0)."""
    conn = get_connection()
    cursor = conn.cursor()
    if exclude_id:
        cursor.execute("SELECT UserID AS id_personel FROM Users WHERE NoKTP = ? AND UserID != ?", nik, exclude_id)
    else:
        cursor.execute("SELECT UserID AS id_personel FROM Users WHERE NoKTP = ?", nik)
    row = cursor.fetchone()
    conn.close()
    return row is not None

def cari_wajah_mirip_driver(embedding_baru, threshold=None, exclude_id=None):
    """Personel aktif paling mirip (dari cache embedding di memori), atau None."""
    from utils.face_cache import cari_terdekat
    if threshold is None:
        from utils import pengaturan          # import di sini: pengaturan juga memakai db_utils
        threshold = pengaturan.nilai("AMBANG_WAJAH")
    id_personel, nama, _ = cari_terdekat(embedding_baru, threshold, exclude_id)
    return (id_personel, nama) if id_personel is not None else None

def insert_driver(nik, nama, no_sim, embedding_binary, foto_path=None, user_id=None, foto_sumber='KAMERA'):
    """Supir baru dari modal Tambah di Form Create Ticket = personel kategori DRIVER, kode otomatis (mis. DRV-012).
    Kembalikan (id_personel, kode_personel)."""
    from utils.db_personel import insert_personel, saran_kode_personel
    kode = saran_kode_personel('DRIVER')
    return insert_personel(nik, nama, no_sim, 'DRIVER', kode, embedding_binary, foto_path, foto_sumber, user_id), kode

def hitung_hash_driver(nik, nama, no_sim, timestamp, secret_key=None):
    if secret_key is None:
        secret_key = os.getenv("HASH_SECRET_KEY")
    data = f"{nik}{nama}{no_sim}{timestamp}{secret_key}"
    return hashlib.sha256(data.encode()).hexdigest()

def update_driver_dengan_audit(driver_id, nik_baru, nama_baru, sim_baru, updated_by, embedding_binary=None, foto_path=None):
    """Ubah identitas supir dari Form Security (modal Update). SIM & wajah lewat personel_sim / personel_wajah."""
    from utils.db_personel import simpan_sim, simpan_wajah
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT NoKTP AS nik, Nama AS nama_personel, LicenseNumber AS no_sim, UserCode AS kode_personel FROM UserProfile WHERE UserID = ?", driver_id)
    lama = cursor.fetchone()

    timestamp = datetime.now()
    hash_baru = hitung_hash_driver(nik_baru, nama_baru, sim_baru, timestamp)
    cursor.execute("UPDATE Users SET NoKTP=?, Nama=?, IsUpload=1, CurrentHash=?, UpdateDate=GETDATE() WHERE UserID=?",
                   nik_baru, nama_baru, hash_baru, driver_id)
    simpan_sim(cursor, driver_id, sim_baru, user_id=updated_by)
    if embedding_binary is not None:
        simpan_wajah(cursor, driver_id, embedding_binary, foto_path, "KAMERA", updated_by)
    from utils import log_aktivitas
    log_aktivitas.catat("PERSONEL", "UPDATE", tabel="Users", id_baris=driver_id, user_id=updated_by, cursor=cursor,
                        lama={"kode_personel": lama.kode_personel, "nik": lama.nik, "nama": lama.nama_personel,
                              "no_sim": lama.no_sim},
                        baru={"kode_personel": lama.kode_personel, "nik": nik_baru, "nama": nama_baru, "no_sim": sim_baru})
    conn.commit()
    conn.close()
    if embedding_binary is not None:
        from utils.face_cache import invalidate
        invalidate()

def cari_riwayat_driver_by_plat(no_plat):
    """Cari transaksi TERAKHIR untuk plat ini (apapun statusnya) untuk menyarankan supir & foto."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT TOP 1 {SQL_KOLOM_DRIVER}, k.IDVehicle AS id_kendaraan, k.NoSTNK AS no_stnk
        FROM transaksi t
        JOIN DetailVehicle k ON t.id_kendaraan = k.IDVehicle
        JOIN UserProfile d ON t.id_driver = d.UserID
        WHERE k.NoVehicle = ?
        ORDER BY t.created_at DESC
    """, no_plat)
    row = cursor.fetchone()
    conn.close()
    return row

def cari_driver_by_nik(nik):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {SQL_KOLOM_DRIVER} FROM UserProfile d WHERE d.NoKTP = ? AND d.Active = 1", nik)
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
               t.created_at, t.qr_reprint_count, t.id_supplier, t.id_produk, s.SupplierName AS nama_supplier, p.ProductName AS nama_produk, p.Category AS kategori,
               t.id_comp_area, t.id_alur, t.cara_angkut, t.id_pengangkutan, k.NoVehicle AS no_plat, k.NoSTNK AS no_stnk,
               d.UserID AS id_driver, d.UserCode AS kode_personel, d.NoKTP AS nik, d.Nama AS nama_driver, d.LicenseNumber AS no_sim,
               d.IsUpload AS is_updated, d.IsBlacklisted AS is_blacklisted, d.PhotoPath AS foto_path
        FROM transaksi t
        JOIN DetailVehicle k ON t.id_kendaraan = k.IDVehicle
        JOIN Supplier s ON t.id_supplier = s.SupplierID
        JOIN Product p ON t.id_produk = p.ProductID
        JOIN UserProfile d ON t.id_driver = d.UserID
        WHERE t.status_alur NOT IN ('SELESAI', 'REJECTED', 'VOID')
          AND (k.NoVehicle = ? OR t.no_tiket = ?)
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
                        id_pengangkutan=None, id_comp_area=None, id_alur=None, id_do=None, cara_angkut="PENGIRIM"):
    """INSERT sungguhan, dipanggil saat 'Mulai Validasi Awal' diklik (bukan saat Tab di base bar)."""
    kendaraan_id = get_or_create_kendaraan(no_plat, no_stnk)
    qr_expired = datetime.now() + timedelta(hours=24)

    conn = get_connection()
    cursor = conn.cursor()
    id_kontrak = cari_kontrak_aktif(kendaraan_id, id_supplier, cursor)
    cursor.execute(
        """INSERT INTO transaksi
           (no_tiket, jenis_transaksi, id_supplier, id_produk, id_kendaraan, id_driver, no_do, qr_expired_at,
            security_id, id_kontrak, id_pengangkutan, id_comp_area, id_alur, id_do, cara_angkut)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        no_tiket, jenis_transaksi, id_supplier, id_produk, kendaraan_id, id_driver, no_do, qr_expired,
        security_id, id_kontrak, id_pengangkutan, id_comp_area, id_alur, id_do, cara_angkut
    )
    # Supir yang membawa truk ini otomatis tercatat di daftar supir truk.
    # Kalau truk belum punya supir sama sekali, supir ini jadi supir utama.
    cursor.execute("SELECT UserID AS id_driver FROM VehicleDriver WHERE IDVehicle = ? AND UserID = ? AND Active = 1",
                   kendaraan_id, id_driver)
    if not cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM VehicleDriver WHERE IDVehicle = ? AND Active = 1", kendaraan_id)
        _daftarkan_supir(cursor, kendaraan_id, id_driver, cursor.fetchone()[0] == 0, security_id)
    from utils import log_aktivitas
    log_aktivitas.catat("TIMELINE", "SECURITY_INIT", tabel="transaksi", id_baris=no_tiket, user_id=security_id, cursor=cursor)
    conn.commit()
    conn.close()
    return no_tiket

def catat_timeline(no_tiket, stage, processed_by):
    from utils import log_aktivitas
    log_aktivitas.catat("TIMELINE", stage, tabel="transaksi", id_baris=no_tiket, user_id=processed_by)

# ===== TIMBANGAN =====

def get_data_timbangan(no_tiket):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tb.no_tiket, tb.berat_bruto, tb.waktu_bruto, tb.berat_tara, tb.waktu_tara, tb.berat_netto,
               tb.operator_timbang_id, tb.id_jembatan, tb.kode_jembatan, s.total_potongan_kg
        FROM v_timbangan tb
        LEFT JOIN sortasi s ON s.no_tiket = tb.no_tiket
        WHERE tb.no_tiket = ?
    """, no_tiket)
    row = cursor.fetchone()
    conn.close()
    return row

def hitung_hash_timbang(no_tiket, ke, berat, id_jembatan, secret_key=None):
    """Hash anti-ubah satu baris penimbangan."""
    if secret_key is None:
        secret_key = os.getenv("HASH_SECRET_KEY")
    data = f"{no_tiket}|{ke}|{float(berat):.2f}|{id_jembatan}|{secret_key}"
    return hashlib.sha256(data.encode()).hexdigest()

def _simpan_penimbangan(cursor, no_tiket, ke, berat, id_jembatan, operator_id):
    cursor.execute("""INSERT INTO penimbangan (no_tiket, ke, id_jembatan, berat_kg, operator, hash)
                      VALUES (?, ?, ?, ?, ?, ?)""",
                   no_tiket, ke, id_jembatan, round(float(berat), 2), operator_id,
                   hitung_hash_timbang(no_tiket, ke, berat, id_jembatan))

def _status_setelah(cursor, no_tiket, kode_tahap):
    """Status tiket setelah tahap ini, menurut alur tiket (utils/alur.py)."""
    from utils.alur import status_setelah
    cursor.execute("""SELECT t.jenis_transaksi, t.id_alur FROM transaksi t
                      WHERE t.no_tiket = ?""", no_tiket)
    row = cursor.fetchone()
    if row.id_alur is None:          # tiket tanpa alur (data lama sebelum migrasi 041): aturan lama
        if kode_tahap == 'TIMBANG_1':
            return 'SELESAI' if row.jenis_transaksi == 'PENIMBANGAN_SAJA' else 'TIMBANG_1'
        return 'SELESAI' if kode_tahap == 'TIMBANG_2' else 'TIMBANG_2'
    return status_setelah(row.id_alur, kode_tahap)

def simpan_timbang_pertama(no_tiket, berat, operator_id, id_jembatan):
    """Timbang masuk (penimbangan ke-1). PEMBELIAN / PENIMBANGAN_SAJA: bruto; PENJUALAN: tara.
    Jembatan masuk dicatat di transaksi; timbang keluar wajib di jembatan yang sama."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT jenis_transaksi FROM transaksi WHERE no_tiket = ?", no_tiket)
    jenis = cursor.fetchone().jenis_transaksi
    _simpan_penimbangan(cursor, no_tiket, 1, berat, id_jembatan, operator_id)
    cursor.execute("UPDATE transaksi SET id_jembatan = ?, status_alur = ? WHERE no_tiket = ?", id_jembatan,
                   _status_setelah(cursor, no_tiket, 'TIMBANG_1'), no_tiket)
    conn.commit()
    conn.close()
    return jenis

def simpan_timbang_kedua(no_tiket, berat, operator_id, id_jembatan):
    """Timbang keluar (penimbangan ke-2) di jembatan yang sama dengan masuk (dicek juga trigger DB)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT berat_kg, id_jembatan FROM penimbangan WHERE no_tiket = ? AND ke = 1", no_tiket)
    masuk = cursor.fetchone()
    if masuk.id_jembatan != id_jembatan:
        conn.close()
        raise ValueError("Timbang keluar harus di jembatan yang sama dengan timbang masuk")
    _simpan_penimbangan(cursor, no_tiket, 2, berat, id_jembatan, operator_id)
    netto = round(abs(float(masuk.berat_kg) - float(berat)), 2)
    cursor.execute("UPDATE transaksi SET status_alur = 'SELESAI' WHERE no_tiket = ?", no_tiket)
    # Potongan sortasi = persen potongan x NETTO (berat buah saja, tanpa truk)
    cursor.execute(f"UPDATE sortasi SET total_potongan_kg = ROUND(? * {SQL_PERSEN_POTONGAN} / 100, 2) WHERE no_tiket = ?",
                   netto, no_tiket)
    conn.commit()
    conn.close()
    return netto

def get_history_timbangan_by_supplier(id_supplier, hari=7, tanggal=None, id_area=None):
    """Default 7 hari terakhir; tanggal (date) = hanya hari itu."""
    if tanggal:
        filter_waktu, param = "t.created_at >= ? AND t.created_at < DATEADD(day, 1, ?)", (tanggal, tanggal)
    else:
        filter_waktu, param = "t.created_at >= DATEADD(day, ?, GETDATE())", (-hari,)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT TOP 200 s.SupplierName AS nama_supplier, k.NoVehicle AS no_plat, tb.berat_bruto, tb.berat_tara, tb.berat_netto, t.created_at
        FROM transaksi t
        JOIN Supplier s ON t.id_supplier = s.SupplierID
        JOIN DetailVehicle k ON t.id_kendaraan = k.IDVehicle
        JOIN v_timbangan tb ON t.no_tiket = tb.no_tiket
        WHERE t.id_supplier = ? AND {filter_waktu}{_filter_area(id_area)[0]}
        ORDER BY t.created_at DESC
    """, id_supplier, *param, *_filter_area(id_area)[1])
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data

def get_list_tiket_aktif(id_area=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT t.no_tiket, k.NoVehicle AS no_plat, s.SupplierName AS supplier, t.status_alur, t.jenis_transaksi,
               p.ProductName AS produk, p.Category AS kategori_produk, t.created_at, t.id_alur,
               t.no_do, d.Nama AS supir
        FROM transaksi t
        LEFT JOIN Users d ON d.UserID = t.id_driver
        JOIN DetailVehicle k ON t.id_kendaraan = k.IDVehicle
        JOIN Supplier s ON t.id_supplier = s.SupplierID
        JOIN Product p ON t.id_produk = p.ProductID
        WHERE t.status_alur NOT IN ('SELESAI', 'REJECTED', 'VOID'){_filter_area(id_area)[0]}
          AND ISNULL(t.id_alur, 0) NOT IN (SELECT id_alur FROM alur WHERE kode = 'POS_SAJA')   -- kunjungan Pos Security
        ORDER BY t.created_at DESC
    """, *_filter_area(id_area)[1])
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data

def get_history_produk(id_produk=None, hari=7, batas=500, id_area=None):
    """Halaman List: transaksi 7 hari terakhir, bisa disaring per produk."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        filter_produk = "AND t.id_produk = ?" if id_produk else ""
        filter_area, param_area = _filter_area(id_area)
        params = [-int(hari)] + ([int(id_produk)] if id_produk else []) + param_area
        cursor.execute(f"""
            SELECT TOP {int(batas)} t.created_at, t.no_tiket, k.NoVehicle AS no_plat, s.SupplierName AS supplier, p.ProductName AS produk,
                   t.jenis_transaksi, tb.berat_bruto, tb.berat_tara, COALESCE(tb.berat_netto, t.berat_split_kg) AS berat_netto,
                   t.status_alur, t.no_do, d.Nama AS supir, t.diperiksa_pada, pr.Nama AS pemeriksa,
                   -- lama truk di dalam: tiket dibuat Security s/d timbang terakhir (hanya tiket yang sudah selesai)
                   CASE WHEN t.status_alur IN ('SELESAI', 'REJECTED') THEN
                        DATEDIFF(MINUTE, t.created_at, (SELECT MAX(pn.waktu) FROM penimbangan pn WHERE pn.no_tiket = t.no_tiket))
                   END AS lama_menit
            FROM transaksi t
            JOIN DetailVehicle k ON t.id_kendaraan = k.IDVehicle
            JOIN Supplier s ON t.id_supplier = s.SupplierID
            JOIN Product p ON t.id_produk = p.ProductID
            LEFT JOIN v_timbangan tb ON tb.no_tiket = t.no_tiket
            LEFT JOIN Users d ON d.UserID = t.id_driver
            LEFT JOIN Users pr ON pr.UserID = t.diperiksa_oleh
            WHERE t.created_at >= DATEADD(day, ?, CAST(GETDATE() AS DATE)) {filter_produk}{filter_area}
            ORDER BY t.created_at DESC""", *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()

def periksa_tiket(no_tiket, user_id, id_area=None):
    """Verifikasi tiket selesai (ERD WeightBridge.IsCheck / CheckDate). Hanya sekali; area mengikuti akses pengguna."""
    filter_area, param_area = _filter_area(id_area)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""UPDATE t SET diperiksa_pada = GETDATE(), diperiksa_oleh = ?
                           FROM transaksi t WHERE t.no_tiket = ? AND t.status_alur = 'SELESAI'
                             AND t.diperiksa_pada IS NULL{filter_area}""", user_id, no_tiket, *param_area)
        berhasil = cursor.rowcount > 0
        conn.commit()
        return berhasil
    finally:
        conn.close()

def get_history_driver(limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT TOP {int(limit)} k.NoVehicle AS no_plat, d.UserID AS id_driver, d.UserCode AS kode_personel,
               d.Nama AS nama_driver, d.NoKTP AS nik, d.LicenseNumber AS no_sim, d.IsBlacklisted AS is_blacklisted
        FROM transaksi t
        JOIN DetailVehicle k ON t.id_kendaraan = k.IDVehicle
        JOIN UserProfile d ON t.id_driver = d.UserID
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
    cursor.execute("UPDATE transaksi SET status_alur = ? WHERE no_tiket = ?",
                   _status_setelah(cursor, no_tiket, 'SORTASI'), no_tiket)
    conn.commit()
    conn.close()
    return total_persen_potongan, total_potongan_kg

SQL_STANDAR = "SELECT ProductID AS id_produk, StandardFFA AS maks_ffa, StandardMoist AS maks_air, StandardDirt AS maks_kotoran FROM Product WHERE ProductID = ?"

@cache_ttl(300)
def get_standar_mutu(id_produk):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(SQL_STANDAR, id_produk)
    row = cursor.fetchone()
    conn.close()
    return row

def update_standar_mutu(id_produk, maks_ffa, maks_air, maks_kotoran, user_id=None):
    """Simpan standar mutu produk + catat riwayatnya di log_aktivitas (STANDAR_MUTU)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Product SET StandardFFA = ?, StandardMoist = ?, StandardDirt = ? WHERE ProductID = ?",
                       maks_ffa, maks_air, maks_kotoran, id_produk)
        if cursor.rowcount == 0:
            raise ValueError("Produk tidak ditemukan")
        from utils import log_aktivitas
        log_aktivitas.catat("STANDAR_MUTU", "STANDAR_UBAH", tabel="Product", id_baris=id_produk, user_id=user_id,
                            baru={"maks_ffa": maks_ffa, "maks_air": maks_air, "maks_kotoran": maks_kotoran}, cursor=cursor)
        conn.commit()
    finally:
        conn.close()
    get_standar_mutu.hapus()

def get_history_standar(hari=2):
    """Perubahan standar mutu N hari terakhir (tab Laboratorium)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT CAST(l.waktu AS DATETIME) AS updated_at, p.ProductName AS nama_produk,
                                 CAST(JSON_VALUE(l.nilai_baru, '$.maks_ffa') AS FLOAT) AS maks_ffa,
                                 CAST(JSON_VALUE(l.nilai_baru, '$.maks_air') AS FLOAT) AS maks_air,
                                 CAST(JSON_VALUE(l.nilai_baru, '$.maks_kotoran') AS FLOAT) AS maks_kotoran, u.Nama AS oleh
                          FROM log_aktivitas l JOIN Product p ON p.ProductID = TRY_CAST(l.id_baris AS INT)
                          LEFT JOIN Users u ON u.UserID = l.id_user
                          WHERE l.kategori = 'STANDAR_MUTU' AND l.waktu >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
                          ORDER BY l.id_log DESC""", -(int(hari) - 1))
        return _rows_to_dicts(cursor)
    finally:
        conn.close()

def simpan_lab(no_tiket, ffa, air, kotoran, warna, keputusan, no_coa, operator_id):
    conn = get_connection()
    cursor = conn.cursor()
    from utils.dokumen import buat_dokumen
    cursor.execute("SELECT id_lab, id_dokumen FROM lab_hasil WHERE no_tiket = ?", no_tiket)
    lama = cursor.fetchone()
    # COA (APPROVE) dicatat di tabel dokumen (jenis COA), cukup sekali per tiket
    id_dokumen = lama.id_dokumen if lama else None
    if no_coa and id_dokumen is None:
        id_dokumen = buat_dokumen(cursor, "COA", no_coa, date.today(), f"COA tiket {no_tiket}", None, operator_id)
    if lama:
        cursor.execute("""UPDATE lab_hasil SET ffa=?, kadar_air=?, kadar_kotoran=?, warna_locis=?,
                           keputusan=?, id_dokumen=?, operator_lab_id=?, waktu_pemeriksaan=GETDATE() WHERE no_tiket=?""",
                       ffa, air, kotoran, warna, keputusan, id_dokumen, operator_id, no_tiket)
    else:
        cursor.execute("""INSERT INTO lab_hasil (no_tiket, ffa, kadar_air, kadar_kotoran, warna_locis, keputusan,
                           id_dokumen, operator_lab_id, waktu_pemeriksaan) VALUES (?,?,?,?,?,?,?,?,GETDATE())""",
                       no_tiket, ffa, air, kotoran, warna, keputusan, id_dokumen, operator_id)

    # APPROVE -> lanjut timbang kedua (bukan langsung SELESAI, supaya netto tetap tercatat)
    if keputusan == 'REJECT':
        cursor.execute("UPDATE transaksi SET status_alur='REJECTED' WHERE no_tiket=?", no_tiket)
        cursor.execute("""IF NOT EXISTS (SELECT 1 FROM pembatalan_tiket WHERE no_tiket = ?)
                          INSERT INTO pembatalan_tiket (no_tiket, jenis, alasan, oleh) VALUES (?, 'REJECT', ?, ?)""",
                       no_tiket, no_tiket, 'Ditolak Lab', operator_id)
    else:
        cursor.execute("UPDATE transaksi SET status_alur=? WHERE no_tiket=?", _status_setelah(cursor, no_tiket, 'LAB'), no_tiket)
    conn.commit()
    conn.close()

# Area tiket = area akun Security pembuatnya. Dipakai menyaring List / history per area akun yang membuka
# (user di site tidak melihat tiket site lain).
AREA_TIKET = "t.id_comp_area"          # area transaksi (migrasi 041)


def _filter_area(id_area):
    from utils.area_filter import sql_area
    return sql_area(AREA_TIKET, id_area)


def get_history_umum(tabel, limit=10, id_area=None):
    conn = get_connection()
    cursor = conn.cursor()
    if tabel not in ("lab_hasil", "sortasi"):          # nama tabel disisipkan ke SQL -> hanya daftar tetap
        raise ValueError(f"Tabel tidak diizinkan: {tabel}")
    kolom_status = "sr.keputusan" if tabel == 'lab_hasil' else "t.status_alur"
    cursor.execute(f"""
        SELECT TOP {int(limit)} k.NoVehicle AS no_plat, p.ProductName AS nama_produk, s.SupplierName AS nama_supplier, {kolom_status} AS status_val
        FROM {tabel} sr
        JOIN transaksi t ON sr.no_tiket = t.no_tiket
        JOIN DetailVehicle k ON t.id_kendaraan = k.IDVehicle
        JOIN Product p ON t.id_produk = p.ProductID
        JOIN Supplier s ON t.id_supplier = s.SupplierID
        WHERE 1 = 1{_filter_area(id_area)[0]}
        ORDER BY t.created_at DESC
    """, *_filter_area(id_area)[1])
    columns = [c[0] for c in cursor.description]
    data = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return data