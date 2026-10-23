"""Kunjungan tamu (Pengenalan Wajah › Kunjungan Tamu). Tamu = personel kategori TAMU (tanpa akun);
setiap kedatangan satu baris kunjungan: orang yang dituju, keperluan, waktu masuk / keluar."""
from datetime import date, datetime, timedelta

from utils.db_utils import get_connection, _rows_to_dicts


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        n = cursor.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def daftar_keperluan():
    try:
        return _query("SELECT PurposeID AS id_keperluan, PurposeName AS nama FROM VisitPurpose WHERE Active = 1 ORDER BY PurposeID")
    except Exception:       # noqa: BLE001 - migrasi 009 belum dijalankan: halaman tetap terbuka
        return []


def daftar_dituju():
    """Orang yang bisa ditemui tamu: karyawan & security aktif."""
    return _query("""SELECT p.UserID AS id_personel, p.UserCode AS kode_personel, p.Nama AS nama_personel, k.CategoryName AS kategori
                     FROM Users p JOIN UserCategory k ON k.CategoryCode = p.CategoryCode
                     WHERE p.Active = 1 AND p.CategoryCode IN ('EMPLOYEE', 'SECURITY')
                     ORDER BY p.Nama""")


def daftar_kunjungan(tanggal=None, hanya_didalam=False):
    sql = """SELECT k.GuestID AS id_kunjungan, k.CheckInDate AS waktu_masuk, k.CheckOutDate AS waktu_keluar, k.CompanyFrom AS asal_perusahaan, k.NoVehicle AS no_plat, k.Description AS keterangan,
                    k.PhotoPath AS foto_masuk_path, t.UserID AS id_personel, t.Nama AS nama_tamu, t.NoKTP AS nik, t.IsBlacklisted AS is_blacklisted,
                    t.PhotoPath AS foto_path, d.UserID AS id_dituju, d.UserCode AS kode_dituju, d.Nama AS nama_dituju,
                    kp.PurposeName AS keperluan, u.Nama AS dicatat_oleh
             FROM Guest k
             JOIN UserProfile t ON t.UserID = k.UserID
             JOIN Users d ON d.UserID = k.VisitToID
             JOIN VisitPurpose kp ON kp.PurposeID = k.PurposeID
             JOIN Users u ON u.UserID = k.CreateBy"""
    if hanya_didalam:
        rows = _query(sql + " WHERE k.CheckOutDate IS NULL ORDER BY k.CheckInDate DESC")
    else:
        hari = tanggal or date.today()
        rows = _query(sql + " WHERE k.CheckInDate >= ? AND k.CheckInDate < ? ORDER BY k.CheckInDate DESC",
                      datetime.combine(hari, datetime.min.time()), datetime.combine(hari + timedelta(days=1), datetime.min.time()))
    for r in rows:
        r["is_blacklisted"] = bool(r["is_blacklisted"])
        for k in ("waktu_masuk", "waktu_keluar"):
            r[k] = r[k].strftime("%Y-%m-%d %H:%M") if r[k] else None
    return rows


def kunjungan_aktif(id_personel):
    rows = _query("SELECT TOP 1 GuestID AS id_kunjungan, CheckInDate AS waktu_masuk FROM Guest WHERE UserID = ? AND CheckOutDate IS NULL",
                  id_personel)
    return rows[0] if rows else None


def catat_masuk(id_personel, id_dituju, id_keperluan, keterangan, asal_perusahaan, no_plat, id_comp_area,
                foto_masuk_path, user_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO Guest (UserID, VisitToID, PurposeID, Description, CompanyFrom, NoVehicle,
                                                 CompAreaID, PhotoPath, CreateBy)
                          OUTPUT INSERTED.GuestID VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       id_personel, id_dituju, id_keperluan, keterangan, asal_perusahaan, no_plat, id_comp_area,
                       foto_masuk_path, user_id)
        id_baru = cursor.fetchone()[0]
        conn.commit()
        return id_baru
    finally:
        conn.close()


def catat_keluar(id_kunjungan):
    return _ubah("UPDATE Guest SET CheckOutDate = GETDATE() WHERE GuestID = ? AND CheckOutDate IS NULL",
                 id_kunjungan)


def area_akun(id_user):
    rows = _query("SELECT CompAreaID AS id_comp_area FROM Users WHERE UserID = ?", id_user)
    return rows[0]["id_comp_area"] if rows else None
