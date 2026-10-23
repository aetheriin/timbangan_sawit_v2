"""Persetujuan (migrasi 027, disederhanakan di 029, berjenjang di 043): pengajuan -> disetujui -> dijalankan.

Berjenjang (Admin › Alur Persetujuan): alur per jenis + kategori target (mis. Tambah blacklist · Driver), tiap
tahap = satu peran (departemen + jabatan). Tahap disalin ke pengajuan_tahap saat diajukan.
- Penyetuju tahap = pengguna dengan peran itu di PT pengajuan (kantor pusat: PT yang dikelolanya).
- Tahap yang perannya dipegang pengaju sendiri dilewati otomatis. Ditolak di tahap mana pun -> berhenti.
- Tahap terakhir disetujui -> pengajuan dijalankan. Setiap tahap naik, peran tahap berikutnya diberi notifikasi.

Tanpa alur untuk jenis/kategori itu (cara lama, satu tahap):

- Penyetuju = siapa pun yang jabatannya punya hak "Setujui" di menu terkait (Admin › Level & Hak Akses), di PT
  pengajuan (user kantor pusat: PT yang dikelolanya). Tidak ada pengaturan penyetuju terpisah; mengikuti hak akses
  terbaru. Yang mengajukan tidak bisa menyetujui pengajuannya sendiri.
- Belum ada jabatan dengan hak Setujui di menu itu -> pengajuan langsung dijalankan.
- Notifikasi: ke jabatan yang punya hak Setujui di PT itu saat diajukan, dan ke pengaju saat selesai.
  Diklik -> tab Persetujuan di halaman menu terkait (mis. /blacklist?tab=persetujuan&id=<id>).
Jenis baru: tambahkan ke JENIS & MENU_JENIS lalu daftarkan pelaksananya dengan @pelaksana("KODE")."""
import json
from datetime import datetime

from utils import hak_akses, notifikasi
from utils.area import company_user
from utils.cache import cache_ttl
from utils.db_kunjungan import area_akun
from utils.db_organisasi import company_area
from utils.db_utils import get_connection, _rows_to_dicts

JENIS = {
    "BLACKLIST_TAMBAH": "Tambah blacklist",
    "BLACKLIST_HAPUS": "Hapus blacklist",
    "KOREKSI_TIKET": "Koreksi tiket",
}
MENU_JENIS = {"BLACKLIST_TAMBAH": "BLACKLIST", "BLACKLIST_HAPUS": "BLACKLIST",       # hak Setujui dicek di menu ini
              "KOREKSI_TIKET": "LIST"}
TAUTAN_MENU = {"BLACKLIST": "/blacklist?tab=persetujuan", "LIST": "/weighbridge?view=list&bagian=koreksi"}
_PELAKSANA, _SAAT_DITOLAK = {}, {}


def pelaksana(jenis, saat_ditolak=None):
    """Daftarkan fungsi(data, id_pengaju, id_penyetuju) yang dijalankan saat pengajuan disetujui penuh."""
    def daftar(fn):
        _PELAKSANA[jenis] = fn
        if saat_ditolak:
            _SAAT_DITOLAK[jenis] = saat_ditolak
        return fn
    return daftar


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


# ===== Alur berjenjang (migrasi 043) =====
def tahap_alur(jenis, kategori=None):
    """[id_level, ...] alur aktif untuk jenis + kategori (cadangan: alur "semua kategori"); None = tidak ada alur."""
    try:
        rows = _query("""SELECT a.kategori, t.urutan, t.id_level
                         FROM alur_persetujuan a JOIN alur_persetujuan_tahap t ON t.id_alur_persetujuan = a.id_alur_persetujuan
                         WHERE a.jenis = ? AND a.is_active = 1 AND (a.kategori = ? OR a.kategori IS NULL)
                         ORDER BY t.urutan""", jenis, kategori or "")
    except Exception:       # noqa: BLE001 - migrasi 043 belum dijalankan -> cara lama
        return None
    khusus = [r["id_level"] for r in rows if r["kategori"]]
    return khusus or [r["id_level"] for r in rows if not r["kategori"]] or None


