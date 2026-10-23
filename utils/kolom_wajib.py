"""Kolom wajib dinamis (ERD RequiredDataField, migrasi 035): admin memilih kolom opsional mana yang wajib diisi
per formulir (Admin › Pengaturan Site › Kolom Wajib). Dicek di server (cek) dan ditandai required di browser
(data-kolom-wajib di base.html, dibaca common.js)."""
import pyodbc

from utils.cache import cache_ttl
from utils.db_utils import get_connection, _rows_to_dicts

# kode form: (nama, id <form> di halaman, {nama kolom di form: label})
DAFTAR = {
    "PERUSAHAAN": ("Perusahaan", "formOrg-company", {"alamat": "Alamat"}),
    "SUPPLIER": ("Supplier", "formMitra", {"alamat": "Alamat"}),
    "KENDARAAN": ("Kendaraan", "formKendaraan", {"id_supir_utama": "Supir utama"}),
    "KONTRAK_DO": ("Kontrak & DO", "formDO", {"qty_kg": "Qty (kg)", "harga_per_kg": "Harga/kg",
                                              "berlaku_sampai": "Berlaku sampai", "keterangan": "Keterangan"}),
    "TAMU": ("Tamu", "formKunjungan", {"asal_perusahaan": "Asal perusahaan", "no_plat": "No. plat kendaraan",
                                       "keterangan": "Keterangan"}),
}


@cache_ttl(60)
def wajib():
    """{kode form: (kolom, ...)} yang diwajibkan."""
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT FormCode AS form, FieldName AS kolom FROM RequiredDataField")
            rows = _rows_to_dicts(cursor)
        finally:
            conn.close()
    except pyodbc.Error:        # sebelum migrasi 035
        return {}
    hasil = {}
    for r in rows:
        if r["kolom"] in DAFTAR.get(r["form"], (None, None, {}))[2]:
            hasil.setdefault(r["form"], []).append(r["kolom"])
    return {k: tuple(v) for k, v in hasil.items()}


def per_form_html():
    """{id <form>: [kolom, ...]} untuk browser."""
    return {DAFTAR[k][1]: list(v) for k, v in wajib().items()}


def cek(form, data):
    """ValueError bila ada kolom wajib form ini yang kosong di data (request.form)."""
    kosong = [DAFTAR[form][2][k] for k in wajib().get(form, ()) if not (data.get(k) or "").strip()]
    if kosong:
        raise ValueError(f"{', '.join(kosong)} wajib diisi.")


def simpan(pilihan):
    """pilihan = {(form, kolom), ...} yang diwajibkan; yang tidak dikenal diabaikan."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM RequiredDataField")
        for form, kolom in sorted(pilihan):
            if kolom in DAFTAR.get(form, (None, None, {}))[2]:
                cursor.execute("INSERT INTO RequiredDataField (FormCode, FieldName) VALUES (?, ?)", form, kolom)
        conn.commit()
    finally:
        conn.close()
    wajib.hapus()
