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
        cursor.execute("""SELECT t.DeliveryOrderID AS id_do, d.DONumber AS no_do, k.ContractQty AS qty_kg, v.Netto AS berat_netto, t.ParentTicketNumber AS no_tiket_induk
                          FROM WeightBridge t
                          JOIN DeliveryOrder d ON d.DeliveryOrderID = t.DeliveryOrderID
                          JOIN Contract k ON k.ContractID = d.ContractID
                          JOIN WeighingSummary v ON v.TicketNumber = t.TicketNumber
                          WHERE t.TicketNumber = ?""", no_tiket)
        r = cursor.fetchone()
        if not r or r.qty_kg is None or r.berat_netto is None or r.no_tiket_induk:
            return None
        # Kunci baris DO supaya dua tiket yang selesai bersamaan tidak menghitung kuota yang sama
        cursor.execute("SELECT DeliveryOrderID AS id_do FROM DeliveryOrder WITH (UPDLOCK, HOLDLOCK) WHERE DeliveryOrderID = ?", r.id_do)
        cursor.execute("""SELECT COALESCE(SUM(v.Netto), 0)
                          FROM WeightBridge t JOIN WeighingSummary v ON v.TicketNumber = t.TicketNumber
                          WHERE t.DeliveryOrderID = ? AND t.ParentTicketNumber IS NULL
                            AND (t.StatusCode = 'SELESAI' OR t.TicketNumber = ?)""", r.id_do, no_tiket)
        total = float(cursor.fetchone()[0])
        cursor.execute("SELECT COALESCE(SUM(ExcessKg), 0) FROM DOExcess WHERE DeliveryOrderID = ?", r.id_do)
        realisasi = total - float(cursor.fetchone()[0])
        kuota, netto = float(r.qty_kg), float(r.berat_netto)
        # Toleransi (Admin › Pengaturan Site): kelebihan kecil masih diterima di DO yang sama
        if realisasi - kuota <= pengaturan.nilai("TOLERANSI_KELEBIHAN_DO"):
            conn.commit()
            return None
        lebih = round(min(netto, realisasi - kuota), 2)
        split = f"{no_tiket}-S1"
        cursor.execute("""INSERT INTO WeightBridge (TicketNumber, WeightTypeCode, SupplierID, ProductID, IDVehicle, DriverID,
                                                 TransportID, VehicleContractID, DONumber, StatusCode, IsQRActive, QRExpiredDate,
                                                 QRReprintCount, DriverPhotoPath, CreateBy, ScaleID, CompAreaID, FlowID,
                                                 DeliveryOrderID, TransportMode, ParentTicketNumber, SplitWeight)
                          SELECT ?, WeightTypeCode AS jenis_transaksi, SupplierID AS id_supplier, ProductID AS id_produk, IDVehicle AS id_kendaraan, DriverID AS id_driver,
                                 TransportID AS id_pengangkutan, VehicleContractID AS id_kontrak, NULL, 'SELESAI', 0, QRExpiredDate AS qr_expired_at,
                                 0, DriverPhotoPath AS driver_photo_path, CreateBy AS security_id, ScaleID AS id_jembatan, CompAreaID AS id_comp_area, FlowID AS id_alur,
                                 NULL, TransportMode AS cara_angkut, TicketNumber AS no_tiket, ?
                          FROM WeightBridge WHERE TicketNumber = ?""", split, lebih, no_tiket)
        cursor.execute("SELECT CompAreaID FROM Users WHERE UserID = ?", user_id)
        area = (cursor.fetchone() or [None])[0]
        cursor.execute("""INSERT INTO DOExcess (TicketNumber, SplitTicketNumber, DeliveryOrderID, QuotaKg, RealizedKg, TicketNettoKg,
                                                    ExcessKg, CompAreaID)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", no_tiket, split, r.id_do, kuota, realisasi, netto, lebih, area)
        notifikasi.buat(MENU, f"DO {r.no_do} melebihi kuota {lebih:,.0f} kg",
                        f"Tiket {no_tiket}: kelebihan {lebih:,.0f} kg menjadi tiket {split}. Isi No. DO baru dari Ascend.",
                        "/kelebihan-do", area, cursor=cursor)
        log_aktivitas.catat("TIMELINE", "KELEBIHAN_DO", tabel="DOExcess", id_baris=no_tiket,
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
        syarat.append("x.Status = ?"); args.append(status)
    sql_a, args_a = sql_area("x.CompAreaID", id_area)
    if sql_a:
        syarat.append(sql_a[5:]); args.extend(args_a)
    sql = f"""SELECT TOP ({int(batas)}) x.ExcessID AS id_kelebihan, x.TicketNumber AS no_tiket, x.SplitTicketNumber AS no_tiket_split, d.DONumber AS no_do, x.QuotaKg AS kuota_kg, x.RealizedKg AS realisasi_kg,
                     x.TicketNettoKg AS netto_tiket_kg, x.ExcessKg AS kelebihan_kg, x.NewDONumber AS no_do_baru, x.Status AS status, x.Notes AS catatan, x.ReturnReason AS alasan_kembali, x.CreateDate AS created_at,
                     x.SubmitDate AS diajukan_at, x.ConfirmDate AS ditetapkan_at, ua.Nama AS diajukan_oleh, ut.Nama AS ditetapkan_oleh,
                     k.NoVehicle AS no_plat, p.Nama AS supir, m.SupplierName AS customer, ar.AreaName AS area
              FROM DOExcess x
              JOIN DeliveryOrder d ON d.DeliveryOrderID = x.DeliveryOrderID
              JOIN WeightBridge t ON t.TicketNumber = x.TicketNumber
              JOIN DetailVehicle k ON k.IDVehicle = t.IDVehicle
              JOIN Users p ON p.UserID = t.DriverID
              JOIN Supplier m ON m.SupplierID = t.SupplierID
              LEFT JOIN Users ua ON ua.UserID = x.SubmitBy
              LEFT JOIN Users ut ON ut.UserID = x.ConfirmBy
              LEFT JOIN CompanyArea ar ON ar.CompAreaID = x.CompAreaID
              {("WHERE " + " AND ".join(syarat)) if syarat else ""}
              ORDER BY CASE x.Status WHEN 'MENUNGGU' THEN 0 WHEN 'DIKEMBALIKAN' THEN 1 WHEN 'DIAJUKAN' THEN 2 ELSE 3 END,
                       x.CreateDate DESC"""
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
        cursor.execute("SELECT Status AS status, TicketNumber AS no_tiket, SplitTicketNumber AS no_tiket_split, CompAreaID AS id_comp_area FROM DOExcess WITH (UPDLOCK) "
                       "WHERE ExcessID = ?", id_kelebihan)
        r = cursor.fetchone()
        if r is None or not area_cocok(id_area, r.id_comp_area):      # site lain tidak bisa mengubah
            raise ValueError("Data kelebihan DO tidak ditemukan")
        if r.status not in status_boleh:
            raise ValueError(f"Status sekarang {r.status}, aksi ini tidak bisa dilakukan")
        cursor.execute(f"UPDATE DOExcess SET {set_sql} WHERE ExcessID = ?", *args, id_kelebihan)
        if notif:
            notifikasi.buat(MENU, notif[0].format(tiket=r.no_tiket_split), notif[1], "/kelebihan-do", r.id_comp_area,
                            cursor=cursor)
        log_aktivitas.catat("TIMELINE", aksi, tabel="DOExcess", id_baris=r.no_tiket, baru={"nilai": [str(a) for a in args]},
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
              "NewDONumber = ?, Notes = ?, Status = 'DIAJUKAN', SubmitBy = ?, SubmitDate = GETDATE(), ReturnReason = NULL",
              (no_do_baru, catatan, user_id), "KELEBIHAN_DO_AJUKAN", user_id, id_area=id_area)
    conn = get_connection()
    try:
        conn.cursor().execute("""UPDATE WeightBridge SET DONumber = ?, DeliveryOrderID = (SELECT DeliveryOrderID AS id_do FROM DeliveryOrder WHERE DONumber = ?)
                                 WHERE TicketNumber = ?""", no_do_baru, no_do_baru, r.no_tiket_split)
        conn.commit()
    finally:
        conn.close()


def tetapkan(id_kelebihan, user_id, id_area=None):
    _ubah(id_kelebihan, ("DIAJUKAN",), "Status = 'SELESAI', ConfirmBy = ?, ConfirmDate = GETDATE()",
          (user_id,), "KELEBIHAN_DO_TETAPKAN", user_id, id_area=id_area)


def kembalikan(id_kelebihan, alasan, user_id, id_area=None):
    _ubah(id_kelebihan, ("DIAJUKAN",), "Status = 'DIKEMBALIKAN', ReturnReason = ?, ConfirmBy = ?, ConfirmDate = GETDATE()",
          (alasan, user_id), "KELEBIHAN_DO_KEMBALIKAN", user_id,
          notif=("Kelebihan DO tiket {tiket} dikembalikan", f"Alasan: {alasan}. Perbaiki No. DO baru."), id_area=id_area)
