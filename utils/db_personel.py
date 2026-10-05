"""Query personel (menu Face Recognition > Personel, Data Master > Driver).

Sejak migrasi 009: SIM di personel_sim, wajah di personel_wajah. Dibaca lewat view v_personel
(kolom no_sim, foto_path, face_embedding_data tetap ada di view), ditulis lewat simpan_sim / simpan_wajah."""
from datetime import datetime
from utils.db_utils import get_connection, _rows_to_dicts, hitung_hash_driver
from utils.personel_utils import PREFIX_KODE, kode_berikutnya
from utils.face_cache import invalidate as reset_cache_wajah
from utils import log_aktivitas

KOLOM_PERSONEL = """p.id_personel, p.kode_personel, p.nik, p.nama_personel, p.no_sim, p.kategori,
                    p.id_jenis_sim, p.kode_jenis_sim, p.sim_berlaku_sampai,
                    p.is_blacklisted, p.foto_path, p.foto_sumber, p.is_updated, p.is_active, p.updated_at"""


def _normalisasi(r):
    for k in ("is_blacklisted", "is_updated", "is_active"):
        if k in r:
            r[k] = bool(r[k])
    if isinstance(r.get("updated_at"), datetime):
        r["updated_at"] = r["updated_at"].strftime("%Y-%m-%d %H:%M")
    if r.get("sim_berlaku_sampai") is not None:
        r["sim_berlaku_sampai"] = r["sim_berlaku_sampai"].isoformat()
    return r


def get_daftar_personel(kategori=None, cari=None, hanya_blacklist=False, batas=200):
    sql = f"SELECT TOP (?) {KOLOM_PERSONEL} FROM v_personel p WHERE p.is_active = 1"
    params = [batas]
    if kategori:
        sql += " AND p.kategori = ?"
        params.append(kategori)
    if hanya_blacklist:
        sql += " AND p.is_blacklisted = 1"
    if cari:
        sql += " AND (p.kode_personel LIKE ? OR p.nik LIKE ? OR p.nama_personel LIKE ? OR CAST(p.id_personel AS VARCHAR) = ?)"
        pola = f"%{cari}%"
        params += [pola, pola, pola, cari.lstrip("0") or "0"]
    sql += " ORDER BY p.id_personel"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, *params)
    data = [_normalisasi(r) for r in _rows_to_dicts(cursor)]
    conn.close()
    return data


def get_personel(id_personel):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {KOLOM_PERSONEL} FROM v_personel p WHERE p.id_personel = ?", id_personel)
    data = _rows_to_dicts(cursor)
    conn.close()
    return _normalisasi(data[0]) if data else None


def cek_kode_ada(kode, exclude_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_personel FROM personel WHERE kode_personel = ? AND id_personel <> ?",
                   kode, exclude_id or 0)
    ada = cursor.fetchone() is not None
    conn.close()
    return ada


def saran_kode_personel():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT kode_personel FROM personel WHERE kode_personel LIKE ?", f"{PREFIX_KODE}%")
    kode = [r.kode_personel for r in cursor.fetchall()]
    conn.close()
    return kode_berikutnya(kode)


def _catat_audit(cursor, id_personel, aksi, lama, baru, user_id):
    """lama / baru: dict {kode_personel, nik, nama, no_sim} (lama None untuk TAMBAH). Dicatat di log_aktivitas."""
    log_aktivitas.catat("PERSONEL", aksi, tabel="personel", id_baris=id_personel, lama=lama, baru=baru,
                        user_id=user_id, cursor=cursor)


# ===== SIM & WAJAH (dipakai juga oleh driver dari Form Security, utils/db_utils.py) =====
def sim_dipakai(no_sim, exclude_id=None):
    """No. SIM aktif milik personel lain."""
    conn = get_connection()
    try:
        row = conn.cursor().execute("""SELECT TOP 1 id_personel FROM personel_sim
                                       WHERE no_sim = ? AND is_active = 1 AND id_personel <> ?""",
                                    no_sim, exclude_id or 0).fetchone()
        return row is not None
    finally:
        conn.close()


