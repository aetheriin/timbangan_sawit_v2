"""Pengajuan koreksi data tiket (ERD DatabaseRequestLog): customer, produk, supir, atau kendaraan tiket yang salah
input diajukan lewat Daftar Tiket (hak Ubah di menu Daftar Tiket) dan berlaku setelah disetujui pemegang hak Setujui
di menu itu. Berat tidak bisa dikoreksi (harus timbang ulang / void). Perubahan dicatat di log (kategori DATA)."""
from utils import log_aktivitas, persetujuan
from utils.db_utils import get_connection, _rows_to_dicts, _filter_area

KOLOM = {"id_supplier": "Customer", "id_produk": "Produk", "id_driver": "Supir", "id_kendaraan": "Kendaraan"}


def data_tiket(no_tiket, id_area=None):
    """Isi tiket yang bisa dikoreksi (sesuai akses area pengguna), atau None."""
    filter_area, param_area = _filter_area(id_area)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""SELECT t.TicketNumber AS no_tiket, t.StatusCode AS status_alur, t.SupplierID AS id_supplier, s.SupplierName AS nama_supplier, t.ProductID AS id_produk, p.ProductName AS nama_produk,
                                  t.DriverID AS id_driver, d.Nama AS nama_driver, t.IDVehicle AS id_kendaraan, k.NoVehicle AS no_plat
                           FROM WeightBridge t JOIN Supplier s ON s.SupplierID = t.SupplierID
                           JOIN Product p ON p.ProductID = t.ProductID JOIN Users d ON d.UserID = t.DriverID
                           JOIN DetailVehicle k ON k.IDVehicle = t.IDVehicle
                           WHERE t.TicketNumber = ? AND t.StatusCode <> 'VOID'{filter_area}""", no_tiket, *param_area)
        rows = _rows_to_dicts(cursor)
    finally:
        conn.close()
    return rows[0] if rows else None


def ajukan(tiket, ubah, nama_baru, alasan, user_id):
    """ubah = {kolom: id baru} (hanya yang berbeda); nama_baru = {kolom: teks}. Kembalikan (status, info penyetuju)."""
    nama_lama = {"id_supplier": tiket["nama_supplier"], "id_produk": tiket["nama_produk"],
                 "id_driver": tiket["nama_driver"], "id_kendaraan": tiket["no_plat"]}
    rincian = [{"label": KOLOM[k], "lama": nama_lama[k], "baru": nama_baru[k]} for k in KOLOM if k in ubah]
    data = {"no_tiket": tiket["no_tiket"], "ubah": ubah, "lama": {k: tiket[k] for k in ubah}, "_rincian": rincian}
    judul = f"Koreksi tiket {tiket['no_tiket']}: " + ", ".join(f"{r['label']} {r['lama']} → {r['baru']}" for r in rincian)
    return persetujuan.ajukan("KOREKSI_TIKET", tiket["no_tiket"], judul, alasan, data, user_id)


@persetujuan.pelaksana("KOREKSI_TIKET")
def _jalankan(data, id_pengaju, id_penyetuju):
    """Diubah hanya bila data tiket masih sama seperti saat diajukan (tidak menimpa perubahan lain)."""
    ubah, lama = data["ubah"], data["lama"]
    kolom = [k for k in KOLOM if k in ubah]
    nama_db = {"id_supplier": "SupplierID", "id_produk": "ProductID", "id_driver": "DriverID", "id_kendaraan": "IDVehicle"}
    set_sql = ", ".join(f"{nama_db[k]} = ?" for k in kolom)
    cek_sql = " AND ".join(f"{nama_db[k]} = ?" for k in kolom)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE WeightBridge SET {set_sql} WHERE TicketNumber = ? AND StatusCode <> 'VOID' AND {cek_sql}",
                       *[ubah[k] for k in kolom], data["no_tiket"], *[lama[k] for k in kolom])
        if cursor.rowcount == 0:
            raise ValueError("Data tiket sudah berubah atau tiket sudah dibatalkan sejak koreksi diajukan. Silakan tolak pengajuan ini.")
        rincian = {r["label"]: r for r in data.get("_rincian", [])}
        log_aktivitas.catat("DATA", "KOREKSI_TIKET", tabel="WeightBridge", id_baris=data["no_tiket"],
                            lama={k: v["lama"] for k, v in rincian.items()}, baru={k: v["baru"] for k, v in rincian.items()},
                            user_id=id_penyetuju, cursor=cursor)
        conn.commit()
    finally:
        conn.close()
