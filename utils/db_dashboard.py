"""Dashboard: harga CPO, harga kernel, OER CPO, biaya olah per tanggal (diisi HO)."""
from utils.db_utils import get_connection, _rows_to_dicts

KOLOM = ("harga_cpo", "harga_kernel", "oer_cpo", "biaya_olah")


def riwayat_harga(hari=30):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT h.tanggal, h.harga_cpo, h.harga_kernel, h.oer_cpo, h.biaya_olah, u.nama AS oleh, h.updated_at
                          FROM harga_harian h LEFT JOIN akun u ON u.id_user = h.updated_by
                          WHERE h.tanggal >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
                          ORDER BY h.tanggal""", -(int(hari) - 1))
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def simpan_harga(tanggal, nilai, user_id):
    """Satu baris per tanggal: tanggal yang sudah ada diperbarui."""
    conn = get_connection()
    try:
        conn.cursor().execute("""
            MERGE harga_harian AS t USING (SELECT ? AS tanggal) AS s ON t.tanggal = s.tanggal
            WHEN MATCHED THEN UPDATE SET harga_cpo = ?, harga_kernel = ?, oer_cpo = ?, biaya_olah = ?,
                                         updated_by = ?, updated_at = GETDATE()
            WHEN NOT MATCHED THEN INSERT (tanggal, harga_cpo, harga_kernel, oer_cpo, biaya_olah, updated_by)
                                  VALUES (?, ?, ?, ?, ?, ?);""",
            tanggal, *nilai, user_id, tanggal, *nilai, user_id)
        conn.commit()
    finally:
        conn.close()


def arus_hari_ini(id_area=None):
    """Ringkasan penimbangan hari ini (area user, None = semua area): angka, distribusi per produk, 5 tiket terakhir."""
    from utils.db_utils import _filter_area
    filter_area, param_area = _filter_area(id_area)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        dasar = f"""
            FROM transaksi t
            JOIN produk p ON p.id_produk = t.id_produk
            LEFT JOIN v_timbangan tb ON tb.no_tiket = t.no_tiket
            OUTER APPLY (SELECT MAX(pn.waktu) AS keluar FROM penimbangan pn WHERE pn.no_tiket = t.no_tiket) w
            WHERE t.created_at >= CAST(GETDATE() AS DATE) AND t.status_alur <> 'VOID'{filter_area}"""
        cursor.execute(f"""SELECT COUNT(*) AS masuk,
                                  SUM(CASE WHEN t.status_alur = 'SELESAI' THEN 1 ELSE 0 END) AS selesai,
                                  SUM(CASE WHEN p.kategori = 'TBS' AND t.status_alur = 'SELESAI'
                                           THEN COALESCE(tb.berat_netto, t.berat_split_kg) ELSE 0 END) AS tbs_kg,
                                  AVG(CASE WHEN t.status_alur = 'SELESAI' AND w.keluar IS NOT NULL
                                           THEN CAST(DATEDIFF(MINUTE, t.created_at, w.keluar) AS FLOAT) END) AS siklus_menit
                           {dasar}""", *param_area)
        ringkas = _rows_to_dicts(cursor)[0]
        cursor.execute(f"""SELECT p.nama_produk AS produk, SUM(COALESCE(tb.berat_netto, t.berat_split_kg)) AS netto
                           {dasar} AND COALESCE(tb.berat_netto, t.berat_split_kg) IS NOT NULL
                           GROUP BY p.nama_produk ORDER BY netto DESC""", *param_area)
        distribusi = _rows_to_dicts(cursor)
        cursor.execute(f"""SELECT COUNT(*) FROM transaksi t
                           WHERE t.status_alur NOT IN ('SELESAI', 'REJECTED', 'VOID'){filter_area}""", *param_area)
        ringkas["di_dalam"] = cursor.fetchone()[0]
        cursor.execute(f"""
            SELECT TOP 5 t.no_tiket, k.no_plat, p.nama_produk AS produk, s.nama_supplier AS customer, t.status_alur,
                   COALESCE(tb.berat_netto, t.berat_split_kg) AS netto, t.created_at
            FROM transaksi t
            JOIN kendaraan k ON k.id_kendaraan = t.id_kendaraan
            JOIN produk p ON p.id_produk = t.id_produk
            JOIN mitra s ON s.id_supplier = t.id_supplier
            LEFT JOIN v_timbangan tb ON tb.no_tiket = t.no_tiket
            WHERE t.status_alur <> 'VOID'{filter_area}
            ORDER BY t.created_at DESC""", *param_area)
        terkini = _rows_to_dicts(cursor)
        return ringkas, distribusi, terkini
    finally:
        conn.close()
