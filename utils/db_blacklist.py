"""Query tabel blacklist (menu Blacklist). Tambah & hapus (cabut) lewat persetujuan (utils/persetujuan.py);
baris tidak pernah dihapus, pencabutan dicatat di dicabut_at / dicabut_oleh / alasan_cabut (migrasi 027)."""
import json
from datetime import date, datetime
from utils.db_utils import get_connection, _rows_to_dicts
from utils.dokumen import buat_dokumen

TIPE_VALID = ("PERSONEL", "KENDARAAN")
_TARGET = {"PERSONEL": ("Users", "UserID"), "KENDARAAN": ("DetailVehicle", "IDVehicle")}   # tabel & kolom target


def _format(r):
    for k, v in list(r.items()):
        if isinstance(v, datetime):
            r[k] = v.strftime("%Y-%m-%d %H:%M")
        elif isinstance(v, date):
            r[k] = v.isoformat()
    return r


def get_riwayat_blacklist(tipe=None, cari=None, batas=200, status="AKTIF", pt=None, kategori=None):
    """List Blacklist. pt = PT yang boleh dilihat user (None = semua): lokasi blacklist (area pengaju) di PT itu.
    Termasuk tanggal & lokasi scan terakhir (blacklist_deteksi)."""
    sql = """
        SELECT TOP (?) b.BlacklistID AS id_blacklist, b.TargetType AS tipe_entitas, dk.no_dokumen AS no_surat_blacklist, b.Reason AS alasan_blacklist,
               df.file_path AS file_surat_blacklist, COALESCE(dk.tanggal, CAST(b.CreateDate AS DATE)) AS tgl_blacklist,
               b.BlacklistDoc AS id_dokumen, b.CreateDate AS created_at, u.Nama AS oleh, lv.LevelDetCode AS role_oleh, ar.AreaName AS area_oleh,
               p.UserID AS id_personel, p.UserCode AS kode_personel, p.Nama AS nama_personel, k.NoVehicle AS no_plat, b.NoVehicle AS no_plat_terkait,
               c.nama_supplier AS customer_terkait, a.nama_supplier AS pengangkutan_terkait,
               b.RevokeDate AS dicabut_at, b.RevokeReason AS alasan_cabut, uc.Nama AS dicabut_oleh, p.NoKTP AS nik, b.AliasName AS nama_alias, b.CategoryCode AS kategori,
               CASE WHEN b.TargetType = 'KENDARAAN' THEN 'Kendaraan' ELSE kp.CategoryName END AS nama_kategori,
               arb.AreaName AS lokasi_blacklist, cb.CompID AS company_blacklist,
               COALESCE(sp.waktu, sk.waktu) AS scan_terakhir, sca.AreaName AS lokasi_scan, csa.CompID AS company_scan,
               (SELECT TOP 1 pg.id_pengajuan FROM pengajuan pg WHERE pg.jenis = 'BLACKLIST_HAPUS' AND pg.status = 'MENUNGGU'
                AND pg.target = 'BLACKLIST:' + CAST(b.BlacklistID AS VARCHAR(20))) AS id_pengajuan_hapus
        FROM Blacklist b
        LEFT JOIN Users uc ON uc.UserID = b.RevokeBy
        LEFT JOIN mitra c ON b.CustomerID = c.id_supplier
        LEFT JOIN mitra a ON b.TransportID = a.id_supplier
        JOIN Users u ON b.CreateBy = u.UserID
        JOIN LevelDetails lv ON lv.LevelDetID = u.UserLevelID
        LEFT JOIN CompanyArea ar ON ar.CompAreaID = u.CompAreaID
        LEFT JOIN Users p ON b.UserID = p.UserID
        LEFT JOIN DetailVehicle k ON b.IDVehicle = k.IDVehicle
        LEFT JOIN dokumen dk ON dk.id_dokumen = b.BlacklistDoc          -- NULL = surat menyusul
        LEFT JOIN UserCategory kp ON kp.CategoryCode = b.CategoryCode
        LEFT JOIN CompanyArea arb ON arb.CompAreaID = b.CompAreaID
        LEFT JOIN Company cb ON cb.CompID = arb.CompID
        OUTER APPLY (SELECT TOP 1 d.DetectDate AS waktu, d.CompAreaID AS id_comp_area FROM BlacklistDetection d
                     WHERE b.UserID IS NOT NULL AND d.UserID = b.UserID ORDER BY d.DetectDate DESC) sp
        OUTER APPLY (SELECT TOP 1 d.DetectDate AS waktu, d.CompAreaID AS id_comp_area FROM BlacklistDetection d
                     WHERE b.IDVehicle IS NOT NULL AND d.IDVehicle = b.IDVehicle ORDER BY d.DetectDate DESC) sk
        LEFT JOIN CompanyArea sca ON sca.CompAreaID = COALESCE(sp.id_comp_area, sk.id_comp_area)
        LEFT JOIN Company csa ON csa.CompID = sca.CompID
        OUTER APPLY (SELECT TOP 1 f.file_path FROM dokumen_file f WHERE f.id_dokumen = dk.id_dokumen ORDER BY f.urutan) df
        WHERE 1 = 1"""
    params = [batas]
    if tipe:
        sql += " AND b.TargetType = ?"
        params.append(tipe)
    if kategori:
        sql += " AND b.CategoryCode = ?"
        params.append(kategori)
    if pt is not None:
        ids = sorted(pt) or [""]           # daftar kosong = tidak ada perusahaan yang cocok
        sql += f" AND (b.CompAreaID IS NULL OR arb.CompID IN ({', '.join('?' * len(ids))}))"
        params += ids
    if status == "AKTIF":
        sql += " AND b.RevokeDate IS NULL"
    elif status == "DICABUT":
        sql += " AND b.RevokeDate IS NOT NULL"
    if cari:
        pola = f"%{cari}%"
        sql += """ AND (p.UserCode LIKE ? OR p.Nama LIKE ? OR p.NoKTP LIKE ?
                        OR k.NoVehicle LIKE ? OR dk.no_dokumen LIKE ? OR b.AliasName LIKE ? OR b.NoVehicle LIKE ?)"""
        params += [pola] * 7
    sql += " ORDER BY b.CreateDate DESC, b.BlacklistID DESC"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, *params)
    data = [_format(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


# Data personel + transaksi terakhirnya sebagai SUPIR (plat, customer, pengangkutan saat itu).
# Bukan supir / belum pernah membawa truk -> kolom transaksi NULL (form blacklist tidak menampilkannya).
_SELECT_PERSONEL = """
    SELECT {top} p.UserID AS id_target, p.UserCode AS kode_personel, p.Nama AS nama_personel, p.NoKTP AS nik, p.LicenseNumber AS no_sim, p.CategoryCode AS kategori,
           kp.CategoryName AS nama_kategori, p.PhotoPath AS foto_path, p.IsBlacklisted AS is_blacklisted, tr.no_plat AS plat_terakhir,
           tr.id_supplier AS id_customer_terakhir, tr.customer AS customer_terakhir,
           tr.id_pengangkutan AS id_pengangkutan_terakhir, tr.pengangkutan AS pengangkutan_terakhir,
           tr.produk AS produk_terakhir, tr.created_at AS waktu_terakhir
    FROM UserProfile p
    LEFT JOIN UserCategory kp ON kp.CategoryCode = p.CategoryCode
    OUTER APPLY (SELECT TOP 1 k.NoVehicle AS no_plat, t.id_supplier, s.nama_supplier AS customer, t.id_pengangkutan,
                        a.nama_supplier AS pengangkutan, pr.nama_produk AS produk, t.created_at
                 FROM transaksi t JOIN DetailVehicle k ON t.id_kendaraan = k.IDVehicle
                 JOIN mitra s ON t.id_supplier = s.id_supplier
                 LEFT JOIN produk pr ON pr.id_produk = t.id_produk
                 LEFT JOIN mitra a ON t.id_pengangkutan = a.id_supplier
                 WHERE t.id_driver = p.UserID ORDER BY t.created_at DESC) tr
    WHERE p.Active = 1"""


def _rapikan_target(data):
    for r in data:
        r["is_blacklisted"] = bool(r["is_blacklisted"])
        if r.get("waktu_terakhir") is not None:
            r["waktu_terakhir"] = r["waktu_terakhir"].strftime("%Y-%m-%d %H:%M")
    return data


def cari_target(tipe, kata, batas=8):
    """Kandidat target: personel (kode / NIK / nama / no SIM / ID) atau kendaraan (plat)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        pola = f"%{kata}%"
        if tipe == "PERSONEL":
            cursor.execute(_SELECT_PERSONEL.format(top=f"TOP {int(batas)}") + """
                AND (p.UserCode LIKE ? OR p.NoKTP LIKE ? OR p.Nama LIKE ? OR p.LicenseNumber LIKE ?
                     OR CAST(p.UserID AS VARCHAR) = ?)
                ORDER BY p.Nama""", pola, pola, pola, pola, kata.lstrip("0") or "0")
        else:
            # Plat + STNK, supir utama, jumlah supir terdaftar, dan transaksi terakhir (supir, customer, angkutan)
            cursor.execute(f"""
                SELECT TOP {int(batas)} k.IDVehicle AS id_target, k.NoVehicle AS no_plat, k.NoSTNK AS no_stnk, CAST(CASE WHEN k.BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted, k.Active AS is_active,
                       u.id_personel AS id_supir_utama, u.kode_personel AS kode_supir_utama, u.nama_personel AS nama_supir_utama,
                       (SELECT COUNT(*) FROM VehicleDriver kd JOIN Users p ON p.UserID = kd.UserID
                        WHERE kd.IDVehicle = k.IDVehicle AND kd.Active = 1 AND p.Active = 1) AS jumlah_supir,
                       tr.id_driver AS id_supir_terakhir, tr.kode_personel AS kode_supir_terakhir,
                       tr.nama_personel AS nama_supir_terakhir, tr.customer AS customer_terakhir,
                       tr.id_supplier AS id_customer_terakhir, tr.id_pengangkutan AS id_pengangkutan_terakhir,
                       tr.pengangkutan AS pengangkutan_terakhir, tr.produk AS produk_terakhir, tr.created_at AS waktu_terakhir
                FROM DetailVehicle k
                OUTER APPLY (SELECT TOP 1 p.UserID AS id_personel, p.UserCode AS kode_personel, p.Nama AS nama_personel
                             FROM VehicleDriver kd JOIN Users p ON p.UserID = kd.UserID
                             WHERE kd.IDVehicle = k.IDVehicle AND kd.Active = 1 AND kd.IsMain = 1) u
                OUTER APPLY (SELECT TOP 1 t.id_driver, p.UserCode AS kode_personel, p.Nama AS nama_personel, s.nama_supplier AS customer,
                                    t.id_supplier, t.id_pengangkutan, a.nama_supplier AS pengangkutan,
                                    pr.nama_produk AS produk, t.created_at
                             FROM transaksi t JOIN Users p ON p.UserID = t.id_driver
                             JOIN mitra s ON t.id_supplier = s.id_supplier
                             LEFT JOIN produk pr ON pr.id_produk = t.id_produk
                             LEFT JOIN mitra a ON t.id_pengangkutan = a.id_supplier
                             WHERE t.id_kendaraan = k.IDVehicle ORDER BY t.created_at DESC) tr
                WHERE REPLACE(k.NoVehicle, ' ', '') LIKE ?
                ORDER BY k.NoVehicle""", f"%{kata.replace(' ', '')}%")
        return _rapikan_target(_rows_to_dicts(cursor))
    finally:
        conn.close()


def info_kendaraan(id_kendaraan):
    """Plat, supplier / pengangkutan / produk transaksi terakhir kendaraan (pengajuan blacklist kendaraan)."""
    rows = _query_satu("""SELECT k.NoVehicle AS no_plat, s.nama_supplier AS customer_terakhir, a.nama_supplier AS pengangkutan_terakhir,
                                 pr.nama_produk AS produk_terakhir, t.id_supplier AS id_customer_terakhir,
                                 t.id_pengangkutan AS id_pengangkutan_terakhir
                          FROM DetailVehicle k
                          OUTER APPLY (SELECT TOP 1 t.id_supplier, t.id_pengangkutan, t.id_produk FROM transaksi t
                                       WHERE t.id_kendaraan = k.IDVehicle ORDER BY t.created_at DESC) t
                          LEFT JOIN mitra s ON s.id_supplier = t.id_supplier
                          LEFT JOIN mitra a ON a.id_supplier = t.id_pengangkutan
                          LEFT JOIN produk pr ON pr.id_produk = t.id_produk
                          WHERE k.IDVehicle = ?""", id_kendaraan)
    return rows[0] if rows else None


def get_target_personel(id_personel):
    """Satu personel (hasil cocok wajah) dengan data transaksi terakhir."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_SELECT_PERSONEL.format(top="") + " AND p.UserID = ?", id_personel)
        rows = _rapikan_target(_rows_to_dicts(cursor))
        return rows[0] if rows else None
    finally:
        conn.close()


def tambah_blacklist(tipe, id_target, no_surat, alasan, file_info, tgl_surat, user_id, terkait=None,
                     nama_alias=None, kategori=None, id_area=None):
    """INSERT dokumen surat + Blacklist + set BlacklistID target dalam satu transaksi. Error bila sudah diblacklist.
    terkait: {no_plat, id_customer (asal supplier), id_pengangkutan} saat itu -> disimpan sebagai informasi.
    kategori = kategori target saat itu, id_area = lokasi blacklist (area pengaju)."""
    terkait = terkait or {}
    if tipe not in TIPE_VALID:                        # nama tabel disisipkan ke SQL -> hanya daftar tetap
        raise ValueError("Tipe blacklist tidak valid")
    tabel, kolom = _TARGET[tipe]
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT BlacklistID FROM {tabel} WITH (UPDLOCK) WHERE {kolom} = ?", id_target)
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Target tidak ditemukan")
        if row.BlacklistID is not None:
            raise ValueError("Target sudah masuk blacklist")
        id_dokumen = (buat_dokumen(cursor, "SURAT_BLACKLIST", no_surat, tgl_surat, f"Blacklist {tipe.lower()}",
                                   [file_info] if file_info else [], user_id) if no_surat else None)   # None = menyusul
        cursor.execute(f"""SET NOCOUNT ON;
                           INSERT INTO Blacklist (TableName, {kolom}, Reason, BlacklistDoc, CreateBy,
                                                  NoVehicle, CustomerID, TransportID,
                                                  AliasName, CategoryCode, CompAreaID, NewValue)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                           SELECT CAST(SCOPE_IDENTITY() AS BIGINT)""",
                       tabel, id_target, alasan, id_dokumen, user_id,
                       terkait.get("no_plat"), terkait.get("id_customer"), terkait.get("id_pengangkutan"),
                       nama_alias, kategori, id_area, json.dumps({"alasan": alasan}, ensure_ascii=False))
        id_blacklist = cursor.fetchone()[0]
        cursor.execute(f"UPDATE {tabel} SET BlacklistID = ? WHERE {kolom} = ?", id_blacklist, id_target)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lampirkan_surat(id_blacklist, no_surat, tgl_surat, file_info, user_id):
    """Surat blacklist yang menyusul. Error bila blacklist tidak ada / surat sudah dilampirkan."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT TargetType AS tipe_entitas, BlacklistDoc AS id_dokumen FROM Blacklist WITH (UPDLOCK) WHERE BlacklistID = ?", id_blacklist)
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Blacklist tidak ditemukan")
        if row.id_dokumen is not None:
            raise ValueError("Surat sudah dilampirkan")
        id_dokumen = buat_dokumen(cursor, "SURAT_BLACKLIST", no_surat, tgl_surat, f"Blacklist {row.tipe_entitas.lower()}",
                                  [file_info], user_id)
        cursor.execute("UPDATE Blacklist SET BlacklistDoc = ? WHERE BlacklistID = ?", id_dokumen, id_blacklist)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_surat_blacklist(tipe, id_target):
    """Surat blacklist terbaru untuk banner di Form Create Ticket."""
    kolom = _TARGET.get(tipe, _TARGET["KENDARAAN"])[1]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""SELECT TOP 1 dk.no_dokumen AS no_surat_blacklist,
                              COALESCE(dk.tanggal, CAST(b.CreateDate AS DATE)) AS tgl_blacklist,
                              df.file_path AS file_surat_blacklist, u.Nama AS oleh, ar.AreaName AS area_oleh
                       FROM Blacklist b JOIN Users u ON b.CreateBy = u.UserID
                       LEFT JOIN CompanyArea ar ON ar.CompAreaID = u.CompAreaID
                       LEFT JOIN dokumen dk ON dk.id_dokumen = b.BlacklistDoc
                       OUTER APPLY (SELECT TOP 1 f.file_path FROM dokumen_file f
                                    WHERE f.id_dokumen = dk.id_dokumen ORDER BY f.urutan) df
                       WHERE b.{kolom} = ? AND b.RevokeDate IS NULL ORDER BY b.CreateDate DESC, b.BlacklistID DESC""", id_target)
    data = _rows_to_dicts(cursor)
    conn.close()
    return _format(data[0]) if data else None


def nama_target(tipe, id_target):
    """(nama tampilan, sudah_blacklist) target; ValueError bila tidak ada."""
    if tipe == "PERSONEL":
        rows = _query_satu("SELECT UserCode AS kode_personel, Nama AS nama_personel, CAST(CASE WHEN BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted FROM Users WHERE UserID = ?", id_target)
        if not rows:
            raise ValueError("Target tidak ditemukan")
        r = rows[0]
        return (f"{r['kode_personel']} · {r['nama_personel']}" if r["kode_personel"] else r["nama_personel"]), bool(r["is_blacklisted"])
    rows = _query_satu("SELECT NoVehicle AS no_plat, CAST(CASE WHEN BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted FROM DetailVehicle WHERE IDVehicle = ?", id_target)
    if not rows:
        raise ValueError("Target tidak ditemukan")
    return rows[0]["no_plat"], bool(rows[0]["is_blacklisted"])


def get_blacklist(id_blacklist):
    rows = _query_satu("""SELECT b.BlacklistID AS id_blacklist, b.TargetType AS tipe_entitas, b.UserID AS id_personel, b.IDVehicle AS id_kendaraan, b.RevokeDate AS dicabut_at,
                                 COALESCE(p.Nama, k.NoVehicle) AS nama, p.NoKTP AS nik, b.AliasName AS nama_alias, b.CategoryCode AS kategori,
                                 COALESCE(b.NoVehicle, k.NoVehicle) AS no_plat, c.nama_supplier AS supplier,
                                 a.nama_supplier AS pengangkutan
                          FROM Blacklist b LEFT JOIN Users p ON p.UserID = b.UserID
                          LEFT JOIN DetailVehicle k ON k.IDVehicle = b.IDVehicle
                          LEFT JOIN mitra c ON c.id_supplier = b.CustomerID
                          LEFT JOIN mitra a ON a.id_supplier = b.TransportID WHERE b.BlacklistID = ?""", id_blacklist)
    return rows[0] if rows else None


def _query_satu(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def cabut_blacklist(id_blacklist, alasan, user_id):
    """Blacklist dicabut (hasil persetujuan). Baris tetap ada; target bebas bila tidak ada blacklist aktif lain.
    Trigger blacklist permanen hanya mengizinkan lewat SESSION_CONTEXT cabut_blacklist = 1 (migrasi 027)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT TargetType AS tipe_entitas, UserID AS id_personel, IDVehicle AS id_kendaraan, RevokeDate AS dicabut_at FROM Blacklist WITH (UPDLOCK) WHERE BlacklistID = ?",
                       id_blacklist)
        r = cursor.fetchone()
        if r is None:
            raise ValueError("Blacklist tidak ditemukan")
        if r.dicabut_at is not None:
            raise ValueError("Blacklist ini sudah dicabut")
        tabel, kolom = _TARGET[r.tipe_entitas]
        id_target = r.id_personel if r.tipe_entitas == "PERSONEL" else r.id_kendaraan
        cursor.execute("UPDATE Blacklist SET RevokeDate = GETDATE(), RevokeBy = ?, RevokeReason = ? WHERE BlacklistID = ?",
                       user_id, (alasan or "")[:500] or None, id_blacklist)
        cursor.execute(f"SELECT MAX(BlacklistID) FROM Blacklist WHERE {kolom} = ? AND RevokeDate IS NULL", id_target)
        sisa = cursor.fetchone()[0]          # blacklist aktif lain (bila ada) tetap menahan target
        if sisa is None:
            cursor.execute("EXEC sp_set_session_context N'cabut_blacklist', 1")
        cursor.execute(f"UPDATE {tabel} SET BlacklistID = ? WHERE {kolom} = ?", sisa, id_target)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.cursor().execute("EXEC sp_set_session_context N'cabut_blacklist', NULL")
        except Exception:       # noqa: BLE001 - koneksi sudah tertutup
            pass
        conn.close()


def mitra_aktif(id_supplier):
    """Nama mitra aktif, atau None."""
    rows = _query_satu("SELECT nama_supplier FROM mitra WHERE id_supplier = ? AND is_active = 1", id_supplier)
    return rows[0]["nama_supplier"] if rows else None
