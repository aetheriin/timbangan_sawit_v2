"""Admin › Organisasi: company, area (site), department. Dipakai akun (users) dan perangkat kiosk."""
from utils.db_utils import get_connection, _rows_to_dicts


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
            raise ValueError("Data tidak ditemukan")
        conn.commit()
    finally:
        conn.close()


# ===== COMPANY =====
def daftar_company():
    return _query("""SELECT c.id_company, c.kode, c.nama, c.is_active,
                            (SELECT COUNT(*) FROM comp_area a WHERE a.id_company = c.id_company) AS jumlah_area
                     FROM company c ORDER BY c.is_active DESC, c.nama""")


def simpan_company(id_company, kode, nama):
    if id_company is None:
        _ubah("INSERT INTO company (kode, nama) VALUES (?, ?)", kode, nama)
    else:
        _ubah("UPDATE company SET kode = ?, nama = ? WHERE id_company = ?", kode, nama, id_company)


def set_aktif_company(id_company, aktif):
    _ubah("UPDATE company SET is_active = ? WHERE id_company = ?", 1 if aktif else 0, id_company)


# ===== AREA (SITE) =====
def daftar_area():
    return _query("""SELECT a.id_comp_area, a.kode, a.nama, a.alamat, a.is_active, a.id_company, c.nama AS company,
                            (SELECT COUNT(*) FROM users u WHERE u.id_comp_area = a.id_comp_area AND u.is_active = 1) AS jumlah_user
                     FROM comp_area a JOIN company c ON c.id_company = a.id_company
                     ORDER BY a.is_active DESC, c.nama, a.nama""")


def simpan_area(id_area, id_company, kode, nama, alamat):
    if id_area is None:
        _ubah("INSERT INTO comp_area (id_company, kode, nama, alamat) VALUES (?, ?, ?, ?)", id_company, kode, nama, alamat)
    else:
        _ubah("UPDATE comp_area SET id_company = ?, kode = ?, nama = ?, alamat = ? WHERE id_comp_area = ?",
              id_company, kode, nama, alamat, id_area)


def set_aktif_area(id_area, aktif):
    _ubah("UPDATE comp_area SET is_active = ? WHERE id_comp_area = ?", 1 if aktif else 0, id_area)


# ===== DEPARTMENT =====
def daftar_department():
    return _query("""SELECT d.id_department, d.nama, d.keterangan, d.is_active,
                            (SELECT COUNT(*) FROM users u WHERE u.id_department = d.id_department AND u.is_active = 1) AS jumlah_user
                     FROM department d ORDER BY d.is_active DESC, d.nama""")


def simpan_department(id_department, nama, keterangan):
    if id_department is None:
        _ubah("INSERT INTO department (nama, keterangan) VALUES (?, ?)", nama, keterangan)
    else:
        _ubah("UPDATE department SET nama = ?, keterangan = ? WHERE id_department = ?", nama, keterangan, id_department)


def set_aktif_department(id_department, aktif):
    _ubah("UPDATE department SET is_active = ? WHERE id_department = ?", 1 if aktif else 0, id_department)


def kode_dipakai(tabel, kolom_id, kolom, nilai, kecuali=None):
    """Cek unik sebelum simpan (pesan ramah, bukan error constraint). tabel / kolom dari kode, bukan input."""
    rows = _query(f"SELECT {kolom_id} AS id FROM {tabel} WHERE {kolom} = ?", nilai)
    return any(r["id"] != kecuali for r in rows)
