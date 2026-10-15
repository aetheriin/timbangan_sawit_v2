"""Admin › Organisasi: company, lokasi, area (site = company + lokasi), department. Dipakai akun dan perangkat kiosk."""
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


# ===== LOKASI (migrasi 025) =====
# Master lokasi yang sama untuk semua PT: 300 (HEAD OFFICE), 600 (PKS), ... is_pusat = kantor pusat.
JENIS_LOKASI = {"KANTOR_PUSAT": "Kantor pusat", "PKS": "PKS", "REFINERY": "Refinery", "TANGKI": "Tangki timbun",
                "LAB": "Laboratorium", "KEBUN": "Kebun", "GUDANG": "Gudang", "LAINNYA": "Lainnya"}


def daftar_lokasi():
    return _query("""SELECT l.id_lokasi, l.kode, l.nama, l.jenis, l.is_pusat, l.is_active,
                            (SELECT COUNT(*) FROM comp_area a WHERE a.id_lokasi = l.id_lokasi) AS jumlah_site
                     FROM lokasi l ORDER BY l.is_active DESC, l.kode""")


def simpan_lokasi(id_lokasi, kode, nama, jenis, is_pusat):
    """Kode site ikut kode lokasi, jadi saat kode lokasi diubah, kode semua site di lokasi itu ikut berubah."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_lokasi is None:
            cursor.execute("INSERT INTO lokasi (kode, nama, jenis, is_pusat) VALUES (?, ?, ?, ?)",
                           kode, nama, jenis, int(is_pusat))
        else:
            cursor.execute("UPDATE lokasi SET kode = ?, nama = ?, jenis = ?, is_pusat = ? WHERE id_lokasi = ?",
                           kode, nama, jenis, int(is_pusat), id_lokasi)
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
    """id site yang berada di lokasi kantor pusat: akun di site ini melihat & mengelola semua PT.
    Sebelum migrasi 025 memakai pengaturan lama AREA_PUSAT."""
    try:
        return frozenset(r["id_comp_area"] for r in _query(
            "SELECT a.id_comp_area FROM comp_area a JOIN lokasi l ON l.id_lokasi = a.id_lokasi WHERE l.is_pusat = 1"))
    except pyodbc.Error:
        rows = _query("SELECT nilai FROM pengaturan WHERE kunci = 'AREA_PUSAT'")
        return frozenset(int(r["nilai"]) for r in rows if str(r["nilai"]).isdigit())


# ===== AREA (SITE) = company + lokasi =====
def daftar_area():
    """label = "YBS · 600 (PKS Sei Mangkei)" untuk pilihan di form; kode site = kode lokasi."""
    return _query("""SELECT a.id_comp_area, a.kode, a.nama, a.alamat, a.is_active, a.id_company, c.nama AS company,
                            c.kode AS kode_company, a.id_lokasi, l.nama AS lokasi, ISNULL(l.is_pusat, 0) AS is_pusat,
                            c.kode + ' · ' + a.kode + ' (' + a.nama + ')' AS label,
                            (SELECT COUNT(*) FROM akun u WHERE u.id_comp_area = a.id_comp_area AND u.is_active = 1) AS jumlah_user
                     FROM comp_area a JOIN company c ON c.id_company = a.id_company
                     LEFT JOIN lokasi l ON l.id_lokasi = a.id_lokasi
                     ORDER BY a.is_active DESC, c.nama, a.kode""")


def simpan_area(id_area, id_company, id_lokasi, nama, alamat):
    """Kode site diambil dari kode lokasi. Satu company hanya punya satu site per lokasi."""
    lokasi = _query("SELECT kode FROM lokasi WHERE id_lokasi = ?", id_lokasi)
    if not lokasi:
        raise ValueError("Lokasi tidak ditemukan")
    dobel = _query("SELECT id_comp_area FROM comp_area WHERE id_company = ? AND id_lokasi = ?", id_company, id_lokasi)
    if any(r["id_comp_area"] != id_area for r in dobel):
        raise ValueError(f"Perusahaan ini sudah punya site di lokasi {lokasi[0]['kode']}")
    kode = lokasi[0]["kode"]
    if id_area is None:
        _ubah("INSERT INTO comp_area (id_company, id_lokasi, kode, nama, alamat) VALUES (?, ?, ?, ?, ?)",
              id_company, id_lokasi, kode, nama, alamat)
        _salin_dari_area_pertama()
    else:
        _ubah("UPDATE comp_area SET id_company = ?, id_lokasi = ?, kode = ?, nama = ?, alamat = ? WHERE id_comp_area = ?",
              id_company, id_lokasi, kode, nama, alamat, id_area)
    area_pusat.hapus()


def _salin_dari_area_pertama():
    """Area baru langsung punya jadwal kerja & mill (disalin dari area pertama), bisa diubah sesudahnya."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO jadwal_kerja (id_comp_area, hari, nama_hari, jam_masuk, jam_pulang, is_libur, toleransi_menit)
                          SELECT a.id_comp_area, j.hari, j.nama_hari, j.jam_masuk, j.jam_pulang, j.is_libur, j.toleransi_menit
                          FROM comp_area a CROSS JOIN jadwal_kerja j
                          WHERE j.id_comp_area = (SELECT MIN(id_comp_area) FROM jadwal_kerja)
                            AND NOT EXISTS (SELECT 1 FROM jadwal_kerja x WHERE x.id_comp_area = a.id_comp_area)""")
        cursor.execute("""INSERT INTO mill (id_comp_area, kode, nama, id_alur)
                          SELECT a.id_comp_area, m.kode, m.nama, m.id_alur
                          FROM comp_area a CROSS JOIN mill m
                          WHERE m.id_comp_area = (SELECT MIN(id_comp_area) FROM mill) AND m.is_active = 1
                            AND NOT EXISTS (SELECT 1 FROM mill x WHERE x.id_comp_area = a.id_comp_area)""")
        conn.commit()
    finally:
        conn.close()
    from utils.alur import hapus_cache
    from utils.db_absensi import get_jadwal_kerja
    hapus_cache()
    get_jadwal_kerja.hapus()


def set_aktif_area(id_area, aktif):
    _ubah("UPDATE comp_area SET is_active = ? WHERE id_comp_area = ?", 1 if aktif else 0, id_area)


# ===== DEPARTMENT =====
def daftar_department():
    return _query("""SELECT d.id_department, d.nama, d.keterangan, d.is_active,
                            (SELECT COUNT(*) FROM akun u WHERE u.id_department = d.id_department AND u.is_active = 1) AS jumlah_user
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
