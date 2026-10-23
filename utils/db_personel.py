from datetime import datetime

import pyodbc
from utils.db_utils import get_connection, _rows_to_dicts, hitung_hash_driver, user_id_baru
from utils.personel_utils import PREFIX_KODE, kode_berikutnya
from utils.face_cache import invalidate as reset_cache_wajah
from utils import log_aktivitas

KOLOM_PERSONEL = """p.UserID AS id_personel, p.UserCode AS kode_personel, p.NoKTP AS nik, p.Nama AS nama_personel, p.LicenseNumber AS no_sim, p.CategoryCode AS kategori,
                    p.LicenseID AS id_jenis_sim, p.LicenseCode AS kode_jenis_sim, p.ExpiredSIM AS sim_berlaku_sampai,
                    p.IsBlacklisted AS is_blacklisted, p.PhotoPath AS foto_path, p.PhotoSource AS foto_sumber, p.IsUpload AS is_updated, p.Active AS is_active, p.UpdateDate AS updated_at"""


def _normalisasi(r):
    for k in ("is_blacklisted", "is_updated", "is_active"):
        if k in r:
            r[k] = bool(r[k])
    if isinstance(r.get("updated_at"), datetime):
        r["updated_at"] = r["updated_at"].strftime("%Y-%m-%d %H:%M")
    if r.get("sim_berlaku_sampai") is not None:
        r["sim_berlaku_sampai"] = r["sim_berlaku_sampai"].isoformat()
    return r


