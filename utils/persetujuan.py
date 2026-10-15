"""Persetujuan dinamis (migrasi 027): pengajuan -> 1-3 langkah penyetuju (per jabatan) -> dijalankan saat disetujui.

- Penyetuju tiap langkah diatur di Admin › Persetujuan per jenis. Jenis tanpa langkah = langsung dijalankan.
- Penyetuju harus berjabatan sesuai langkah DAN berada di PT pengajuan (user kantor pusat: PT yang dikelolanya).
  Yang mengajukan tidak bisa menyetujui pengajuannya sendiri.
- Langkah disalin ke pengajuan saat diajukan, jadi perubahan pengaturan tidak mengubah pengajuan yang sedang berjalan.
- Setiap langkah mengirim notifikasi: ke jabatan penyetuju berikutnya di PT itu, dan ke pengaju saat selesai.
  Notifikasi membuka /persetujuan?id=<id> (baris pengajuan disorot).
Jenis baru: tambahkan ke JENIS lalu daftarkan fungsi pelaksananya dengan @pelaksana("KODE")."""
import json
from datetime import datetime

from utils import notifikasi
from utils.area import company_user
from utils.cache import cache_ttl
from utils.db_kunjungan import area_akun
from utils.db_organisasi import company_area
from utils.db_utils import get_connection, _rows_to_dicts

JENIS = {
    "BLACKLIST_TAMBAH": "Tambah blacklist",
    "BLACKLIST_HAPUS": "Hapus blacklist",
}
MENU = "PERSETUJUAN"
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


# ===== Pengaturan langkah (Admin › Persetujuan) =====
@cache_ttl(30)
def semua_langkah():
    """{jenis: [{urutan, id_level, jabatan}, ...]} urut langkah."""
    hasil = {j: [] for j in JENIS}
    for r in _query("""SELECT s.jenis, s.urutan, s.id_level, l.nama AS jabatan FROM persetujuan_langkah s
                       JOIN level l ON l.id_level = s.id_level ORDER BY s.jenis, s.urutan"""):
        hasil.setdefault(r["jenis"], []).append(r)
    return hasil


def simpan_langkah(jenis, daftar_level):
    """daftar_level = [id_level, ...] maksimal 3, urut langkah 1..n."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM persetujuan_langkah WHERE jenis = ?", jenis)
        for i, id_level in enumerate(daftar_level[:3], start=1):
            cursor.execute("INSERT INTO persetujuan_langkah (jenis, urutan, id_level) VALUES (?, ?, ?)", jenis, i, id_level)
        conn.commit()
    finally:
        conn.close()
    semua_langkah.hapus()


# ===== Pengajuan =====
def _notif_langkah(cursor, p, langkah_ke, id_level):
    notifikasi.buat(MENU, f"Persetujuan {JENIS[p['jenis']].lower()} menunggu Anda",
                    f"{p['judul']} · langkah {langkah_ke} dari {p['total_langkah']}",
                    f"/persetujuan?id={p['id_pengajuan']}", p["id_comp_area"], cursor=cursor,
                    id_level=id_level, id_company=p["id_company"])


def _riwayat(cursor, id_pengajuan, langkah, aksi, id_user, id_level=None, catatan=None):
    cursor.execute("""INSERT INTO pengajuan_riwayat (id_pengajuan, langkah, aksi, id_level, id_user, catatan)
                      VALUES (?, ?, ?, ?, ?, ?)""", id_pengajuan, langkah, aksi, id_level, id_user, catatan)


def ajukan(jenis, target, judul, alasan, data, user_id):
    """Buat pengajuan. Tanpa langkah penyetuju -> langsung dijalankan. Kembalikan (status, pesan)."""
    if jenis not in JENIS:
        raise ValueError("Jenis pengajuan tidak dikenal")
    langkah = [r["id_level"] for r in semua_langkah().get(jenis, [])]
    if not langkah:
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
        isi = {**data, "_langkah": langkah}
        cursor.execute("""INSERT INTO pengajuan (jenis, total_langkah, id_company, id_comp_area, target, judul, alasan, data, diajukan_oleh)
                          OUTPUT INSERTED.id_pengajuan VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       jenis, len(langkah), id_company, id_area, target, judul[:200], (alasan or "")[:500] or None,
                       json.dumps(isi, default=str), user_id)
        id_p = cursor.fetchone()[0]
        _riwayat(cursor, id_p, 0, "DIAJUKAN", user_id, catatan=alasan)
        _notif_langkah(cursor, {"id_pengajuan": id_p, "jenis": jenis, "judul": judul, "total_langkah": len(langkah),
                                "id_comp_area": id_area, "id_company": id_company}, 1, langkah[0])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    nama = next((r["jabatan"] for r in semua_langkah()[jenis] if r["urutan"] == 1), "penyetuju")
    return "MENUNGGU", nama


