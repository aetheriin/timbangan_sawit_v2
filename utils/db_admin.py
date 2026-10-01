"""Query menu Admin: user, master supplier & produk, jadwal kerja, audit admin, kesehatan database."""
from utils.db_utils import get_connection, _rows_to_dicts, get_semua_supplier, get_semua_produk
from utils.db_absensi import get_jadwal_kerja

ROLE_VALID = ("ADMIN", "HO", "SECURITY", "OPERATOR_TIMBANG", "SORTASI", "LAB")
TIPE_SUPPLIER = ("SUPPLIER_PEMBELIAN", "BUYER_PENJUALAN")
KATEGORI_PRODUK = ("TBS", "PRODUK_PKS")


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def _ubah(sql, *params, pesan_kosong="Data tidak ditemukan"):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        if cursor.rowcount == 0:
            raise ValueError(pesan_kosong)
        conn.commit()
    finally:
        conn.close()


# ===== USER =====
def daftar_user():
    return _query("""SELECT id_user, username, nama, role, is_active, last_login, created_at
                     FROM users ORDER BY is_active DESC, role, nama""")


def get_user(id_user):
    rows = _query("SELECT id_user, username, nama, role, is_active FROM users WHERE id_user = ?", id_user)
    return rows[0] if rows else None


def username_dipakai(username, kecuali=None):
    rows = _query("SELECT id_user FROM users WHERE LOWER(username) = LOWER(?)", username)
    return any(r["id_user"] != kecuali for r in rows)


def jumlah_admin_aktif(kecuali=None):
    rows = _query("SELECT id_user FROM users WHERE role = 'ADMIN' AND is_active = 1")
    return len([r for r in rows if r["id_user"] != kecuali])


def tambah_user(username, nama, role, password_hash):
    _ubah("INSERT INTO users (username, nama, role, password) VALUES (?, ?, ?, ?)", username, nama, role, password_hash)


def ubah_user(id_user, nama, role):
    """Ganti role -> sesi lama dicabut (sesi_versi naik) supaya hak akses baru langsung berlaku."""
    _ubah("""UPDATE users SET nama = ?, sesi_versi = sesi_versi + CASE WHEN role <> ? THEN 1 ELSE 0 END,
             role = ?, updated_at = GETDATE() WHERE id_user = ?""", nama, role, role, id_user)


def reset_password(id_user, password_hash):
    _ubah("""UPDATE users SET password = ?, sesi_versi = sesi_versi + 1, updated_at = GETDATE()
             WHERE id_user = ?""", password_hash, id_user)


def set_aktif_user(id_user, aktif):
    _ubah("""UPDATE users SET is_active = ?, sesi_versi = sesi_versi + 1, updated_at = GETDATE()
             WHERE id_user = ?""", 1 if aktif else 0, id_user)


def cabut_sesi(id_user):
    _ubah("UPDATE users SET sesi_versi = sesi_versi + 1 WHERE id_user = ?", id_user)


# ===== MASTER SUPPLIER & PRODUK =====
def daftar_supplier():
    return _query("""SELECT id_supplier, kode_supplier, nama_supplier, tipe, is_active, created_at
                     FROM supplier ORDER BY is_active DESC, nama_supplier""")


def kode_supplier_dipakai(kode, kecuali=None):
    rows = _query("SELECT id_supplier FROM supplier WHERE kode_supplier = ?", kode)
    return any(r["id_supplier"] != kecuali for r in rows)


def simpan_supplier(id_supplier, kode, nama, tipe):
    if id_supplier:
        _ubah("UPDATE supplier SET kode_supplier = ?, nama_supplier = ?, tipe = ? WHERE id_supplier = ?",
              kode, nama, tipe, id_supplier)
    else:
        _ubah("INSERT INTO supplier (kode_supplier, nama_supplier, tipe) VALUES (?, ?, ?)", kode, nama, tipe)
    get_semua_supplier.hapus()


def set_aktif_supplier(id_supplier, aktif):
    _ubah("UPDATE supplier SET is_active = ? WHERE id_supplier = ?", 1 if aktif else 0, id_supplier)
    get_semua_supplier.hapus()


