"""Admin › Organisasi (ERD Ladder Desk): Company (kode = CompID), CompanyArea (area milik perusahaan, bertipe Mill),
Mill (tipe area), Department + DepartmentDetails (departemen yang ada di sebuah area). Dipakai akun dan perangkat kiosk."""
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


def _ganti_kode(cursor, tabel, kolom, lama, baru, kolom_unik=None):
    """Ganti kode yang juga dipakai sebagai ID (Company.CompID, Department.DeptID) dalam satu transaksi:
    salin baris ke kode baru, pindahkan semua baris tabel lain yang menunjuk ke kode lama (dicari dari FK), hapus baris lama.
    kolom_unik = kolom teks ber-UNIQUE di baris lama yang diberi nilai sementara agar salinan bisa dibuat
    (pemanggil menulis ulang nilainya sesudah ini). tabel / kolom dari kode, bukan input."""
    if kolom_unik:
        cursor.execute(f"UPDATE dbo.[{tabel}] SET [{kolom_unik}] = N'~' + [{kolom}] WHERE [{kolom}] = ?", lama)
    cursor.execute("""SELECT c.name FROM sys.columns c WHERE c.object_id = OBJECT_ID(?) AND c.is_identity = 0
                      AND c.is_computed = 0 AND TYPE_NAME(c.user_type_id) NOT IN ('timestamp', 'rowversion')
                      ORDER BY c.column_id""", f"dbo.{tabel}")
    kolom_tabel = [r[0] for r in cursor.fetchall()]
    pilih = ", ".join("?" if k == kolom else "N'~' + ?" if k == kolom_unik else f"[{k}]" for k in kolom_tabel)
    nilai = [baru for k in kolom_tabel if k in (kolom, kolom_unik)]
    cursor.execute(f"INSERT INTO dbo.[{tabel}] ({', '.join(f'[{k}]' for k in kolom_tabel)}) "
                   f"SELECT {pilih} FROM dbo.[{tabel}] WHERE [{kolom}] = ?", *nilai, lama)
    if cursor.rowcount == 0:
        raise ValueError("Data tidak ditemukan")
    cursor.execute("""SELECT OBJECT_SCHEMA_NAME(fk.parent_object_id), OBJECT_NAME(fk.parent_object_id),
                             COL_NAME(fk.parent_object_id, fk.parent_column_id)
                      FROM sys.foreign_key_columns fk
                      WHERE fk.referenced_object_id = OBJECT_ID(?) AND COL_NAME(fk.referenced_object_id, fk.referenced_column_id) = ?""",
                   f"dbo.{tabel}", kolom)
    for skema, anak, kol in cursor.fetchall():
        cursor.execute(f"UPDATE [{skema}].[{anak}] SET [{kol}] = ? WHERE [{kol}] = ?", baru, lama)
    cursor.execute(f"DELETE FROM dbo.[{tabel}] WHERE [{kolom}] = ?", lama)


# ===== COMPANY (CompID = kode perusahaan, mis. YBS) =====
def daftar_company():
    """Perusahaan + nama area-areanya (label 'OFFICE, REFINERY')."""
    rows = _query("""SELECT c.CompID AS id_company, c.CompID AS kode, c.CompName AS nama, c.CompAddress AS alamat,
                            c.Active AS is_active,
                            (SELECT COUNT(*) FROM CompanyArea a WHERE a.CompID = c.CompID AND a.Active = 1) AS jumlah_area
                     FROM Company c ORDER BY c.Active DESC, c.CompName""")
    area = _query("SELECT CompID, AreaName FROM CompanyArea WHERE Active = 1 ORDER BY AreaCode, AreaName")
    for r in rows:
        r["label_area"] = ", ".join(x["AreaName"] for x in area if x["CompID"] == r["id_company"])
    return rows