def _ambil(cursor, id_pengajuan):
    cursor.execute("SELECT * FROM pengajuan WITH (UPDLOCK) WHERE id_pengajuan = ?", id_pengajuan)
    rows = _rows_to_dicts(cursor)
    if not rows:
        raise ValueError("Pengajuan tidak ditemukan")
    p = rows[0]
    p["data"] = json.loads(p["data"] or "{}")
    return p


def boleh_setujui(p, user):
    """User boleh menyetujui langkah yang sedang berjalan dari pengajuan p."""
    if p["status"] != "MENUNGGU" or p["diajukan_oleh"] == user.id or getattr(user, "is_admin", False):
        return False
    langkah = p["data"].get("_langkah", [])
    if not (0 < p["langkah"] <= len(langkah)) or langkah[p["langkah"] - 1] != user.id_level:
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
            raise ValueError("Anda tidak bisa menyetujui pengajuan ini pada langkah sekarang")
        langkah = p["data"]["_langkah"]
        if p["langkah"] < len(langkah):
            _riwayat(cursor, id_pengajuan, p["langkah"], "DISETUJUI", user.id, user.id_level, catatan)
            cursor.execute("UPDATE pengajuan SET langkah = langkah + 1 WHERE id_pengajuan = ?", id_pengajuan)
            _notif_langkah(cursor, p, p["langkah"] + 1, langkah[p["langkah"]])
            conn.commit()
            return f"Langkah {p['langkah']} berhasil disetujui. Pengajuan diteruskan ke penyetuju berikutnya."
        conn.rollback()
    finally:
        conn.close()
    # Langkah terakhir: jalankan dulu, baru catat & tandai selesai (gagal dijalankan -> tetap menunggu, pesan ke penyetuju)
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
            raise ValueError("Anda tidak bisa menolak pengajuan ini pada langkah sekarang")
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
            notifikasi.buat(MENU, f"Pengajuan {JENIS[p['jenis']].lower()} {kata}",
                            p["judul"] + (f" · Catatan: {catatan}" if catatan else ""),
                            f"/persetujuan?id={p['id_pengajuan']}", p["id_comp_area"], cursor=cursor, id_user=p["diajukan_oleh"])
        conn.commit()
    finally:
        conn.close()
    if status != "DISETUJUI" and p["jenis"] in _SAAT_DITOLAK:
        _SAAT_DITOLAK[p["jenis"]]({k: v for k, v in p["data"].items() if not k.startswith("_")})


# ===== Daftar (halaman Persetujuan) =====
def daftar(user, mode="menunggu", batas=200):
    """mode: menunggu (yang bisa saya setujui sekarang) · saya (yang saya ajukan) · semua (di PT saya)."""
    syarat, args = ["1 = 1"], []
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
                             c.kode AS kode_company, ar.kode + ' (' + ar.nama + ')' AS site
                      FROM pengajuan p JOIN akun u ON u.id_user = p.diajukan_oleh
                      JOIN company c ON c.id_company = p.id_company
                      JOIN comp_area ar ON ar.id_comp_area = p.id_comp_area
                      WHERE {' AND '.join(syarat)} ORDER BY CASE p.status WHEN 'MENUNGGU' THEN 0 ELSE 1 END, p.created_at DESC""",
                  *args)
    riwayat = _riwayat_semua([r["id_pengajuan"] for r in rows])
    jabatan = _nama_jabatan()
    hasil = []
    for r in rows:
        r["data"] = json.loads(r["data"] or "{}")
        bisa = boleh_setujui(r, user)
        if mode == "menunggu" and not bisa:
            continue
        langkah = r["data"].get("_langkah", [])
        hasil.append({
            "id_pengajuan": r["id_pengajuan"], "jenis": r["jenis"], "nama_jenis": JENIS.get(r["jenis"], r["jenis"]),
            "status": r["status"], "langkah": r["langkah"], "total_langkah": r["total_langkah"], "judul": r["judul"],
            "alasan": r["alasan"], "pengaju": r["pengaju"], "company": r["kode_company"], "site": r["site"],
            "waktu": r["created_at"].strftime("%Y-%m-%d %H:%M"), "bisa_setujui": bisa,
            "bisa_batal": r["status"] == "MENUNGGU" and r["diajukan_oleh"] == user.id,
            "rantai": [jabatan.get(i, "-") for i in langkah],
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