def peran_di_alur(id_level, menu):
    """Peran ini menjadi salah satu tahap alur aktif untuk jenis pengajuan menu itu (List Request: tab bawaan)."""
    jenis = [j for j, m in MENU_JENIS.items() if m == menu] or ["-"]
    try:
        return bool(_query(f"""SELECT TOP 1 1 AS ada FROM alur_persetujuan a
                               JOIN alur_persetujuan_tahap t ON t.id_alur_persetujuan = a.id_alur_persetujuan
                               WHERE a.is_active = 1 AND t.id_level = ? AND a.jenis IN ({', '.join('?' * len(jenis))})""",
                            id_level, *jenis))
    except Exception:       # noqa: BLE001 - sebelum migrasi 043
        return False


def nama_tahap(daftar_level):
    nama = _nama_jabatan()
    return [nama.get(i, "-") for i in daftar_level]


def _level_user(user_id):
    rows = _query("SELECT UserLevelID AS id_level FROM Users WHERE UserID = ?", user_id)
    return rows[0]["id_level"] if rows else None


def _tahap_pengajuan(ids):
    """{id_pengajuan: [id_level tahap 1, tahap 2, ...]} untuk pengajuan berjenjang."""
    hasil = {}
    ids = list(ids)
    for i in range(0, len(ids), 500):
        bagian = ids[i:i + 500]
        try:
            rows = _query(f"""SELECT id_pengajuan, urutan, id_level FROM pengajuan_tahap
                              WHERE id_pengajuan IN ({', '.join('?' * len(bagian))}) ORDER BY id_pengajuan, urutan""", *bagian)
        except Exception:   # noqa: BLE001 - sebelum migrasi 043
            return {}
        for r in rows:
            hasil.setdefault(r["id_pengajuan"], []).append(r["id_level"])
    return hasil


def _tahap_berikut(tahap, mulai, level_pengaju):
    """Nomor tahap (1-based) berikutnya mulai dari `mulai` yang perannya bukan peran pengaju; None = habis."""
    for n in range(mulai, len(tahap) + 1):
        if tahap[n - 1] != level_pengaju:
            return n
    return None


def _notif_tahap(cursor, p, id_level):
    judul = f"Persetujuan {JENIS[p['jenis']].lower()} menunggu Anda"
    notifikasi.buat(MENU_JENIS[p["jenis"]], judul, p["judul"], tautan(p["jenis"], p["id_pengajuan"]), p["id_comp_area"],
                    cursor=cursor, id_level=id_level, id_company=p["id_company"])


# ===== Pengajuan =====
def tautan(jenis, id_pengajuan):
    return f"{TAUTAN_MENU[MENU_JENIS[jenis]]}&id={id_pengajuan}"


def penyetuju(jenis):
    """id jabatan yang punya hak Setujui untuk jenis pengajuan ini."""
    return hak_akses.jabatan_dengan(MENU_JENIS[jenis], "setujui")


def _notif_penyetuju(cursor, p, daftar_jabatan, daftar_user=()):
    """Ke jabatan yang punya hak Setujui, ditambah pengguna yang diberi hak Setujui khusus (Kelola Pengguna)."""
    judul = f"Persetujuan {JENIS[p['jenis']].lower()} menunggu Anda"
    for id_level in daftar_jabatan:
        notifikasi.buat(MENU_JENIS[p["jenis"]], judul, p["judul"], tautan(p["jenis"], p["id_pengajuan"]), p["id_comp_area"],
                        cursor=cursor, id_level=id_level, id_company=p["id_company"])
    for id_user in daftar_user:
        notifikasi.buat(MENU_JENIS[p["jenis"]], judul, p["judul"], tautan(p["jenis"], p["id_pengajuan"]), p["id_comp_area"],
                        cursor=cursor, id_user=id_user)


