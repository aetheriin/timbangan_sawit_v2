"""Kelebihan DO: total netto tiket satu DO melewati kuota kontrak (kontrak.qty_kg).

Saat tiket selesai ditimbang, kelebihannya menjadi tiket baru '<no tiket>-S1' (truk & supir sama, tanpa timbang ulang,
netto di transaksi.berat_split_kg) dan dicatat di kelebihan_do + notifikasi ke level yang punya hak menu KELEBIHAN_DO.
Krani mengisi No. DO baru (dari Ascend) -> KTU / HO menetapkan atau mengembalikan."""
from utils.area_filter import area_cocok, sql_area
from utils.db_utils import get_connection, _rows_to_dicts
from utils import log_aktivitas, notifikasi, pengaturan

MENU = "KELEBIHAN_DO"
STATUS = ("MENUNGGU", "DIAJUKAN", "SELESAI", "DIKEMBALIKAN")


def proses_tiket_selesai(no_tiket, user_id):
    """Dipanggil setelah tiket selesai ditimbang. Kembalikan info kelebihan (dict) atau None bila DO belum lewat kuota."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""SELECT t.id_do, d.DONumber AS no_do, k.ContractQty AS qty_kg, v.berat_netto, t.no_tiket_induk
                          FROM transaksi t
                          JOIN DeliveryOrder d ON d.DeliveryOrderID = t.id_do
                          JOIN Contract k ON k.ContractID = d.ContractID
                          JOIN v_timbangan v ON v.no_tiket = t.no_tiket
                          WHERE t.no_tiket = ?""", no_tiket)
        r = cursor.fetchone()
        if not r or r.qty_kg is None or r.berat_netto is None or r.no_tiket_induk:
            return None
        # Kunci baris DO supaya dua tiket yang selesai bersamaan tidak menghitung kuota yang sama
        cursor.execute("SELECT DeliveryOrderID AS id_do FROM DeliveryOrder WITH (UPDLOCK, HOLDLOCK) WHERE DeliveryOrderID = ?", r.id_do)
        cursor.execute("""SELECT COALESCE(SUM(v.berat_netto), 0)
                          FROM transaksi t JOIN v_timbangan v ON v.no_tiket = t.no_tiket
                          WHERE t.id_do = ? AND t.no_tiket_induk IS NULL
                            AND (t.status_alur = 'SELESAI' OR t.no_tiket = ?)""", r.id_do, no_tiket)
        total = float(cursor.fetchone()[0])
        cursor.execute("SELECT COALESCE(SUM(kelebihan_kg), 0) FROM kelebihan_do WHERE id_do = ?", r.id_do)
        realisasi = total - float(cursor.fetchone()[0])
        kuota, netto = float(r.qty_kg), float(r.berat_netto)
        # Toleransi (Admin › Pengaturan Site): kelebihan kecil masih diterima di DO yang sama
        if realisasi - kuota <= pengaturan.nilai("TOLERANSI_KELEBIHAN_DO"):
            conn.commit()
            return None
        lebih = round(min(netto, realisasi - kuota), 2)
        split = f"{no_tiket}-S1"
        cursor.execute("""INSERT INTO transaksi (no_tiket, jenis_transaksi, id_supplier, id_produk, id_kendaraan, id_driver,
                                                 id_pengangkutan, id_kontrak, no_do, status_alur, is_qr_active, qr_expired_at,
                                                 qr_reprint_count, driver_photo_path, security_id, id_jembatan, id_comp_area, id_alur,
                                                 id_do, cara_angkut, no_tiket_induk, berat_split_kg)
                          SELECT ?, jenis_transaksi, id_supplier, id_produk, id_kendaraan, id_driver,
                                 id_pengangkutan, id_kontrak, NULL, 'SELESAI', 0, qr_expired_at,
                                 0, driver_photo_path, security_id, id_jembatan, id_comp_area, id_alur,
                                 NULL, cara_angkut, no_tiket, ?
                          FROM transaksi WHERE no_tiket = ?""", split, lebih, no_tiket)
        cursor.execute("SELECT CompAreaID FROM Users WHERE UserID = ?", user_id)
        area = (cursor.fetchone() or [None])[0]
        cursor.execute("""INSERT INTO kelebihan_do (no_tiket, no_tiket_split, id_do, kuota_kg, realisasi_kg, netto_tiket_kg,
                                                    kelebihan_kg, id_comp_area)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", no_tiket, split, r.id_do, kuota, realisasi, netto, lebih, area)
        notifikasi.buat(MENU, f"DO {r.no_do} melebihi kuota {lebih:,.0f} kg",
                        f"Tiket {no_tiket}: kelebihan {lebih:,.0f} kg menjadi tiket {split}. Isi No. DO baru dari Ascend.",
                        "/kelebihan-do", area, cursor=cursor)
        log_aktivitas.catat("TIMELINE", "KELEBIHAN_DO", tabel="kelebihan_do", id_baris=no_tiket,
                            baru={"no_do": r.no_do, "kuota_kg": kuota, "realisasi_kg": realisasi, "kelebihan_kg": lebih,
                                  "tiket_split": split}, user_id=user_id, cursor=cursor)
        conn.commit()
        return {"no_do": r.no_do, "kuota_kg": kuota, "realisasi_kg": realisasi, "kelebihan_kg": lebih, "tiket_split": split}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def daftar(status=None, batas=300, id_area=None):
    """id_area None = semua area (kantor pusat)."""
    syarat, args = [], []
    if status:
        syarat.append("x.status = ?"); args.append(status)
    sql_a, args_a = sql_area("x.id_comp_area", id_area)
    if sql_a:
        syarat.append(sql_a[5:]); args.extend(args_a)
    sql = f"""SELECT TOP ({int(batas)}) x.id_kelebihan, x.no_tiket, x.no_tiket_split, d.DONumber AS no_do, x.kuota_kg, x.realisasi_kg,
                     x.netto_tiket_kg, x.kelebihan_kg, x.no_do_baru, x.status, x.catatan, x.alasan_kembali, x.created_at,
                     x.diajukan_at, x.ditetapkan_at, ua.Nama AS diajukan_oleh, ut.Nama AS ditetapkan_oleh,
                     k.NoVehicle AS no_plat, p.Nama AS supir, m.SupplierName AS customer, ar.AreaName AS area
              FROM kelebihan_do x
              JOIN DeliveryOrder d ON d.DeliveryOrderID = x.id_do
              JOIN transaksi t ON t.no_tiket = x.no_tiket
              JOIN DetailVehicle k ON k.IDVehicle = t.id_kendaraan
              JOIN Users p ON p.UserID = t.id_driver
              JOIN Supplier m ON m.SupplierID = t.id_supplier
              LEFT JOIN Users ua ON ua.UserID = x.diajukan_oleh
              LEFT JOIN Users ut ON ut.UserID = x.ditetapkan_oleh
              LEFT JOIN CompanyArea ar ON ar.CompAreaID = x.id_comp_area
              {("WHERE " + " AND ".join(syarat)) if syarat else ""}
              ORDER BY CASE x.status WHEN 'MENUNGGU' THEN 0 WHEN 'DIKEMBALIKAN' THEN 1 WHEN 'DIAJUKAN' THEN 2 ELSE 3 END,
                       x.created_at DESC"""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *args)
        rows = _rows_to_dicts(cursor)
    finally:
        conn.close()
    for r in rows:
        for k in ("created_at", "diajukan_at", "ditetapkan_at"):
            r[k] = r[k].strftime("%Y-%m-%d %H:%M") if r[k] else None
        for k in ("kuota_kg", "realisasi_kg", "netto_tiket_kg", "kelebihan_kg"):
            r[k] = float(r[k])
    return rows


def _ubah(id_kelebihan, status_boleh, set_sql, args, aksi, user_id, notif=None, id_area=None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT status, no_tiket, no_tiket_split, id_comp_area FROM kelebihan_do WITH (UPDLOCK) "
                       "WHERE id_kelebihan = ?", id_kelebihan)
        r = cursor.fetchone()
        if r is None or not area_cocok(id_area, r.id_comp_area):      # site lain tidak bisa mengubah
            raise ValueError("Data kelebihan DO tidak ditemukan")
        if r.status not in status_boleh:
            raise ValueError(f"Status sekarang {r.status}, aksi ini tidak bisa dilakukan")
        cursor.execute(f"UPDATE kelebihan_do SET {set_sql} WHERE id_kelebihan = ?", *args, id_kelebihan)
        if notif:
            notifikasi.buat(MENU, notif[0].format(tiket=r.no_tiket_split), notif[1], "/kelebihan-do", r.id_comp_area,
                            cursor=cursor)
        log_aktivitas.catat("TIMELINE", aksi, tabel="kelebihan_do", id_baris=r.no_tiket, baru={"nilai": [str(a) for a in args]},
                            user_id=user_id, cursor=cursor)
        conn.commit()
        return r
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ajukan(id_kelebihan, no_do_baru, catatan, user_id, id_area=None):
    """Krani: No. DO baru dari Ascend. Tiket split ikut memakai DO itu (id_do bila DO itu ada di sistem ini)."""
    r = _ubah(id_kelebihan, ("MENUNGGU", "DIKEMBALIKAN"),
              "no_do_baru = ?, catatan = ?, status = 'DIAJUKAN', diajukan_oleh = ?, diajukan_at = GETDATE(), alasan_kembali = NULL",
              (no_do_baru, catatan, user_id), "KELEBIHAN_DO_AJUKAN", user_id, id_area=id_area)
    conn = get_connection()
    try:
        conn.cursor().execute("""UPDATE transaksi SET DONumber = ?, DeliveryOrderID = (SELECT DeliveryOrderID AS id_do FROM DeliveryOrder WHERE DONumber = ?)
                                 WHERE no_tiket = ?""", no_do_baru, no_do_baru, r.no_tiket_split)
        conn.commit()
    finally:
        conn.close()


def tetapkan(id_kelebihan, user_id, id_area=None):
    _ubah(id_kelebihan, ("DIAJUKAN",), "status = 'SELESAI', ditetapkan_oleh = ?, ditetapkan_at = GETDATE()",
          (user_id,), "KELEBIHAN_DO_TETAPKAN", user_id, id_area=id_area)


def kembalikan(id_kelebihan, alasan, user_id, id_area=None):
    _ubah(id_kelebihan, ("DIAJUKAN",), "status = 'DIKEMBALIKAN', alasan_kembali = ?, ditetapkan_oleh = ?, ditetapkan_at = GETDATE()",
          (alasan, user_id), "KELEBIHAN_DO_KEMBALIKAN", user_id,
          notif=("Kelebihan DO tiket {tiket} dikembalikan", f"Alasan: {alasan}. Perbaiki No. DO baru."), id_area=id_area)
