"""Data Master › tabel referensi sederhana (satu pola untuk semua): Mata Uang, Bank, Rekening, Jenis & Grup Supplier,
Jenis Produk, Harga Produk. Tiap jenis = satu tabel; kolom, validasi, pilihan, dan hak menunya dari REF di bawah.
Kunci JSON memakai nama Indonesia (kunci field), kolom database memakai nama ERD."""
from datetime import date

from utils.db_utils import get_connection, _rows_to_dicts


def F(kolom, kunci, label, tipe="teks", wajib=False, maks=None, unik=False, pilihan=None, kunci_tetap=False):
    """tipe: teks | kode (huruf besar) | angka | tanggal | pilih (pilihan = jenis sumber, lihat PILIHAN).
    kunci_tetap = tidak bisa diubah setelah dibuat (kode yang dipakai aturan aplikasi)."""
    return {"kolom": kolom, "kunci": kunci, "label": label, "tipe": tipe, "wajib": wajib, "maks": maks, "unik": unik,
            "pilihan": pilihan, "kunci_tetap": kunci_tetap}


REF = {
    "mata_uang": {"judul": "Mata Uang", "tabel": "Currency", "id": "CurrencyID", "menu": "MASTER_KEUANGAN", "urut": "x.CurrencyCode",
                  "kolom": [F("CurrencyCode", "kode", "Kode", "kode", True, 10, True), F("CurrencyName", "nama", "Nama", wajib=True, maks=100),
                            F("CurrencyRate", "kurs", "Kurs ke IDR", "angka"), F("Description", "keterangan", "Keterangan", maks=255)]},
    "bank": {"judul": "Bank", "tabel": "Bank", "id": "BankAccountID", "menu": "MASTER_KEUANGAN", "urut": "x.BankName",
             "kolom": [F("BankName", "nama", "Nama Bank", wajib=True, maks=300), F("BankRegion", "cabang", "Cabang / Wilayah", maks=170),
                       F("CurrencyID", "id_mata_uang", "Mata Uang", "pilih", pilihan="mata_uang"),
                       F("CompAreaID", "id_area", "Area Perusahaan", "pilih", pilihan="area")]},
    "rekening": {"judul": "Rekening", "tabel": "BankDetails", "id": "BankAccountDetailsID", "menu": "MASTER_KEUANGAN",
                 "urut": "x.BankAccountCode",
                 "kolom": [F("BankAccountID", "id_bank", "Bank", "pilih", True, pilihan="bank"),
                           F("BankAccountCode", "no_rekening", "No. Rekening", wajib=True, maks=100, unik=True),
                           F("BankName", "atas_nama", "Atas Nama", maks=300), F("Balance", "saldo", "Saldo", "angka")]},
    "jenis_supplier": {"judul": "Jenis Supplier", "tabel": "SupplierType", "id": "SupplierTypeID", "menu": "MASTER_MITRA",
                       "urut": "x.TypeCode", "tambah": False, "aktif": False,
                       "kolom": [F("TypeCode", "kode", "Kode", "kode", True, 20, True, kunci_tetap=True),
                                 F("NameType", "nama", "Nama", wajib=True, maks=255), F("Description", "keterangan", "Keterangan", maks=255)]},
    "grup_supplier": {"judul": "Grup Supplier", "tabel": "SupplierGroup", "id": "SupplierGroupID", "menu": "MASTER_MITRA",
                      "urut": "x.NameGroup",
                      "kolom": [F("NameGroup", "nama", "Nama Grup", wajib=True, maks=255, unik=True),
                                F("Description", "keterangan", "Keterangan", maks=255)]},
    "jenis_produk": {"judul": "Jenis Produk", "tabel": "ProductType", "id": "ProductTypeID", "menu": "MASTER_PRODUK",
                     "urut": "x.ProductTypeCode", "tambah": False, "aktif": False,
                     "kolom": [F("ProductTypeCode", "kode", "Kode", "kode", True, 20, True, kunci_tetap=True),
                               F("ProductTypeName", "nama", "Nama", wajib=True, maks=50), F("Description", "keterangan", "Keterangan", maks=150)]},
    # Harga: riwayat, tidak diubah; salah input dibatalkan (void) lalu input ulang
    "harga_produk": {"judul": "Harga Produk", "tabel": "ProductPrice", "id": "ProductPriceID", "menu": "MASTER_PRODUK",
                     "urut": "x.PriceDate DESC, x.ProductPriceID DESC", "ubah": False, "aktif": False, "void": True, "batas": 300,
                     "kolom": [F("ProductID", "id_produk", "Produk", "pilih", True, pilihan="produk"),
                               F("PriceDate", "tanggal", "Tanggal", "tanggal", True),
                               F("Price", "harga", "Harga / kg", "angka", True),
                               F("CurrencyID", "id_mata_uang", "Mata Uang", "pilih", pilihan="mata_uang")],
                     "tambahan": "u.Nama AS dibuat_oleh, x.IsVoid AS is_void, v.Nama AS void_oleh",
                     "join": "LEFT JOIN Users u ON u.UserID = x.CreateBy LEFT JOIN Users v ON v.UserID = x.VoidBy"},
}

