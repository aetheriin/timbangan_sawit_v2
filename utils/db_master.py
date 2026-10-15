"""Menu Data Master > Kendaraan: daftar semua truk, tambah / ubah plat & STNK, aktif / nonaktif, supir utama."""
from utils.db_utils import get_connection, _rows_to_dicts, _daftarkan_supir


def daftar_kendaraan(cari="", batas=500):
    sql = f"""
        SELECT TOP {int(batas)} k.id_kendaraan, k.no_plat, k.no_stnk, k.is_active, k.is_blacklisted, k.created_at,
               k.id_jenis_kendaraan, jk.nama AS jenis_kendaraan,
               u.id_driver AS id_supir_utama, u.nama_personel AS nama_supir_utama, u.kode_personel AS kode_supir_utama,
               (SELECT COUNT(*) FROM kendaraan_driver kd JOIN personel p ON p.id_personel = kd.id_driver
                WHERE kd.id_kendaraan = k.id_kendaraan AND kd.is_active = 1 AND p.is_active = 1) AS jumlah_supir,
               (SELECT MAX(t.created_at) FROM transaksi t WHERE t.id_kendaraan = k.id_kendaraan) AS transaksi_terakhir
        FROM kendaraan k
        LEFT JOIN jenis_kendaraan jk ON jk.id_jenis_kendaraan = k.id_jenis_kendaraan
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


def daftar_jenis_kendaraan(semua=False):
    """Jenis kendaraan + kapasitas (migrasi 032). Bawaan hanya yang aktif (pilihan form)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""SELECT j.id_jenis_kendaraan, j.kode, j.nama, j.is_active, j.berat_kosong_kg, j.muatan_maks_kg, j.kursi,
                                  (SELECT COUNT(*) FROM kendaraan k WHERE k.id_jenis_kendaraan = j.id_jenis_kendaraan
                                     AND k.is_active = 1) AS jumlah_kendaraan
                           FROM jenis_kendaraan j {'' if semua else 'WHERE j.is_active = 1'}
                           ORDER BY j.is_active DESC, j.id_jenis_kendaraan""")
        rows = _rows_to_dicts(cursor)
    finally:
        conn.close()
    for r in rows:
        for k in ("berat_kosong_kg", "muatan_maks_kg"):
            r[k] = float(r[k]) if r[k] is not None else None
    return rows


def simpan_jenis_kendaraan(id_jenis, kode, nama, berat_kosong, muatan_maks, kursi):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id_jenis_kendaraan FROM jenis_kendaraan WHERE kode = ? AND id_jenis_kendaraan <> ?", kode, id_jenis or 0)
        if cursor.fetchone():
            raise ValueError(f"Kode {kode} sudah dipakai.")
        if id_jenis:
            cursor.execute("""UPDATE jenis_kendaraan SET kode = ?, nama = ?, berat_kosong_kg = ?, muatan_maks_kg = ?, kursi = ?
                              WHERE id_jenis_kendaraan = ?""", kode, nama, berat_kosong, muatan_maks, kursi, id_jenis)
            if cursor.rowcount == 0:
                raise ValueError("Jenis kendaraan tidak ditemukan.")
        else:
            cursor.execute("""INSERT INTO jenis_kendaraan (kode, nama, berat_kosong_kg, muatan_maks_kg, kursi)
                              VALUES (?, ?, ?, ?, ?)""", kode, nama, berat_kosong, muatan_maks, kursi)
        conn.commit()
    finally:
        conn.close()


def set_aktif_jenis_kendaraan(id_jenis, aktif):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE jenis_kendaraan SET is_active = ? WHERE id_jenis_kendaraan = ?", 1 if aktif else 0, id_jenis)
        if cursor.rowcount == 0:
            raise ValueError("Jenis kendaraan tidak ditemukan.")
        conn.commit()
    finally:
        conn.close()


def cek_kapasitas(no_tiket):
    """Peringatan kapasitas kendaraan tiket ini (tidak menahan penimbangan):
    - tara berbeda lebih dari TOLERANSI_TARA_PERSEN dari berat kosong jenis kendaraannya (truk tidak benar-benar kosong
      / jenis kendaraan salah), - netto melebihi muatan maksimal jenis kendaraannya."""
    from utils import pengaturan
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT k.no_plat, j.nama, j.berat_kosong_kg, j.muatan_maks_kg, v.berat_bruto, v.berat_tara, v.berat_netto
                          FROM transaksi t JOIN kendaraan k ON k.id_kendaraan = t.id_kendaraan
                          JOIN jenis_kendaraan j ON j.id_jenis_kendaraan = k.id_jenis_kendaraan
                          JOIN v_timbangan v ON v.no_tiket = t.no_tiket
                          WHERE t.no_tiket = ?""", no_tiket)
        r = cursor.fetchone()
    finally:
        conn.close()
    if not r:
        return []
    angka = lambda v: f"{float(v):,.0f}".replace(",", ".")
    hasil = []
    toleransi = pengaturan.nilai("TOLERANSI_TARA_PERSEN")
    # Truk kosong = timbangan yang lebih ringan bila sudah dua kali; sebelum itu hanya tara (timbang masuk penjualan)
    kosong = (min(float(r.berat_bruto), float(r.berat_tara)) if r.berat_bruto is not None and r.berat_tara is not None
              else float(r.berat_tara) if r.berat_tara is not None else None)
    if r.berat_kosong_kg and kosong is not None and toleransi:
        selisih = abs(kosong - float(r.berat_kosong_kg)) / float(r.berat_kosong_kg) * 100
        if selisih > toleransi:
            hasil.append(f"Tara {r.no_plat} {angka(kosong)} kg, berbeda {selisih:.0f}% dari berat kosong "
                         f"{r.nama} ({angka(r.berat_kosong_kg)} kg). Pastikan truk benar-benar kosong.")
    if r.muatan_maks_kg and r.berat_netto is not None and float(r.berat_netto) > float(r.muatan_maks_kg):
        hasil.append(f"Muatan {r.no_plat} {angka(r.berat_netto)} kg melebihi muatan maksimal {r.nama} "
                     f"({angka(r.muatan_maks_kg)} kg).")
    return hasil


def stnk_dipakai(no_stnk, kecuali=None):
    """No STNK unik (migrasi 014). Kembalikan plat pemakainya, atau None."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT id_kendaraan, no_plat FROM kendaraan WHERE no_stnk = ?", no_stnk).fetchone()
        return row[1] if row and row[0] != kecuali else None
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


def simpan_kendaraan(id_kendaraan, no_plat, no_stnk, id_supir_utama, user_id, id_jenis=None):
    """Tambah (id_kendaraan None) / ubah. id_supir_utama None -> truk tanpa supir utama (supir lain tetap terdaftar)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_kendaraan is None:
            cursor.execute("""INSERT INTO kendaraan (no_plat, no_stnk, id_jenis_kendaraan) OUTPUT INSERTED.id_kendaraan
                              VALUES (?, ?, ?)""", no_plat, no_stnk, id_jenis)
            id_kendaraan = cursor.fetchone()[0]
        else:
            cursor.execute("UPDATE kendaraan SET no_plat = ?, no_stnk = ?, id_jenis_kendaraan = ? WHERE id_kendaraan = ?",
                           no_plat, no_stnk, id_jenis, id_kendaraan)
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