def simpan_company(id_company, kode, nama, alamat):
    """id_company None = baru. Kode (CompID) boleh diganti: semua tabel yang memakainya ikut dipindah."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_company is None:
            cursor.execute("INSERT INTO Company (CompID, CompName, CompAddress) VALUES (?, ?, ?)", kode, nama, alamat)
        else:
            if kode != id_company:
                _ganti_kode(cursor, "Company", "CompID", id_company, kode)
            cursor.execute("UPDATE Company SET CompName = ?, CompAddress = ? WHERE CompID = ?", nama, alamat, kode)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    _hapus_cache_area()
    pt_kelola.hapus()


def set_aktif_company(id_company, aktif):
    _ubah("UPDATE Company SET Active = ? WHERE CompID = ?", 1 if aktif else 0, id_company)
    _hapus_cache_area()


# ===== MILL (tipe area untuk semua PT: 300 HO, 600 PKS, ...; IsHeadOffice = kantor pusat) =====
def daftar_lokasi():
    return _query("""SELECT m.MillID AS id_lokasi, m.MillCode AS kode, m.MillName AS nama, m.Description AS keterangan,
                            m.IsHeadOffice AS is_pusat, m.Active AS is_active,
                            (SELECT COUNT(*) FROM CompanyArea a WHERE a.MillID = m.MillID AND a.Active = 1) AS jumlah_area
                     FROM Mill m ORDER BY m.Active DESC, m.MillCode""")


def simpan_lokasi(id_lokasi, kode, nama, keterangan, is_pusat):
    """Kode area ikut kode Mill-nya, jadi saat kode Mill diubah, kode semua area bertipe itu ikut berubah."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_lokasi is None:
            cursor.execute("INSERT INTO Mill (MillCode, MillName, Description, IsHeadOffice) VALUES (?, ?, ?, ?)",
                           kode, nama, keterangan, int(is_pusat))
        else:
            cursor.execute("UPDATE Mill SET MillCode = ?, MillName = ?, Description = ?, IsHeadOffice = ? WHERE MillID = ?",
                           kode, nama, keterangan, int(is_pusat), id_lokasi)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
            cursor.execute("UPDATE CompanyArea SET AreaCode = ? WHERE MillID = ?", kode, id_lokasi)
            cursor.execute("""UPDATE dd SET Location = CASE WHEN ? = 1 THEN 'HO' ELSE 'SITE' END FROM DepartmentDetails dd
                              JOIN CompanyArea a ON a.CompAreaID = dd.CompAreaID WHERE a.MillID = ?""", int(is_pusat), id_lokasi)
        conn.commit()
    finally:
        conn.close()
    area_pusat.hapus()


def set_aktif_lokasi(id_lokasi, aktif):
    _ubah("UPDATE Mill SET Active = ? WHERE MillID = ?", 1 if aktif else 0, id_lokasi)


@cache_ttl(60)
def area_pusat():
    """id area bertipe Mill kantor pusat (HO): akun di area ini melihat & mengelola semua PT."""
    return frozenset(r["CompAreaID"] for r in _query(
        "SELECT a.CompAreaID FROM CompanyArea a JOIN Mill m ON m.MillID = a.MillID WHERE m.IsHeadOffice = 1"))


def cakupan_user(id_user):
    """Ringkasan cakupan data dari dbo.fn_UserScopeInfo + daftar area (tuple id) bila kantor pusat dibatasi PT.
    None = user tidak ditemukan / nonaktif."""
    rows = _query("""SELECT i.OwnAreaID, i.OwnCompID, i.IsHeadOffice, i.AllAreas,
                            CASE WHEN i.IsHeadOffice = 1 AND i.AllAreas = 0 THEN
                                 (SELECT STRING_AGG(CAST(s.CompAreaID AS VARCHAR(20)), ',') FROM dbo.fn_UserScope(?) s) END AS Areas
                     FROM dbo.fn_UserScopeInfo(?) i""", id_user, id_user)
    if not rows:
        return None
    r = rows[0]
    r["areas"] = tuple(sorted(int(x) for x in (r.pop("Areas") or "").split(",") if x))
    return r


@cache_ttl(30)
def pt_kelola(id_user):
    """Kode perusahaan yang dikelola user kantor pusat (tabel UserCompany). Kosong = semua PT."""
    return frozenset(r["CompID"] for r in _query("SELECT CompID FROM UserCompany WHERE UserID = ?", id_user))


