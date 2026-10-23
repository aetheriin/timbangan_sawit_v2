"""Query menu Admin: user, master supplier & produk, jadwal kerja, audit admin, kesehatan database."""
import pyodbc

from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts, get_semua_supplier, get_semua_produk, get_user_by_id
from utils.db_absensi import get_jadwal_kerja

PERAN_SUPPLIER = ("CUSTOMER", "PENGANGKUTAN")    # satu mitra boleh keduanya (tabel mitra_peran)
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


# ===== USER (Users + LevelDetails = peran + DepartmentDetails; hak akses di utils/hak_akses.py) =====
# Akun = personel yang bisa login: nama & NIK juga disimpan di personel (digabung ke Users di tahap 2).
_SELECT_USER = """SELECT u.UserID AS id_user, u.UserName AS username, u.Nama AS nama, u.UserLevelID AS id_level,
                         ld.LevelDetCode AS role, ld.LevelDetName AS nama_level, lv.IsAdmin AS is_admin, ld.LevelID AS id_jabatan,
                         dd.DeptID AS id_department, ISNULL(d.DeptName, 'Admin sistem') AS department, u.CompAreaID AS id_comp_area,
                         a.CompID + ' · ' + a.AreaName AS area, u.Active AS is_active, u.LastLogin AS last_login,
                         u.CreateDate AS created_at, u.PersonnelID AS id_personel, p.kode_personel, p.nik, p.email, p.kategori,
                         (SELECT COUNT(DISTINCT x.MenuID) FROM AccessMenu x WHERE x.UserID = u.UserID) AS jumlah_akses_khusus
                  FROM Users u JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID JOIN Level lv ON lv.LevelID = ld.LevelID
                  LEFT JOIN DepartmentDetails dd ON dd.DeptDetailID = u.UserDeptID
                  LEFT JOIN Department d ON d.DeptID = dd.DeptID
                  JOIN CompanyArea a ON a.CompAreaID = u.CompAreaID
                  JOIN personel p ON p.id_personel = u.PersonnelID"""


def daftar_user():
    return _query(_SELECT_USER + " ORDER BY u.Active DESC, lv.IsAdmin DESC, ld.LevelDetName, u.Nama")


def get_user(id_user):
    rows = _query(_SELECT_USER + " WHERE u.UserID = ?", id_user)
    return rows[0] if rows else None


def username_dipakai(username, kecuali=None):
    rows = _query("SELECT UserID AS id_user FROM Users WHERE LOWER(UserName) = LOWER(?)", username)
    return any(r["id_user"] != kecuali for r in rows)


def jumlah_admin_aktif(kecuali=None):
    rows = _query("""SELECT u.UserID AS id_user FROM Users u JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID
                     JOIN Level lv ON lv.LevelID = ld.LevelID WHERE lv.IsAdmin = 1 AND ld.Active = 1 AND u.Active = 1""")
    return len([r for r in rows if r["id_user"] != kecuali])


def personel_untuk_nik(nik):
    """Personel dengan NIK ini (untuk dihubungkan ke akun baru) beserta akunnya bila sudah punya."""
    rows = _query("""SELECT p.id_personel, p.nama_personel, p.kategori, k.nama AS nama_kategori, k.boleh_akun,
                            u.UserName AS akun
                     FROM personel p LEFT JOIN kategori_personel k ON k.kode = p.kategori
                     LEFT JOIN Users u ON u.PersonnelID = p.id_personel WHERE p.nik = ?""", nik)
    return rows[0] if rows else None


def _dept_detail(cursor, id_department, id_comp_area):
    """DeptDetailID departemen ini di area user (DepartmentDetails); None untuk admin sistem."""
    if not id_department:
        return None
    row = cursor.execute("SELECT DeptDetailID FROM DepartmentDetails WHERE DeptID = ? AND CompAreaID = ? AND Active = 1",
                         id_department, id_comp_area).fetchone()
    if not row:
        raise ValueError("Departemen ini tidak ada di area yang dipilih. Atur di Admin › Organisasi › Departemen")
    return row[0]


