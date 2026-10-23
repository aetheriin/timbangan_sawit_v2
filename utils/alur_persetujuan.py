"""Admin › Alur Persetujuan (migrasi 043): susunan tahap persetujuan per jenis pengajuan + kategori target.
Tiap tahap = satu peran (departemen + jabatan); dipakai utils/persetujuan.py saat pengajuan dibuat."""
from utils import hak_akses
from utils.db_utils import get_connection, _rows_to_dicts
from utils.persetujuan import JENIS, MENU_JENIS

KATEGORI_KENDARAAN = ("KENDARAAN", "Kendaraan")
MAKS_TAHAP = 10


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def daftar_kategori():
    """Pilihan kategori target: kategori personel aktif + Kendaraan."""
    return ([{"kode": r["kode"], "nama": r["nama"]}
             for r in _query("SELECT kode, nama FROM kategori_personel WHERE is_active = 1 ORDER BY nama")]
            + [{"kode": KATEGORI_KENDARAAN[0], "nama": KATEGORI_KENDARAAN[1]}])


def daftar():
    """Semua alur beserta tahapnya (peran, jumlah pengguna aktif, peran boleh membuka menu pengajuan)."""
    alur = _query("""SELECT a.id_alur_persetujuan, a.jenis, a.kategori, a.keterangan, a.is_active, kp.nama AS nama_kategori
                     FROM alur_persetujuan a LEFT JOIN kategori_personel kp ON kp.kode = a.kategori
                     ORDER BY a.jenis, CASE WHEN a.kategori IS NULL THEN 1 ELSE 0 END, kp.nama, a.kategori""")
    tahap = _query("""SELECT t.id_alur_persetujuan, t.urutan, t.id_level, l.LevelDetName AS nama, l.DeptID AS id_department, l.LevelID AS id_jabatan,
                             (SELECT COUNT(*) FROM Users u WHERE u.UserLevelID = l.LevelDetID AND u.Active = 1) AS jumlah_user
                      FROM alur_persetujuan_tahap t JOIN LevelDetails l ON l.LevelDetID = t.id_level ORDER BY t.id_alur_persetujuan, t.urutan""")
    akses = hak_akses.peta_akses()
    per_alur = {}
    for t in tahap:
        per_alur.setdefault(t["id_alur_persetujuan"], []).append(t)
    for a in alur:
        menu = MENU_JENIS.get(a["jenis"], "")
        a["nama_jenis"] = JENIS.get(a["jenis"], a["jenis"])
        if a["kategori"] == KATEGORI_KENDARAAN[0]:
            a["nama_kategori"] = KATEGORI_KENDARAAN[1]
        a["tahap"] = [{**t, "bisa_lihat": bool(akses.get(t["id_level"], {}).get(menu, {}).get("lihat"))}
                      for t in per_alur.get(a["id_alur_persetujuan"], [])]
    return alur


def simpan(id_alur, jenis, kategori, keterangan, daftar_level):
    """Tambah / ubah alur; tahap diganti seluruhnya sesuai urutan daftar_level. Kembalikan id alur."""
    if jenis not in JENIS:
        raise ValueError("Jenis pengajuan tidak dikenal")
    if kategori and kategori not in {k["kode"] for k in daftar_kategori()}:
        raise ValueError("Kategori tidak dikenal")
    if not daftar_level:
        raise ValueError("Tambahkan minimal satu tahap")
    if len(daftar_level) > MAKS_TAHAP:
        raise ValueError(f"Maksimal {MAKS_TAHAP} tahap")
    if len(set(daftar_level)) != len(daftar_level):
        raise ValueError("Peran yang sama tidak boleh muncul di dua tahap")
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""SELECT id_alur_persetujuan FROM alur_persetujuan WITH (UPDLOCK, HOLDLOCK)
                          WHERE jenis = ? AND ISNULL(kategori, '') = ? AND id_alur_persetujuan <> ?""",
                       jenis, kategori or "", id_alur or 0)
        if cursor.fetchone():
            raise ValueError("Alur untuk jenis & kategori ini sudah ada. Ubah alur yang sudah ada.")
        if id_alur:
            cursor.execute("UPDATE alur_persetujuan SET jenis = ?, kategori = ?, keterangan = ? WHERE id_alur_persetujuan = ?",
                           jenis, kategori, keterangan, id_alur)
            if cursor.rowcount == 0:
                raise ValueError("Alur tidak ditemukan")
            cursor.execute("DELETE FROM alur_persetujuan_tahap WHERE id_alur_persetujuan = ?", id_alur)
        else:
            cursor.execute("""INSERT INTO alur_persetujuan (jenis, kategori, keterangan) OUTPUT INSERTED.id_alur_persetujuan
                              VALUES (?, ?, ?)""", jenis, kategori, keterangan)
            id_alur = cursor.fetchone()[0]
        for n, id_level in enumerate(daftar_level, 1):
            cursor.execute("INSERT INTO alur_persetujuan_tahap (id_alur_persetujuan, urutan, id_level) VALUES (?, ?, ?)",
                           id_alur, n, id_level)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return id_alur


def set_aktif(id_alur, aktif):
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE alur_persetujuan SET is_active = ? WHERE id_alur_persetujuan = ?", 1 if aktif else 0, id_alur)
        conn.commit()
    finally:
        conn.close()


def hapus(id_alur):
    """Hapus alur (pengajuan yang sedang berjalan tidak terpengaruh: tahapnya sudah disalin)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM alur_persetujuan_tahap WHERE id_alur_persetujuan = ?", id_alur)
        cursor.execute("DELETE FROM alur_persetujuan WHERE id_alur_persetujuan = ?", id_alur)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