def simpan_sim(cursor, id_personel, no_sim, id_jenis_sim=None, berlaku_sampai=None, user_id=None):
    """SIM aktif personel. Kosong -> SIM aktif dinonaktifkan. Nomor sama -> jenis & masa berlaku diperbarui bila diisi.
    Nomor berbeda -> SIM lama nonaktif (riwayat tetap), SIM baru ditambah. Jenis kosong = BELUM_DIISI (data cepat dari pos)."""
    cursor.execute("SELECT id_sim, no_sim FROM personel_sim WHERE id_personel = ? AND is_active = 1", id_personel)
    aktif = cursor.fetchall()
    sama = next((x for x in aktif if no_sim and x.no_sim == no_sim), None)
    for x in aktif:
        if x is not sama:
            cursor.execute("UPDATE personel_sim SET is_active = 0 WHERE id_sim = ?", x.id_sim)
    if not no_sim:
        return
    if sama:
        if id_jenis_sim:
            cursor.execute("UPDATE personel_sim SET id_jenis_sim = ?, berlaku_sampai = ? WHERE id_sim = ?",
                           id_jenis_sim, berlaku_sampai, sama.id_sim)
        return
    cursor.execute("""INSERT INTO personel_sim (id_personel, id_jenis_sim, no_sim, berlaku_sampai, created_by)
                      VALUES (?, COALESCE(?, (SELECT id_jenis_sim FROM jenis_sim WHERE kode = 'BELUM_DIISI')), ?, ?, ?)""",
                   id_personel, id_jenis_sim, no_sim, berlaku_sampai, user_id)


def simpan_wajah(cursor, id_personel, embedding_binary, foto_path, sumber, user_id=None):
    """Wajah baru menjadi wajah utama; wajah lama dinonaktifkan (tidak dikenali lagi, riwayat & foto tetap)."""
    cursor.execute("UPDATE personel_wajah SET is_utama = 0, is_active = 0 WHERE id_personel = ? AND is_active = 1",
                   id_personel)
    cursor.execute("""INSERT INTO personel_wajah (id_personel, embedding, foto_path, sumber, created_by)
                      VALUES (?, ?, ?, ?, ?)""", id_personel, embedding_binary, foto_path, sumber, user_id)


def _data_lama(cursor, id_personel):
    cursor.execute("SELECT kode_personel, nik, nama_personel, no_sim FROM v_personel WHERE id_personel = ?", id_personel)
    r = cursor.fetchone()
    return {"kode_personel": r.kode_personel, "nik": r.nik, "nama": r.nama_personel, "no_sim": r.no_sim}


