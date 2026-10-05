"""Kontrak & DO (menu Kontrak & DO, diisi HO). 1 kontrak = 1 produk = 1 DO; 1 DO boleh beberapa pengangkut
(do_pengangkutan: kendaraan PENGIRIM / PENERIMA sendiri, atau PIHAK_KETIGA). Security cukup mengetik No DO di Form,
jenis transaksi / customer / produk terisi dan pengangkutan dipilih dari daftar DO itu (migrasi 013)."""
from utils.db_utils import get_connection, _rows_to_dicts, get_semua_supplier

JENIS_VALID = ("PEMBELIAN", "PENJUALAN", "PENIMBANGAN_SAJA")
CARA_ANGKUT = ("PENGIRIM", "PENERIMA", "PIHAK_KETIGA")

_SELECT = """SELECT o.id_do, o.no_do, o.id_kontrak, k.no_kontrak, k.jenis_transaksi, k.id_customer,
                    c.nama_supplier AS nama_customer, k.id_produk, p.nama_produk, k.tanggal AS tanggal_kontrak,
                    k.qty_kg, k.harga_per_kg, k.keterangan, o.tanggal_do, o.berlaku_sampai, o.is_active, o.created_at
             FROM delivery_order o
             JOIN kontrak k ON k.id_kontrak = o.id_kontrak
             JOIN supplier c ON c.id_supplier = k.id_customer
             JOIN produk p ON p.id_produk = k.id_produk"""


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
        rows = _query(f"""SELECT a.id_do, a.cara_angkut, a.id_pengangkutan, s.nama_supplier AS nama_pengangkutan, a.qty_kg
                          FROM do_pengangkutan a LEFT JOIN supplier s ON s.id_supplier = a.id_pengangkutan
                          WHERE a.id_do IN ({','.join('?' * len(bagian))}) ORDER BY a.id_do_angkut""", *bagian)
        for r in rows:
            d = per_do[r["id_do"]]
            d["angkutan"].append({**r, "label": label_angkut(r["cara_angkut"], d["jenis_transaksi"], d["nama_customer"],
                                                             r["nama_pengangkutan"])})
    return daftar


def daftar_do(cari="", batas=500):
    cari = f"%{cari.strip()}%"
    return _lengkapi_angkut(_query(f"""{_SELECT.replace('SELECT', f'SELECT TOP {int(batas)}', 1)}
                      WHERE o.no_do LIKE ? OR k.no_kontrak LIKE ? OR c.nama_supplier LIKE ?
                      ORDER BY o.is_active DESC, o.created_at DESC""", cari, cari, cari))


def get_do(no_do):
    """DO aktif & masih berlaku (dipakai Form Security), lengkap dengan daftar pengangkutan. None bila tidak ada."""
    rows = _query(f"""{_SELECT} WHERE o.no_do = ? AND o.is_active = 1 AND k.is_active = 1
                      AND (o.berlaku_sampai IS NULL OR o.berlaku_sampai >= CAST(GETDATE() AS DATE))""", no_do)
    return _lengkapi_angkut(rows)[0] if rows else None


def no_do_dipakai(no_do, kecuali=None):
    return any(r["id_do"] != kecuali for r in _query("SELECT id_do FROM delivery_order WHERE no_do = ?", no_do))


def no_kontrak_dipakai(no_kontrak, kecuali_do=None):
    rows = _query("""SELECT o.id_do FROM kontrak k LEFT JOIN delivery_order o ON o.id_kontrak = k.id_kontrak
                     WHERE k.no_kontrak = ?""", no_kontrak)
    return any(r["id_do"] is None or r["id_do"] != kecuali_do for r in rows)


