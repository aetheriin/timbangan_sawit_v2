"""Pencarian global (header › Cari / Ctrl+K): tiket, DO / kontrak, personel, kendaraan; admin: akun."""
from utils.db_utils import get_connection, _rows_to_dicts, _filter_area


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def _pola(kata):
    """'bk 8492' cocok dengan 'BK 8492 XA'; % dan _ dari user tidak dianggap wildcard."""
    aman = kata.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")
    return f"%{aman}%"


def cari_tiket(kata, id_area=None, batas=8):
    filter_area, param_area = _filter_area(id_area)
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} t.no_tiket, k.no_plat, t.no_do, t.status_alur, t.created_at,
               s.nama_supplier AS customer, p.nama_produk AS produk, d.nama_personel AS supir,
               COALESCE(tb.berat_netto, t.berat_split_kg) AS netto
        FROM transaksi t
        JOIN kendaraan k ON k.id_kendaraan = t.id_kendaraan
        JOIN mitra s ON s.id_supplier = t.id_supplier
        JOIN produk p ON p.id_produk = t.id_produk
        JOIN personel d ON d.id_personel = t.id_driver
        LEFT JOIN v_timbangan tb ON tb.no_tiket = t.no_tiket
        WHERE (t.no_tiket LIKE ? OR REPLACE(k.no_plat, ' ', '') LIKE REPLACE(?, ' ', '') OR t.no_do LIKE ?
               OR d.nama_personel LIKE ? OR s.nama_supplier LIKE ?){filter_area}
        ORDER BY t.created_at DESC""", pola, pola, pola, pola, pola, *param_area)


def cari_do(kata, batas=5):
    """DO / kontrak: no. DO, no. kontrak, atau nama customer. Realisasi = total netto tiket DO (tanpa VOID)."""
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} o.no_do, k.no_kontrak, c.nama_supplier AS customer, p.nama_produk AS produk,
               k.qty_kg, o.is_active, o.berlaku_sampai,
               (SELECT SUM(COALESCE(tb.berat_netto, t.berat_split_kg)) FROM transaksi t
                LEFT JOIN v_timbangan tb ON tb.no_tiket = t.no_tiket
                WHERE t.id_do = o.id_do AND t.status_alur <> 'VOID') AS realisasi_kg
        FROM delivery_order o
        JOIN kontrak k ON k.id_kontrak = o.id_kontrak
        JOIN mitra c ON c.id_supplier = k.id_customer
        JOIN produk p ON p.id_produk = k.id_produk
        WHERE o.no_do LIKE ? OR k.no_kontrak LIKE ? OR c.nama_supplier LIKE ?
        ORDER BY o.is_active DESC, o.created_at DESC""", pola, pola, pola)


def cari_personel(kata, batas=5):
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} id_personel, kode_personel, nama_personel, nik, kategori, is_blacklisted
        FROM personel
        WHERE is_active = 1 AND (nama_personel LIKE ? OR nik LIKE ? OR kode_personel LIKE ?)
        ORDER BY nama_personel""", pola, pola, pola)


def cari_kendaraan(kata, batas=5):
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} id_kendaraan, no_plat, no_stnk, is_blacklisted
        FROM kendaraan
        WHERE is_active = 1 AND (REPLACE(no_plat, ' ', '') LIKE REPLACE(?, ' ', '') OR no_stnk LIKE ?)
        ORDER BY no_plat""", pola, pola)


def cari_akun(kata, batas=8):
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} u.UserID AS id_user, u.Nama AS nama, u.UserName AS username, u.Active AS is_active, l.LevelDetName AS nama_level, a.AreaName AS area
        FROM Users u JOIN LevelDetails l ON l.LevelDetID = u.UserLevelID JOIN CompanyArea a ON a.CompAreaID = u.CompAreaID
        WHERE u.Nama LIKE ? OR u.UserName LIKE ?
        ORDER BY u.Active DESC, u.Nama""", pola, pola)