def _riwayat(cursor, id_pengajuan, langkah, aksi, id_user, id_level=None, catatan=None):
    cursor.execute("""INSERT INTO pengajuan_riwayat (id_pengajuan, langkah, aksi, id_level, id_user, catatan)
                      VALUES (?, ?, ?, ?, ?, ?)""", id_pengajuan, langkah, aksi, id_level, id_user, catatan)


def _pengaju_berhak(jenis, user_id):
    """Pengaju (pengguna yang sedang login) punya hak Setujui di menu jenis ini."""
    from flask_login import current_user
    try:
        user = current_user if getattr(current_user, "id", None) == user_id else None
    except RuntimeError:        # di luar request
        user = None
    return bool(user) and hak_akses.boleh(MENU_JENIS[jenis], "setujui", user=user)


def _catat_langsung(jenis, target, judul, alasan, data, user_id, kategori=None, tahap=None):
    """Jejak pengajuan yang langsung disetujui (pengaju berhak menyetujui / semua tahap dipegang pengaju)."""
    id_area = area_akun(user_id)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        total = len(tahap) if tahap else 1
        cursor.execute(f"""SET NOCOUNT ON; INSERT INTO pengajuan (jenis, total_langkah, langkah, status, selesai_at, id_company,
                                                                  id_comp_area, target, judul, alasan, data, diajukan_oleh
                                                                  {", kategori" if kategori else ""})
                           VALUES (?, ?, ?, 'DISETUJUI', GETDATE(), ?, ?, ?, ?, ?, ?, ?{", ?" if kategori else ""});
                           SELECT CAST(SCOPE_IDENTITY() AS INT)""",
                       jenis, total, total, company_area().get(id_area), id_area, target, judul[:200],
                       (alasan or "")[:500] or None, json.dumps(data, default=str), user_id, *([kategori] if kategori else []))
        id_p = cursor.fetchone()[0]
        _riwayat(cursor, id_p, 0, "DIAJUKAN", user_id, catatan=alasan)
        if tahap:
            for n, id_level in enumerate(tahap, 1):
                cursor.execute("INSERT INTO pengajuan_tahap (id_pengajuan, urutan, id_level) VALUES (?, ?, ?)", id_p, n, id_level)
                _riwayat(cursor, id_p, n, "DILEWATI", user_id, id_level, "Peran pengaju sendiri")
        else:
            _riwayat(cursor, id_p, 1, "DISETUJUI", user_id, catatan="Disetujui langsung: pengaju memiliki hak Setujui")
        conn.commit()
    except Exception:       # noqa: BLE001 - jejak gagal tidak membatalkan yang sudah dijalankan
        conn.rollback()
        import logging
        logging.getLogger("weighbridge").exception("Gagal mencatat pengajuan langsung %s", jenis)
    finally:
        conn.close()


def _bersih(data):
    return {k: v for k, v in data.items() if not k.startswith("_")}


