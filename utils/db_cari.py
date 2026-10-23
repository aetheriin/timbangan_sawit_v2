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
        SELECT TOP {int(batas)} t.no_tiket, k.NoVehicle AS no_plat, t.no_do, t.status_alur, t.created_at,
               s.SupplierName AS customer, p.ProductName AS produk, d.Nama AS supir,
               COALESCE(tb.berat_netto, t.berat_split_kg) AS netto
        FROM transaksi t
        JOIN DetailVehicle k ON k.IDVehicle = t.id_kendaraan
        JOIN Supplier s ON s.SupplierID = t.id_supplier
        JOIN Product p ON p.ProductID = t.id_produk
        JOIN Users d ON d.UserID = t.id_driver
        LEFT JOIN v_timbangan tb ON tb.no_tiket = t.no_tiket
        WHERE (t.no_tiket LIKE ? OR REPLACE(k.NoVehicle, ' ', '') LIKE REPLACE(?, ' ', '') OR t.no_do LIKE ?
               OR d.Nama LIKE ? OR s.SupplierName LIKE ?){filter_area}
        ORDER BY t.created_at DESC""", pola, pola, pola, pola, pola, *param_area)


def cari_do(kata, batas=5):
    """DO / kontrak: no. DO, no. kontrak, atau nama customer. Realisasi = total netto tiket DO (tanpa VOID)."""
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} o.DONumber AS no_do, k.ContractNumber AS no_kontrak, c.SupplierName AS customer, p.ProductName AS produk,
               k.ContractQty AS qty_kg, o.Active AS is_active, o.ExpiredDate AS berlaku_sampai,
               (SELECT SUM(COALESCE(tb.berat_netto, t.berat_split_kg)) FROM transaksi t
                LEFT JOIN v_timbangan tb ON tb.no_tiket = t.no_tiket
                WHERE t.id_do = o.DeliveryOrderID AND t.status_alur <> 'VOID') AS realisasi_kg
        FROM DeliveryOrder o
        JOIN Contract k ON k.ContractID = o.ContractID
        JOIN Supplier c ON c.SupplierID = k.SupplierID
        JOIN Product p ON p.ProductID = k.ProductID
        WHERE o.DONumber LIKE ? OR k.ContractNumber LIKE ? OR c.SupplierName LIKE ?
        ORDER BY o.Active DESC, o.CreateDate DESC""", pola, pola, pola)


def cari_personel(kata, batas=5):
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} UserID AS id_personel, UserCode AS kode_personel, Nama AS nama_personel, NoKTP AS nik, CategoryCode AS kategori, CAST(CASE WHEN BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted
        FROM Users
        WHERE Active = 1 AND (Nama LIKE ? OR NoKTP LIKE ? OR UserCode LIKE ?)
        ORDER BY Nama""", pola, pola, pola)


def cari_kendaraan(kata, batas=5):
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} IDVehicle AS id_kendaraan, NoVehicle AS no_plat, NoSTNK AS no_stnk, CAST(CASE WHEN BlacklistID IS NULL THEN 0 ELSE 1 END AS BIT) AS is_blacklisted
        FROM DetailVehicle
        WHERE Active = 1 AND (REPLACE(NoVehicle, ' ', '') LIKE REPLACE(?, ' ', '') OR NoSTNK LIKE ?)
        ORDER BY NoVehicle""", pola, pola)


def cari_akun(kata, batas=8):
    pola = _pola(kata)
    return _query(f"""
        SELECT TOP {int(batas)} u.UserID AS id_user, u.Nama AS nama, u.UserName AS username, u.Active AS is_active, l.LevelDetName AS nama_level, a.AreaName AS area
        FROM Users u JOIN LevelDetails l ON l.LevelDetID = u.UserLevelID JOIN CompanyArea a ON a.CompAreaID = u.CompAreaID
        WHERE u.Nama LIKE ? OR u.UserName LIKE ?
        ORDER BY u.Active DESC, u.Nama""", pola, pola)