def get_daftar_personel(kategori=None, cari=None, hanya_blacklist=False, batas=200):
    sql = f"SELECT TOP (?) {KOLOM_PERSONEL} FROM UserProfile p WHERE p.Active = 1"
    params = [batas]
    if kategori:
        sql += " AND p.CategoryCode = ?"
        params.append(kategori)
    if hanya_blacklist:
        sql += " AND p.IsBlacklisted = 1"
    if cari:
        sql += " AND (p.UserCode LIKE ? OR p.NoKTP LIKE ? OR p.Nama LIKE ? OR CAST(p.UserID AS VARCHAR) = ?)"
        pola = f"%{cari}%"
        params += [pola, pola, pola, cari.lstrip("0") or "0"]
    sql += " ORDER BY p.UserID"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, *params)
    data = [_normalisasi(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


def get_personel(id_personel):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {KOLOM_PERSONEL} FROM UserProfile p WHERE p.UserID = ?", id_personel)
    data = _rows_to_dicts(cursor)
    conn.close()
    return _normalisasi(data[0]) if data else None


def cek_kode_ada(kode, exclude_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT UserID AS id_personel FROM Users WHERE UserCode = ? AND UserID <> ?",
                   kode, exclude_id or 0)
    ada = cursor.fetchone() is not None
    conn.close()
    return ada


def prefix_kategori(kategori):
    """'DRV-' untuk kategori dengan prefix (Admin › Organisasi › Kategori Personel), selain itu PREFIX_KODE lama."""
    prefix = ((daftar_kategori(semua=True).get(kategori or "") or {}).get("prefix_kode") or "").strip().upper()
    return f"{prefix}-" if prefix else PREFIX_KODE


def saran_kode_personel(kategori=None):
    """Kode berikutnya untuk kategori: nomor terbesar prefix itu + 1 (unik, tidak menimpa kode lama)."""
    prefix = prefix_kategori(kategori)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT UserCode AS kode_personel FROM Users WHERE UserCode LIKE ?",
                       prefix.replace("[", "[[]").replace("_", "[_]").replace("%", "[%]") + "%")
        kode = [r.kode_personel for r in cursor.fetchall()]
    finally:
        conn.close()
    return kode_berikutnya(kode, prefix)


def _catat_audit(cursor, id_personel, aksi, lama, baru, user_id):
    """lama / baru: dict {kode_personel, nik, nama, no_sim} (lama None untuk TAMBAH). Dicatat di log_aktivitas."""
    log_aktivitas.catat("PERSONEL", aksi, tabel="Users", id_baris=id_personel, lama=lama, baru=baru,
                        user_id=user_id, cursor=cursor)


# ===== SIM & WAJAH (dipakai juga oleh driver dari Form Security, utils/db_utils.py) =====
def sim_dipakai(no_sim, exclude_id=None):
    """No. SIM aktif milik personel lain."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("""SELECT TOP 1 UserID AS id_personel FROM LicenseDetail
                                       WHERE LicenseNumber = ? AND Active = 1 AND UserID <> ?""",
                                    no_sim, exclude_id or 0).fetchone()
        return row is not None
    finally:
        conn.close()


def simpan_sim(cursor, id_personel, no_sim, id_jenis_sim=None, berlaku_sampai=None, user_id=None):
    """SIM aktif personel. Kosong -> SIM aktif dinonaktifkan. Nomor sama -> jenis & masa berlaku diperbarui bila diisi.
    Nomor berbeda -> SIM lama nonaktif (riwayat tetap), SIM baru ditambah. Jenis kosong = BELUM_DIISI (data cepat dari pos)."""
    cursor.execute("SELECT DetailLicenseID AS id_sim, LicenseNumber AS no_sim FROM LicenseDetail WHERE UserID = ? AND Active = 1", id_personel)
    aktif = cursor.fetchall()
    sama = next((x for x in aktif if no_sim and x.no_sim == no_sim), None)
    for x in aktif:
        if x is not sama:
            cursor.execute("UPDATE LicenseDetail SET Active = 0 WHERE DetailLicenseID = ?", x.id_sim)
    if not no_sim:
        return
    if sama:
        if id_jenis_sim:
            cursor.execute("UPDATE LicenseDetail SET SIMType = ?, ExpiredSIM = ? WHERE DetailLicenseID = ?",
                           id_jenis_sim, berlaku_sampai, sama.id_sim)
        return
    cursor.execute("""INSERT INTO LicenseDetail (UserID, SIMType, LicenseNumber, ExpiredSIM, CreateBy)
                      VALUES (?, COALESCE(?, (SELECT LicenseID FROM License WHERE LicenseCode = 'BELUM_DIISI')), ?, ?, ?)""",
                   id_personel, id_jenis_sim, no_sim, berlaku_sampai, user_id)


def simpan_wajah(cursor, id_personel, embedding_binary, foto_path, sumber, user_id=None):
    """Wajah baru menjadi wajah utama; wajah lama dinonaktifkan (tidak dikenali lagi, riwayat & foto tetap)."""
    cursor.execute("UPDATE FaceRecog SET IsMain = 0, Active = 0 WHERE UserID = ? AND Active = 1",
                   id_personel)
    cursor.execute("""INSERT INTO FaceRecog (UserID, FaceDet, PhotoPath, Source, CreateBy)
                      VALUES (?, ?, ?, ?, ?)""", id_personel, embedding_binary, foto_path, sumber, user_id)


def _data_lama(cursor, id_personel):
    cursor.execute("SELECT UserCode AS kode_personel, NoKTP AS nik, Nama AS nama_personel, LicenseNumber AS no_sim FROM UserProfile WHERE UserID = ?", id_personel)
    r = cursor.fetchone()
    return {"kode_personel": r.kode_personel, "nik": r.nik, "nama": r.nama_personel, "no_sim": r.no_sim}


def insert_personel(nik, nama, no_sim, kategori, kode, embedding_binary, foto_path, foto_sumber, user_id,
                    id_jenis_sim=None, sim_berlaku=None):
    conn = get_connection()
    cursor = conn.cursor()
    id_personel = user_id_baru(cursor)
    cursor.execute("""INSERT INTO Users (UserID, UserCode, NoKTP, Nama, CategoryCode, CurrentHash)
                      VALUES (?, ?, ?, ?, ?, ?)""",
                   id_personel, kode or None, nik, nama, kategori, hitung_hash_driver(nik, nama, no_sim, datetime.now()))
    simpan_sim(cursor, id_personel, no_sim or None, id_jenis_sim, sim_berlaku, user_id)
    if embedding_binary is not None:
        simpan_wajah(cursor, id_personel, embedding_binary, foto_path, foto_sumber, user_id)
    if user_id:
        _catat_audit(cursor, id_personel, "TAMBAH", None,
                     {"kode_personel": kode or None, "nik": nik, "nama": nama, "no_sim": no_sim or None}, user_id)
    conn.commit()
    conn.close()
    reset_cache_wajah()
    return id_personel


def update_personel(id_personel, kode, nik, nama, no_sim, kategori, user_id,
                    embedding_binary=None, foto_path=None, foto_sumber=None, id_jenis_sim=None, sim_berlaku=None):
    conn = get_connection()
    cursor = conn.cursor()
    lama = _data_lama(cursor, id_personel)
    baru = {"kode_personel": kode or None, "nik": nik, "nama": nama, "no_sim": no_sim or None}
    hash_baru = hitung_hash_driver(nik, nama, no_sim, datetime.now())
    cursor.execute("""UPDATE Users SET UserCode = ?, NoKTP = ?, Nama = ?, CategoryCode = ?,
                      IsUpload = 1, CurrentHash = ?, UpdateDate = GETDATE()
                      WHERE UserID = ?""", kode or None, nik, nama, kategori, hash_baru, id_personel)
    simpan_sim(cursor, id_personel, no_sim or None, id_jenis_sim, sim_berlaku, user_id)
    if embedding_binary is not None:
        simpan_wajah(cursor, id_personel, embedding_binary, foto_path, foto_sumber, user_id)
    _catat_audit(cursor, id_personel, "UPDATE", lama, baru, user_id)
    conn.commit()
    conn.close()
    if embedding_binary is not None:
        reset_cache_wajah()


def akun_personel(id_personel):
    """username akun aktif milik personel ini, atau None."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT UserName FROM Users WHERE UserID = ? AND Active = 1", id_personel).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def hapus_personel(id_personel, user_id):
    """Soft delete: wajah tidak dikenali lagi & dilepas dari truk; riwayat tiket/absensi tetap."""
    conn = get_connection()
    cursor = conn.cursor()
    data = _data_lama(cursor, id_personel)
    cursor.execute("UPDATE Users SET Active = 0, UpdateDate = GETDATE() WHERE UserID = ?", id_personel)
    cursor.execute("""UPDATE VehicleDriver SET Active = 0, IsMain = 0, UpdateDate = GETDATE()
                      WHERE UserID = ?""", id_personel)
    _catat_audit(cursor, id_personel, "HAPUS", data, data, user_id)
    conn.commit()
    conn.close()
    reset_cache_wajah()


