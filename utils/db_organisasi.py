"""Admin › Organisasi: perusahaan (Company), area perusahaan (CompanyArea), Mill (tipe area; tabel lokasi), departemen
(+ area tempat tersedia). Dipakai akun dan perangkat kiosk."""
import pyodbc

from utils.cache import cache_ttl
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
    """Perusahaan + nama area-areanya (label 'OFFICE, REFINERY')."""
    rows = _query("""SELECT c.id_company, c.kode, c.nama, c.alamat, c.is_active,
                            (SELECT COUNT(*) FROM comp_area a WHERE a.id_company = c.id_company AND a.is_active = 1) AS jumlah_area
                     FROM company c ORDER BY c.is_active DESC, c.nama""")
    area = _query("SELECT id_company, nama FROM comp_area WHERE is_active = 1 ORDER BY kode, nama")
    for r in rows:
        r["label_area"] = ", ".join(x["nama"] for x in area if x["id_company"] == r["id_company"])
    return rows


def simpan_company(id_company, kode, nama, alamat):
    if id_company is None:
        _ubah("INSERT INTO company (kode, nama, alamat) VALUES (?, ?, ?)", kode, nama, alamat)
    else:
        _ubah("UPDATE company SET kode = ?, nama = ?, alamat = ? WHERE id_company = ?", kode, nama, alamat, id_company)
    _hapus_cache_area()


def set_aktif_company(id_company, aktif):
    _ubah("UPDATE company SET is_active = ? WHERE id_company = ?", 1 if aktif else 0, id_company)
    _hapus_cache_area()


# ===== MILL (tabel lokasi, migrasi 025 & 030) =====
# Tipe area yang sama untuk semua PT: 300 HO, 600 PKS, DOWNSTREAM, TANGKI, ... is_pusat = kantor pusat.
def daftar_lokasi():
    return _query("""SELECT l.id_lokasi, l.kode, l.nama, l.keterangan, l.is_pusat, l.is_active,
                            (SELECT COUNT(*) FROM comp_area a WHERE a.id_lokasi = l.id_lokasi AND a.is_active = 1) AS jumlah_area
                     FROM lokasi l ORDER BY l.is_active DESC, l.kode""")


