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
def get_jadwal_kerja():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hari, nama_hari, jam_masuk, jam_pulang, is_libur, toleransi_menit FROM jadwal_kerja ORDER BY hari")
    data = [_jadwal_dict(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


def get_jadwal_hari(hari):
    return next((j for j in get_jadwal_kerja() if j["hari"] == hari), None)


def get_scan_terakhir(id_personel, tanggal):
    """Scan BERHASIL terakhir hari itu dan apakah sudah ada MASUK."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT MAX(waktu) AS terakhir,
                             SUM(CASE WHEN jenis = 'MASUK' THEN 1 ELSE 0 END) AS jml_masuk
                      FROM absensi WHERE id_personel = ? AND tanggal = ? AND status = 'BERHASIL'""",
                   id_personel, tanggal)
    r = cursor.fetchone()
    conn.close()
    return r.terakhir, bool(r.jml_masuk)


def insert_absensi(id_personel, jenis, status, status_waktu, selisih_menit, jarak_wajah, tantangan,
                   foto_path, perangkat, ip_address, waktu):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO absensi (id_personel, jenis, status, status_waktu, selisih_menit, jarak_wajah,
                                           tantangan_liveness, foto_path, perangkat, ip_address, waktu)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                   id_personel, jenis, status, status_waktu, selisih_menit, jarak_wajah, tantangan,
                   foto_path, perangkat, ip_address, waktu)
    conn.commit()
    conn.close()


def get_absensi_harian(tanggal, kategori=None):
    """Satu baris per personel aktif: MASUK pertama & PULANG terakhir hari itu."""
    sql = """
        SELECT p.id_personel, p.kode_personel, p.nama_personel, p.kategori, p.is_blacklisted,
               m.waktu AS jam_masuk, m.status_waktu AS status_masuk, m.selisih_menit AS selisih_masuk,
               k.waktu AS jam_pulang, k.status_waktu AS status_pulang, k.selisih_menit AS selisih_pulang
        FROM personel p
        OUTER APPLY (SELECT TOP 1 waktu, status_waktu, selisih_menit FROM absensi a
                     WHERE a.id_personel = p.id_personel AND a.tanggal = ? AND a.status = 'BERHASIL' AND a.jenis = 'MASUK'
                     ORDER BY a.waktu) m
        OUTER APPLY (SELECT TOP 1 waktu, status_waktu, selisih_menit FROM absensi a
                     WHERE a.id_personel = p.id_personel AND a.tanggal = ? AND a.status = 'BERHASIL' AND a.jenis = 'PULANG'
                     ORDER BY a.waktu DESC) k
        WHERE p.is_active = 1"""
    params = [tanggal, tanggal]
    if kategori:
        sql += " AND p.kategori = ?"
        params.append(kategori)
    sql += " ORDER BY CASE WHEN p.kode_personel IS NULL THEN 1 ELSE 0 END, p.kode_personel, p.id_personel"
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
        SELECT p.id_personel, p.kode_personel, p.nama_personel, p.kategori,
               COUNT(DISTINCT CASE WHEN a.jenis = 'MASUK' THEN a.tanggal END) AS hari_hadir,
               SUM(CASE WHEN a.jenis = 'MASUK' AND a.status_waktu = 'TERLAMBAT' THEN 1 ELSE 0 END) AS jml_terlambat,
               SUM(CASE WHEN a.jenis = 'MASUK' AND a.status_waktu = 'TERLAMBAT' THEN a.selisih_menit ELSE 0 END) AS menit_terlambat,
               SUM(CASE WHEN a.jenis = 'PULANG' AND a.status_waktu = 'PULANG_AWAL' THEN 1 ELSE 0 END) AS jml_pulang_awal
        FROM personel p
        LEFT JOIN absensi a ON a.id_personel = p.id_personel AND a.status = 'BERHASIL'
                           AND a.tanggal >= ? AND a.tanggal < ?
        WHERE p.is_active = 1
        GROUP BY p.id_personel, p.kode_personel, p.nama_personel, p.kategori
        ORDER BY CASE WHEN p.kode_personel IS NULL THEN 1 ELSE 0 END, p.kode_personel, p.id_personel
    """, awal, akhir)
    data = _rows_to_dicts(cursor)
    conn.close()
    return data
