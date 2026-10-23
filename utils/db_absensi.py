from datetime import datetime, time, date
from utils.db_utils import get_connection, _rows_to_dicts
from utils.cache import cache_ttl


def _jam(v):
    """Kolom TIME dari pyodbc bisa berupa time atau string 'HH:MM:SS'."""
    if v is None or isinstance(v, time):
        return v
    return time.fromisoformat(str(v)[:8])


def _jadwal_dict(r):
    return {"hari": r["hari"], "nama_hari": r["nama_hari"], "jam_masuk": _jam(r["jam_masuk"]),
            "jam_pulang": _jam(r["jam_pulang"]), "is_libur": bool(r["is_libur"]),
            "toleransi_menit": r["toleransi_menit"] or 0}


@cache_ttl(300)
def get_jadwal_kerja(id_comp_area=None):
    """Jadwal mingguan satu area (migrasi 014). Tanpa area -> area pertama."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT hari, nama_hari, jam_masuk, jam_pulang, is_libur, toleransi_menit FROM jadwal_kerja
                      WHERE id_comp_area = COALESCE(?, (SELECT MIN(id_comp_area) FROM jadwal_kerja))
                      ORDER BY hari""", id_comp_area)
    data = [_jadwal_dict(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


def get_jadwal_hari(hari, id_comp_area=None):
    return next((j for j in get_jadwal_kerja(id_comp_area) if j["hari"] == hari), None)


def get_scan_terakhir(id_personel, tanggal):
    """Scan BERHASIL terakhir hari itu dan apakah sudah ada MASUK."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT MAX(LogDate) AS terakhir,
                             SUM(CASE WHEN ActivityType = 'MASUK' THEN 1 ELSE 0 END) AS jml_masuk
                      FROM FaceActivity WHERE UserID = ? AND LogDay = ? AND Status = 'BERHASIL'""",
                   id_personel, tanggal)
    r = cursor.fetchone()
    conn.close()
    return r.terakhir, bool(r.jml_masuk)


def insert_absensi(id_personel, jenis, status, status_waktu, selisih_menit, jarak_wajah, tantangan,
                   foto_path, perangkat, ip_address, waktu):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO FaceActivity (UserID, ActivityType, Status, TimeStatus, DiffMinutes, FaceDistance,
                                           LivenessChallenge, PhotoPath, Device, IPAddress, LogDate)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   id_personel, jenis, status, status_waktu, selisih_menit, jarak_wajah, tantangan,
                   foto_path, perangkat, ip_address, waktu)
    conn.commit()
    conn.close()


def get_absensi_harian(tanggal, kategori=None):
    """Satu baris per personel aktif: MASUK pertama & PULANG terakhir hari itu."""
    sql = """
        SELECT p.UserID AS id_personel, p.UserCode AS kode_personel, p.Nama AS nama_personel, p.CategoryCode AS kategori, CAST(CASE WHEN p.BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted,
               m.waktu AS jam_masuk, m.status_waktu AS status_masuk, m.selisih_menit AS selisih_masuk,
               k.waktu AS jam_pulang, k.status_waktu AS status_pulang, k.selisih_menit AS selisih_pulang
        FROM Users p
        OUTER APPLY (SELECT TOP 1 a.LogDate AS waktu, a.TimeStatus AS status_waktu, a.DiffMinutes AS selisih_menit FROM FaceActivity a
                     WHERE a.UserID = p.UserID AND a.LogDay = ? AND a.Status = 'BERHASIL' AND a.ActivityType = 'MASUK'
                     ORDER BY a.LogDate) m
        OUTER APPLY (SELECT TOP 1 a.LogDate AS waktu, a.TimeStatus AS status_waktu, a.DiffMinutes AS selisih_menit FROM FaceActivity a
                     WHERE a.UserID = p.UserID AND a.LogDay = ? AND a.Status = 'BERHASIL' AND a.ActivityType = 'PULANG'
                     ORDER BY a.LogDate DESC) k
        WHERE p.Active = 1 AND p.CategoryCode <> 'TAMU'"""
    params = [tanggal, tanggal]
    if kategori:
        sql += " AND p.CategoryCode = ?"
        params.append(kategori)
    sql += " ORDER BY CASE WHEN p.UserCode IS NULL THEN 1 ELSE 0 END, p.UserCode, p.UserID"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, *params)
    data = _rows_to_dicts(cursor)
    conn.close()
    for r in data:
        for k in ("jam_masuk", "jam_pulang"):
            r[k] = r[k].strftime("%H:%M") if isinstance(r[k], datetime) else None
        r["is_blacklisted"] = bool(r["is_blacklisted"])
    return data


def get_rekap_bulanan(tahun, bulan):
    awal = date(tahun, bulan, 1)
    akhir = date(tahun + (bulan == 12), bulan % 12 + 1, 1)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.UserID AS id_personel, p.UserCode AS kode_personel, p.Nama AS nama_personel, p.CategoryCode AS kategori,
               COUNT(DISTINCT CASE WHEN a.ActivityType = 'MASUK' THEN a.LogDay END) AS hari_hadir,
               SUM(CASE WHEN a.ActivityType = 'MASUK' AND a.TimeStatus = 'TERLAMBAT' THEN 1 ELSE 0 END) AS jml_terlambat,
               SUM(CASE WHEN a.ActivityType = 'MASUK' AND a.TimeStatus = 'TERLAMBAT' THEN a.DiffMinutes ELSE 0 END) AS menit_terlambat,
               SUM(CASE WHEN a.ActivityType = 'PULANG' AND a.TimeStatus = 'PULANG_AWAL' THEN 1 ELSE 0 END) AS jml_pulang_awal
        FROM Users p
        LEFT JOIN FaceActivity a ON a.UserID = p.UserID AND a.Status = 'BERHASIL'
                           AND a.LogDay >= ? AND a.LogDay < ?
        WHERE p.Active = 1 AND p.CategoryCode <> 'TAMU'
        GROUP BY p.UserID, p.UserCode, p.Nama, p.CategoryCode
        ORDER BY CASE WHEN p.UserCode IS NULL THEN 1 ELSE 0 END, p.UserCode, p.UserID
    """, awal, akhir)
    data = _rows_to_dicts(cursor)
    conn.close()
    return data
