"""Dashboard: harga CPO, harga kernel, OER CPO, biaya olah, qty RSI per perusahaan per tanggal (diisi HO)."""
from utils.db_utils import get_connection, _rows_to_dicts

KOLOM = ("harga_cpo", "harga_kernel", "oer_cpo", "biaya_olah")

# Katalog widget (yang sudah dibuat di kode: templates/dashboard/widget/<nama>.html + dashboard.js + API datanya).
# Menu.Widgets hanya boleh berisi nama di sini; urutan di Menu.Widgets = urutan tampil.
WIDGET = {
    "harga": "Harga CPO, kernel, OER, biaya olah & TBS",
    "riwayat": "Riwayat harga",
    "arus": "Arus penimbangan & status jembatan timbang hari ini",
    "security": "Truk masuk & di dalam area, tamu, blacklist terdeteksi hari ini",
}
WIDGET_HARGA = {"harga", "riwayat"}       # widget yang memakai tombol Isi Harga (aksi Ubah menu dashboard)


def daftar_dashboard():
    """Menu dashboard (Lv2 di grup Dashboard, Url /dashboard...), termasuk yang nonaktif, untuk Admin › Dashboard."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT m.MenuID AS id_menu, m.MenuCode AS kode, m.MenuName AS nama, m.Url AS url, m.Widgets AS widget,
                                 m.ActionList AS daftar_aksi, m.Active AS is_active,
                                 (SELECT COUNT(DISTINCT a.LevelDetID) FROM AccessMenu a
                                  WHERE a.MenuID = m.MenuID AND a.ActionID = 1 AND a.Active = 1) AS jumlah_peran
                          FROM Menu m JOIN Menu g ON g.MenuID = m.ParentMenuID
                          WHERE g.MenuCode = 'G_DASHBOARD' AND m.MenuLevel = 2
                            AND (m.Url = '/dashboard' OR m.Url LIKE '/dashboard/%')
                          ORDER BY m.SortOrder, m.MenuID""")
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def simpan_dashboard(id_menu, nama, slug, widget, isi_harga):
    """Tambah (id_menu None, Url /dashboard/<slug>, kode DASH_<SLUG>) atau ubah nama / widget / Isi Harga.
    Alamat tidak diubah setelah dibuat (dipakai sebagai halaman awal peran). Kembalikan kode menu."""
    aksi = "3" if isi_harga and WIDGET_HARGA & set(widget) else ""
    daftar = ",".join(widget)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_menu is None:
            kode = "DASH_" + slug.upper().replace("-", "_")
            cursor.execute("SELECT 1 FROM Menu WHERE MenuCode = ? OR Url = ?", kode, f"/dashboard/{slug}")
            if cursor.fetchone():
                raise ValueError("Alamat dashboard ini sudah dipakai")
            cursor.execute("""INSERT INTO Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder, ActionList, Widgets)
                              SELECT ?, ?, g.MenuID, 2, ?, 'fa-chart-line', 'CPOS',
                                     (SELECT ISNULL(MAX(SortOrder), 10) + 1 FROM Menu WHERE ParentMenuID = g.MenuID
                                      AND (Url = '/dashboard' OR Url LIKE '/dashboard/%')), ?, ?
                              FROM Menu g WHERE g.MenuCode = 'G_DASHBOARD'""", kode, nama, f"/dashboard/{slug}", aksi, daftar)
        else:
            cursor.execute("SELECT MenuCode FROM Menu WHERE MenuID = ? AND (Url = '/dashboard' OR Url LIKE '/dashboard/%')", id_menu)
            baris = cursor.fetchone()
            if not baris:
                raise ValueError("Dashboard tidak ditemukan")
            kode = baris[0]
            cursor.execute("UPDATE Menu SET MenuName = ?, Widgets = ?, ActionList = ? WHERE MenuID = ?", nama, daftar, aksi, id_menu)
            if not aksi:       # Isi Harga dimatikan -> hak Ubah yang tersisa di menu ini ikut dicabut
                cursor.execute("DELETE FROM AccessMenu WHERE MenuID = ? AND ActionID = 3", id_menu)
        conn.commit()
        return kode
    finally:
        conn.close()


def set_aktif_dashboard(id_menu, aktif):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""UPDATE Menu SET Active = ? WHERE MenuID = ? AND (Url = '/dashboard' OR Url LIKE '/dashboard/%')""",
                       1 if aktif else 0, id_menu)
        if cursor.rowcount == 0:
            raise ValueError("Dashboard tidak ditemukan")
        conn.commit()
    finally:
        conn.close()


def riwayat_harga(id_user, id_company, hari=30):
    """Data widget harga dari dbo.sp_DashboardHarga (sama dengan aplikasi lain): harga harian + harga TBS per tanggal,
    hanya perusahaan dalam cakupan user."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("EXEC dbo.sp_DashboardHarga @UserID = ?, @CompID = ?, @Days = ?", id_user, id_company, int(hari))
        return _rows_to_dicts(cursor) if cursor.description else []
    finally:
        conn.close()


def ringkas_security(id_area):
    """Dashboard Security: truk masuk hari ini & yang masih di dalam (logbook), tamu di dalam, blacklist terdeteksi hari ini."""
    from datetime import date
    from utils.area_filter import sql_area
    from utils.db_pos import logbook
    lb = logbook(id_area, date.today())
    f_tamu, p_tamu = sql_area("CompAreaID", id_area)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM Guest WHERE CheckOutDate IS NULL{f_tamu}", *p_tamu)
        tamu = cursor.fetchone()[0]
        cursor.execute(f"SELECT COUNT(*) FROM BlacklistDetection WHERE DetectDate >= CAST(GETDATE() AS DATE){f_tamu}", *p_tamu)
        blacklist = cursor.fetchone()[0]
    finally:
        conn.close()
    return {"masuk": lb["masuk_hari_ini"], "di_dalam": len(lb["dalam"]), "keluar": len(lb["keluar"]), "tamu": tamu,
            "blacklist": blacklist, "dalam": lb["dalam"]}


def simpan_harga(id_company, tanggal, nilai, qty_rsi, user_id):
    """Satu baris per perusahaan per tanggal: yang sudah ada diperbarui."""
    conn = get_connection()
    try:
        conn.cursor().execute("""
            MERGE DailyPrice AS t USING (SELECT ? AS CompID, ? AS PriceDate) AS s
                ON t.CompID = s.CompID AND t.PriceDate = s.PriceDate
            WHEN MATCHED THEN UPDATE SET CPOPrice = ?, KernelPrice = ?, OERCPO = ?, ProcessingCost = ?, RSIQty = ?,
                                         UpdateBy = ?, UpdateDate = GETDATE()
            WHEN NOT MATCHED THEN INSERT (CompID, PriceDate, CPOPrice, KernelPrice, OERCPO, ProcessingCost, RSIQty, UpdateBy)
                                  VALUES (s.CompID, s.PriceDate, ?, ?, ?, ?, ?, ?);""",
            id_company, tanggal, *nilai, qty_rsi, user_id, *nilai, qty_rsi, user_id)
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
