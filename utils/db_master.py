"""Menu Data Master > Kendaraan: daftar semua truk, tambah / ubah plat & STNK, aktif / nonaktif, supir utama."""
from utils.db_utils import get_connection, _rows_to_dicts, _daftarkan_supir


def daftar_kendaraan(cari="", batas=500):
    sql = f"""
        SELECT TOP {int(batas)} k.id_kendaraan, k.no_plat, k.no_stnk, k.is_active, k.is_blacklisted, k.created_at,
               u.id_driver AS id_supir_utama, u.nama_personel AS nama_supir_utama, u.kode_personel AS kode_supir_utama,
               (SELECT COUNT(*) FROM kendaraan_driver kd JOIN personel p ON p.id_personel = kd.id_driver
                WHERE kd.id_kendaraan = k.id_kendaraan AND kd.is_active = 1 AND p.is_active = 1) AS jumlah_supir,
               (SELECT MAX(t.created_at) FROM transaksi t WHERE t.id_kendaraan = k.id_kendaraan) AS transaksi_terakhir
        FROM kendaraan k
        OUTER APPLY (SELECT TOP 1 kd.id_driver, p.nama_personel, p.kode_personel
                     FROM kendaraan_driver kd JOIN personel p ON p.id_personel = kd.id_driver
                     WHERE kd.id_kendaraan = k.id_kendaraan AND kd.is_active = 1 AND kd.is_utama = 1
                       AND p.is_active = 1) u
        WHERE REPLACE(k.no_plat, ' ', '') LIKE ? OR k.no_stnk LIKE ?
        ORDER BY k.is_active DESC, k.no_plat"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, f"%{cari.replace(' ', '')}%", f"%{cari}%")
        data = _rows_to_dicts(cursor)
    finally:
        conn.close()
    for r in data:
        r["is_active"], r["is_blacklisted"] = bool(r["is_active"]), bool(r["is_blacklisted"])
        for k in ("created_at", "transaksi_terakhir"):
            r[k] = r[k].strftime("%Y-%m-%d %H:%M") if r[k] else None
    return data


def get_kendaraan(id_kendaraan):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id_kendaraan, no_plat, no_stnk, is_active FROM kendaraan WHERE id_kendaraan = ?",
                       id_kendaraan)
        rows = _rows_to_dicts(cursor)
        return rows[0] if rows else None
    finally:
        conn.close()


def plat_dipakai(no_plat, kecuali=None):
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT id_kendaraan FROM kendaraan WHERE no_plat = ?", no_plat).fetchone()
        return bool(row and row[0] != kecuali)
    finally:
        conn.close()


def ada_tiket_aktif(id_kendaraan):
    conn = get_connection()
    try:
        row = conn.cursor().execute("""SELECT TOP 1 no_tiket FROM transaksi WHERE id_kendaraan = ?
                                       AND status_alur NOT IN ('SELESAI', 'REJECTED', 'VOID')""", id_kendaraan).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def simpan_kendaraan(id_kendaraan, no_plat, no_stnk, id_supir_utama, user_id):
    """Tambah (id_kendaraan None) / ubah. id_supir_utama None -> truk tanpa supir utama (supir lain tetap terdaftar)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_kendaraan is None:
            cursor.execute("INSERT INTO kendaraan (no_plat, no_stnk) OUTPUT INSERTED.id_kendaraan VALUES (?, ?)",
                           no_plat, no_stnk)
            id_kendaraan = cursor.fetchone()[0]
        else:
            cursor.execute("UPDATE kendaraan SET no_plat = ?, no_stnk = ? WHERE id_kendaraan = ?",
                           no_plat, no_stnk, id_kendaraan)
        if id_supir_utama:
            _daftarkan_supir(cursor, id_kendaraan, id_supir_utama, True, user_id)
        else:
            cursor.execute("UPDATE kendaraan_driver SET is_utama = 0, updated_at = GETDATE() WHERE id_kendaraan = ?",
                           id_kendaraan)
        conn.commit()
        return id_kendaraan
    finally:
        conn.close()


def set_aktif_kendaraan(id_kendaraan, aktif):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE kendaraan SET is_active = ? WHERE id_kendaraan = ?", 1 if aktif else 0, id_kendaraan)
        conn.commit()
    finally:
        conn.close()


def daftar_driver_aktif():
    """Pilihan supir utama: driver aktif & tidak blacklist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT id_personel, kode_personel, nama_personel, nik FROM personel
                          WHERE kategori = 'DRIVER' AND is_active = 1 AND is_blacklisted = 0
                          ORDER BY nama_personel""")
        return _rows_to_dicts(cursor)
    finally:
        conn.close()