def simpan_do(id_do, d, angkutan, user_id):
    """Kontrak + DO + daftar pengangkutan dalam satu transaksi DB.
    angkutan: [{"cara_angkut", "id_pengangkutan", "qty_kg"}] (minimal satu, tanpa duplikat)."""
    kontrak = (d["no_kontrak"], d["jenis_transaksi"], d["id_customer"], d["id_produk"], d["tanggal_kontrak"],
               d["qty_kg"], d["harga_per_kg"], d["keterangan"])
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_do:
            cursor.execute("SELECT id_kontrak FROM delivery_order WHERE id_do = ?", id_do)
            row = cursor.fetchone()
            if row is None:
                raise ValueError("DO tidak ditemukan")
            cursor.execute("""UPDATE kontrak SET no_kontrak = ?, jenis_transaksi = ?, id_customer = ?, id_produk = ?,
                              tanggal = ?, qty_kg = ?, harga_per_kg = ?, keterangan = ? WHERE id_kontrak = ?""",
                           *kontrak, row.id_kontrak)
            cursor.execute("UPDATE delivery_order SET no_do = ?, tanggal_do = ?, berlaku_sampai = ? WHERE id_do = ?",
                           d["no_do"], d["tanggal_do"], d["berlaku_sampai"], id_do)
            cursor.execute("DELETE FROM do_pengangkutan WHERE id_do = ?", id_do)
        else:
            cursor.execute("""INSERT INTO kontrak (no_kontrak, jenis_transaksi, id_customer, id_produk, tanggal, qty_kg,
                              harga_per_kg, keterangan, created_by) OUTPUT INSERTED.id_kontrak
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", *kontrak, user_id)
            id_kontrak = cursor.fetchone()[0]
            cursor.execute("""INSERT INTO delivery_order (no_do, id_kontrak, tanggal_do, berlaku_sampai, created_by)
                              OUTPUT INSERTED.id_do VALUES (?, ?, ?, ?, ?)""",
                           d["no_do"], id_kontrak, d["tanggal_do"], d["berlaku_sampai"], user_id)
            id_do = cursor.fetchone()[0]
        for a in angkutan:
            cursor.execute("INSERT INTO do_pengangkutan (id_do, cara_angkut, id_pengangkutan, qty_kg) VALUES (?, ?, ?, ?)",
                           id_do, a["cara_angkut"], a["id_pengangkutan"], a["qty_kg"])
        conn.commit()
    finally:
        conn.close()


def set_aktif_do(id_do, aktif):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE delivery_order SET is_active = ? WHERE id_do = ?", 1 if aktif else 0, id_do)
        if cursor.rowcount == 0:
            raise ValueError("DO tidak ditemukan")
        cursor.execute("""UPDATE k SET k.is_active = ? FROM kontrak k JOIN delivery_order o ON o.id_kontrak = k.id_kontrak
                          WHERE o.id_do = ?""", 1 if aktif else 0, id_do)
        conn.commit()
    finally:
        conn.close()


def daftar_mitra():
    """Customer & pengangkutan aktif untuk pilihan form DO (satu mitra boleh dua peran)."""
    return _query("""SELECT s.id_supplier, s.nama_supplier, p.peran FROM supplier s
                     JOIN supplier_peran p ON p.id_supplier = s.id_supplier
                     WHERE s.is_active = 1 ORDER BY s.nama_supplier""")


def id_pengangkutan_dari_nama(nama):
    """Pengangkutan pihak ketiga: pakai mitra yang namanya sama (ditambah peran PENGANGKUTAN bila belum),
    atau buat baru (kode ANG-001 dst)."""
    nama = " ".join(nama.split())[:100]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id_supplier FROM supplier WHERE LOWER(nama_supplier) = LOWER(?)", nama)
        row = cursor.fetchone()
        if row:
            id_mitra = row.id_supplier
        else:
            cursor.execute("SELECT COUNT(*) FROM supplier WHERE kode_supplier LIKE 'ANG-%'")
            kode = f"ANG-{cursor.fetchone()[0] + 1:03d}"
            cursor.execute("INSERT INTO supplier (kode_supplier, nama_supplier) OUTPUT INSERTED.id_supplier VALUES (?, ?)",
                           kode, nama)
            id_mitra = cursor.fetchone()[0]
        cursor.execute("""IF NOT EXISTS (SELECT 1 FROM supplier_peran WHERE id_supplier = ? AND peran = 'PENGANGKUTAN')
                          INSERT INTO supplier_peran (id_supplier, peran) VALUES (?, 'PENGANGKUTAN')""", id_mitra, id_mitra)
        conn.commit()
    finally:
        conn.close()
    get_semua_supplier.hapus()
    return id_mitra