def ajukan(jenis, target, judul, alasan, data, user_id, kategori=None):
    """Buat pengajuan. kategori = kategori target (memilih alur berjenjang). Tanpa penyetuju -> langsung dijalankan.
    Kembalikan (status, nama penyetuju yang ditunggu)."""
    if jenis not in JENIS:
        raise ValueError("Jenis pengajuan tidak dikenal")
    tahap = tahap_alur(jenis, kategori)
    if tahap:
        return _ajukan_berjenjang(jenis, target, judul, alasan, data, user_id, kategori, tahap)
    if _pengaju_berhak(jenis, user_id):
        # Pengaju sendiri punya hak Setujui: tidak perlu menunggu orang lain (dan tidak menyetujui sendiri lewat
        # antrean). Langsung dijalankan, tetap tercatat sebagai pengajuan yang disetujui.
        _PELAKSANA[jenis](_bersih(data), user_id, user_id)
        _catat_langsung(jenis, target, judul, alasan, data, user_id, kategori)
        return "DISETUJUI", None
    langkah = penyetuju(jenis)
    khusus = [i for i in hak_akses.pengguna_khusus_dengan(MENU_JENIS[jenis], "setujui") if i != user_id]
    if not langkah and not khusus:
        _PELAKSANA[jenis](_bersih(data), user_id, user_id)
        return "DISETUJUI", None
    id_area = area_akun(user_id)
    id_company = company_area().get(id_area)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_pengajuan FROM pengajuan WITH (UPDLOCK, HOLDLOCK) WHERE jenis = ? AND target = ? AND status = 'MENUNGGU'",
                       jenis, target)
        if cursor.fetchone():
            raise ValueError("Sudah ada pengajuan yang sama dan masih menunggu persetujuan")
        cursor.execute("""INSERT INTO pengajuan (jenis, total_langkah, id_company, id_comp_area, target, judul, alasan, data,
                                                 diajukan_oleh, kategori)
                          OUTPUT INSERTED.id_pengajuan VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       jenis, id_company, id_area, target, judul[:200], (alasan or "")[:500] or None,
                       json.dumps(data, default=str), user_id, kategori)
        id_p = cursor.fetchone()[0]
        _riwayat(cursor, id_p, 0, "DIAJUKAN", user_id, catatan=alasan)
        _notif_penyetuju(cursor, {"id_pengajuan": id_p, "jenis": jenis, "judul": judul,
                                  "id_comp_area": id_area, "id_company": id_company}, langkah, khusus)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return "MENUNGGU", ", ".join(_nama_jabatan().get(i, "-") for i in langkah)


def _ajukan_berjenjang(jenis, target, judul, alasan, data, user_id, kategori, tahap):
    level_pengaju = _level_user(user_id)
    mulai = _tahap_berikut(tahap, 1, level_pengaju)
    if mulai is None:           # semua tahap dipegang pengaju sendiri
        _PELAKSANA[jenis](_bersih(data), user_id, user_id)
        _catat_langsung(jenis, target, judul, alasan, data, user_id, kategori, tahap)
        return "DISETUJUI", None
    id_area = area_akun(user_id)
    id_company = company_area().get(id_area)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id_pengajuan FROM pengajuan WITH (UPDLOCK, HOLDLOCK) WHERE jenis = ? AND target = ? AND status = 'MENUNGGU'",
                       jenis, target)
        if cursor.fetchone():
            raise ValueError("Sudah ada pengajuan yang sama dan masih menunggu persetujuan")
        cursor.execute("""INSERT INTO pengajuan (jenis, total_langkah, langkah, id_company, id_comp_area, target, judul, alasan,
                                                 data, diajukan_oleh, kategori)
                          OUTPUT INSERTED.id_pengajuan VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       jenis, len(tahap), mulai, id_company, id_area, target, judul[:200], (alasan or "")[:500] or None,
                       json.dumps(data, default=str), user_id, kategori)
        id_p = cursor.fetchone()[0]
        _riwayat(cursor, id_p, 0, "DIAJUKAN", user_id, catatan=alasan)
        for n, id_level in enumerate(tahap, 1):
            cursor.execute("INSERT INTO pengajuan_tahap (id_pengajuan, urutan, id_level) VALUES (?, ?, ?)", id_p, n, id_level)
            if n < mulai:
                _riwayat(cursor, id_p, n, "DILEWATI", user_id, id_level, "Peran pengaju sendiri")
        _notif_tahap(cursor, {"id_pengajuan": id_p, "jenis": jenis, "judul": judul, "id_comp_area": id_area,
                              "id_company": id_company}, tahap[mulai - 1])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return "MENUNGGU", _nama_jabatan().get(tahap[mulai - 1], "-")


def _ambil(cursor, id_pengajuan):
    cursor.execute("SELECT * FROM pengajuan WITH (UPDLOCK) WHERE id_pengajuan = ?", id_pengajuan)
    rows = _rows_to_dicts(cursor)
    if not rows:
        raise ValueError("Pengajuan tidak ditemukan")
    p = rows[0]
    p["data"] = json.loads(p["data"] or "{}")
    p["tahap"] = _tahap_pengajuan([id_pengajuan]).get(id_pengajuan, [])
    return p


