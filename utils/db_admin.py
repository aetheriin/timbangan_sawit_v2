"""Query menu Admin: user, master supplier & produk, jadwal kerja, audit admin, kesehatan database."""
from utils.db_utils import get_connection, _rows_to_dicts, get_semua_supplier, get_semua_produk, get_user_by_id
from utils.db_absensi import get_jadwal_kerja

TIPE_SUPPLIER = ("CUSTOMER", "PENGANGKUTAN")     # customer bisa membeli / menjual; pengangkutan = angkutan pihak ketiga
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


# ===== USER (level, department, area dari tabel; hak akses di utils/hak_akses.py) =====
_SELECT_USER = """SELECT u.id_user, u.username, u.nama, u.id_level, lv.kode AS role, lv.nama AS nama_level, lv.is_admin,
                         u.id_department, d.nama AS department, u.id_comp_area, a.nama AS area,
                         u.is_active, u.last_login, u.created_at
                  FROM users u JOIN level lv ON lv.id_level = u.id_level
                  JOIN department d ON d.id_department = u.id_department
                  JOIN comp_area a ON a.id_comp_area = u.id_comp_area"""


def daftar_user():
    return _query(_SELECT_USER + " ORDER BY u.is_active DESC, lv.is_admin DESC, lv.nama, u.nama")


def get_user(id_user):
    rows = _query(_SELECT_USER + " WHERE u.id_user = ?", id_user)
    return rows[0] if rows else None


def username_dipakai(username, kecuali=None):
    rows = _query("SELECT id_user FROM users WHERE LOWER(username) = LOWER(?)", username)
    return any(r["id_user"] != kecuali for r in rows)


def jumlah_admin_aktif(kecuali=None):
    rows = _query("""SELECT u.id_user FROM users u JOIN level lv ON lv.id_level = u.id_level
                     WHERE lv.is_admin = 1 AND lv.is_active = 1 AND u.is_active = 1""")
    return len([r for r in rows if r["id_user"] != kecuali])


def tambah_user(username, nama, id_level, id_department, id_comp_area, password_hash):
    _ubah("""INSERT INTO users (username, nama, id_level, id_department, id_comp_area, password)
             VALUES (?, ?, ?, ?, ?, ?)""", username, nama, id_level, id_department, id_comp_area, password_hash)


def ubah_user(id_user, nama, id_level, id_department, id_comp_area):
    """Ganti level -> sesi lama dicabut (sesi_versi naik) supaya hak akses baru langsung berlaku."""
    _ubah("""UPDATE users SET nama = ?, sesi_versi = sesi_versi + CASE WHEN id_level <> ? THEN 1 ELSE 0 END,
             id_level = ?, id_department = ?, id_comp_area = ?, updated_at = GETDATE() WHERE id_user = ?""",
          nama, id_level, id_level, id_department, id_comp_area, id_user)
    get_user_by_id.hapus()          # perubahan user / sesi langsung berlaku


def reset_password(id_user, password_hash):
    # password_changed_at = NULL -> user wajib mengganti password ini saat login berikutnya
    _ubah("""UPDATE users SET password = ?, password_changed_at = NULL, sesi_versi = sesi_versi + 1,
             updated_at = GETDATE() WHERE id_user = ?""", password_hash, id_user)
    get_user_by_id.hapus()          # perubahan user / sesi langsung berlaku


def set_aktif_user(id_user, aktif):
    _ubah("""UPDATE users SET is_active = ?, sesi_versi = sesi_versi + 1, updated_at = GETDATE()
             WHERE id_user = ?""", 1 if aktif else 0, id_user)
    get_user_by_id.hapus()          # perubahan user / sesi langsung berlaku


def cabut_sesi(id_user):
    _ubah("UPDATE users SET sesi_versi = sesi_versi + 1 WHERE id_user = ?", id_user)
    get_user_by_id.hapus()          # perubahan user / sesi langsung berlaku


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


# ===== VOID TIKET (pembatalan_tiket, migrasi 010) =====
def daftar_tiket(cari="", hari=30, batas=500):
    cari = f"%{cari.strip()}%"
    return _query(f"""SELECT TOP {int(batas)} t.no_tiket, k.no_plat, s.nama_supplier AS customer, t.no_do, t.jenis_transaksi,
                             t.status_alur, t.created_at, pb.jenis AS jenis_batal, pb.alasan AS alasan_void,
                             pb.waktu AS void_at, u.nama AS void_oleh, pb.id_dokumen,
                             dk.no_dokumen AS no_ba, df.file_path AS file_ba
                      FROM transaksi t
                      JOIN kendaraan k ON k.id_kendaraan = t.id_kendaraan
                      JOIN supplier s ON s.id_supplier = t.id_supplier
                      LEFT JOIN pembatalan_tiket pb ON pb.no_tiket = t.no_tiket
                      LEFT JOIN users u ON u.id_user = pb.oleh
                      LEFT JOIN dokumen dk ON dk.id_dokumen = pb.id_dokumen
                      OUTER APPLY (SELECT TOP 1 f.file_path FROM dokumen_file f
                                   WHERE f.id_dokumen = pb.id_dokumen ORDER BY f.urutan) df
                      WHERE t.created_at >= DATEADD(DAY, -?, GETDATE())
                        AND (t.no_tiket LIKE ? OR k.no_plat LIKE ? OR t.no_do LIKE ?)
                      ORDER BY t.created_at DESC""", int(hari), cari, cari, cari)


def _ba(cursor, no_tiket, berita_acara, user_id):
    """berita_acara = {no, tanggal, file_info} -> id_dokumen BA_VOID, atau None."""
    if not berita_acara:
        return None
    from utils.dokumen import buat_dokumen
    return buat_dokumen(cursor, "BA_VOID", berita_acara["no"], berita_acara["tanggal"], f"Void tiket {no_tiket}",
                        [berita_acara["file_info"]], user_id)


def void_tiket(no_tiket, alasan, user_id, berita_acara=None):
    """Tiket dibatalkan (tidak dihapus): keluar dari daftar aktif, QR tidak berlaku, timbang ditolak.
    Berita acara boleh dilampirkan sekarang atau menyusul (lampirkan_ba_void)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""UPDATE transaksi SET status_alur = 'VOID', is_qr_active = 0
                          WHERE no_tiket = ? AND status_alur <> 'VOID'""", no_tiket)
        if cursor.rowcount == 0:
            raise ValueError("Tiket tidak ditemukan atau sudah di-void")
        cursor.execute("DELETE FROM pembatalan_tiket WHERE no_tiket = ? AND jenis = 'REJECT'", no_tiket)
        cursor.execute("""INSERT INTO pembatalan_tiket (no_tiket, jenis, alasan, id_dokumen, oleh)
                          VALUES (?, 'VOID', ?, ?, ?)""", no_tiket, alasan, _ba(cursor, no_tiket, berita_acara, user_id), user_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lampirkan_ba_void(no_tiket, berita_acara, user_id):
    """Berita acara yang menyusul untuk tiket yang sudah di-void (hanya bila belum ada)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id_dokumen FROM pembatalan_tiket WHERE no_tiket = ? AND jenis = 'VOID'", no_tiket)
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Tiket ini belum di-void")
        if row.id_dokumen:
            raise ValueError("Berita acara sudah dilampirkan")
        cursor.execute("UPDATE pembatalan_tiket SET id_dokumen = ? WHERE no_tiket = ?",
                       _ba(cursor, no_tiket, berita_acara, user_id), no_tiket)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
