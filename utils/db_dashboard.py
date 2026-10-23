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
            FROM WeightBridge t
            JOIN Product p ON p.ProductID = t.ProductID
            LEFT JOIN WeighingSummary tb ON tb.TicketNumber = t.TicketNumber
            OUTER APPLY (SELECT MAX(pn.WeighDate) AS keluar FROM Weighing pn WHERE pn.TicketNumber = t.TicketNumber) w
            WHERE t.TicketDate >= CAST(GETDATE() AS DATE) AND t.StatusCode <> 'VOID'{filter_area}"""
        cursor.execute(f"""SELECT COUNT(*) AS masuk,
                                  SUM(CASE WHEN t.StatusCode = 'SELESAI' THEN 1 ELSE 0 END) AS selesai,
                                  SUM(CASE WHEN p.Category = 'TBS' AND t.StatusCode = 'SELESAI'
                                           THEN COALESCE(tb.Netto, t.SplitWeight) ELSE 0 END) AS tbs_kg,
                                  AVG(CASE WHEN t.StatusCode = 'SELESAI' AND w.keluar IS NOT NULL
                                           THEN CAST(DATEDIFF(MINUTE, t.TicketDate, w.keluar) AS FLOAT) END) AS siklus_menit
                           {dasar}""", *param_area)
        ringkas = _rows_to_dicts(cursor)[0]
        cursor.execute(f"""SELECT p.ProductName AS produk, SUM(COALESCE(tb.Netto, t.SplitWeight)) AS netto
                           {dasar} AND COALESCE(tb.Netto, t.SplitWeight) IS NOT NULL
                           GROUP BY p.ProductName ORDER BY netto DESC""", *param_area)
        distribusi = _rows_to_dicts(cursor)

        # Per jam: masuk = jam tiket dibuat; selesai = jam timbang terakhir tiket yang sudah SELESAI
        per_jam = [{"jam": j, "masuk": 0, "selesai": 0} for j in range(24)]
        cursor.execute(f"SELECT DATEPART(HOUR, t.TicketDate) AS jam, COUNT(*) AS n {dasar} GROUP BY DATEPART(HOUR, t.TicketDate)",
                       *param_area)
        for jam, n in cursor.fetchall():
            per_jam[jam]["masuk"] = n
        cursor.execute(f"""SELECT DATEPART(HOUR, w.keluar) AS jam, COUNT(*) AS n {dasar}
                           AND t.StatusCode = 'SELESAI' AND w.keluar IS NOT NULL GROUP BY DATEPART(HOUR, w.keluar)""",
                       *param_area)
        for jam, n in cursor.fetchall():
            per_jam[jam]["selesai"] = n

        # Posisi truk yang masih di dalam (semua tiket aktif, tidak hanya yang dibuat hari ini).
        # Setelah timbang 1: TBS ke Sortasi, produk lain ke Laboratorium.
        cursor.execute(f"""SELECT
                SUM(CASE WHEN t.StatusCode = 'SECURITY_REGISTER' AND ISNULL(a.FlowCode, '') <> 'POS_SAJA' THEN 1 ELSE 0 END) AS timbang_1,
                SUM(CASE WHEN t.StatusCode = 'TIMBANG_1' AND p.Category = 'TBS' THEN 1 ELSE 0 END) AS sortasi,
                SUM(CASE WHEN t.StatusCode = 'TIMBANG_1' AND p.Category <> 'TBS' THEN 1 ELSE 0 END) AS lab,
                SUM(CASE WHEN t.StatusCode = 'TIMBANG_2' THEN 1 ELSE 0 END) AS timbang_2,
                COUNT(*) AS di_dalam
            FROM WeightBridge t JOIN Product p ON p.ProductID = t.ProductID
            LEFT JOIN Flow a ON a.FlowID = t.FlowID
            WHERE t.StatusCode NOT IN ('SELESAI', 'REJECTED', 'VOID'){filter_area}""", *param_area)
        posisi = {k: int(v or 0) for k, v in _rows_to_dicts(cursor)[0].items()}
        ringkas["di_dalam"] = posisi.pop("di_dalam")
        return ringkas, distribusi, per_jam, posisi
    finally:
        conn.close()