def boleh_setujui(p, user):
    """User boleh menyetujui / menolak pengajuan p: hak Setujui di menunya, PT sama, bukan pengaju sendiri."""
    if p["status"] != "MENUNGGU" or p["diajukan_oleh"] == user.id or getattr(user, "is_admin", False):
        return False
    if p.get("tahap"):          # berjenjang: hanya peran tahap yang sedang berjalan
        if p["tahap"][p["langkah"] - 1] != user.id_level:
            return False
    elif not hak_akses.boleh(MENU_JENIS.get(p["jenis"], ""), "setujui", user=user):
        return False
    pt = company_user(user.id)
    return pt is None or p["id_company"] in pt


def setujui(id_pengajuan, user, catatan=None):
    """Satu langkah disetujui. Langkah terakhir -> pengajuan dijalankan. Kembalikan pesan."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        p = _ambil(cursor, id_pengajuan)
        if not boleh_setujui(p, user):
            raise ValueError("Anda tidak memiliki hak untuk menyetujui pengajuan ini")
        conn.rollback()
    finally:
        conn.close()
    if p["tahap"]:
        berikut = _tahap_berikut(p["tahap"], p["langkah"] + 1, _level_user(p["diajukan_oleh"]))
        if berikut:
            _naik_tahap(p, berikut, user, catatan)
            return (f"Tahap {p['langkah']} disetujui. Pengajuan diteruskan ke "
                    f"{_nama_jabatan().get(p['tahap'][berikut - 1], '-')} (tahap {berikut}/{len(p['tahap'])}).")
    # Jalankan dulu, baru catat & tandai selesai (gagal dijalankan -> tetap menunggu, pesan ke penyetuju)
    data = _bersih(p["data"])
    _PELAKSANA[p["jenis"]](data, p["diajukan_oleh"], user.id)
    # Sisa tahap (bila ada) semuanya peran pengaju sendiri -> dicatat dilewati
    _selesai(p, "DISETUJUI", user, catatan, lewati=range(p["langkah"] + 1, len(p["tahap"]) + 1))
    return f"{JENIS[p['jenis']]} berhasil disetujui dan sudah berlaku."


def _naik_tahap(p, berikut, user, catatan):
    """Tahap berjalan disetujui -> pindah ke tahap `berikut` (tahap peran pengaju di antaranya dicatat dilewati)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE pengajuan SET langkah = ? WHERE id_pengajuan = ? AND status = 'MENUNGGU' AND langkah = ?",
                       berikut, p["id_pengajuan"], p["langkah"])
        if cursor.rowcount == 0:
            raise ValueError("Pengajuan ini sudah diproses oleh pengguna lain")
        _riwayat(cursor, p["id_pengajuan"], p["langkah"], "DISETUJUI", user.id, user.id_level, catatan)
        for n in range(p["langkah"] + 1, berikut):
            _riwayat(cursor, p["id_pengajuan"], n, "DILEWATI", p["diajukan_oleh"], p["tahap"][n - 1], "Peran pengaju sendiri")
        _notif_tahap(cursor, p, p["tahap"][berikut - 1])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def tolak(id_pengajuan, user, catatan):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        p = _ambil(cursor, id_pengajuan)
        if not boleh_setujui(p, user):
            raise ValueError("Anda tidak memiliki hak untuk menolak pengajuan ini")
        conn.rollback()
    finally:
        conn.close()
    _selesai(p, "DITOLAK", user, catatan)
    return f"Pengajuan {JENIS[p['jenis']].lower()} berhasil ditolak."