PILIHAN = {
    "mata_uang": "SELECT CurrencyID AS id, CurrencyCode + ' · ' + CurrencyName AS label FROM Currency WHERE Active = 1 ORDER BY CurrencyCode",
    "area": "SELECT CompAreaID AS id, CompID + ' · ' + AreaName AS label FROM CompanyArea WHERE Active = 1 ORDER BY CompID, AreaName",
    "bank": "SELECT BankAccountID AS id, BankName + ISNULL(' · ' + BankRegion, '') AS label FROM Bank WHERE Active = 1 ORDER BY BankName",
    "produk": "SELECT ProductID AS id, ProductName AS label FROM Product WHERE Active = 1 ORDER BY ProductName",
    "grup_supplier": "SELECT SupplierGroupID AS id, NameGroup AS label FROM SupplierGroup WHERE Active = 1 ORDER BY NameGroup",
    "rekening": """SELECT d.BankAccountDetailsID AS id, b.BankName + ' · ' + d.BankAccountCode + ISNULL(' · ' + d.BankName, '') AS label
                   FROM BankDetails d JOIN Bank b ON b.BankAccountID = d.BankAccountID WHERE d.Active = 1 ORDER BY b.BankName""",
}


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def info(jenis):
    """Metadata untuk layar (tanpa nama kolom database)."""
    c = REF[jenis]
    return {"jenis": jenis, "judul": c["judul"], "menu": c["menu"], "tambah": c.get("tambah", True), "ubah": c.get("ubah", True),
            "aktif": c.get("aktif", True), "void": c.get("void", False),
            "kolom": [{k: v for k, v in f.items() if k != "kolom"} for f in c["kolom"]]}


def opsi(nama):
    """Daftar {id, label} satu sumber pilihan (dipakai juga form Supplier)."""
    return _query(PILIHAN[nama])


def pilihan(jenis):
    return {f["kunci"]: opsi(f["pilihan"]) for f in REF[jenis]["kolom"] if f["tipe"] == "pilih"}


def daftar(jenis):
    c = REF[jenis]
    kolom = ", ".join(f"x.{f['kolom']} AS {f['kunci']}" for f in c["kolom"])
    aktif = ", x.Active AS is_active" if c.get("aktif", True) else ""
    tambahan = f", {c['tambahan']}" if c.get("tambahan") else ""
    rows = _query(f"""SELECT TOP {int(c.get('batas', 1000))} x.{c['id']} AS id, {kolom}{aktif}{tambahan}
                      FROM {c['tabel']} x {c.get('join', '')} ORDER BY {c['urut']}""")
    for r in rows:
        for k, v in r.items():
            if isinstance(v, date):
                r[k] = v.isoformat()
            elif hasattr(v, "as_tuple"):          # Decimal -> float untuk JSON
                r[k] = float(v)
    return rows


