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
    """Perusahaan + lokasi yang dimilikinya (id lokasi aktif, dan label '600 PKS, 300 HEAD OFFICE')."""
    try:
        rows = _query("""SELECT c.id_company, c.kode, c.nama, c.alamat, c.is_active,
                                (SELECT COUNT(*) FROM comp_area a WHERE a.id_company = c.id_company AND a.is_active = 1) AS jumlah_area
                         FROM company c ORDER BY c.is_active DESC, c.nama""")
        lokasi = _query("""SELECT a.id_company, a.id_lokasi, l.kode, l.nama FROM comp_area a
                           JOIN lokasi l ON l.id_lokasi = a.id_lokasi WHERE a.is_active = 1 ORDER BY l.kode""")
    except pyodbc.Error:        # sebelum migrasi 029 (tanpa company.alamat)
        rows = _query("""SELECT c.id_company, c.kode, c.nama, NULL AS alamat, c.is_active,
                                (SELECT COUNT(*) FROM comp_area a WHERE a.id_company = c.id_company) AS jumlah_area
                         FROM company c ORDER BY c.is_active DESC, c.nama""")
        lokasi = []
    for r in rows:
        milik = [l for l in lokasi if l["id_company"] == r["id_company"]]
        r["lokasi"] = [l["id_lokasi"] for l in milik]
        r["label_lokasi"] = ", ".join(f"{l['kode']} {l['nama']}" for l in milik)
    return rows


def simpan_company(id_company, kode, nama, alamat, daftar_lokasi_id):
    """Perusahaan + lokasi yang dimilikinya. Pasangan perusahaan-lokasi (tabel comp_area) dibuat / diaktifkan untuk
    lokasi yang dicentang dan dinonaktifkan untuk yang tidak (ditolak bila masih dipakai pengguna aktif)."""
    pilih = set(daftar_lokasi_id)
    conn = get_connection()
    cursor = conn.cursor()
    baru = False
    try:
        if id_company is None:
            cursor.execute("INSERT INTO company (kode, nama, alamat) OUTPUT INSERTED.id_company VALUES (?, ?, ?)", kode, nama, alamat)
            id_company = cursor.fetchone()[0]
        else:
            cursor.execute("UPDATE company SET kode = ?, nama = ?, alamat = ? WHERE id_company = ?", kode, nama, alamat, id_company)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
        cursor.execute("""SELECT a.id_comp_area, a.id_lokasi, a.is_active, l.kode,
                                 (SELECT COUNT(*) FROM akun u WHERE u.id_comp_area = a.id_comp_area AND u.is_active = 1) AS pengguna
                          FROM comp_area a JOIN lokasi l ON l.id_lokasi = a.id_lokasi WHERE a.id_company = ?""", id_company)
        ada = {r["id_lokasi"]: r for r in _rows_to_dicts(cursor)}
        for id_l, r in ada.items():
            if id_l not in pilih and r["is_active"]:
                if r["pengguna"]:
                    raise ValueError(f"Lokasi {r['kode']} masih dipakai {r['pengguna']} pengguna aktif. Pindahkan penggunanya terlebih dahulu")
                cursor.execute("UPDATE comp_area SET is_active = 0 WHERE id_comp_area = ?", r["id_comp_area"])
            elif id_l in pilih and not r["is_active"]:
                cursor.execute("UPDATE comp_area SET is_active = 1 WHERE id_comp_area = ?", r["id_comp_area"])
        for id_l in pilih - set(ada):
            cursor.execute("""INSERT INTO comp_area (id_company, id_lokasi, kode, nama)
                              SELECT ?, id_lokasi, kode, nama FROM lokasi WHERE id_lokasi = ?""", id_company, id_l)
            baru = True
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if baru:
        _salin_dari_area_pertama()
    area_pusat.hapus()
    area_per_company.hapus()
    company_area.hapus()


def set_aktif_company(id_company, aktif):
    _ubah("UPDATE company SET is_active = ? WHERE id_company = ?", 1 if aktif else 0, id_company)


# ===== LOKASI (migrasi 025) =====
# Master lokasi yang sama untuk semua PT: 300 (HEAD OFFICE), 600 (PKS), ... is_pusat = kantor pusat.
JENIS_LOKASI = {"KANTOR_PUSAT": "Kantor pusat", "PKS": "PKS", "REFINERY": "Refinery", "TANGKI": "Tangki timbun",
                "LAB": "Laboratorium", "KEBUN": "Kebun", "GUDANG": "Gudang", "LAINNYA": "Lainnya"}


def daftar_lokasi():
    return _query("""SELECT l.id_lokasi, l.kode, l.nama, l.jenis, l.is_pusat, l.is_active,
                            (SELECT COUNT(*) FROM comp_area a WHERE a.id_lokasi = l.id_lokasi AND a.is_active = 1) AS jumlah_site
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
            cursor.execute("UPDATE comp_area SET kode = ?, nama = ? WHERE id_lokasi = ?", kode, nama, id_lokasi)
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


# ===== AREA (SITE) = company + lokasi =====
def daftar_area():
    """Pasangan perusahaan + lokasi (dipakai akun, jembatan, pos, pabrik, tiket). label = "YBS · 600 PKS"."""
    return _query("""SELECT a.id_comp_area, a.kode, a.nama, a.alamat, a.is_active, a.id_company, c.nama AS company,
                            c.kode AS kode_company, a.id_lokasi, l.nama AS lokasi, ISNULL(l.is_pusat, 0) AS is_pusat,
                            c.kode + ' · ' + a.kode + ' ' + a.nama AS label,
                            (SELECT COUNT(*) FROM akun u WHERE u.id_comp_area = a.id_comp_area AND u.is_active = 1) AS jumlah_user
                     FROM comp_area a JOIN company c ON c.id_company = a.id_company
                     LEFT JOIN lokasi l ON l.id_lokasi = a.id_lokasi
                     ORDER BY a.is_active DESC, c.nama, a.kode""")


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
