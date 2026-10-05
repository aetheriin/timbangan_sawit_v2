"""Jembatan timbang per area (Admin › Perangkat / Kiosk) dan penimbangan per tiket (migrasi 011)."""
from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

COOKIE_JEMBATAN = "jembatan_timbang"


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
            raise ValueError("Jembatan timbang tidak ditemukan")
        conn.commit()
    finally:
        conn.close()


@cache_ttl(30)
def daftar_jembatan():
    rows = _query("""SELECT j.id_jembatan, j.id_comp_area, a.nama AS area, j.kode, j.nama, j.port, j.baudrate,
                            j.is_active, j.created_at
                     FROM jembatan_timbang j JOIN comp_area a ON a.id_comp_area = j.id_comp_area
                     ORDER BY j.is_active DESC, a.nama, j.kode""")
    for r in rows:
        r["is_active"] = bool(r["is_active"])
    return rows


def get_jembatan(id_jembatan):
    return next((j for j in daftar_jembatan() if j["id_jembatan"] == id_jembatan), None)


def jembatan_dipilih(request):
    """Jembatan timbang yang dipakai PC ini (cookie, dipilih di tab Timbangan); None bila belum / tidak aktif."""
    teks = request.cookies.get(COOKIE_JEMBATAN, "")
    if not teks.isdigit():
        return None
    j = get_jembatan(int(teks))
    return j if j and j["is_active"] else None


def kode_dipakai(id_area, kode, kecuali=None):
    return any(j["id_comp_area"] == id_area and j["kode"] == kode and j["id_jembatan"] != kecuali
               for j in daftar_jembatan())


def simpan_jembatan(id_jembatan, id_area, kode, nama, port, baudrate):
    if id_jembatan is None:
        _ubah("""INSERT INTO jembatan_timbang (id_comp_area, kode, nama, port, baudrate) VALUES (?, ?, ?, ?, ?)""",
              id_area, kode, nama, port, baudrate)
    else:
        _ubah("""UPDATE jembatan_timbang SET id_comp_area = ?, kode = ?, nama = ?, port = ?, baudrate = ?
                 WHERE id_jembatan = ?""", id_area, kode, nama, port, baudrate, id_jembatan)
    daftar_jembatan.hapus()


def set_aktif_jembatan(id_jembatan, aktif):
    _ubah("UPDATE jembatan_timbang SET is_active = ? WHERE id_jembatan = ?", 1 if aktif else 0, id_jembatan)
    daftar_jembatan.hapus()