def get_riwayat_perubahan_personel(hari=7, batas=300):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP (?) l.id_log, p.UserID AS id_personel, l.aksi,
               JSON_VALUE(l.nilai_lama, '$.kode_personel') AS kode_personel_lama,
               JSON_VALUE(l.nilai_baru, '$.kode_personel') AS kode_personel_baru,
               JSON_VALUE(l.nilai_lama, '$.nik') AS nik_lama, JSON_VALUE(l.nilai_baru, '$.nik') AS nik_baru,
               JSON_VALUE(l.nilai_lama, '$.nama') AS nama_lama, JSON_VALUE(l.nilai_baru, '$.nama') AS nama_baru,
               JSON_VALUE(l.nilai_lama, '$.no_sim') AS no_sim_lama, JSON_VALUE(l.nilai_baru, '$.no_sim') AS no_sim_baru,
               CAST(l.waktu AS DATETIME) AS updated_at, u.Nama AS oleh, lv.LevelDetCode AS role_oleh,
               p.UserCode AS kode_personel, p.Nama AS nama_personel
        FROM log_aktivitas l
        JOIN Users p ON p.UserID = TRY_CAST(l.id_baris AS BIGINT)
        LEFT JOIN Users u ON l.id_user = u.UserID
        LEFT JOIN LevelDetails lv ON lv.LevelDetID = u.UserLevelID
        WHERE l.kategori = 'PERSONEL' AND l.waktu >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
        ORDER BY l.id_log DESC
    """, batas, -(hari - 1))
    data = _rows_to_dicts(cursor)
    conn.close()
    return data


# ===== MASTER KATEGORI & JENIS SIM =====
# Kategori personel tetap (Supir, Karyawan, Security, Tamu): terikat aturan program, tidak diatur dari Admin.
def daftar_kategori(semua=False):
    """{kode: {kode, nama, wajib_sim, boleh_akun, prefix_kode, is_active}}; bawaan hanya yang aktif.
    Sebelum migrasi 020 (tanpa prefix_kode) tetap jalan dengan prefix kosong."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT CategoryCode AS kode, CategoryName AS nama, RequireLicense AS wajib_sim, CanLogin AS boleh_akun, CodePrefix AS prefix_kode, Active AS is_active FROM UserCategory")
        except pyodbc.Error:
            cursor.execute("SELECT CategoryCode AS kode, CategoryName AS nama, RequireLicense AS wajib_sim, CanLogin AS boleh_akun, NULL AS prefix_kode, Active AS is_active FROM UserCategory")
        return {r["kode"]: {**r, "wajib_sim": bool(r["wajib_sim"]), "boleh_akun": bool(r["boleh_akun"]),
                            "is_active": bool(r["is_active"])}
                for r in _rows_to_dicts(cursor) if semua or r["is_active"]}
    finally:
        conn.close()


def daftar_jenis_sim():
    """Pilihan jenis SIM di form (tanpa penanda BELUM_DIISI)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT LicenseID AS id_jenis_sim, LicenseCode AS kode, LicenseType AS nama FROM License WHERE Active = 1 ORDER BY LicenseID")
        return _rows_to_dicts(cursor)
    finally:
        conn.close()
