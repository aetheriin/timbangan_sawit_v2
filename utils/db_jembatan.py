"""Jembatan timbang per area (Admin › Perangkat / Kios) dan penimbangan per tiket (migrasi 011)."""
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
# kunci profil -> kolom tabel Scale
KOLOM_PROFIL = {"mode": "Mode", "data_bits": "DataBits", "parity": "Parity", "stop_bits": "StopBits", "format_data": "DataFormat",
                "pola": "Pattern", "faktor": "Factor", "toleransi_kg": "ToleranceKg", "durasi_stabil": "StableSeconds",
                "berat_min_kg": "MinWeightKg", "wajib_st": "RequireST"}


@cache_ttl(30)
def daftar_jembatan():
    """Jembatan + profil indikator (migrasi 017). Sebelum migrasi 017 profil memakai nilai bawaan (perilaku lama)."""
    dasar = """SELECT j.ScaleID AS id_jembatan, j.CompAreaID AS id_comp_area, a.AreaName AS area, j.ScaleCode AS kode, j.ScaleName AS nama, j.Port AS port, j.BaudRate AS baudrate,
                      j.Active AS is_active, j.CreateDate AS created_at{tambahan}
               FROM Scale j JOIN CompanyArea a ON a.CompAreaID = j.CompAreaID
               ORDER BY j.Active DESC, a.AreaName, j.ScaleCode"""
    try:
        rows = _query(dasar.format(tambahan="".join(f", j.{KOLOM_PROFIL[k]} AS {k}" for k in PROFIL)))
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
        _ubah(f"""INSERT INTO Scale (CompAreaID, ScaleCode, ScaleName, Port, BaudRate, {", ".join(KOLOM_PROFIL[k] for k in PROFIL)})
                  VALUES (?, ?, ?, ?, ?{", ?" * len(PROFIL)})""", id_area, kode, nama, port, baudrate, *nilai)
    else:
        _ubah(f"""UPDATE Scale SET CompAreaID = ?, ScaleCode = ?, ScaleName = ?, Port = ?, BaudRate = ?,
                  {", ".join(f"{KOLOM_PROFIL[k]} = ?" for k in PROFIL)} WHERE ScaleID = ?""",
              id_area, kode, nama, port, baudrate, *nilai, id_jembatan)
    daftar_jembatan.hapus()


def set_aktif_jembatan(id_jembatan, aktif):
    _ubah("UPDATE Scale SET Active = ? WHERE ScaleID = ?", 1 if aktif else 0, id_jembatan)
    daftar_jembatan.hapus()