def pt_kelola_semua():
    """{id_user: [kode perusahaan, ...]} untuk tabel Kelola Pengguna."""
    hasil = {}
    for r in _query("SELECT UserID, CompID FROM UserCompany"):
        hasil.setdefault(r["UserID"], []).append(r["CompID"])
    return hasil


def simpan_pt_kelola(id_user, daftar_company):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM UserCompany WHERE UserID = ?", id_user)
        for id_c in sorted(set(daftar_company)):
            cursor.execute("INSERT INTO UserCompany (UserID, CompID) VALUES (?, ?)", id_user, id_c)
        conn.commit()
    finally:
        conn.close()
    pt_kelola.hapus()


@cache_ttl(60)
def area_per_company():
    """{kode perusahaan: (id area, ...)} termasuk area nonaktif (data lama tetap terlihat)."""
    hasil = {}
    for r in _query("SELECT CompAreaID, CompID FROM CompanyArea"):
        hasil.setdefault(r["CompID"], []).append(r["CompAreaID"])
    return {k: tuple(v) for k, v in hasil.items()}


@cache_ttl(60)
def company_area():
    """{id area: kode perusahaan}"""
    return {r["CompAreaID"]: r["CompID"] for r in _query("SELECT CompAreaID, CompID FROM CompanyArea")}


# ===== AREA PERUSAHAAN (CompanyArea) =====
def daftar_area():
    """Area milik perusahaan (dipakai akun, jembatan, pos, tiket). label = "YBS · REFINERY"."""
    return _query("""SELECT a.CompAreaID AS id_comp_area, a.AreaCode AS kode, a.AreaName AS nama, a.AreaDesc AS keterangan,
                            a.Active AS is_active, a.CompID AS id_company, c.CompName AS company, c.CompID AS kode_company,
                            a.MillID AS id_lokasi, m.MillName AS mill, ISNULL(m.IsHeadOffice, 0) AS is_pusat,
                            a.CompID + ' · ' + a.AreaName AS label,
                            (SELECT COUNT(*) FROM Users u WHERE u.CompAreaID = a.CompAreaID AND u.Active = 1) AS jumlah_user
                     FROM CompanyArea a JOIN Company c ON c.CompID = a.CompID
                     LEFT JOIN Mill m ON m.MillID = a.MillID
                     ORDER BY a.Active DESC, c.CompName, a.AreaCode, a.AreaName""")