def tambah_user(username, id_level, id_department, id_comp_area, password_hash, personel):
    """personel = {id_personel (None = buat baru), nama, nik}. Personel yang sudah ada (dicari dari NIK) dihubungkan ke
    akun ini; personel baru berkategori Karyawan. Password pertama wajib diganti saat login."""
    from utils.db_utils import simpan_password, user_id_baru
    conn = get_connection()
    try:
        cursor = conn.cursor()
        id_personel = _simpan_personel_akun(cursor, personel)
        id_user = user_id_baru(cursor)
        cursor.execute("""INSERT INTO Users (UserID, UserName, Nama, UserLevelID, UserDeptID, CompAreaID, PersonnelID, NoKTP)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                       id_user, username, personel["nama"], id_level, _dept_detail(cursor, id_department, id_comp_area),
                       id_comp_area, id_personel, personel.get("nik"))
        simpan_password(cursor, id_user, password_hash, wajib_ganti=True)
        conn.commit()
        return id_user
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _simpan_personel_akun(cursor, d):
    """Nama & NIK personel akun. Kategori & email tidak diubah dari sini (menu Personel)."""
    if d.get("id_personel"):
        cursor.execute("UPDATE personel SET nama_personel = ?, nik = ?, updated_at = GETDATE() WHERE id_personel = ?",
                       d["nama"], d["nik"], d["id_personel"])
        return d["id_personel"]
    cursor.execute("""INSERT INTO personel (nik, nama_personel, kategori) OUTPUT INSERTED.id_personel
                      VALUES (?, ?, 'EMPLOYEE')""", d["nik"], d["nama"])
    return cursor.fetchone()[0]


def ubah_user(id_user, id_level, id_department, id_comp_area, personel):
    """Ganti peran -> sesi lama dicabut (SessionVersion naik) supaya hak akses baru langsung berlaku."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        _simpan_personel_akun(cursor, personel)
        cursor.execute("""UPDATE Users SET Nama = ?, SessionVersion = SessionVersion + CASE WHEN UserLevelID <> ? THEN 1 ELSE 0 END,
                          UserLevelID = ?, UserDeptID = ?, CompAreaID = ?, NoKTP = ?, UpdateDate = GETDATE()
                          WHERE UserID = ?""",
                       personel["nama"], id_level, id_level, _dept_detail(cursor, id_department, id_comp_area), id_comp_area,
                       personel.get("nik"), id_user)
        if cursor.rowcount == 0:
            raise ValueError("Data tidak ditemukan")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    get_user_by_id.hapus()          # perubahan user / sesi langsung berlaku


def reset_password(id_user, password_hash):
    # MustChange = 1 -> user wajib mengganti password ini saat login berikutnya
    from utils.db_utils import simpan_password
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Users SET SessionVersion = SessionVersion + 1, UpdateDate = GETDATE() WHERE UserID = ?", id_user)
        if cursor.rowcount == 0:
            raise ValueError("Data tidak ditemukan")
        simpan_password(cursor, id_user, password_hash, wajib_ganti=True)
        conn.commit()
    finally:
        conn.close()
    get_user_by_id.hapus()          # perubahan user / sesi langsung berlaku


def set_aktif_user(id_user, aktif):
    _ubah("""UPDATE Users SET Active = ?, SessionVersion = SessionVersion + 1, UpdateDate = GETDATE()
             WHERE UserID = ?""", 1 if aktif else 0, id_user)
    get_user_by_id.hapus()          # perubahan user / sesi langsung berlaku


def cabut_sesi(id_user):
    _ubah("UPDATE Users SET SessionVersion = SessionVersion + 1 WHERE UserID = ?", id_user)
    get_user_by_id.hapus()          # perubahan user / sesi langsung berlaku


# ===== MASTER SUPPLIER & PRODUK =====
def daftar_supplier():
    rows = _query("""SELECT s.id_supplier, s.kode_supplier, s.nama_supplier, s.alamat, s.is_active, s.created_at,
                            pc.peran AS peran_customer, pa.peran AS peran_angkutan
                     FROM mitra s
                     LEFT JOIN mitra_peran pc ON pc.id_supplier = s.id_supplier AND pc.peran = 'CUSTOMER'
                     LEFT JOIN mitra_peran pa ON pa.id_supplier = s.id_supplier AND pa.peran = 'PENGANGKUTAN'
                     ORDER BY s.is_active DESC, s.nama_supplier""")
    pt = company_supplier()
    for r in rows:
        r.update(is_customer=bool(r.pop("peran_customer")), is_angkutan=bool(r.pop("peran_angkutan")),
                 company=list(pt.get(r["id_supplier"], ())))
    return rows


@cache_ttl(300)
def company_supplier():
    """{id_supplier: (id_company, ...)} (tabel mitra_company, migrasi 032). Supplier yang tidak ada di sini = semua PT."""
    hasil = {}
    try:
        for r in _query("SELECT id_supplier, id_company FROM mitra_company ORDER BY id_company"):
            hasil.setdefault(r["id_supplier"], []).append(r["id_company"])
    except pyodbc.Error:
        pass
    return {k: tuple(v) for k, v in hasil.items()}


def supplier_boleh(id_supplier, pt_user):
    """Supplier berlaku untuk PT user. pt_user = None (kantor pusat: semua PT) atau frozenset id company."""
    pt = company_supplier().get(id_supplier)
    return not pt or pt_user is None or bool(set(pt) & set(pt_user))


def kode_supplier_dipakai(kode, kecuali=None):
    rows = _query("SELECT id_supplier FROM mitra WHERE kode_supplier = ?", kode)
    return any(r["id_supplier"] != kecuali for r in rows)


def simpan_supplier(id_supplier, kode, nama, peran, alamat=None, daftar_company=()):
    """peran: daftar dari PERAN_SUPPLIER (minimal satu). daftar_company kosong = berlaku di semua PT."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_supplier:
            cursor.execute("UPDATE mitra SET kode_supplier = ?, nama_supplier = ?, alamat = ? WHERE id_supplier = ?",
                           kode, nama, alamat, id_supplier)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
        else:
            cursor.execute("""SET NOCOUNT ON; INSERT INTO mitra (kode_supplier, nama_supplier, alamat) VALUES (?, ?, ?);
                              SELECT CAST(SCOPE_IDENTITY() AS INT)""", kode, nama, alamat)
            id_supplier = cursor.fetchone()[0]
        cursor.execute("DELETE FROM mitra_peran WHERE id_supplier = ?", id_supplier)
        for p in peran:
            cursor.execute("INSERT INTO mitra_peran (id_supplier, peran) VALUES (?, ?)", id_supplier, p)
        cursor.execute("DELETE FROM mitra_company WHERE id_supplier = ?", id_supplier)
        for id_c in sorted(set(daftar_company)):
            cursor.execute("INSERT INTO mitra_company (id_supplier, id_company) VALUES (?, ?)", id_supplier, id_c)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    get_semua_supplier.hapus()
    company_supplier.hapus()


def set_aktif_supplier(id_supplier, aktif):
    _ubah("UPDATE mitra SET is_active = ? WHERE id_supplier = ?", 1 if aktif else 0, id_supplier)
    get_semua_supplier.hapus()


def daftar_produk():
    return _query("""SELECT p.id_produk, p.nama_produk, p.kategori, p.is_active, p.id_alur, a.nama AS nama_alur,
                            CASE WHEN s.id_produk IS NULL THEN 0 ELSE 1 END AS ada_standar
                     FROM produk p LEFT JOIN standar_mutu s ON s.id_produk = p.id_produk
                     LEFT JOIN alur a ON a.id_alur = p.id_alur
                     ORDER BY p.is_active DESC, p.nama_produk""")


def nama_produk_dipakai(nama, kecuali=None):
    rows = _query("SELECT id_produk FROM produk WHERE LOWER(nama_produk) = LOWER(?)", nama)
    return any(r["id_produk"] != kecuali for r in rows)


def simpan_produk(id_produk, nama, kategori, id_alur):
    if id_produk:
        _ubah("UPDATE produk SET nama_produk = ?, kategori = ?, id_alur = ? WHERE id_produk = ?", nama, kategori, id_alur, id_produk)
    else:
        _ubah("INSERT INTO produk (nama_produk, kategori, id_alur) VALUES (?, ?, ?)", nama, kategori, id_alur)
    get_semua_produk.hapus()


def set_aktif_produk(id_produk, aktif):
    _ubah("UPDATE produk SET is_active = ? WHERE id_produk = ?", 1 if aktif else 0, id_produk)
    get_semua_produk.hapus()


# ===== JADWAL KERJA =====
def ubah_jadwal(id_comp_area, hari, is_libur, jam_masuk, jam_pulang, toleransi):
    _ubah("""UPDATE jadwal_kerja SET is_libur = ?, jam_masuk = ?, jam_pulang = ?, toleransi_menit = ?
             WHERE id_comp_area = ? AND hari = ?""", 1 if is_libur else 0, jam_masuk, jam_pulang, toleransi, id_comp_area, hari)
    get_jadwal_kerja.hapus()


# ===== AUDIT ADMIN =====
def catat_audit_admin(user_id, aksi, target=None, detail=None, ip=None):
    """Gagal mencatat tidak boleh menggagalkan aksi admin yang sudah tersimpan."""
    from utils import log_aktivitas
    log_aktivitas.catat("ADMIN", aksi, id_baris=(target or "")[:100] or None,
                        baru={"detail": detail[:500]} if detail else None, user_id=user_id, ip=ip)


def daftar_audit_admin(hari=7, batas=300):
    from utils import log_aktivitas
    return [{"id_log": r["id_log"], "aksi": r["aksi"], "target": r["id_baris"], "detail": r["nilai_baru"].get("detail"),
             "ip_address": r["ip"], "created_at": r["waktu"], "oleh": r["oleh"], "username": r["username"]}
            for r in log_aktivitas.daftar("ADMIN", hari, batas)]


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
                             pb.waktu AS void_at, u.Nama AS void_oleh, pb.id_dokumen,
                             dk.no_dokumen AS no_ba, df.file_path AS file_ba
                      FROM transaksi t
                      JOIN kendaraan k ON k.id_kendaraan = t.id_kendaraan
                      JOIN mitra s ON s.id_supplier = t.id_supplier
                      LEFT JOIN pembatalan_tiket pb ON pb.no_tiket = t.no_tiket
                      LEFT JOIN Users u ON u.UserID = pb.oleh
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
            raise ValueError("Tiket tidak ditemukan atau sudah dibatalkan")
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
            raise ValueError("Tiket ini belum dibatalkan")
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
