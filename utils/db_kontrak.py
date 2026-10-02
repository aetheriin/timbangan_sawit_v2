"""Kontrak & DO (menu Kontrak & DO, diisi HO). Security cukup mengetik No DO di Form,
jenis transaksi / customer / produk / pengangkutan diambil dari sini (tidak bisa dipilih security)."""
from utils.db_utils import get_connection, _rows_to_dicts

JENIS_VALID = ("PEMBELIAN", "PENJUALAN", "PENIMBANGAN_SAJA")

_SELECT = """SELECT d.id_do, d.no_do, d.no_kontrak, d.jenis_transaksi, d.id_customer, c.nama_supplier AS nama_customer,
                    d.id_produk, p.nama_produk, d.id_pengangkutan, a.nama_supplier AS nama_pengangkutan,
                    d.tanggal_do, d.berlaku_sampai, d.keterangan, d.is_active, d.created_at
             FROM delivery_order d
             JOIN supplier c ON c.id_supplier = d.id_customer
             JOIN produk p ON p.id_produk = d.id_produk
             LEFT JOIN supplier a ON a.id_supplier = d.id_pengangkutan"""


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        if cursor.rowcount == 0:
            raise ValueError("DO tidak ditemukan")
        conn.commit()
    finally:
        conn.close()


def daftar_do(cari="", batas=500):
    cari = f"%{cari.strip()}%"
    return _query(f"""{_SELECT.replace('SELECT', f'SELECT TOP {int(batas)}', 1)}
                      WHERE d.no_do LIKE ? OR d.no_kontrak LIKE ? OR c.nama_supplier LIKE ?
                      ORDER BY d.is_active DESC, d.created_at DESC""", cari, cari, cari)


def get_do(no_do):
    """DO aktif & masih berlaku (dipakai Form Security). None bila tidak ada."""
    rows = _query(f"""{_SELECT} WHERE d.no_do = ? AND d.is_active = 1
                      AND (d.berlaku_sampai IS NULL OR d.berlaku_sampai >= CAST(GETDATE() AS DATE))""", no_do)
    return rows[0] if rows else None


def kontrak_terakhir(no_kontrak):
    """Isian DO sebelumnya dengan No Kontrak sama (mengisi otomatis form DO baru)."""
    rows = _query(f"{_SELECT.replace('SELECT', 'SELECT TOP 1', 1)} WHERE d.no_kontrak = ? ORDER BY d.created_at DESC", no_kontrak)
    return rows[0] if rows else None


def no_do_dipakai(no_do, kecuali=None):
    return any(r["id_do"] != kecuali for r in _query("SELECT id_do FROM delivery_order WHERE no_do = ?", no_do))


def simpan_do(id_do, d, user_id):
    kolom = (d["no_do"], d["no_kontrak"], d["jenis_transaksi"], d["id_customer"], d["id_produk"],
             d["id_pengangkutan"], d["tanggal_do"], d["berlaku_sampai"], d["keterangan"])
    if id_do:
        _ubah("""UPDATE delivery_order SET no_do = ?, no_kontrak = ?, jenis_transaksi = ?, id_customer = ?, id_produk = ?,
                 id_pengangkutan = ?, tanggal_do = ?, berlaku_sampai = ?, keterangan = ? WHERE id_do = ?""", *kolom, id_do)
    else:
        _ubah("""INSERT INTO delivery_order (no_do, no_kontrak, jenis_transaksi, id_customer, id_produk, id_pengangkutan,
                 tanggal_do, berlaku_sampai, keterangan, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", *kolom, user_id)


def set_aktif_do(id_do, aktif):
    _ubah("UPDATE delivery_order SET is_active = ? WHERE id_do = ?", 1 if aktif else 0, id_do)


def daftar_mitra():
    """Customer & pengangkutan aktif untuk pilihan form DO."""
    return _query("SELECT id_supplier, nama_supplier, tipe FROM supplier WHERE is_active = 1 ORDER BY nama_supplier")