def simpan_area(id_area, id_company, id_lokasi, nama, keterangan):
    """Kode area = kode Mill. Area baru langsung mendapat jadwal kerja (disalin dari area pertama)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_area is None:
            cursor.execute("""INSERT INTO CompanyArea (CompID, MillID, AreaCode, AreaName, AreaDesc)
                              SELECT ?, MillID, MillCode, ?, ? FROM Mill WHERE MillID = ?""",
                           id_company, nama, keterangan, id_lokasi)
        else:
            cursor.execute("""UPDATE a SET CompID = ?, MillID = m.MillID, AreaCode = m.MillCode, AreaName = ?, AreaDesc = ?
                              FROM CompanyArea a JOIN Mill m ON m.MillID = ? WHERE a.CompAreaID = ?""",
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
    rows = _query("SELECT CompAreaID FROM CompanyArea WHERE CompID = ? AND AreaName = ?", id_company, nama)
    return any(r["CompAreaID"] != kecuali for r in rows)


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
        cursor.execute("""INSERT INTO WorkSchedule (CompAreaID, DayNo, DayName, TimeIn, TimeOut, IsHoliday, ToleranceMinutes)
                          SELECT a.CompAreaID, j.DayNo, j.DayName, j.TimeIn, j.TimeOut, j.IsHoliday, j.ToleranceMinutes
                          FROM CompanyArea a CROSS JOIN WorkSchedule j
                          WHERE j.CompAreaID = (SELECT MIN(CompAreaID) FROM WorkSchedule)
                            AND NOT EXISTS (SELECT 1 FROM WorkSchedule x WHERE x.CompAreaID = a.CompAreaID)""")
        conn.commit()
    finally:
        conn.close()
    from utils.alur import hapus_cache
    from utils.db_absensi import get_jadwal_kerja
    hapus_cache()
    get_jadwal_kerja.hapus()


def set_aktif_area(id_area, aktif):
    _ubah("UPDATE CompanyArea SET Active = ? WHERE CompAreaID = ?", 1 if aktif else 0, id_area)
    _hapus_cache_area()


# ===== DEPARTMENT (DeptID = kode) + area tempat departemen ada (DepartmentDetails) =====
def daftar_department():
    """area = id area tempat departemen ini ada (DepartmentDetails)."""
    rows = _query("""SELECT d.DeptID AS id_department, d.DeptID AS kode, d.DeptName AS nama, d.Description AS keterangan,
                            d.Active AS is_active,
                            (SELECT COUNT(*) FROM Users u JOIN DepartmentDetails dd ON dd.DeptDetailID = u.UserDeptID
                             WHERE dd.DeptID = d.DeptID AND u.Active = 1) AS jumlah_user
                     FROM Department d ORDER BY d.Active DESC, d.DeptName""")
    peta = area_department()
    for r in rows:
        r["area"] = list(peta.get(r["id_department"], ()))
    return rows


@cache_ttl(60)
def area_department():
    """{kode departemen: (id area, ...)} dari DepartmentDetails yang aktif."""
    hasil = {}
    for r in _query("SELECT DeptID, CompAreaID FROM DepartmentDetails WHERE Active = 1 ORDER BY CompAreaID"):
        hasil.setdefault(r["DeptID"], []).append(r["CompAreaID"])
    return {k: tuple(v) for k, v in hasil.items()}


def department_di_area(id_department, id_area):
    """Departemen ada di area ini (DepartmentDetails)."""
    return id_area in area_department().get(id_department, ())


def simpan_department(id_department, kode, nama, keterangan, daftar_area_id):
    """id_department None = baru. Kode (DeptID) boleh diganti: semua tabel yang memakainya ikut dipindah. Area yang dilepas dinonaktifkan
    (baris DepartmentDetails tetap ada karena bisa dipakai akun lama)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_department is None:
            cursor.execute("INSERT INTO Department (DeptID, DeptName, Description) VALUES (?, ?, ?)", kode, nama, keterangan)
        else:
            if kode != id_department:
                _ganti_kode(cursor, "Department", "DeptID", id_department, kode, kolom_unik="DeptName")
            cursor.execute("UPDATE Department SET DeptName = ?, Description = ? WHERE DeptID = ?", nama, keterangan, kode)
            if cursor.rowcount == 0:
                raise ValueError("Data tidak ditemukan")
            cursor.execute("""UPDATE ld SET LevelDetName = LEFT(? + N' · ' + lv.LevelName, 120) FROM LevelDetails ld
                              JOIN Level lv ON lv.LevelID = ld.LevelID WHERE ld.DeptID = ?""", nama, kode)
        cursor.execute("UPDATE DepartmentDetails SET Active = 0 WHERE DeptID = ?", kode)
        for id_a in sorted(set(daftar_area_id)):
            cursor.execute("""MERGE DepartmentDetails AS t
                              USING (SELECT a.CompAreaID, CASE WHEN m.IsHeadOffice = 1 THEN 'HO' ELSE 'SITE' END AS Location
                                     FROM CompanyArea a LEFT JOIN Mill m ON m.MillID = a.MillID WHERE a.CompAreaID = ?) AS s
                              ON t.CompAreaID = s.CompAreaID AND t.DeptID = ?
                              WHEN MATCHED THEN UPDATE SET Active = 1, Location = s.Location
                              WHEN NOT MATCHED THEN INSERT (CompAreaID, DeptID, Location) VALUES (s.CompAreaID, ?, s.Location);""",
                           id_a, kode, kode)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    area_department.hapus()


def set_aktif_department(id_department, aktif):
    _ubah("UPDATE Department SET Active = ? WHERE DeptID = ?", 1 if aktif else 0, id_department)


def kode_dipakai(tabel, kolom_id, kolom, nilai, kecuali=None):
    """Cek unik sebelum simpan (pesan ramah, bukan error constraint). tabel / kolom dari kode, bukan input."""
    rows = _query(f"SELECT {kolom_id} AS id FROM {tabel} WHERE {kolom} = ?", nilai)
    return any(r["id"] != kecuali for r in rows)
