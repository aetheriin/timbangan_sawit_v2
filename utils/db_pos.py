"""Pos Security & Logbook Kendaraan (tahap 1) di atas tabel transaksi, tanpa tabel baru (migrasi 039).

Jam masuk = transaksi.created_at (petugas security_id), jam keluar = waktu_keluar (petugas keluar_oleh).
Kendaraan dari Pos Security memakai alur POS_SAJA: selesai saat dicatat keluar.
"Masih di dalam" = belum dicatat keluar dan tidak dibatalkan (tiket biasa ikut, supaya Logbook tetap dipakai di tahap 2)."""
from datetime import datetime, timedelta

from utils.area_filter import sql_area
from utils.db_utils import get_connection, _rows_to_dicts, AREA_TIKET

DI_DALAM = "t.waktu_keluar IS NULL AND t.status_alur <> 'VOID'"

_KOLOM = """t.no_tiket, k.no_plat, t.id_driver, d.nama_personel AS supir, d.kode_personel,
            s.nama_supplier AS customer, p.nama_produk AS produk, t.jenis_transaksi, t.status_alur,
            ISNULL(ang.nama_supplier, '') AS pengangkutan, t.created_at AS waktu_masuk, t.waktu_keluar,
            um.nama AS petugas_masuk, uk.nama AS petugas_keluar, a.kode AS kode_alur"""
_DARI = """FROM transaksi t
           JOIN kendaraan k ON k.id_kendaraan = t.id_kendaraan
           JOIN personel d ON d.id_personel = t.id_driver
           JOIN mitra s ON s.id_supplier = t.id_supplier
           JOIN produk p ON p.id_produk = t.id_produk
           LEFT JOIN mitra ang ON ang.id_supplier = t.id_pengangkutan
           LEFT JOIN akun um ON um.id_user = t.security_id
           LEFT JOIN akun uk ON uk.id_user = t.keluar_oleh
           LEFT JOIN alur a ON a.id_alur = t.id_alur"""


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def logbook(id_area, tanggal):
    """{dalam: [...], keluar: [...] (keluar pada tanggal), masuk_hari_ini: n} sesuai area user."""
    f_area, p_area = sql_area(AREA_TIKET, id_area)
    awal = datetime.combine(tanggal, datetime.min.time())
    akhir = awal + timedelta(days=1)
    dalam = _query(f"SELECT {_KOLOM} {_DARI} WHERE {DI_DALAM}{f_area} ORDER BY t.created_at", *p_area)
    keluar = _query(f"""SELECT {_KOLOM} {_DARI} WHERE t.waktu_keluar >= ? AND t.waktu_keluar < ?{f_area}
                        ORDER BY t.waktu_keluar DESC""", awal, akhir, *p_area)
    masuk = _query(f"""SELECT COUNT(*) AS n FROM transaksi t WHERE t.status_alur <> 'VOID'
                       AND t.created_at >= ? AND t.created_at < ?{f_area}""", awal, akhir, *p_area)[0]["n"]
    return {"dalam": dalam, "keluar": keluar, "masuk_hari_ini": masuk}


def di_dalam(no_plat):
    """Kunjungan plat yang belum dicatat keluar (di area mana pun), atau None."""
    rows = _query(f"SELECT TOP 1 {_KOLOM} {_DARI} WHERE k.no_plat = ? AND {DI_DALAM} ORDER BY t.created_at DESC", no_plat)
    return rows[0] if rows else None


def kendaraan(no_plat):
    rows = _query("""SELECT k.id_kendaraan, k.no_stnk, k.is_blacklisted, k.is_active, k.id_jenis_kendaraan, jk.nama AS jenis
                     FROM kendaraan k LEFT JOIN jenis_kendaraan jk ON jk.id_jenis_kendaraan = k.id_jenis_kendaraan
                     WHERE k.no_plat = ?""", no_plat)
    return rows[0] if rows else None


def atur_jenis_kendaraan(no_plat, id_jenis):
    """Jenis kendaraan dipilih security saat masuk -> disimpan di data kendaraan (perubahan tercatat trigger log data)."""
    conn = get_connection()
    try:
        conn.cursor().execute("""UPDATE kendaraan SET id_jenis_kendaraan = ?
                                 WHERE no_plat = ? AND ISNULL(id_jenis_kendaraan, 0) <> ?""", id_jenis, no_plat, id_jenis)
        conn.commit()
    finally:
        conn.close()


def supir_terakhir(no_plat):
    rows = _query("""SELECT TOP 1 t.created_at AS waktu, d.id_personel AS id_driver, d.kode_personel, d.nik,
                            d.nama_personel AS nama, d.no_sim, d.kategori, d.is_blacklisted, d.is_updated, d.foto_path
                     FROM transaksi t JOIN kendaraan k ON k.id_kendaraan = t.id_kendaraan
                     JOIN v_personel d ON d.id_personel = t.id_driver
                     WHERE k.no_plat = ? ORDER BY t.created_at DESC""", no_plat)
    return rows[0] if rows else None


def blacklist_aktif(tipe, id_target):
    """Alasan, sejak kapan, dan penetap blacklist yang berlaku (untuk panel peringatan)."""
    kolom = "id_personel" if tipe == "PERSONEL" else "id_kendaraan"
    rows = _query(f"""SELECT TOP 1 b.alasan_blacklist AS alasan, b.created_at AS sejak, u.nama AS oleh,
                             dk.no_dokumen AS no_surat
                      FROM blacklist b JOIN akun u ON u.id_user = b.created_by
                      LEFT JOIN dokumen dk ON dk.id_dokumen = b.id_dokumen
                      WHERE b.{kolom} = ? AND b.dicabut_at IS NULL ORDER BY b.created_at DESC""", id_target)
    return rows[0] if rows else None


def sim_supir(id_personel):
    """SIM aktif yang paling lama berlaku (None bila belum ada)."""
    rows = _query("""SELECT TOP 1 js.nama AS jenis, s.no_sim, s.berlaku_sampai
                     FROM personel_sim s JOIN jenis_sim js ON js.id_jenis_sim = s.id_jenis_sim
                     WHERE s.id_personel = ? AND s.is_active = 1
                     ORDER BY CASE WHEN s.berlaku_sampai IS NULL THEN 1 ELSE 0 END, s.berlaku_sampai DESC""", id_personel)
    return rows[0] if rows else None


def catat_keluar(no_tiket, id_user, id_area):
    """Isi jam keluar. Kunjungan Pos Security (alur POS_SAJA) sekaligus selesai. Kembalikan baris sebelum keluar,
    atau None bila tidak ada / sudah keluar / di luar area user."""
    f_area, p_area = sql_area(AREA_TIKET, id_area)
    rows = _query(f"SELECT {_KOLOM} {_DARI} WHERE t.no_tiket = ? AND {DI_DALAM}{f_area}", no_tiket, *p_area)
    if not rows:
        return None
    pos = rows[0]["kode_alur"] == "POS_SAJA"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"""UPDATE transaksi SET waktu_keluar = GETDATE(), keluar_oleh = ?
                           {", status_alur = 'SELESAI', is_qr_active = 0" if pos else ""}
                           WHERE no_tiket = ? AND waktu_keluar IS NULL""", id_user, no_tiket)
        if cursor.rowcount == 0:
            conn.rollback()
            return None
        from utils import log_aktivitas
        log_aktivitas.catat("TIMELINE", "POS_KELUAR", tabel="transaksi", id_baris=no_tiket, user_id=id_user, cursor=cursor)
        conn.commit()
    finally:
        conn.close()
    return rows[0]
