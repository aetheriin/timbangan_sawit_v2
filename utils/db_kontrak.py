"""Kontrak & DO (menu Kontrak & DO, diisi HO). 1 kontrak = 1 produk = 1 DO; 1 DO boleh beberapa pengangkut
(do_pengangkutan: kendaraan PENGIRIM / PENERIMA sendiri, atau PIHAK_KETIGA). Security cukup mengetik No DO di Form,
jenis transaksi / customer / produk terisi dan pengangkutan dipilih dari daftar DO itu (migrasi 013)."""
from utils.db_utils import get_connection, _rows_to_dicts, get_semua_supplier

JENIS_VALID = ("PEMBELIAN", "PENJUALAN", "PENIMBANGAN_SAJA")
CARA_ANGKUT = ("PENGIRIM", "PENERIMA", "PIHAK_KETIGA")

_SELECT = """SELECT o.DeliveryOrderID AS id_do, o.DONumber AS no_do, o.ContractID AS id_kontrak, k.ContractNumber AS no_kontrak, k.TransactionType AS jenis_transaksi, k.SupplierID AS id_customer,
                    c.SupplierName AS nama_customer, k.ProductID AS id_produk, p.ProductName AS nama_produk, k.ContractDate AS tanggal_kontrak,
                    k.ContractQty AS qty_kg, k.Price AS harga_per_kg, k.Description AS keterangan, k.PPN AS ppn, k.IncludePPN AS harga_termasuk_ppn, k.CompID AS id_company,
                    co.CompID AS kode_company, o.DODate AS tanggal_do, o.ExpiredDate AS berlaku_sampai, o.Active AS is_active, o.CreateDate AS created_at,
                    -- realisasi: total netto tiket DO ini (tanpa VOID)
                    (SELECT SUM(COALESCE(tb.Netto, t.SplitWeight)) FROM WeightBridge t
                     LEFT JOIN WeighingSummary tb ON tb.TicketNumber = t.TicketNumber
                     WHERE t.DeliveryOrderID = o.DeliveryOrderID AND t.StatusCode <> 'VOID') AS realisasi_kg
             FROM DeliveryOrder o
             JOIN Contract k ON k.ContractID = o.ContractID
             JOIN Supplier c ON c.SupplierID = k.SupplierID
             JOIN Product p ON p.ProductID = k.ProductID
             LEFT JOIN Company co ON co.CompID = k.CompID"""


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def label_angkut(cara, jenis, nama_customer, nama_pengangkutan=None):
    """Teks pilihan pengangkutan. Pembelian: pengirim = customer; penjualan: penerima = customer."""
    if cara == "PIHAK_KETIGA":
        return f"{nama_pengangkutan} (pihak ketiga)"
    pihak_customer = (cara == "PENGIRIM") == (jenis != "PENJUALAN")
    return f"Kendaraan {nama_customer if pihak_customer else 'PT sendiri'} ({cara.lower()})"


def _lengkapi_angkut(daftar):
    """Tambahkan daftar pengangkutan (do_pengangkutan) ke setiap DO."""
    if not daftar:
        return daftar
    per_do = {d["id_do"]: d for d in daftar}
    for d in daftar:
        d["angkutan"] = []
    ids = list(per_do)
    for i in range(0, len(ids), 1000):
        bagian = ids[i:i + 1000]
        rows = _query(f"""SELECT a.DeliveryOrderID AS id_do, a.TransportMode AS cara_angkut, a.TransportID AS id_pengangkutan, s.SupplierName AS nama_pengangkutan, a.DOQty AS qty_kg,
                                 a.PriceTransport AS ongkos_per_kg
                          FROM DOTransport a LEFT JOIN Supplier s ON s.SupplierID = a.TransportID
                          WHERE a.DeliveryOrderID IN ({','.join('?' * len(bagian))}) ORDER BY a.DOTransportID""", *bagian)
        for r in rows:
            d = per_do[r["id_do"]]
            d["angkutan"].append({**r, "label": label_angkut(r["cara_angkut"], d["jenis_transaksi"], d["nama_customer"],
                                                             r["nama_pengangkutan"])})
    return daftar


def daftar_do(cari="", batas=500):
    cari = f"%{cari.strip()}%"
    return _lengkapi_angkut(_query(f"""{_SELECT.replace('SELECT', f'SELECT TOP {int(batas)}', 1)}
                      WHERE o.DONumber LIKE ? OR k.ContractNumber LIKE ? OR c.SupplierName LIKE ?
                      ORDER BY o.Active DESC, o.CreateDate DESC""", cari, cari, cari))


def get_do(no_do):
    """DO aktif & masih berlaku (dipakai Form Security), lengkap dengan daftar pengangkutan. None bila tidak ada."""
    rows = _query(f"""{_SELECT} WHERE o.DONumber = ? AND o.Active = 1 AND k.Active = 1
                      AND (o.ExpiredDate IS NULL OR o.ExpiredDate >= CAST(GETDATE() AS DATE))""", no_do)
    return _lengkapi_angkut(rows)[0] if rows else None


def no_do_dipakai(no_do, kecuali=None):
    return any(r["id_do"] != kecuali for r in _query("SELECT DeliveryOrderID AS id_do FROM DeliveryOrder WHERE DONumber = ?", no_do))


def no_kontrak_dipakai(no_kontrak, kecuali_do=None):
    rows = _query("""SELECT o.DeliveryOrderID AS id_do FROM Contract k LEFT JOIN DeliveryOrder o ON o.ContractID = k.ContractID
                     WHERE k.ContractNumber = ?""", no_kontrak)
    return any(r["id_do"] is None or r["id_do"] != kecuali_do for r in rows)


