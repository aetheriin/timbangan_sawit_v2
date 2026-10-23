from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

INSPEKSI = ("SORTASI", "LAB")
NAMA_TAHAP = {"SECURITY": "Security", "TIMBANG_1": "timbang masuk", "SORTASI": "sortasi", "LAB": "hasil lab (Diterima)",
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
    peta = {a["id_alur"]: {**a, "tahap": []} for a in _query("SELECT FlowID AS id_alur, FlowCode AS kode, FlowName AS nama, Active AS is_active FROM Flow")}
    for r in _query("SELECT FlowID AS id_alur, StageCode AS kode_tahap FROM FlowStep ORDER BY FlowID, StepNo"):
        if r["id_alur"] in peta:
            peta[r["id_alur"]]["tahap"].append(r["kode_tahap"])
    return peta


# Warna status tiket (tabel status_tiket, migrasi 033), diatur di Admin › Organisasi
WARNA_STATUS = ("abu", "biru", "hijau", "oranye", "merah", "ungu", "kuning", "toska")


@cache_ttl(60)
def daftar_status():
    try:
        return _query("SELECT StatusCode AS kode, StatusName AS nama, StatusColor AS warna FROM Status ORDER BY SortOrder, StatusCode")
    except Exception:       # noqa: BLE001 - sebelum migrasi 033 memakai label bawaan di common.js
        return []


def simpan_status(kode, nama, warna):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Status SET StatusName = ?, StatusColor = ? WHERE StatusCode = ?", nama, warna, kode)
        if cursor.rowcount == 0:
            raise ValueError("Status tidak ditemukan.")
        conn.commit()
    finally:
        conn.close()
    daftar_status.hapus()


def hapus_cache():
    peta_alur.hapus()


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


def alur_tiket(jenis_transaksi, id_alur_produk):
    """Alur tahap transaksi baru: Penimbangan saja = TIMBANG_SAJA, selain itu alur produk (Admin › Produk)."""
    return id_alur_kode("TIMBANG_SAJA") if jenis_transaksi == "PENIMBANGAN_SAJA" else id_alur_produk


def daftar_alur():
    """Alur aktif untuk pilihan (Admin › Produk)."""
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


def id_alur_kode(kode):
    return next((i for i, a in peta_alur().items() if a["kode"] == kode), None)
