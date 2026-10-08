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


PROFIL = ("mode", "data_bits", "parity", "stop_bits", "format_data", "pola", "faktor", "toleransi_kg", "durasi_stabil",
          "berat_min_kg", "wajib_st")


@cache_ttl(30)
def daftar_jembatan():
    """Jembatan + profil indikator (migrasi 017). Sebelum migrasi 017 profil memakai nilai bawaan (perilaku lama)."""
    dasar = """SELECT j.id_jembatan, j.id_comp_area, a.nama AS area, j.kode, j.nama, j.port, j.baudrate,
                      j.is_active, j.created_at{tambahan}
               FROM jembatan_timbang j JOIN comp_area a ON a.id_comp_area = j.id_comp_area
               ORDER BY j.is_active DESC, a.nama, j.kode"""
    try:
        rows = _query(dasar.format(tambahan="".join(f", j.{k}" for k in PROFIL)))
    except Exception:       # noqa: BLE001 - kolom profil belum ada (migrasi 017 belum dijalankan)
        from utils.serial_reader import BAWAAN
        rows = [{**{k: BAWAAN[k] for k in PROFIL}, **r} for r in _query(dasar.format(tambahan=""))]
    for r in rows:
        r["is_active"], r["wajib_st"] = bool(r["is_active"]), bool(r["wajib_st"])
        for k in ("stop_bits", "faktor", "toleransi_kg", "durasi_stabil", "berat_min_kg"):
            r[k] = float(r[k])
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


def simpan_jembatan(id_jembatan, id_area, kode, nama, port, baudrate, profil):
    """profil: dict kunci PROFIL (sudah divalidasi routes/admin.py)."""
    nilai = [profil[k] for k in PROFIL]
    if id_jembatan is None:
        _ubah(f"""INSERT INTO jembatan_timbang (id_comp_area, kode, nama, port, baudrate, {", ".join(PROFIL)})
                  VALUES (?, ?, ?, ?, ?{", ?" * len(PROFIL)})""", id_area, kode, nama, port, baudrate, *nilai)
    else:
        _ubah(f"""UPDATE jembatan_timbang SET id_comp_area = ?, kode = ?, nama = ?, port = ?, baudrate = ?,
                  {", ".join(f"{k} = ?" for k in PROFIL)} WHERE id_jembatan = ?""",
              id_area, kode, nama, port, baudrate, *nilai, id_jembatan)
    daftar_jembatan.hapus()


def set_aktif_jembatan(id_jembatan, aktif):
    _ubah("UPDATE jembatan_timbang SET is_active = ? WHERE id_jembatan = ?", 1 if aktif else 0, id_jembatan)
    daftar_jembatan.hapus()
