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
# Akun = baris Users (orang) yang punya UserName + peran. Orang tanpa akun dikelola di menu Personel.
_SELECT_USER = """SELECT u.UserID AS id_user, u.UserName AS username, u.Nama AS nama, u.UserLevelID AS id_level,
                         ld.LevelDetCode AS role, ld.LevelDetName AS nama_level, lv.IsAdmin AS is_admin, ld.LevelID AS id_jabatan,
                         dd.DeptID AS id_department, ISNULL(d.DeptName, 'Admin sistem') AS department, u.CompAreaID AS id_comp_area,
                         a.CompID + ' · ' + a.AreaName AS area, u.Active AS is_active, u.LastLogin AS last_login,
                         u.CreateDate AS created_at, u.UserID AS id_personel, u.UserCode AS kode_personel, u.NoKTP AS nik, u.Email AS email, u.CategoryCode AS kategori,
                         (SELECT COUNT(DISTINCT x.MenuID) FROM AccessMenu x WHERE x.UserID = u.UserID) AS jumlah_akses_khusus
                  FROM Users u JOIN LevelDetails ld ON ld.LevelDetID = u.UserLevelID JOIN Level lv ON lv.LevelID = ld.LevelID
                  LEFT JOIN DepartmentDetails dd ON dd.DeptDetailID = u.UserDeptID
                  LEFT JOIN Department d ON d.DeptID = dd.DeptID
                  JOIN CompanyArea a ON a.CompAreaID = u.CompAreaID"""


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
    rows = _query("""SELECT p.UserID AS id_personel, p.Nama AS nama_personel, p.CategoryCode AS kategori, k.CategoryName AS nama_kategori, k.CanLogin AS boleh_akun,
                            p.UserName AS akun
                     FROM Users p LEFT JOIN UserCategory k ON k.CategoryCode = p.CategoryCode WHERE p.NoKTP = ?""", nik)
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
    """personel = {id_personel (None = buat baru), nama, nik}. Orang yang sudah terdaftar (dicari dari NIK) diberi login
    di barisnya sendiri; orang baru berkategori Karyawan. Password pertama wajib diganti saat login."""
    from utils.db_utils import simpan_password, user_id_baru
    conn = get_connection()
    try:
        cursor = conn.cursor()
        id_user = personel.get("id_personel")
        if not id_user:
            id_user = user_id_baru(cursor)
            cursor.execute("INSERT INTO Users (UserID, Nama, NoKTP, CategoryCode) VALUES (?, ?, ?, 'EMPLOYEE')",
                           id_user, personel["nama"], personel.get("nik"))
        cursor.execute("""UPDATE Users SET UserName = ?, Nama = ?, NoKTP = ?, UserLevelID = ?, UserDeptID = ?, CompAreaID = ?,
                                 Active = 1, UpdateDate = GETDATE()
                          WHERE UserID = ? AND UserName IS NULL""",
                       username, personel["nama"], personel.get("nik"), id_level,
                       _dept_detail(cursor, id_department, id_comp_area), id_comp_area, id_user)
        if cursor.rowcount == 0:
            raise ValueError("Orang ini sudah punya akun")
        simpan_password(cursor, id_user, password_hash, wajib_ganti=True)
        conn.commit()
        return id_user
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ubah_user(id_user, id_level, id_department, id_comp_area, personel):
    """Ganti peran -> sesi lama dicabut (SessionVersion naik) supaya hak akses baru langsung berlaku."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
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
    rows = _query("""SELECT s.SupplierID AS id_supplier, s.SupplierCode AS kode_supplier, s.SupplierName AS nama_supplier, s.SupplierAddress AS alamat, s.Active AS is_active, s.CreateDate AS created_at,
                            CAST(CASE WHEN s.BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted,
                            pc.TypeCode AS peran_customer, pa.TypeCode AS peran_angkutan
                     FROM Supplier s
                     LEFT JOIN SupplierTypeDetails pc ON pc.SupplierID = s.SupplierID AND pc.TypeCode = 'CUSTOMER'
                     LEFT JOIN SupplierTypeDetails pa ON pa.SupplierID = s.SupplierID AND pa.TypeCode = 'PENGANGKUTAN'
                     ORDER BY s.Active DESC, s.SupplierName""")
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
        for r in _query("SELECT SupplierID AS id_supplier, CompID AS id_company FROM SupplierCompany ORDER BY CompID"):
            hasil.setdefault(r["id_supplier"], []).append(r["id_company"])
    except pyodbc.Error:
        pass
    return {k: tuple(v) for k, v in hasil.items()}


def supplier_boleh(id_supplier, pt_user):
    """Supplier berlaku untuk PT user. pt_user = None (kantor pusat: semua PT) atau frozenset id company."""
    pt = company_supplier().get(id_supplier)
    return not pt or pt_user is None or bool(set(pt) & set(pt_user))


def kode_supplier_dipakai(kode, kecuali=None):
    rows = _query("SELECT SupplierID AS id_supplier FROM Supplier WHERE SupplierCode = ?", kode)
    return any(r["id_supplier"] != kecuali for r in rows)


def simpan_supplier(id_supplier, kode, nama, peran, alamat=None, daftar_company=()):
    """peran: daftar dari PERAN_SUPPLIER (minimal satu). daftar_company kosong = berlaku di semua PT."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_supplier:
            cursor.execute("UPDATE Supplier SET SupplierCode = ?, SupplierName = ?, SupplierAddress = ? WHERE SupplierID = ?",
                           kode, nama, alamat, id_supplier)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
        else:
            cursor.execute("""SET NOCOUNT ON; INSERT INTO Supplier (SupplierCode, SupplierName, SupplierAddress) VALUES (?, ?, ?);
                              SELECT CAST(SCOPE_IDENTITY() AS INT)""", kode, nama, alamat)
            id_supplier = cursor.fetchone()[0]
        cursor.execute("DELETE FROM SupplierTypeDetails WHERE SupplierID = ?", id_supplier)
        for p in peran:
            cursor.execute("INSERT INTO SupplierTypeDetails (SupplierID, TypeCode) VALUES (?, ?)", id_supplier, p)
        cursor.execute("DELETE FROM SupplierCompany WHERE SupplierID = ?", id_supplier)
        for id_c in sorted(set(daftar_company)):
            cursor.execute("INSERT INTO SupplierCompany (SupplierID, CompID) VALUES (?, ?)", id_supplier, id_c)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    get_semua_supplier.hapus()
    company_supplier.hapus()


def set_aktif_supplier(id_supplier, aktif):
    _ubah("UPDATE Supplier SET Active = ? WHERE SupplierID = ?", 1 if aktif else 0, id_supplier)
    get_semua_supplier.hapus()


def daftar_produk():
    return _query("""SELECT p.ProductID AS id_produk, p.ProductName AS nama_produk, p.Category AS kategori, p.Active AS is_active, p.FlowID AS id_alur, a.FlowName AS nama_alur,
                            1 AS ada_standar
                     FROM Product p
                     LEFT JOIN Flow a ON a.FlowID = p.FlowID
                     ORDER BY p.Active DESC, p.ProductName""")


def nama_produk_dipakai(nama, kecuali=None):
    rows = _query("SELECT ProductID AS id_produk FROM Product WHERE LOWER(ProductName) = LOWER(?)", nama)
    return any(r["id_produk"] != kecuali for r in rows)


def simpan_produk(id_produk, nama, kategori, id_alur):
    if id_produk:
        _ubah("UPDATE Product SET ProductName = ?, Category = ?, FlowID = ? WHERE ProductID = ?", nama, kategori, id_alur, id_produk)
    else:
        _ubah("INSERT INTO Product (ProductName, Category, FlowID) VALUES (?, ?, ?)", nama, kategori, id_alur)
    get_semua_produk.hapus()


def set_aktif_produk(id_produk, aktif):
    _ubah("UPDATE Product SET Active = ? WHERE ProductID = ?", 1 if aktif else 0, id_produk)
    get_semua_produk.hapus()


# ===== JADWAL KERJA =====
def ubah_jadwal(id_comp_area, hari, is_libur, jam_masuk, jam_pulang, toleransi):
    _ubah("""UPDATE WorkSchedule SET IsHoliday = ?, TimeIn = ?, TimeOut = ?, ToleranceMinutes = ?
             WHERE CompAreaID = ? AND DayNo = ?""", 1 if is_libur else 0, jam_masuk, jam_pulang, toleransi, id_comp_area, hari)
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
    return _query(f"""SELECT TOP {int(batas)} t.TicketNumber AS no_tiket, k.NoVehicle AS no_plat, s.SupplierName AS customer, t.DONumber AS no_do, t.WeightTypeCode AS jenis_transaksi,
                             t.StatusCode AS status_alur, t.TicketDate AS created_at, pb.VoidType AS jenis_batal, pb.Reason AS alasan_void,
                             pb.VoidDate AS void_at, u.Nama AS void_oleh, pb.DocumentID AS id_dokumen,
                             dk.DocNumber AS no_ba, df.file_path AS file_ba
                      FROM WeightBridge t
                      JOIN DetailVehicle k ON k.IDVehicle = t.IDVehicle
                      JOIN Supplier s ON s.SupplierID = t.SupplierID
                      LEFT JOIN TicketVoid pb ON pb.TicketNumber = t.TicketNumber
                      LEFT JOIN Users u ON u.UserID = pb.VoidBy
                      LEFT JOIN Document dk ON dk.DocumentID = pb.DocumentID
                      OUTER APPLY (SELECT TOP 1 f.FilePath AS file_path FROM DocumentFile f
                                   WHERE f.DocumentID = pb.DocumentID ORDER BY f.SortOrder) df
                      WHERE t.TicketDate >= DATEADD(DAY, -?, GETDATE())
                        AND (t.TicketNumber LIKE ? OR k.NoVehicle LIKE ? OR t.DONumber LIKE ?)
                      ORDER BY t.TicketDate DESC""", int(hari), cari, cari, cari)


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
        cursor.execute("""UPDATE WeightBridge SET StatusCode = 'VOID', IsQRActive = 0
                          WHERE TicketNumber = ? AND StatusCode <> 'VOID'""", no_tiket)
        if cursor.rowcount == 0:
            raise ValueError("Tiket tidak ditemukan atau sudah dibatalkan")
        cursor.execute("DELETE FROM TicketVoid WHERE TicketNumber = ? AND VoidType = 'REJECT'", no_tiket)
        cursor.execute("""INSERT INTO TicketVoid (TicketNumber, VoidType, Reason, DocumentID, VoidBy)
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
        cursor.execute("SELECT DocumentID AS id_dokumen FROM TicketVoid WHERE TicketNumber = ? AND VoidType = 'VOID'", no_tiket)
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Tiket ini belum dibatalkan")
        if row.id_dokumen:
            raise ValueError("Berita acara sudah dilampirkan")
        cursor.execute("UPDATE TicketVoid SET DocumentID = ? WHERE TicketNumber = ?",
                       _ba(cursor, no_tiket, berita_acara, user_id), no_tiket)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