def daftar_produk():
    return _query("""SELECT p.id_produk, p.nama_produk, p.kategori, p.is_active,
                            CASE WHEN s.id_produk IS NULL THEN 0 ELSE 1 END AS ada_standar
                     FROM produk p LEFT JOIN standar_mutu s ON s.id_produk = p.id_produk
                     ORDER BY p.is_active DESC, p.nama_produk""")


def nama_produk_dipakai(nama, kecuali=None):
    rows = _query("SELECT id_produk FROM produk WHERE LOWER(nama_produk) = LOWER(?)", nama)
    return any(r["id_produk"] != kecuali for r in rows)


def simpan_produk(id_produk, nama, kategori):
    if id_produk:
        _ubah("UPDATE produk SET nama_produk = ?, kategori = ? WHERE id_produk = ?", nama, kategori, id_produk)
    else:
        _ubah("INSERT INTO produk (nama_produk, kategori) VALUES (?, ?)", nama, kategori)
    get_semua_produk.hapus()


def set_aktif_produk(id_produk, aktif):
    _ubah("UPDATE produk SET is_active = ? WHERE id_produk = ?", 1 if aktif else 0, id_produk)
    get_semua_produk.hapus()


# ===== JADWAL KERJA =====
def ubah_jadwal(hari, is_libur, jam_masuk, jam_pulang, toleransi):
    _ubah("""UPDATE jadwal_kerja SET is_libur = ?, jam_masuk = ?, jam_pulang = ?, toleransi_menit = ?
             WHERE hari = ?""", 1 if is_libur else 0, jam_masuk, jam_pulang, toleransi, hari)
    get_jadwal_kerja.hapus()


# ===== AUDIT ADMIN =====
def catat_audit_admin(user_id, aksi, target=None, detail=None, ip=None):
    """Gagal mencatat tidak boleh menggagalkan aksi admin yang sudah tersimpan."""
    try:
        _ubah("INSERT INTO admin_audit_logs (user_id, aksi, target, detail, ip_address) VALUES (?, ?, ?, ?, ?)",
              user_id, aksi, (target or "")[:100] or None, (detail or "")[:500] or None, ip)
    except Exception:       # noqa: BLE001
        import logging
        logging.getLogger("weighbridge").exception("Gagal mencatat audit admin %s", aksi)


def daftar_audit_admin(hari=7, batas=300):
    return _query(f"""SELECT TOP {int(batas)} a.id_log, a.aksi, a.target, a.detail, a.ip_address, a.created_at,
                             u.nama AS oleh, u.username
                      FROM admin_audit_logs a JOIN users u ON u.id_user = a.user_id
                      WHERE a.created_at >= DATEADD(DAY, -?, CAST(GETDATE() AS DATE))
                      ORDER BY a.created_at DESC""", int(hari) - 1)


# ===== KESEHATAN DATABASE =====
def info_database():
    """Ukuran database & backup terakhir. Backup dibaca dari msdb (butuh izin; bila tidak ada -> None)."""
    info = {"ukuran_mb": None, "backup_terakhir": None, "backup_tipe": None}
    rows = _query("SELECT DB_NAME() AS nama, SUM(CAST(size AS BIGINT)) * 8 / 1024 AS ukuran_mb FROM sys.database_files")
    if rows:
        info["nama"], info["ukuran_mb"] = rows[0]["nama"], rows[0]["ukuran_mb"]
    try:
        b = _query("""SELECT TOP 1 backup_finish_date, type FROM msdb.dbo.backupset
                      WHERE database_name = DB_NAME() ORDER BY backup_finish_date DESC""")
        if b:
            info["backup_terakhir"] = b[0]["backup_finish_date"]
            info["backup_tipe"] = {"D": "Full", "I": "Differential", "L": "Log"}.get(b[0]["type"], b[0]["type"])
    except Exception:       # noqa: BLE001 - akun aplikasi tidak punya akses msdb
        info["backup_terakhir"] = "tidak bisa dibaca"
    return info
