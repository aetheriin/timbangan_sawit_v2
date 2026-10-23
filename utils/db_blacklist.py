"""Query tabel blacklist (menu Blacklist). Tambah & hapus (cabut) lewat persetujuan (utils/persetujuan.py);
baris tidak pernah dihapus, pencabutan dicatat di dicabut_at / dicabut_oleh / alasan_cabut (migrasi 027)."""
from datetime import date, datetime
from utils.db_utils import get_connection, _rows_to_dicts
from utils.dokumen import buat_dokumen

TIPE_VALID = ("PERSONEL", "KENDARAAN")


def _format(r):
    for k, v in list(r.items()):
        if isinstance(v, datetime):
            r[k] = v.strftime("%Y-%m-%d %H:%M")
        elif isinstance(v, date):
            r[k] = v.isoformat()
    return r


def get_riwayat_blacklist(tipe=None, cari=None, batas=200, status="AKTIF", pt=None, kategori=None):
    """List Blacklist. pt = PT yang boleh dilihat user (None = semua): lokasi blacklist (area pengaju) di PT itu.
    Termasuk tanggal & lokasi scan terakhir (blacklist_deteksi)."""
    sql = """
        SELECT TOP (?) b.id_blacklist, b.tipe_entitas, dk.no_dokumen AS no_surat_blacklist, b.alasan_blacklist,
               df.file_path AS file_surat_blacklist, COALESCE(dk.tanggal, CAST(b.created_at AS DATE)) AS tgl_blacklist,
               b.id_dokumen, b.created_at, u.nama AS oleh, lv.kode AS role_oleh, ar.nama AS area_oleh,
               p.id_personel, p.kode_personel, p.nama_personel, k.no_plat, b.no_plat_terkait,
               c.nama_supplier AS customer_terkait, a.nama_supplier AS pengangkutan_terkait,
               b.dicabut_at, b.alasan_cabut, uc.nama AS dicabut_oleh, p.nik, b.nama_alias, b.kategori,
               CASE WHEN b.tipe_entitas = 'KENDARAAN' THEN 'Kendaraan' ELSE kp.nama END AS nama_kategori,
               arb.nama AS lokasi_blacklist, cb.kode AS company_blacklist,
               COALESCE(sp.waktu, sk.waktu) AS scan_terakhir, sca.nama AS lokasi_scan, csa.kode AS company_scan,
               (SELECT TOP 1 pg.id_pengajuan FROM pengajuan pg WHERE pg.jenis = 'BLACKLIST_HAPUS' AND pg.status = 'MENUNGGU'
                AND pg.target = 'BLACKLIST:' + CAST(b.id_blacklist AS VARCHAR(20))) AS id_pengajuan_hapus
        FROM blacklist b
        LEFT JOIN akun uc ON uc.id_user = b.dicabut_oleh
        LEFT JOIN mitra c ON b.id_customer_terkait = c.id_supplier
        LEFT JOIN mitra a ON b.id_pengangkutan_terkait = a.id_supplier
        JOIN akun u ON b.created_by = u.id_user
        JOIN level lv ON lv.id_level = u.id_level
        LEFT JOIN comp_area ar ON ar.id_comp_area = u.id_comp_area
        LEFT JOIN personel p ON b.id_personel = p.id_personel
        LEFT JOIN kendaraan k ON b.id_kendaraan = k.id_kendaraan
        LEFT JOIN dokumen dk ON dk.id_dokumen = b.id_dokumen          -- NULL = surat menyusul
        LEFT JOIN kategori_personel kp ON kp.kode = b.kategori
        LEFT JOIN comp_area arb ON arb.id_comp_area = b.id_comp_area
        LEFT JOIN company cb ON cb.id_company = arb.id_company
        OUTER APPLY (SELECT TOP 1 d.waktu, d.id_comp_area FROM blacklist_deteksi d
                     WHERE b.id_personel IS NOT NULL AND d.id_personel = b.id_personel ORDER BY d.waktu DESC) sp
        OUTER APPLY (SELECT TOP 1 d.waktu, d.id_comp_area FROM blacklist_deteksi d
                     WHERE b.id_kendaraan IS NOT NULL AND d.id_kendaraan = b.id_kendaraan ORDER BY d.waktu DESC) sk
        LEFT JOIN comp_area sca ON sca.id_comp_area = COALESCE(sp.id_comp_area, sk.id_comp_area)
        LEFT JOIN company csa ON csa.id_company = sca.id_company
        OUTER APPLY (SELECT TOP 1 f.file_path FROM dokumen_file f WHERE f.id_dokumen = dk.id_dokumen ORDER BY f.urutan) df
        WHERE 1 = 1"""
    params = [batas]
    if tipe:
        sql += " AND b.tipe_entitas = ?"
        params.append(tipe)
    if kategori:
        sql += " AND b.kategori = ?"
        params.append(kategori)
    if pt is not None:
        ids = sorted(pt) or [-1]
        sql += f" AND (b.id_comp_area IS NULL OR arb.id_company IN ({', '.join('?' * len(ids))}))"
        params += ids
    if status == "AKTIF":
        sql += " AND b.dicabut_at IS NULL"
    elif status == "DICABUT":
        sql += " AND b.dicabut_at IS NOT NULL"
    if cari:
        pola = f"%{cari}%"
        sql += """ AND (p.kode_personel LIKE ? OR p.nama_personel LIKE ? OR p.nik LIKE ?
                        OR k.no_plat LIKE ? OR dk.no_dokumen LIKE ? OR b.nama_alias LIKE ? OR b.no_plat_terkait LIKE ?)"""
        params += [pola] * 7
    sql += " ORDER BY b.created_at DESC, b.id_blacklist DESC"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, *params)
    data = [_format(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


# Data personel + transaksi terakhirnya sebagai SUPIR (plat, customer, pengangkutan saat itu).
# Bukan supir / belum pernah membawa truk -> kolom transaksi NULL (form blacklist tidak menampilkannya).
_SELECT_PERSONEL = """
    SELECT {top} p.id_personel AS id_target, p.kode_personel, p.nama_personel, p.nik, p.no_sim, p.kategori,
           kp.nama AS nama_kategori, p.foto_path, p.is_blacklisted, tr.no_plat AS plat_terakhir,
           tr.id_supplier AS id_customer_terakhir, tr.customer AS customer_terakhir,
           tr.id_pengangkutan AS id_pengangkutan_terakhir, tr.pengangkutan AS pengangkutan_terakhir,
           tr.produk AS produk_terakhir, tr.created_at AS waktu_terakhir
    FROM v_personel p
    LEFT JOIN kategori_personel kp ON kp.kode = p.kategori
    OUTER APPLY (SELECT TOP 1 k.no_plat, t.id_supplier, s.nama_supplier AS customer, t.id_pengangkutan,
                        a.nama_supplier AS pengangkutan, pr.nama_produk AS produk, t.created_at
                 FROM transaksi t JOIN kendaraan k ON t.id_kendaraan = k.id_kendaraan
                 JOIN mitra s ON t.id_supplier = s.id_supplier
                 LEFT JOIN produk pr ON pr.id_produk = t.id_produk
                 LEFT JOIN mitra a ON t.id_pengangkutan = a.id_supplier
                 WHERE t.id_driver = p.id_personel ORDER BY t.created_at DESC) tr
    WHERE p.is_active = 1"""


def _rapikan_target(data):
    for r in data:
        r["is_blacklisted"] = bool(r["is_blacklisted"])
        if r.get("waktu_terakhir") is not None:
            r["waktu_terakhir"] = r["waktu_terakhir"].strftime("%Y-%m-%d %H:%M")
    return data


def cari_target(tipe, kata, batas=8):
    """Kandidat target: personel (kode / NIK / nama / no SIM / ID) atau kendaraan (plat)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        pola = f"%{kata}%"
        if tipe == "PERSONEL":
            cursor.execute(_SELECT_PERSONEL.format(top=f"TOP {int(batas)}") + """
                AND (p.kode_personel LIKE ? OR p.nik LIKE ? OR p.nama_personel LIKE ? OR p.no_sim LIKE ?
                     OR CAST(p.id_personel AS VARCHAR) = ?)
                ORDER BY p.nama_personel""", pola, pola, pola, pola, kata.lstrip("0") or "0")
        else:
            # Plat + STNK, supir utama, jumlah supir terdaftar, dan transaksi terakhir (supir, customer, angkutan)
            cursor.execute(f"""
                SELECT TOP {int(batas)} k.id_kendaraan AS id_target, k.no_plat, k.no_stnk, k.is_blacklisted, k.is_active,
                       u.id_personel AS id_supir_utama, u.kode_personel AS kode_supir_utama, u.nama_personel AS nama_supir_utama,
                       (SELECT COUNT(*) FROM kendaraan_driver kd JOIN personel p ON p.id_personel = kd.id_driver
                        WHERE kd.id_kendaraan = k.id_kendaraan AND kd.is_active = 1 AND p.is_active = 1) AS jumlah_supir,
                       tr.id_driver AS id_supir_terakhir, tr.kode_personel AS kode_supir_terakhir,
                       tr.nama_personel AS nama_supir_terakhir, tr.customer AS customer_terakhir,
                       tr.id_supplier AS id_customer_terakhir, tr.id_pengangkutan AS id_pengangkutan_terakhir,
                       tr.pengangkutan AS pengangkutan_terakhir, tr.produk AS produk_terakhir, tr.created_at AS waktu_terakhir
                FROM kendaraan k
                OUTER APPLY (SELECT TOP 1 p.id_personel, p.kode_personel, p.nama_personel
                             FROM kendaraan_driver kd JOIN personel p ON p.id_personel = kd.id_driver
                             WHERE kd.id_kendaraan = k.id_kendaraan AND kd.is_active = 1 AND kd.is_utama = 1) u
                OUTER APPLY (SELECT TOP 1 t.id_driver, p.kode_personel, p.nama_personel, s.nama_supplier AS customer,
                                    t.id_supplier, t.id_pengangkutan, a.nama_supplier AS pengangkutan,
                                    pr.nama_produk AS produk, t.created_at
                             FROM transaksi t JOIN personel p ON p.id_personel = t.id_driver
                             JOIN mitra s ON t.id_supplier = s.id_supplier
                             LEFT JOIN produk pr ON pr.id_produk = t.id_produk
                             LEFT JOIN mitra a ON t.id_pengangkutan = a.id_supplier
                             WHERE t.id_kendaraan = k.id_kendaraan ORDER BY t.created_at DESC) tr
                WHERE REPLACE(k.no_plat, ' ', '') LIKE ?
                ORDER BY k.no_plat""", f"%{kata.replace(' ', '')}%")
        return _rapikan_target(_rows_to_dicts(cursor))
    finally:
        conn.close()


def info_kendaraan(id_kendaraan):
    """Plat, supplier / pengangkutan / produk transaksi terakhir kendaraan (pengajuan blacklist kendaraan)."""
    rows = _query_satu("""SELECT k.no_plat, s.nama_supplier AS customer_terakhir, a.nama_supplier AS pengangkutan_terakhir,
                                 pr.nama_produk AS produk_terakhir, t.id_supplier AS id_customer_terakhir,
                                 t.id_pengangkutan AS id_pengangkutan_terakhir
                          FROM kendaraan k
                          OUTER APPLY (SELECT TOP 1 t.id_supplier, t.id_pengangkutan, t.id_produk FROM transaksi t
                                       WHERE t.id_kendaraan = k.id_kendaraan ORDER BY t.created_at DESC) t
                          LEFT JOIN mitra s ON s.id_supplier = t.id_supplier
                          LEFT JOIN mitra a ON a.id_supplier = t.id_pengangkutan
                          LEFT JOIN produk pr ON pr.id_produk = t.id_produk
                          WHERE k.id_kendaraan = ?""", id_kendaraan)
    return rows[0] if rows else None


def get_target_personel(id_personel):
    """Satu personel (hasil cocok wajah) dengan data transaksi terakhir."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(_SELECT_PERSONEL.format(top="") + " AND p.id_personel = ?", id_personel)
        rows = _rapikan_target(_rows_to_dicts(cursor))
        return rows[0] if rows else None
    finally:
        conn.close()


def tambah_blacklist(tipe, id_target, no_surat, alasan, file_info, tgl_surat, user_id, terkait=None,
                     nama_alias=None, kategori=None, id_area=None):
    """INSERT dokumen surat + blacklist + set is_blacklisted = 1 dalam satu transaksi. Error bila sudah diblacklist.
    terkait: {no_plat, id_customer (asal supplier), id_pengangkutan} saat itu -> disimpan sebagai informasi.
    kategori = kategori target saat itu, id_area = lokasi blacklist (area pengaju)."""
    terkait = terkait or {}
    if tipe not in TIPE_VALID:                        # nama tabel disisipkan ke SQL -> hanya daftar tetap
        raise ValueError("Tipe blacklist tidak valid")
    tabel, kolom = ("personel", "id_personel") if tipe == "PERSONEL" else ("kendaraan", "id_kendaraan")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT is_blacklisted FROM {tabel} WHERE {kolom} = ?", id_target)
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Target tidak ditemukan")
        if row.is_blacklisted:
            raise ValueError("Target sudah masuk blacklist")
        id_dokumen = (buat_dokumen(cursor, "SURAT_BLACKLIST", no_surat, tgl_surat, f"Blacklist {tipe.lower()}",
                                   [file_info] if file_info else [], user_id) if no_surat else None)   # None = menyusul
        cursor.execute(f"""INSERT INTO blacklist (tipe_entitas, {kolom}, alasan_blacklist, id_dokumen, created_by,
                                                  no_plat_terkait, id_customer_terkait, id_pengangkutan_terkait,
                                                  nama_alias, kategori, id_comp_area)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       tipe, id_target, alasan, id_dokumen, user_id,
                       terkait.get("no_plat"), terkait.get("id_customer"), terkait.get("id_pengangkutan"),
                       nama_alias, kategori, id_area)
        cursor.execute(f"UPDATE {tabel} SET is_blacklisted = 1 WHERE {kolom} = ?", id_target)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lampirkan_surat(id_blacklist, no_surat, tgl_surat, file_info, user_id):
    """Surat blacklist yang menyusul. Error bila blacklist tidak ada / surat sudah dilampirkan."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT tipe_entitas, id_dokumen FROM blacklist WITH (UPDLOCK) WHERE id_blacklist = ?", id_blacklist)
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Blacklist tidak ditemukan")
        if row.id_dokumen is not None:
            raise ValueError("Surat sudah dilampirkan")
        id_dokumen = buat_dokumen(cursor, "SURAT_BLACKLIST", no_surat, tgl_surat, f"Blacklist {row.tipe_entitas.lower()}",
                                  [file_info], user_id)
        cursor.execute("UPDATE blacklist SET id_dokumen = ? WHERE id_blacklist = ?", id_dokumen, id_blacklist)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_surat_blacklist(tipe, id_target):
    """Surat blacklist terbaru untuk banner di Form Create Ticket."""
    kolom = "id_personel" if tipe == "PERSONEL" else "id_kendaraan"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"""SELECT TOP 1 dk.no_dokumen AS no_surat_blacklist,
                              COALESCE(dk.tanggal, CAST(b.created_at AS DATE)) AS tgl_blacklist,
                              df.file_path AS file_surat_blacklist, u.nama AS oleh, ar.nama AS area_oleh
                       FROM blacklist b JOIN akun u ON b.created_by = u.id_user
                       LEFT JOIN comp_area ar ON ar.id_comp_area = u.id_comp_area
                       LEFT JOIN dokumen dk ON dk.id_dokumen = b.id_dokumen
                       OUTER APPLY (SELECT TOP 1 f.file_path FROM dokumen_file f
                                    WHERE f.id_dokumen = dk.id_dokumen ORDER BY f.urutan) df
                       WHERE b.{kolom} = ? AND b.dicabut_at IS NULL ORDER BY b.created_at DESC, b.id_blacklist DESC""", id_target)
    data = _rows_to_dicts(cursor)
    conn.close()
    return _format(data[0]) if data else None


def nama_target(tipe, id_target):
    """(nama tampilan, sudah_blacklist) target; ValueError bila tidak ada."""
    if tipe == "PERSONEL":
        rows = _query_satu("SELECT kode_personel, nama_personel, is_blacklisted FROM personel WHERE id_personel = ?", id_target)
        if not rows:
            raise ValueError("Target tidak ditemukan")
        r = rows[0]
        return (f"{r['kode_personel']} · {r['nama_personel']}" if r["kode_personel"] else r["nama_personel"]), bool(r["is_blacklisted"])
    rows = _query_satu("SELECT no_plat, is_blacklisted FROM kendaraan WHERE id_kendaraan = ?", id_target)
    if not rows:
        raise ValueError("Target tidak ditemukan")
    return rows[0]["no_plat"], bool(rows[0]["is_blacklisted"])


def get_blacklist(id_blacklist):
    rows = _query_satu("""SELECT b.id_blacklist, b.tipe_entitas, b.id_personel, b.id_kendaraan, b.dicabut_at,
                                 COALESCE(p.nama_personel, k.no_plat) AS nama, p.nik, b.nama_alias, b.kategori,
                                 COALESCE(b.no_plat_terkait, k.no_plat) AS no_plat, c.nama_supplier AS supplier,
                                 a.nama_supplier AS pengangkutan
                          FROM blacklist b LEFT JOIN personel p ON p.id_personel = b.id_personel
                          LEFT JOIN kendaraan k ON k.id_kendaraan = b.id_kendaraan
                          LEFT JOIN mitra c ON c.id_supplier = b.id_customer_terkait
                          LEFT JOIN mitra a ON a.id_supplier = b.id_pengangkutan_terkait WHERE b.id_blacklist = ?""", id_blacklist)
    return rows[0] if rows else None


def _query_satu(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def cabut_blacklist(id_blacklist, alasan, user_id):
    """Blacklist dicabut (hasil persetujuan). Baris tetap ada; target bebas bila tidak ada blacklist aktif lain.
    Trigger blacklist permanen hanya mengizinkan lewat SESSION_CONTEXT cabut_blacklist = 1 (migrasi 027)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT tipe_entitas, id_personel, id_kendaraan, dicabut_at FROM blacklist WITH (UPDLOCK) WHERE id_blacklist = ?",
                       id_blacklist)
        r = cursor.fetchone()
        if r is None:
            raise ValueError("Blacklist tidak ditemukan")
        if r.dicabut_at is not None:
            raise ValueError("Blacklist ini sudah dicabut")
        tabel, kolom, id_target = (("personel", "id_personel", r.id_personel) if r.tipe_entitas == "PERSONEL"
                                   else ("kendaraan", "id_kendaraan", r.id_kendaraan))
        cursor.execute("UPDATE blacklist SET dicabut_at = GETDATE(), dicabut_oleh = ?, alasan_cabut = ? WHERE id_blacklist = ?",
                       user_id, (alasan or "")[:500] or None, id_blacklist)
        cursor.execute(f"SELECT COUNT(*) FROM blacklist WHERE {kolom} = ? AND dicabut_at IS NULL", id_target)
        if cursor.fetchone()[0] == 0:
            cursor.execute("EXEC sp_set_session_context N'cabut_blacklist', 1")
            cursor.execute(f"UPDATE {tabel} SET is_blacklisted = 0 WHERE {kolom} = ?", id_target)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.cursor().execute("EXEC sp_set_session_context N'cabut_blacklist', NULL")
        except Exception:       # noqa: BLE001 - koneksi sudah tertutup
            pass
        conn.close()


def mitra_aktif(id_supplier):
    """Nama mitra aktif, atau None."""
    rows = _query_satu("SELECT nama_supplier FROM mitra WHERE id_supplier = ? AND is_active = 1", id_supplier)
    return rows[0]["nama_supplier"] if rows else None