def batalkan(id_pengajuan, user):
    """Pengaju membatalkan pengajuannya yang masih menunggu."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        p = _ambil(cursor, id_pengajuan)
        if p["status"] != "MENUNGGU" or p["diajukan_oleh"] != user.id:
            raise ValueError("Hanya pengajuan Anda yang masih menunggu yang bisa dibatalkan")
        if not p["tahap"] and not hak_akses.boleh(MENU_JENIS.get(p["jenis"], ""), "setujui", user=user):
            raise ValueError("Pengajuan hanya bisa diputuskan oleh pemegang hak Setujui")
        conn.rollback()
    finally:
        conn.close()
    _selesai(p, "DIBATALKAN", user)
    return "Pengajuan berhasil dibatalkan."


def _selesai(p, status, user, catatan=None, lewati=()):
    """Catat riwayat langkah terakhir + status akhir dalam satu transaksi (hanya bila masih MENUNGGU)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE pengajuan SET status = ?, selesai_at = GETDATE() WHERE id_pengajuan = ? AND status = 'MENUNGGU'",
                       status, p["id_pengajuan"])
        if cursor.rowcount == 0:
            raise ValueError("Pengajuan ini sudah diproses oleh pengguna lain")
        _riwayat(cursor, p["id_pengajuan"], p["langkah"], status, user.id,
                 user.id_level if status != "DIBATALKAN" else None, catatan)
        for n in lewati:
            _riwayat(cursor, p["id_pengajuan"], n, "DILEWATI", p["diajukan_oleh"], p["tahap"][n - 1], "Peran pengaju sendiri")
        if status != "DIBATALKAN":
            kata = "disetujui" if status == "DISETUJUI" else "ditolak"
            notifikasi.buat(MENU_JENIS[p["jenis"]], f"Pengajuan {JENIS[p['jenis']].lower()} {kata}",
                            p["judul"] + (f" · Catatan: {catatan}" if catatan else ""),
                            tautan(p["jenis"], p["id_pengajuan"]), p["id_comp_area"], cursor=cursor, id_user=p["diajukan_oleh"])
        conn.commit()
    finally:
        conn.close()
    if status != "DISETUJUI" and p["jenis"] in _SAAT_DITOLAK:
        _SAAT_DITOLAK[p["jenis"]](_bersih(p["data"]))


# ===== Daftar (List Request / bagian Pengajuan Koreksi) =====
def _terlihat(r, user, bisa):
    """Mode "semua": pengajuan sendiri, yang bisa saya putuskan, yang peran saya ada di tahapnya,
    atau (cara lama) saya pemegang hak Setujui menu itu."""
    if r["diajukan_oleh"] == user.id or bisa:
        return True
    if r["tahap"]:
        return user.id_level in r["tahap"]
    return hak_akses.boleh(MENU_JENIS.get(r["jenis"], ""), "setujui", user=user)