def insert_personel(nik, nama, no_sim, kategori, kode, embedding_binary, foto_path, foto_sumber, user_id,
                    id_jenis_sim=None, sim_berlaku=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO personel (kode_personel, nik, nama_personel, kategori, current_hash)
           OUTPUT INSERTED.id_personel
           VALUES (?, ?, ?, ?, ?)""",
        kode or None, nik, nama, kategori, hitung_hash_driver(nik, nama, no_sim, datetime.now()))
    id_personel = cursor.fetchone()[0]
    simpan_sim(cursor, id_personel, no_sim or None, id_jenis_sim, sim_berlaku, user_id)
    if embedding_binary is not None:
        simpan_wajah(cursor, id_personel, embedding_binary, foto_path, foto_sumber, user_id)
    if user_id:
        _catat_audit(cursor, id_personel, "TAMBAH", None,
                     {"kode_personel": kode or None, "nik": nik, "nama": nama, "no_sim": no_sim or None}, user_id)
    conn.commit()
    conn.close()
    reset_cache_wajah()
    return id_personel


def update_personel(id_personel, kode, nik, nama, no_sim, kategori, user_id,
                    embedding_binary=None, foto_path=None, foto_sumber=None, id_jenis_sim=None, sim_berlaku=None):
    conn = get_connection()
    cursor = conn.cursor()
    lama = _data_lama(cursor, id_personel)
    baru = {"kode_personel": kode or None, "nik": nik, "nama": nama, "no_sim": no_sim or None}
    hash_baru = hitung_hash_driver(nik, nama, no_sim, datetime.now())
    cursor.execute("""UPDATE personel SET kode_personel = ?, nik = ?, nama_personel = ?, kategori = ?,
                      is_updated = 1, current_hash = ?, updated_at = GETDATE()
                      WHERE id_personel = ?""", kode or None, nik, nama, kategori, hash_baru, id_personel)
    simpan_sim(cursor, id_personel, no_sim or None, id_jenis_sim, sim_berlaku, user_id)
    if embedding_binary is not None:
        simpan_wajah(cursor, id_personel, embedding_binary, foto_path, foto_sumber, user_id)
    _catat_audit(cursor, id_personel, "UPDATE", lama, baru, user_id)
    conn.commit()
    conn.close()
    if embedding_binary is not None:
        reset_cache_wajah()


def hapus_personel(id_personel, user_id):
    """Soft delete: wajah tidak dikenali lagi & dilepas dari truk; riwayat tiket/absensi tetap."""
    conn = get_connection()
    cursor = conn.cursor()
    data = _data_lama(cursor, id_personel)
    cursor.execute("UPDATE personel SET is_active = 0, updated_at = GETDATE() WHERE id_personel = ?", id_personel)
    cursor.execute("""UPDATE kendaraan_driver SET is_active = 0, is_utama = 0, updated_at = GETDATE()
                      WHERE id_driver = ?""", id_personel)
    _catat_audit(cursor, id_personel, "HAPUS", data, data, user_id)
    conn.commit()
    conn.close()
    reset_cache_wajah()


def get_riwayat_perubahan_personel(hari=7, batas=300):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP (?) l.id_log, p.id_personel, l.aksi,
               JSON_VALUE(l.nilai_lama, '$.kode_personel') AS kode_personel_lama,
               JSON_VALUE(l.nilai_baru, '$.kode_personel') AS kode_personel_baru,
               JSON_VALUE(l.nilai_lama, '$.nik') AS nik_lama, JSON_VALUE(l.nilai_baru, '$.nik') AS nik_baru,
               JSON_VALUE(l.nilai_lama, '$.nama') AS nama_lama, JSON_VALUE(l.nilai_baru, '$.nama') AS nama_baru,
               JSON_VALUE(l.nilai_lama, '$.no_sim') AS no_sim_lama, JSON_VALUE(l.nilai_baru, '$.no_sim') AS no_sim_baru,
               CAST(l.waktu AS DATETIME) AS updated_at, u.nama AS oleh, lv.kode AS role_oleh,
               p.kode_personel, p.nama_personel
        FROM log_aktivitas l
        JOIN personel p ON p.id_personel = TRY_CAST(l.id_baris AS INT)
        LEFT JOIN akun u ON l.id_user = u.id_user
        LEFT JOIN level lv ON lv.id_level = u.id_level
        WHERE l.kategori = 'PERSONEL' AND l.waktu >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
        ORDER BY l.id_log DESC
    """, batas, -(hari - 1))
    data = _rows_to_dicts(cursor)
    conn.close()
    return data


# ===== MASTER KATEGORI & JENIS SIM =====
def daftar_kategori():
    """{kode: {nama, wajib_sim, boleh_akun}} kategori aktif."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT kode, nama, wajib_sim, boleh_akun FROM kategori_personel WHERE is_active = 1")
        return {r["kode"]: {**r, "wajib_sim": bool(r["wajib_sim"]), "boleh_akun": bool(r["boleh_akun"])}
                for r in _rows_to_dicts(cursor)}
    finally:
        conn.close()


def daftar_jenis_sim():
    """Pilihan jenis SIM di form (tanpa penanda BELUM_DIISI)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id_jenis_sim, kode, nama FROM jenis_sim WHERE is_active = 1 ORDER BY id_jenis_sim")
        return _rows_to_dicts(cursor)
    finally:
        conn.close()
