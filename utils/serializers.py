def serialisasi_tiket(row):
    return {
        "status": "ADA_TIKET",
        "no_tiket": row.no_tiket, "jenis_transaksi": row.jenis_transaksi, "no_do": row.no_do,
        "status_alur": row.status_alur,
        "id_supplier": row.id_supplier, "supplier": row.nama_supplier,
        "id_produk": row.id_produk, "produk": row.nama_produk, "kategori_produk": row.kategori,
        "no_plat": row.no_plat, "no_stnk": row.no_stnk,
        "driver": {
            "id_driver": row.id_driver, "nik": row.nik, "nama": row.nama_driver,
            "no_sim": row.no_sim, "is_updated": bool(row.is_updated), "foto_path": row.foto_path
        }
    }