def simpan_lokasi(id_lokasi, kode, nama, keterangan, is_pusat):
    """Kode area ikut kode Mill-nya, jadi saat kode Mill diubah, kode semua area bertipe itu ikut berubah."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_lokasi is None:
            cursor.execute("INSERT INTO lokasi (kode, nama, keterangan, is_pusat) VALUES (?, ?, ?, ?)",
                           kode, nama, keterangan, int(is_pusat))
        else:
            cursor.execute("UPDATE lokasi SET kode = ?, nama = ?, keterangan = ?, is_pusat = ? WHERE id_lokasi = ?",
                           kode, nama, keterangan, int(is_pusat), id_lokasi)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
            cursor.execute("UPDATE comp_area SET kode = ? WHERE id_lokasi = ?", kode, id_lokasi)
        conn.commit()
    finally:
        conn.close()
    area_pusat.hapus()


def set_aktif_lokasi(id_lokasi, aktif):
    _ubah("UPDATE lokasi SET is_active = ? WHERE id_lokasi = ?", 1 if aktif else 0, id_lokasi)


@cache_ttl(60)
def area_pusat():
    """id area bertipe Mill kantor pusat (HO): akun di area ini melihat & mengelola semua PT.
    Sebelum migrasi 025 memakai pengaturan lama AREA_PUSAT."""
    try:
        return frozenset(r["id_comp_area"] for r in _query(
            "SELECT a.id_comp_area FROM comp_area a JOIN lokasi l ON l.id_lokasi = a.id_lokasi WHERE l.is_pusat = 1"))
    except pyodbc.Error:
        rows = _query("SELECT nilai FROM pengaturan WHERE kunci = 'AREA_PUSAT'")
        return frozenset(int(r["nilai"]) for r in rows if str(r["nilai"]).isdigit())


@cache_ttl(30)
def pt_kelola(id_user):
    """id company yang dikelola user kantor pusat (tabel akun_company, migrasi 026). Kosong = semua PT."""
    try:
        return frozenset(r["id_company"] for r in _query("SELECT id_company FROM akun_company WHERE id_user = ?", id_user))
    except pyodbc.Error:
        return frozenset()


def pt_kelola_semua():
    """{id_user: [id_company, ...]} untuk tabel Kelola Pengguna."""
    hasil = {}
    try:
        for r in _query("SELECT id_user, id_company FROM akun_company"):
            hasil.setdefault(r["id_user"], []).append(r["id_company"])
    except pyodbc.Error:
        pass
    return hasil


def simpan_pt_kelola(id_user, daftar_company):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM akun_company WHERE id_user = ?", id_user)
        for id_c in sorted(set(daftar_company)):
            cursor.execute("INSERT INTO akun_company (id_user, id_company) VALUES (?, ?)", id_user, id_c)
        conn.commit()
    finally:
        conn.close()
    pt_kelola.hapus()


@cache_ttl(60)
def area_per_company():
    """{id_company: (id_comp_area, ...)} termasuk site nonaktif (data lama tetap terlihat)."""
    hasil = {}
    for r in _query("SELECT id_comp_area, id_company FROM comp_area"):
        hasil.setdefault(r["id_company"], []).append(r["id_comp_area"])
    return {k: tuple(v) for k, v in hasil.items()}


@cache_ttl(60)
def company_area():
    """{id_comp_area: id_company}"""
    return {r["id_comp_area"]: r["id_company"] for r in _query("SELECT id_comp_area, id_company FROM comp_area")}


# ===== AREA PERUSAHAAN (CompanyArea) =====
def daftar_area():
    """Area milik perusahaan (dipakai akun, jembatan, pos, tiket). label = "YBS · REFINERY"."""
    return _query("""SELECT a.id_comp_area, a.kode, a.nama, a.keterangan, a.is_active, a.id_company, c.nama AS company,
                            c.kode AS kode_company, a.id_lokasi, l.nama AS mill, ISNULL(l.is_pusat, 0) AS is_pusat,
                            c.kode + ' · ' + a.nama AS label,
                            (SELECT COUNT(*) FROM akun u WHERE u.id_comp_area = a.id_comp_area AND u.is_active = 1) AS jumlah_user
                     FROM comp_area a JOIN company c ON c.id_company = a.id_company
                     LEFT JOIN lokasi l ON l.id_lokasi = a.id_lokasi
                     ORDER BY a.is_active DESC, c.nama, a.kode, a.nama""")


def simpan_area(id_area, id_company, id_lokasi, nama, keterangan):
    """Kode area = kode Mill. Area baru langsung mendapat jadwal kerja (disalin dari area pertama)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_area is None:
            cursor.execute("""INSERT INTO comp_area (id_company, id_lokasi, kode, nama, keterangan)
                              SELECT ?, id_lokasi, kode, ?, ? FROM lokasi WHERE id_lokasi = ?""",
                           id_company, nama, keterangan, id_lokasi)
        else:
            cursor.execute("""UPDATE a SET id_company = ?, id_lokasi = l.id_lokasi, kode = l.kode, nama = ?, keterangan = ?
                              FROM comp_area a JOIN lokasi l ON l.id_lokasi = ? WHERE a.id_comp_area = ?""",
                           id_company, nama, keterangan, id_lokasi, id_area)
        if cursor.rowcount == 0:
            raise ValueError("Data tidak ditemukan")
        conn.commit()
    finally:
        conn.close()
    if id_area is None:
        _salin_dari_area_pertama()
    _hapus_cache_area()


def nama_area_dipakai(id_company, nama, kecuali=None):
    rows = _query("SELECT id_comp_area FROM comp_area WHERE id_company = ? AND nama = ?", id_company, nama)
    return any(r["id_comp_area"] != kecuali for r in rows)


