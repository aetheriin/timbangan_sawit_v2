def _tahap(id_alur):
    """Urutan tahap tiket dari alur mill-nya (kosong bila tiket lama tanpa mill)."""
    if not id_alur:
        return []
    from utils.alur import tahap_alur
    return tahap_alur(id_alur)


def serialisasi_tiket(row):
    return {
        "status": "ADA_TIKET",
        "no_tiket": row.no_tiket, "jenis_transaksi": row.jenis_transaksi, "no_do": row.no_do,
        "status_alur": row.status_alur,
        "id_supplier": row.id_supplier, "supplier": row.nama_supplier,
        "id_produk": row.id_produk, "produk": row.nama_produk, "kategori_produk": row.kategori,
        "alur_tahap": _tahap(getattr(row, "id_alur", None)),
        "no_plat": row.no_plat, "no_stnk": row.no_stnk,
        "driver": {
            "id_driver": row.id_driver, "nik": row.nik, "nama": row.nama_driver,
            "no_sim": row.no_sim, "is_updated": bool(row.is_updated), "foto_path": row.foto_path,
            "kode_personel": row.kode_personel, "is_blacklisted": bool(row.is_blacklisted)
        }
    }

def serialisasi_driver(row):
    """Baris personel (alias id_driver / nama_driver dari db_utils) -> dict untuk form Security."""
    if row is None:
        return None
    return {"id_driver": row.id_driver, "kode_personel": row.kode_personel, "nik": row.nik, "nama": row.nama_driver,
            "no_sim": row.no_sim, "kategori": row.kategori, "is_blacklisted": bool(row.is_blacklisted),
            "is_updated": bool(row.is_updated), "foto_path": row.foto_path}
