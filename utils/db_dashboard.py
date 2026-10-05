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
