"""Dashboard: harga CPO, harga kernel, OER CPO, biaya olah per tanggal (diisi HO)."""
from utils.db_utils import get_connection, _rows_to_dicts

KOLOM = ("harga_cpo", "harga_kernel", "oer_cpo", "biaya_olah")


def riwayat_harga(hari=30):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT h.PriceDate AS tanggal, h.CPOPrice AS harga_cpo, h.KernelPrice AS harga_kernel, h.OERCPO AS oer_cpo, h.ProcessingCost AS biaya_olah, u.Nama AS oleh, h.UpdateDate AS updated_at
                          FROM DailyPrice h LEFT JOIN Users u ON u.UserID = h.UpdateBy
                          WHERE h.PriceDate >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
                          ORDER BY h.PriceDate""", -(int(hari) - 1))
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def simpan_harga(tanggal, nilai, user_id):
    """Satu baris per tanggal: tanggal yang sudah ada diperbarui."""
    conn = get_connection()
    try:
        conn.cursor().execute("""
            MERGE DailyPrice AS t USING (SELECT ? AS PriceDate) AS s ON t.PriceDate = s.PriceDate
            WHEN MATCHED THEN UPDATE SET CPOPrice = ?, KernelPrice = ?, OERCPO = ?, ProcessingCost = ?,
                                         UpdateBy = ?, UpdateDate = GETDATE()
            WHEN NOT MATCHED THEN INSERT (PriceDate, CPOPrice, KernelPrice, OERCPO, ProcessingCost, UpdateBy)
                                  VALUES (?, ?, ?, ?, ?, ?);""",
            tanggal, *nilai, user_id, tanggal, *nilai, user_id)
        conn.commit()
    finally:
        conn.close()


def arus_hari_ini(id_area=None):
    """Ringkasan penimbangan hari ini (id_area None = semua area): angka, distribusi per produk,
    jumlah truk masuk / selesai per jam, dan posisi truk yang masih di dalam per tahap."""
    from utils.db_utils import _filter_area
    filter_area, param_area = _filter_area(id_area)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        dasar = f"""
            FROM transaksi t
            JOIN Product p ON p.ProductID = t.id_produk
            LEFT JOIN v_timbangan tb ON tb.no_tiket = t.no_tiket
            OUTER APPLY (SELECT MAX(pn.waktu) AS keluar FROM penimbangan pn WHERE pn.no_tiket = t.no_tiket) w
            WHERE t.created_at >= CAST(GETDATE() AS DATE) AND t.status_alur <> 'VOID'{filter_area}"""
        cursor.execute(f"""SELECT COUNT(*) AS masuk,
                                  SUM(CASE WHEN t.status_alur = 'SELESAI' THEN 1 ELSE 0 END) AS selesai,
                                  SUM(CASE WHEN p.Category = 'TBS' AND t.status_alur = 'SELESAI'
                                           THEN COALESCE(tb.berat_netto, t.berat_split_kg) ELSE 0 END) AS tbs_kg,
                                  AVG(CASE WHEN t.status_alur = 'SELESAI' AND w.keluar IS NOT NULL
                                           THEN CAST(DATEDIFF(MINUTE, t.created_at, w.keluar) AS FLOAT) END) AS siklus_menit
                           {dasar}""", *param_area)
        ringkas = _rows_to_dicts(cursor)[0]
        cursor.execute(f"""SELECT p.ProductName AS produk, SUM(COALESCE(tb.berat_netto, t.berat_split_kg)) AS netto
                           {dasar} AND COALESCE(tb.berat_netto, t.berat_split_kg) IS NOT NULL
                           GROUP BY p.ProductName ORDER BY netto DESC""", *param_area)
        distribusi = _rows_to_dicts(cursor)

        # Per jam: masuk = jam tiket dibuat; selesai = jam timbang terakhir tiket yang sudah SELESAI
        per_jam = [{"jam": j, "masuk": 0, "selesai": 0} for j in range(24)]
        cursor.execute(f"SELECT DATEPART(HOUR, t.created_at) AS jam, COUNT(*) AS n {dasar} GROUP BY DATEPART(HOUR, t.created_at)",
                       *param_area)
        for jam, n in cursor.fetchall():
            per_jam[jam]["masuk"] = n
        cursor.execute(f"""SELECT DATEPART(HOUR, w.keluar) AS jam, COUNT(*) AS n {dasar}
                           AND t.status_alur = 'SELESAI' AND w.keluar IS NOT NULL GROUP BY DATEPART(HOUR, w.keluar)""",
                       *param_area)
        for jam, n in cursor.fetchall():
            per_jam[jam]["selesai"] = n

        # Posisi truk yang masih di dalam (semua tiket aktif, tidak hanya yang dibuat hari ini).
        # Setelah timbang 1: TBS ke Sortasi, produk lain ke Laboratorium.
        cursor.execute(f"""SELECT
                SUM(CASE WHEN t.status_alur = 'SECURITY_REGISTER' AND ISNULL(a.kode, '') <> 'POS_SAJA' THEN 1 ELSE 0 END) AS timbang_1,
                SUM(CASE WHEN t.status_alur = 'TIMBANG_1' AND p.Category = 'TBS' THEN 1 ELSE 0 END) AS sortasi,
                SUM(CASE WHEN t.status_alur = 'TIMBANG_1' AND p.Category <> 'TBS' THEN 1 ELSE 0 END) AS lab,
                SUM(CASE WHEN t.status_alur = 'TIMBANG_2' THEN 1 ELSE 0 END) AS timbang_2,
                COUNT(*) AS di_dalam
            FROM transaksi t JOIN Product p ON p.ProductID = t.id_produk
            LEFT JOIN alur a ON a.id_alur = t.id_alur
            WHERE t.status_alur NOT IN ('SELESAI', 'REJECTED', 'VOID'){filter_area}""", *param_area)
        posisi = {k: int(v or 0) for k, v in _rows_to_dicts(cursor)[0].items()}
        ringkas["di_dalam"] = posisi.pop("di_dalam")
        return ringkas, distribusi, per_jam, posisi
    finally:
        conn.close()
