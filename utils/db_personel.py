"""Query tabel personel & personel_audit_logs (menu Face Recognition > Personel)."""
from datetime import datetime
from utils.db_utils import get_connection, _rows_to_dicts, hitung_hash_driver
from utils.personel_utils import PREFIX_KODE, kode_berikutnya
from utils.face_cache import invalidate as reset_cache_wajah

KOLOM_PERSONEL = """p.id_personel, p.kode_personel, p.nik, p.nama_personel, p.no_sim, p.kategori,
                    p.is_blacklisted, p.foto_path, p.foto_sumber, p.is_updated, p.is_active, p.updated_at"""


def _normalisasi(r):
    for k in ("is_blacklisted", "is_updated", "is_active"):
        if k in r:
            r[k] = bool(r[k])
    if isinstance(r.get("updated_at"), datetime):
        r["updated_at"] = r["updated_at"].strftime("%Y-%m-%d %H:%M")
    return r


def get_daftar_personel(kategori=None, cari=None, hanya_blacklist=False, batas=200):
    sql = f"SELECT TOP (?) {KOLOM_PERSONEL} FROM personel p WHERE p.is_active = 1"
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
    cursor.execute(f"SELECT {KOLOM_PERSONEL} FROM personel p WHERE p.id_personel = ?", id_personel)
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
    """lama / baru: dict {kode_personel, nik, nama, no_sim} (None untuk TAMBAH)."""
    lama = lama or {}
    hash_audit = hitung_hash_driver(baru.get("nik"), baru.get("nama"), baru.get("no_sim"), datetime.now())
    cursor.execute(
        """INSERT INTO personel_audit_logs
           (id_personel, aksi, kode_personel_lama, kode_personel_baru, nik_lama, nik_baru, nama_lama, nama_baru,
            no_sim_lama, no_sim_baru, hash_audit, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        id_personel, aksi, lama.get("kode_personel"), baru.get("kode_personel"), lama.get("nik"), baru.get("nik"),
        lama.get("nama"), baru.get("nama"), lama.get("no_sim"), baru.get("no_sim"), hash_audit, user_id)


def insert_personel(nik, nama, no_sim, kategori, kode, embedding_binary, foto_path, foto_sumber, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO personel (kode_personel, nik, nama_personel, no_sim, kategori, face_embedding_data,
                                 foto_path, foto_sumber)
           OUTPUT INSERTED.id_personel
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        kode or None, nik, nama, no_sim or None, kategori, embedding_binary, foto_path, foto_sumber)
    id_personel = cursor.fetchone()[0]
    if user_id:
        _catat_audit(cursor, id_personel, "TAMBAH", None,
                     {"kode_personel": kode or None, "nik": nik, "nama": nama, "no_sim": no_sim or None}, user_id)
    conn.commit()
    conn.close()
    reset_cache_wajah()
    return id_personel


def update_personel(id_personel, kode, nik, nama, no_sim, kategori, user_id,
                    embedding_binary=None, foto_path=None, foto_sumber=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT kode_personel, nik, nama_personel, no_sim FROM personel WHERE id_personel = ?", id_personel)
    r = cursor.fetchone()
    lama = {"kode_personel": r.kode_personel, "nik": r.nik, "nama": r.nama_personel, "no_sim": r.no_sim}
    baru = {"kode_personel": kode or None, "nik": nik, "nama": nama, "no_sim": no_sim or None}
    hash_baru = hitung_hash_driver(nik, nama, no_sim, datetime.now())

    set_foto = ", face_embedding_data = ?, foto_path = ?, foto_sumber = ?" if embedding_binary is not None else ""
    params = [kode or None, nik, nama, no_sim or None, kategori, hash_baru]
    if embedding_binary is not None:
        params += [embedding_binary, foto_path, foto_sumber]
    cursor.execute(f"""UPDATE personel SET kode_personel = ?, nik = ?, nama_personel = ?, no_sim = ?, kategori = ?,
                       is_updated = 1, current_hash = ?, updated_at = GETDATE(){set_foto}
                       WHERE id_personel = ?""", *params, id_personel)
    _catat_audit(cursor, id_personel, "UPDATE", lama, baru, user_id)
    conn.commit()
    conn.close()
    if embedding_binary is not None:
        reset_cache_wajah()


def hapus_personel(id_personel, user_id):
    """Soft delete: wajah tidak dikenali lagi & dilepas dari truk; riwayat tiket/absensi tetap."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT kode_personel, nik, nama_personel, no_sim FROM personel WHERE id_personel = ?", id_personel)
    r = cursor.fetchone()
    data = {"kode_personel": r.kode_personel, "nik": r.nik, "nama": r.nama_personel, "no_sim": r.no_sim}
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
        SELECT TOP (?) a.id_log, a.id_personel, a.aksi, a.kode_personel_lama, a.kode_personel_baru, a.nik_lama, a.nik_baru,
               a.nama_lama, a.nama_baru, a.no_sim_lama, a.no_sim_baru, a.updated_at, u.nama AS oleh, lv.kode AS role_oleh,
               p.kode_personel, p.nama_personel
        FROM personel_audit_logs a
        JOIN users u ON a.updated_by = u.id_user
        JOIN level lv ON lv.id_level = u.id_level
        JOIN personel p ON a.id_personel = p.id_personel
        WHERE a.updated_at >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
        ORDER BY a.updated_at DESC
    """, batas, -(hari - 1))
    data = _rows_to_dicts(cursor)
    conn.close()
    return data