def _hapus_cache_area():
    from utils.alur import hapus_cache
    area_pusat.hapus()
    area_per_company.hapus()
    company_area.hapus()
    hapus_cache()


def _salin_dari_area_pertama():
    """Area baru langsung punya jadwal kerja (disalin dari area pertama), bisa diubah sesudahnya."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO jadwal_kerja (id_comp_area, hari, nama_hari, jam_masuk, jam_pulang, is_libur, toleransi_menit)
                          SELECT a.id_comp_area, j.hari, j.nama_hari, j.jam_masuk, j.jam_pulang, j.is_libur, j.toleransi_menit
                          FROM comp_area a CROSS JOIN jadwal_kerja j
                          WHERE j.id_comp_area = (SELECT MIN(id_comp_area) FROM jadwal_kerja)
                            AND NOT EXISTS (SELECT 1 FROM jadwal_kerja x WHERE x.id_comp_area = a.id_comp_area)""")
        conn.commit()
    finally:
        conn.close()
    from utils.alur import hapus_cache
    from utils.db_absensi import get_jadwal_kerja
    hapus_cache()
    get_jadwal_kerja.hapus()


def set_aktif_area(id_area, aktif):
    _ubah("UPDATE comp_area SET is_active = ? WHERE id_comp_area = ?", 1 if aktif else 0, id_area)
    _hapus_cache_area()


# ===== DEPARTMENT + perusahaan yang memilikinya (department_company = DepartmentDetails, migrasi 040) =====
def daftar_department():
    """company = id perusahaan yang memiliki departemen; kosong = semua perusahaan."""
    rows = _query("""SELECT d.id_department, d.nama, d.keterangan, d.is_active,
                            (SELECT COUNT(*) FROM akun u WHERE u.id_department = d.id_department AND u.is_active = 1) AS jumlah_user
                     FROM department d ORDER BY d.is_active DESC, d.nama""")
    peta = company_department()
    for r in rows:
        r["company"] = list(peta.get(r["id_department"], ()))
    return rows


@cache_ttl(60)
def company_department():
    """{id_department: (id_company, ...)}; departemen yang tidak ada di sini tersedia di semua perusahaan."""
    hasil = {}
    try:
        for r in _query("SELECT id_department, id_company FROM department_company ORDER BY id_company"):
            hasil.setdefault(r["id_department"], []).append(r["id_company"])
    except pyodbc.Error:        # sebelum migrasi 040
        pass
    return {k: tuple(v) for k, v in hasil.items()}


def department_di_area(id_department, id_area):
    """Departemen tersedia di perusahaan pemilik area ini."""
    pt = company_department().get(id_department)
    return not pt or company_area().get(id_area) in pt


def simpan_department(id_department, nama, keterangan, daftar_company_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_department is None:
            cursor.execute("""SET NOCOUNT ON; INSERT INTO department (nama, keterangan) VALUES (?, ?);
                              SELECT CAST(SCOPE_IDENTITY() AS INT)""", nama, keterangan)
            id_department = cursor.fetchone()[0]
        else:
            cursor.execute("UPDATE department SET nama = ?, keterangan = ? WHERE id_department = ?", nama, keterangan, id_department)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
        cursor.execute("DELETE FROM department_company WHERE id_department = ?", id_department)
        for id_c in sorted(set(daftar_company_id)):
            cursor.execute("INSERT INTO department_company (id_department, id_company) VALUES (?, ?)", id_department, id_c)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    company_department.hapus()


def set_aktif_department(id_department, aktif):
    _ubah("UPDATE department SET is_active = ? WHERE id_department = ?", 1 if aktif else 0, id_department)


def kode_dipakai(tabel, kolom_id, kolom, nilai, kecuali=None):
    """Cek unik sebelum simpan (pesan ramah, bukan error constraint). tabel / kolom dari kode, bukan input."""
    rows = _query(f"SELECT {kolom_id} AS id FROM {tabel} WHERE {kolom} = ?", nilai)
    return any(r["id"] != kecuali for r in rows)