def simpan_do(id_do, d, angkutan, user_id):
    """Kontrak + DO + daftar pengangkutan dalam satu transaksi DB.
    angkutan: [{"cara_angkut", "id_pengangkutan", "qty_kg"}] (minimal satu, tanpa duplikat)."""
    kontrak = (d["no_kontrak"], d["jenis_transaksi"], d["id_customer"], d["id_produk"], d["tanggal_kontrak"],
               d["qty_kg"], d["harga_per_kg"], d["keterangan"], int(d["ppn"]), int(d["harga_termasuk_ppn"]), d["id_company"])
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_do:
            cursor.execute("SELECT ContractID AS id_kontrak FROM DeliveryOrder WHERE DeliveryOrderID = ?", id_do)
            row = cursor.fetchone()
            if row is None:
                raise ValueError("DO tidak ditemukan")
            cursor.execute("""UPDATE Contract SET ContractNumber = ?, TransactionType = ?, SupplierID = ?, ProductID = ?,
                              ContractDate = ?, ContractQty = ?, Price = ?, Description = ?, PPN = ?, IncludePPN = ?,
                              CompID = ? WHERE ContractID = ?""",
                           *kontrak, row.id_kontrak)
            cursor.execute("UPDATE DeliveryOrder SET DONumber = ?, DODate = ?, ExpiredDate = ? WHERE DeliveryOrderID = ?",
                           d["no_do"], d["tanggal_do"], d["berlaku_sampai"], id_do)
            cursor.execute("DELETE FROM DOTransport WHERE DeliveryOrderID = ?", id_do)
        else:
            cursor.execute("""SET NOCOUNT ON; INSERT INTO Contract (ContractNumber, TransactionType, SupplierID, ProductID, ContractDate,
                              ContractQty, Price, Description, PPN, IncludePPN, CompID, CreateBy)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?); SELECT CAST(SCOPE_IDENTITY() AS INT)""", *kontrak, user_id)
            id_kontrak = cursor.fetchone()[0]
            cursor.execute("""SET NOCOUNT ON; INSERT INTO DeliveryOrder (DONumber, ContractID, DODate, ExpiredDate, CreateBy)
                              VALUES (?, ?, ?, ?, ?); SELECT CAST(SCOPE_IDENTITY() AS INT)""",
                           d["no_do"], id_kontrak, d["tanggal_do"], d["berlaku_sampai"], user_id)
            id_do = cursor.fetchone()[0]
        for a in angkutan:
            cursor.execute("""INSERT INTO DOTransport (DeliveryOrderID, TransportMode, TransportID, DOQty, PriceTransport)
                              VALUES (?, ?, ?, ?, ?)""", id_do, a["cara_angkut"], a["id_pengangkutan"], a["qty_kg"],
                           a.get("ongkos_per_kg"))
        conn.commit()
    finally:
        conn.close()


def set_aktif_do(id_do, aktif):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE DeliveryOrder SET Active = ? WHERE DeliveryOrderID = ?", 1 if aktif else 0, id_do)
        if cursor.rowcount == 0:
            raise ValueError("DO tidak ditemukan")
        cursor.execute("""UPDATE k SET k.Active = ? FROM Contract k JOIN DeliveryOrder o ON o.ContractID = k.ContractID
                          WHERE o.DeliveryOrderID = ?""", 1 if aktif else 0, id_do)
        conn.commit()
    finally:
        conn.close()


def daftar_mitra():
    """Customer & pengangkutan aktif untuk pilihan form DO (satu mitra boleh dua peran)."""
    return _query("""SELECT s.SupplierID AS id_supplier, s.SupplierName AS nama_supplier, p.TypeCode AS peran FROM Supplier s
                     JOIN SupplierTypeDetails p ON p.SupplierID = s.SupplierID
                     WHERE s.Active = 1 ORDER BY s.SupplierName""")


def id_pengangkutan_dari_nama(nama):
    """Pengangkutan pihak ketiga: pakai mitra yang namanya sama (ditambah peran PENGANGKUTAN bila belum),
    atau buat baru (kode ANG-001 dst)."""
    nama = " ".join(nama.split())[:100]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SupplierID AS id_supplier FROM Supplier WHERE LOWER(SupplierName) = LOWER(?)", nama)
        row = cursor.fetchone()
        if row:
            id_mitra = row.id_supplier
        else:
            cursor.execute("SELECT COUNT(*) FROM Supplier WHERE SupplierCode LIKE 'ANG-%'")
            kode = f"ANG-{cursor.fetchone()[0] + 1:03d}"
            cursor.execute("""SET NOCOUNT ON; INSERT INTO Supplier (SupplierCode, SupplierName) VALUES (?, ?);
                              SELECT CAST(SCOPE_IDENTITY() AS INT)""", kode, nama)
            id_mitra = cursor.fetchone()[0]
        cursor.execute("""IF NOT EXISTS (SELECT 1 FROM SupplierTypeDetails WHERE SupplierID = ? AND TypeCode = 'PENGANGKUTAN')
                          INSERT INTO SupplierTypeDetails (SupplierID, TypeCode) VALUES (?, 'PENGANGKUTAN')""", id_mitra, id_mitra)
        conn.commit()
    finally:
        conn.close()
    get_semua_supplier.hapus()
    return id_mitra
