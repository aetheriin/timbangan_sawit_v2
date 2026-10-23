"""Menu Data Master > Kendaraan: daftar semua truk, tambah / ubah plat & STNK, aktif / nonaktif, supir utama."""
from utils.db_utils import get_connection, _rows_to_dicts, _daftarkan_supir


def daftar_kendaraan(cari="", batas=500):
    sql = f"""
        SELECT TOP {int(batas)} k.IDVehicle AS id_kendaraan, k.NoVehicle AS no_plat, k.NoSTNK AS no_stnk, k.Active AS is_active, CAST(CASE WHEN k.BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted, k.CreateDate AS created_at,
               k.VehicleType AS id_jenis_kendaraan, jk.NameType AS jenis_kendaraan,
               u.id_driver AS id_supir_utama, u.nama_personel AS nama_supir_utama, u.kode_personel AS kode_supir_utama,
               (SELECT COUNT(*) FROM VehicleDriver kd JOIN Users p ON p.UserID = kd.UserID
                WHERE kd.IDVehicle = k.IDVehicle AND kd.Active = 1 AND p.Active = 1) AS jumlah_supir,
               (SELECT MAX(t.TicketDate) FROM WeightBridge t WHERE t.IDVehicle = k.IDVehicle) AS transaksi_terakhir
        FROM DetailVehicle k
        LEFT JOIN VehicleType jk ON jk.VehicleTypeID = k.VehicleType
        OUTER APPLY (SELECT TOP 1 kd.UserID AS id_driver, p.Nama AS nama_personel, p.UserCode AS kode_personel
                     FROM VehicleDriver kd JOIN Users p ON p.UserID = kd.UserID
                     WHERE kd.IDVehicle = k.IDVehicle AND kd.Active = 1 AND kd.IsMain = 1
                       AND p.Active = 1) u
        WHERE REPLACE(k.NoVehicle, ' ', '') LIKE ? OR k.NoSTNK LIKE ?
        ORDER BY k.Active DESC, k.NoVehicle"""
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
        cursor.execute("SELECT IDVehicle AS id_kendaraan, NoVehicle AS no_plat, NoSTNK AS no_stnk, Active AS is_active FROM DetailVehicle WHERE IDVehicle = ?",
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
        cursor.execute(f"""SELECT j.VehicleTypeID AS id_jenis_kendaraan, j.VehicleTypeCode AS kode, j.NameType AS nama, j.Active AS is_active, j.WeightCar AS berat_kosong_kg, j.MaxLoad AS muatan_maks_kg, j.Seat AS kursi,
                                  (SELECT COUNT(*) FROM DetailVehicle k WHERE k.VehicleType = j.VehicleTypeID
                                     AND k.Active = 1) AS jumlah_kendaraan
                           FROM VehicleType j {'' if semua else 'WHERE j.Active = 1'}
                           ORDER BY j.Active DESC, j.VehicleTypeID""")
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
        cursor.execute("SELECT VehicleTypeID AS id_jenis_kendaraan FROM VehicleType WHERE VehicleTypeCode = ? AND VehicleTypeID <> ?", kode, id_jenis or 0)
        if cursor.fetchone():
            raise ValueError(f"Kode {kode} sudah dipakai.")
        if id_jenis:
            cursor.execute("""UPDATE VehicleType SET VehicleTypeCode = ?, NameType = ?, WeightCar = ?, MaxLoad = ?, Seat = ?
                              WHERE VehicleTypeID = ?""", kode, nama, berat_kosong, muatan_maks, kursi, id_jenis)
            if cursor.rowcount == 0:
                raise ValueError("Jenis kendaraan tidak ditemukan.")
        else:
            cursor.execute("""INSERT INTO VehicleType (VehicleTypeCode, NameType, WeightCar, MaxLoad, Seat)
                              VALUES (?, ?, ?, ?, ?)""", kode, nama, berat_kosong, muatan_maks, kursi)
        conn.commit()
    finally:
        conn.close()


def set_aktif_jenis_kendaraan(id_jenis, aktif):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE VehicleType SET Active = ? WHERE VehicleTypeID = ?", 1 if aktif else 0, id_jenis)
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
        cursor.execute("""SELECT k.NoVehicle AS no_plat, j.NameType AS nama, j.WeightCar AS berat_kosong_kg, j.MaxLoad AS muatan_maks_kg, v.Bruto AS berat_bruto, v.Tara AS berat_tara, v.Netto AS berat_netto
                          FROM WeightBridge t JOIN DetailVehicle k ON k.IDVehicle = t.IDVehicle
                          JOIN VehicleType j ON j.VehicleTypeID = k.VehicleType
                          JOIN WeighingSummary v ON v.TicketNumber = t.TicketNumber
                          WHERE t.TicketNumber = ?""", no_tiket)
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
        row = conn.cursor().execute("SELECT IDVehicle AS id_kendaraan, NoVehicle AS no_plat FROM DetailVehicle WHERE NoSTNK = ?", no_stnk).fetchone()
        return row[1] if row and row[0] != kecuali else None
    finally:
        conn.close()


def plat_dipakai(no_plat, kecuali=None):
    conn = get_connection()
    try:
        row = conn.cursor().execute("SELECT IDVehicle AS id_kendaraan FROM DetailVehicle WHERE NoVehicle = ?", no_plat).fetchone()
        return bool(row and row[0] != kecuali)
    finally:
        conn.close()


def ada_tiket_aktif(id_kendaraan):
    conn = get_connection()
    try:
        row = conn.cursor().execute("""SELECT TOP 1 TicketNumber AS no_tiket FROM WeightBridge WHERE IDVehicle = ?
                                       AND StatusCode NOT IN ('SELESAI', 'REJECTED', 'VOID')""", id_kendaraan).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def simpan_kendaraan(id_kendaraan, no_plat, no_stnk, id_supir_utama, user_id, id_jenis=None):
    """Tambah (id_kendaraan None) / ubah. id_supir_utama None -> truk tanpa supir utama (supir lain tetap terdaftar)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_kendaraan is None:
            cursor.execute("""SET NOCOUNT ON; INSERT INTO DetailVehicle (NoVehicle, NoSTNK, VehicleType) VALUES (?, ?, ?);
                              SELECT CAST(SCOPE_IDENTITY() AS INT)""", no_plat, no_stnk, id_jenis)
            id_kendaraan = cursor.fetchone()[0]
        else:
            cursor.execute("UPDATE DetailVehicle SET NoVehicle = ?, NoSTNK = ?, VehicleType = ? WHERE IDVehicle = ?",
                           no_plat, no_stnk, id_jenis, id_kendaraan)
        if id_supir_utama:
            _daftarkan_supir(cursor, id_kendaraan, id_supir_utama, True, user_id)
        else:
            cursor.execute("UPDATE VehicleDriver SET IsMain = 0, UpdateDate = GETDATE() WHERE IDVehicle = ?",
                           id_kendaraan)
        conn.commit()
        return id_kendaraan
    finally:
        conn.close()


def set_aktif_kendaraan(id_kendaraan, aktif):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE DetailVehicle SET Active = ? WHERE IDVehicle = ?", 1 if aktif else 0, id_kendaraan)
        conn.commit()
    finally:
        conn.close()


def daftar_driver_aktif():
    """Pilihan supir utama: driver aktif & tidak blacklist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT UserID AS id_personel, UserCode AS kode_personel, Nama AS nama_personel, NoKTP AS nik FROM Users
                          WHERE CategoryCode = 'DRIVER' AND Active = 1 AND CAST(CASE WHEN BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) = 0
                          ORDER BY Nama""")
        return _rows_to_dicts(cursor)
    finally:
        conn.close()
