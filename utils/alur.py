"""Alur tahap tiket dari database (tabel alur, alur_tahap, mill; migrasi 012).

Status tiket (transaksi.status_alur) tetap memakai kode lama supaya List & tab Form tidak berubah:
    SECURITY_REGISTER  = menunggu timbang masuk
    TIMBANG_1          = sudah timbang masuk, menunggu inspeksi (sortasi / lab)
    TIMBANG_2          = siap timbang keluar
    SELESAI / REJECTED / VOID
Urutan tahapnya dibaca dari alur_tahap, jadi alur baru (mis. TBS tanpa sortasi, atau sortasi + lab) cukup
ditambah barisnya tanpa mengubah kode."""
from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

INSPEKSI = ("SORTASI", "LAB")
NAMA_TAHAP = {"SECURITY": "Security", "TIMBANG_1": "timbang masuk", "SORTASI": "sortasi", "LAB": "hasil lab (Approve)",
              "TIMBANG_2": "timbang keluar"}


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


@cache_ttl(60)
def peta_alur():
    """{id_alur: {"kode": .., "nama": .., "tahap": [kode_tahap urut]}}"""
    peta = {a["id_alur"]: {**a, "tahap": []} for a in _query("SELECT id_alur, kode, nama, is_active FROM alur")}
    for r in _query("SELECT id_alur, kode_tahap FROM alur_tahap ORDER BY id_alur, urutan"):
        if r["id_alur"] in peta:
            peta[r["id_alur"]]["tahap"].append(r["kode_tahap"])
    return peta


@cache_ttl(60)
def daftar_mill():
    rows = _query("""SELECT m.id_mill, m.id_comp_area, ar.nama AS area, m.kode, m.nama, m.id_alur, a.kode AS kode_alur,
                            a.nama AS nama_alur, m.is_active
                     FROM mill m JOIN alur a ON a.id_alur = m.id_alur JOIN comp_area ar ON ar.id_comp_area = m.id_comp_area
                     ORDER BY m.is_active DESC, ar.nama, m.kode""")
    for r in rows:
        r["is_active"] = bool(r["is_active"])
    return rows


def hapus_cache():
    peta_alur.hapus()
    daftar_mill.hapus()


def tahap_alur(id_alur):
    return list(peta_alur().get(id_alur, {}).get("tahap", []))


def punya_tahap(id_alur, kode_tahap):
    return kode_tahap in tahap_alur(id_alur)


def tahap_berikut(id_alur, kode_selesai):
    tahap = tahap_alur(id_alur)
    if kode_selesai not in tahap:
        return None
    i = tahap.index(kode_selesai)
    return tahap[i + 1] if i + 1 < len(tahap) else None


def status_setelah(id_alur, kode_selesai):
    """Status tiket setelah tahap ini selesai (lihat docstring modul)."""
    berikut = tahap_berikut(id_alur, kode_selesai)
    if berikut is None:
        return "SELESAI"
    if berikut in INSPEKSI:
        return "TIMBANG_1"
    if berikut == "TIMBANG_2":
        return "TIMBANG_2"
    return "SECURITY_REGISTER"


def menunggu(id_alur, status_alur):
    """Teks tahap yang sedang ditunggu tiket (untuk pesan 'belum bisa timbang kedua')."""
    if status_alur == "TIMBANG_1":
        sisa = [t for t in tahap_alur(id_alur) if t in INSPEKSI]
        return " / ".join(NAMA_TAHAP[t] for t in sisa) or "inspeksi"
    return NAMA_TAHAP.get({"SECURITY_REGISTER": "TIMBANG_1", "TIMBANG_2": "TIMBANG_2"}.get(status_alur, ""), status_alur)


def pilih_mill(id_comp_area, id_alur):
    """Mill aktif pertama di area itu untuk alur ini (dipakai saat tiket dibuat). None bila belum diatur."""
    return next((m for m in daftar_mill() if m["is_active"] and m["id_comp_area"] == id_comp_area
                 and m["id_alur"] == id_alur), None)


def daftar_alur():
    """Alur aktif untuk pilihan (Admin › Organisasi › Mill, Admin › Produk)."""
    return [{"id_alur": i, "kode": a["kode"], "nama": a["nama"], "tahap": a["tahap"]}
            for i, a in sorted(peta_alur().items()) if a["is_active"]]


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        if cursor.rowcount == 0:
            raise ValueError("Data tidak ditemukan")
        conn.commit()
    finally:
        conn.close()
    hapus_cache()


def kode_mill_dipakai(id_comp_area, kode, kecuali=None):
    return any(m["id_mill"] != kecuali for m in daftar_mill() if m["id_comp_area"] == id_comp_area and m["kode"] == kode)


def simpan_mill(id_mill, id_comp_area, kode, nama, id_alur):
    if id_mill is None:
        _ubah("INSERT INTO mill (id_comp_area, kode, nama, id_alur) VALUES (?, ?, ?, ?)", id_comp_area, kode, nama, id_alur)
    else:
        _ubah("UPDATE mill SET id_comp_area = ?, kode = ?, nama = ?, id_alur = ? WHERE id_mill = ?",
              id_comp_area, kode, nama, id_alur, id_mill)


def set_aktif_mill(id_mill, aktif):
    _ubah("UPDATE mill SET is_active = ? WHERE id_mill = ?", 1 if aktif else 0, id_mill)


def id_alur_kode(kode):
    return next((i for i, a in peta_alur().items() if a["kode"] == kode), None)