def _nilai(f, teks, opsi):
    """Validasi satu field form -> nilai database. ValueError bila tidak valid."""
    teks = (teks or "").strip()
    if not teks:
        if f["wajib"]:
            raise ValueError(f"{f['label']} wajib diisi")
        return None
    if f["tipe"] == "kode":
        teks = teks.upper()
        if not all(ch.isalnum() or ch in "-_" for ch in teks):
            raise ValueError(f"{f['label']}: hanya huruf, angka, - atau _")
    if f["tipe"] in ("teks", "kode"):
        if f["maks"] and len(teks) > f["maks"]:
            raise ValueError(f"{f['label']} maksimal {f['maks']} karakter")
        return teks
    if f["tipe"] == "angka":
        try:
            n = float(teks.replace(",", "."))
        except ValueError:
            raise ValueError(f"{f['label']} harus berupa angka")
        if n < 0:
            raise ValueError(f"{f['label']} tidak boleh negatif")
        return n
    if f["tipe"] == "tanggal":
        try:
            return date.fromisoformat(teks)
        except ValueError:
            raise ValueError(f"{f['label']} tidak valid")
    if not teks.isdigit() or int(teks) not in {o["id"] for o in opsi.get(f["kunci"], [])}:
        raise ValueError(f"Pilih {f['label'].lower()} dari daftar")
    return int(teks)


def simpan(jenis, id_baris, form, user_id):
    """Tambah (id_baris None) / ubah. Kembalikan id."""
    c = REF[jenis]
    if id_baris is None and not c.get("tambah", True):
        raise ValueError(f"{c['judul']} tidak bisa ditambah (dipakai aturan aplikasi)")
    if id_baris is not None and not c.get("ubah", True):
        raise ValueError(f"{c['judul']} tidak bisa diubah. Batalkan (void) lalu input ulang.")
    opsi = pilihan(jenis)
    nilai = {}
    for f in c["kolom"]:
        if id_baris is not None and f["kunci_tetap"]:
            continue
        nilai[f["kolom"]] = _nilai(f, form.get(f["kunci"]), opsi)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for f in c["kolom"]:
            if f["unik"] and f["kolom"] in nilai:
                cursor.execute(f"SELECT 1 FROM {c['tabel']} WHERE {f['kolom']} = ? AND {c['id']} <> ?", nilai[f["kolom"]], id_baris or 0)
                if cursor.fetchone():
                    raise ValueError(f"{f['label']} {nilai[f['kolom']]} sudah dipakai")
        if id_baris is None:
            if c.get("void"):
                nilai["CreateBy"] = user_id
            cursor.execute(f"""SET NOCOUNT ON; INSERT INTO {c['tabel']} ({', '.join(nilai)}) VALUES ({', '.join('?' * len(nilai))});
                               SELECT CAST(SCOPE_IDENTITY() AS BIGINT)""", *nilai.values())
            id_baris = cursor.fetchone()[0]
        else:
            cursor.execute(f"UPDATE {c['tabel']} SET {', '.join(f'{k} = ?' for k in nilai)} WHERE {c['id']} = ?",
                           *nilai.values(), id_baris)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return id_baris


def set_aktif(jenis, id_baris, aktif):
    c = REF[jenis]
    if not c.get("aktif", True):
        raise ValueError(f"{c['judul']} tidak bisa dinonaktifkan")
    _ubah(f"UPDATE {c['tabel']} SET Active = ? WHERE {c['id']} = ?", 1 if aktif else 0, id_baris)


def batalkan(jenis, id_baris, user_id):
    c = REF[jenis]
    if not c.get("void"):
        raise ValueError(f"{c['judul']} tidak bisa dibatalkan")
    _ubah(f"UPDATE {c['tabel']} SET IsVoid = 1, VoidDate = GETDATE(), VoidBy = ? WHERE {c['id']} = ? AND IsVoid = 0",
          user_id, id_baris)


def _ubah(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        if cursor.rowcount == 0:
            raise ValueError("Data tidak ditemukan atau sudah diproses")
        conn.commit()
    finally:
        conn.close()
