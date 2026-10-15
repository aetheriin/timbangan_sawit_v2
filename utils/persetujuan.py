"""Persetujuan (migrasi 027, disederhanakan di 029): pengajuan -> disetujui satu penyetuju -> dijalankan.

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
}
MENU_JENIS = {"BLACKLIST_TAMBAH": "BLACKLIST", "BLACKLIST_HAPUS": "BLACKLIST"}       # hak Setujui dicek di menu ini
TAUTAN_MENU = {"BLACKLIST": "/blacklist?tab=persetujuan"}
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


def ajukan(jenis, target, judul, alasan, data, user_id):
    """Buat pengajuan. Tanpa langkah penyetuju -> langsung dijalankan. Kembalikan (status, pesan)."""
    if jenis not in JENIS:
        raise ValueError("Jenis pengajuan tidak dikenal")
    langkah = penyetuju(jenis)
    khusus = [i for i in hak_akses.pengguna_khusus_dengan(MENU_JENIS[jenis], "setujui") if i != user_id]
    if not langkah and not khusus:
        _PELAKSANA[jenis](data, user_id, user_id)
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
        cursor.execute("""INSERT INTO pengajuan (jenis, total_langkah, id_company, id_comp_area, target, judul, alasan, data, diajukan_oleh)
                          OUTPUT INSERTED.id_pengajuan VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)""",
                       jenis, id_company, id_area, target, judul[:200], (alasan or "")[:500] or None,
                       json.dumps(data, default=str), user_id)
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


def _ambil(cursor, id_pengajuan):
    cursor.execute("SELECT * FROM pengajuan WITH (UPDLOCK) WHERE id_pengajuan = ?", id_pengajuan)
    rows = _rows_to_dicts(cursor)
    if not rows:
        raise ValueError("Pengajuan tidak ditemukan")
    p = rows[0]
    p["data"] = json.loads(p["data"] or "{}")
    return p


def boleh_setujui(p, user):
    """User boleh menyetujui / menolak pengajuan p: hak Setujui di menunya, PT sama, bukan pengaju sendiri."""
    if p["status"] != "MENUNGGU" or p["diajukan_oleh"] == user.id or getattr(user, "is_admin", False):
        return False
    if not hak_akses.boleh(MENU_JENIS.get(p["jenis"], ""), "setujui", user=user):
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
    # Jalankan dulu, baru catat & tandai selesai (gagal dijalankan -> tetap menunggu, pesan ke penyetuju)
    data = {k: v for k, v in p["data"].items() if not k.startswith("_")}
    _PELAKSANA[p["jenis"]](data, p["diajukan_oleh"], user.id)
    _selesai(p, "DISETUJUI", user, catatan)
    return f"{JENIS[p['jenis']]} berhasil disetujui dan sudah berlaku."


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
        conn.rollback()
    finally:
        conn.close()
    _selesai(p, "DIBATALKAN", user)
    return "Pengajuan berhasil dibatalkan."


def _selesai(p, status, user, catatan=None):
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
        if status != "DIBATALKAN":
            kata = "disetujui" if status == "DISETUJUI" else "ditolak"
            notifikasi.buat(MENU_JENIS[p["jenis"]], f"Pengajuan {JENIS[p['jenis']].lower()} {kata}",
                            p["judul"] + (f" · Catatan: {catatan}" if catatan else ""),
                            tautan(p["jenis"], p["id_pengajuan"]), p["id_comp_area"], cursor=cursor, id_user=p["diajukan_oleh"])
        conn.commit()
    finally:
        conn.close()
    if status != "DISETUJUI" and p["jenis"] in _SAAT_DITOLAK:
        _SAAT_DITOLAK[p["jenis"]]({k: v for k, v in p["data"].items() if not k.startswith("_")})


# ===== Daftar (halaman Persetujuan) =====
def daftar(user, mode="menunggu", batas=200, menu=None):
    """mode: menunggu (yang bisa saya setujui sekarang) · saya (yang saya ajukan) · semua (di PT saya).
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
            ids = sorted(pt) or [-1]
            syarat.append(f"p.id_company IN ({', '.join('?' * len(ids))})"); args += ids
        if mode == "menunggu":
            syarat.append("p.status = 'MENUNGGU'")
    rows = _query(f"""SELECT TOP ({int(batas)}) p.id_pengajuan, p.jenis, p.status, p.langkah, p.total_langkah, p.judul, p.alasan,
                             p.data, p.id_company, p.diajukan_oleh, p.created_at, p.selesai_at, u.nama AS pengaju,
                             c.kode AS kode_company, ar.nama AS site
                      FROM pengajuan p JOIN akun u ON u.id_user = p.diajukan_oleh
                      JOIN company c ON c.id_company = p.id_company
                      JOIN comp_area ar ON ar.id_comp_area = p.id_comp_area
                      WHERE {' AND '.join(syarat)} ORDER BY CASE p.status WHEN 'MENUNGGU' THEN 0 ELSE 1 END, p.created_at DESC""",
                  *args)
    riwayat = _riwayat_semua([r["id_pengajuan"] for r in rows])
    hasil = []
    for r in rows:
        r["data"] = json.loads(r["data"] or "{}")
        bisa = boleh_setujui(r, user)
        if mode == "menunggu" and not bisa:
            continue
        hasil.append({
            "id_pengajuan": r["id_pengajuan"], "jenis": r["jenis"], "nama_jenis": JENIS.get(r["jenis"], r["jenis"]),
            "status": r["status"], "langkah": r["langkah"], "total_langkah": r["total_langkah"], "judul": r["judul"],
            "alasan": r["alasan"], "pengaju": r["pengaju"], "company": r["kode_company"], "site": r["site"],
            "waktu": r["created_at"].strftime("%Y-%m-%d %H:%M"), "bisa_setujui": bisa,
            "bisa_batal": r["status"] == "MENUNGGU" and r["diajukan_oleh"] == user.id,
            "riwayat": riwayat.get(r["id_pengajuan"], []),
        })
    return hasil


def _riwayat_semua(ids):
    if not ids:
        return {}
    hasil = {}
    for i in range(0, len(ids), 500):
        bagian = ids[i:i + 500]
        for r in _query(f"""SELECT r.id_pengajuan, r.langkah, r.aksi, r.catatan, r.waktu, u.nama
                            FROM pengajuan_riwayat r JOIN akun u ON u.id_user = r.id_user
                            WHERE r.id_pengajuan IN ({', '.join('?' * len(bagian))}) ORDER BY r.waktu, r.id_riwayat""", *bagian):
            hasil.setdefault(r["id_pengajuan"], []).append(
                {"langkah": r["langkah"], "aksi": r["aksi"], "catatan": r["catatan"], "oleh": r["nama"],
                 "waktu": r["waktu"].strftime("%Y-%m-%d %H:%M") if isinstance(r["waktu"], datetime) else str(r["waktu"])})
    return hasil


@cache_ttl(30)
def _nama_jabatan():
    return {r["id_level"]: r["nama"] for r in _query("SELECT id_level, nama FROM level")}


def jumlah_menunggu(user):
    """Untuk badge: pengajuan yang bisa disetujui user ini sekarang."""
    if getattr(user, "is_admin", False):
        return 0
    return len(daftar(user, "menunggu"))