def daftar(user, mode="menunggu", batas=200, menu=None):
    """mode: menunggu (yang bisa saya setujui sekarang) · saya (yang saya ajukan) · semua (yang terkait saya, di PT saya).
    menu: hanya jenis milik menu itu (mis. BLACKLIST)."""
    syarat, args = ["1 = 1"], []
    if menu:
        jenis = [j for j, m in MENU_JENIS.items() if m == menu] or ["-"]
        syarat.append(f"p.jenis IN ({', '.join('?' * len(jenis))})"); args += jenis
    if mode == "saya":
        syarat.append("p.diajukan_oleh = ?"); args.append(user.id)
    else:
        pt = company_user(user.id)
        if pt is not None:
            ids = sorted(pt) or [""]           # daftar kosong = tidak ada perusahaan yang cocok
            syarat.append(f"(p.id_company IN ({', '.join('?' * len(ids))}) OR p.diajukan_oleh = ?)"); args += [*ids, user.id]
        if mode == "menunggu":
            syarat.append("p.status = 'MENUNGGU'")
    rows = _query(f"""SELECT TOP ({int(batas)}) p.id_pengajuan, p.jenis, p.status, p.langkah, p.total_langkah, p.judul, p.alasan,
                             p.data, p.id_company, p.diajukan_oleh, p.created_at, p.selesai_at, p.kategori, u.Nama AS pengaju,
                             c.CompID AS kode_company, ar.AreaName AS site, kp.CategoryName AS nama_kategori
                      FROM pengajuan p JOIN Users u ON u.UserID = p.diajukan_oleh
                      JOIN Company c ON c.CompID = p.id_company
                      JOIN CompanyArea ar ON ar.CompAreaID = p.id_comp_area
                      LEFT JOIN UserCategory kp ON kp.CategoryCode = p.kategori
                      WHERE {' AND '.join(syarat)} ORDER BY CASE p.status WHEN 'MENUNGGU' THEN 0 ELSE 1 END, p.created_at DESC""",
                  *args)
    tahap = _tahap_pengajuan([r["id_pengajuan"] for r in rows])
    riwayat = _riwayat_semua([r["id_pengajuan"] for r in rows])
    nama_peran = _nama_jabatan()
    hasil = []
    for r in rows:
        r["data"] = json.loads(r["data"] or "{}")
        r["tahap"] = tahap.get(r["id_pengajuan"], [])
        bisa = boleh_setujui(r, user)
        if mode == "menunggu" and not bisa:
            continue
        if mode == "semua" and not _terlihat(r, user, bisa):
            continue
        hasil.append({
            "id_pengajuan": r["id_pengajuan"], "jenis": r["jenis"], "nama_jenis": JENIS.get(r["jenis"], r["jenis"]),
            "status": r["status"], "langkah": r["langkah"], "total_langkah": r["total_langkah"], "judul": r["judul"],
            "alasan": r["alasan"], "pengaju": r["pengaju"], "company": r["kode_company"], "site": r["site"],
            "kategori": r["kategori"], "nama_kategori": r["nama_kategori"] or ("Kendaraan" if r["kategori"] == "KENDARAAN" else None),
            "waktu": r["created_at"].strftime("%Y-%m-%d %H:%M"), "bisa_setujui": bisa,
            "bisa_batal": (r["status"] == "MENUNGGU" and r["diajukan_oleh"] == user.id
                           and (bool(r["tahap"]) or hak_akses.boleh(MENU_JENIS.get(r["jenis"], ""), "setujui", user=user))),
            "tahap": [nama_peran.get(i, "-") for i in r["tahap"]],
            "menunggu": (nama_peran.get(r["tahap"][r["langkah"] - 1], "-") if r["tahap"] and r["status"] == "MENUNGGU" else None),
            "riwayat": riwayat.get(r["id_pengajuan"], []), "rincian": r["data"].get("_rincian", []),
            "info": r["data"].get("_info", {}),
        })
    return hasil


def _riwayat_semua(ids):
    if not ids:
        return {}
    hasil = {}
    for i in range(0, len(ids), 500):
        bagian = ids[i:i + 500]
        for r in _query(f"""SELECT r.id_pengajuan, r.langkah, r.aksi, r.catatan, r.waktu, u.Nama AS nama
                            FROM pengajuan_riwayat r JOIN Users u ON u.UserID = r.id_user
                            WHERE r.id_pengajuan IN ({', '.join('?' * len(bagian))}) ORDER BY r.waktu, r.id_riwayat""", *bagian):
            hasil.setdefault(r["id_pengajuan"], []).append(
                {"langkah": r["langkah"], "aksi": r["aksi"], "catatan": r["catatan"], "oleh": r["nama"],
                 "waktu": r["waktu"].strftime("%Y-%m-%d %H:%M") if isinstance(r["waktu"], datetime) else str(r["waktu"])})
    return hasil


@cache_ttl(30)
def _nama_jabatan():
    return {r["id_level"]: r["nama"] for r in _query("SELECT LevelDetID AS id_level, LevelDetName AS nama FROM LevelDetails")}


def jumlah_menunggu(user):
    """Untuk badge: pengajuan yang bisa disetujui user ini sekarang."""
    if getattr(user, "is_admin", False):
        return 0
    return len(daftar(user, "menunggu"))
