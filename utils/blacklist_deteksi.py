"""Log Validasi Blacklist (migrasi 028): setiap orang / kendaraan blacklist yang terdeteksi dicatat per kejadian.

Dipanggil otomatis dari catat_security_audit(..., "TRY_SCAN_BLACKLIST", details={...}) dengan kunci details:
  sumber (SCAN_WAJAH, ABSENSI, TAMU, TAMU_MASUK, TIKET, TAMBAH_SUPIR, PENDAFTARAN, PLAT,
  POS_MASUK), tindakan (DITOLAK /
  PERINGATAN / DILOLOSKAN), id_personel, id_kendaraan, no_plat, jarak, keterangan.
- Kejadian sama (target, sumber, petugas) dalam 60 detik tidak dicatat ulang (mis. plat diketik berulang).
- Deteksi pertama hari itu untuk target di lokasi tersebut mengirim notifikasi ke jabatan yang punya hak Setujui di
  menu Blacklist (Admin › Level & Hak Akses) di PT itu; bila belum ada, ke jabatan yang punya hak menu Blacklist.
Gagal mencatat tidak pernah menggagalkan proses utama."""
import logging
from datetime import date, datetime, timedelta

from utils.db_utils import get_connection, _rows_to_dicts

log = logging.getLogger(__name__)

SUMBER = {"SCAN_WAJAH": "Scan wajah Form Security", "ABSENSI": "Scan absensi", "TAMU": "Scan tamu",
          "TAMU_MASUK": "Tamu dicatat masuk", "TIKET": "Tiket tetap dibuat", "TAMBAH_SUPIR": "Tambah supir",
          "PENDAFTARAN": "Pendaftaran personel", "PLAT": "Cek plat di info bar",
          "POS_MASUK": "Kendaraan masuk di Pos Security", "LAINNYA": "Lainnya"}
TINDAKAN = ("DITOLAK", "PERINGATAN", "DILOLOSKAN")
JEDA_DETIK = 60


def catat(details, user_id, no_tiket=None):
    try:
        _catat(details or {}, user_id, no_tiket)
    except Exception:          # noqa: BLE001 - log validasi tidak boleh menggagalkan scan / tiket
        log.exception("Gagal mencatat deteksi blacklist")


def _catat(d, user_id, no_tiket):
    from utils.db_kunjungan import area_akun
    sumber = d.get("sumber") if d.get("sumber") in SUMBER else "LAINNYA"
    tindakan = d.get("tindakan") if d.get("tindakan") in TINDAKAN else "PERINGATAN"
    target = []
    if d.get("id_personel"):
        target.append(("id_personel", int(d["id_personel"])))
    if d.get("id_kendaraan"):
        target.append(("id_kendaraan", int(d["id_kendaraan"])))
    if not target:
        return
    id_area = area_akun(user_id) if user_id else None
    jarak = float(d["jarak"]) if d.get("jarak") is not None else None
    conn = get_connection()
    cursor = conn.cursor()
    baru = []
    try:
        for kolom, nilai in target:
            cursor.execute(f"""SELECT TOP 1 1 FROM blacklist_deteksi WHERE {kolom} = ? AND sumber = ?
                               AND ISNULL(id_user, 0) = ? AND waktu >= DATEADD(SECOND, -{JEDA_DETIK}, GETDATE())""",
                           nilai, sumber, user_id or 0)
            if cursor.fetchone():
                continue
            cursor.execute(f"""SELECT COUNT(*) FROM blacklist_deteksi WHERE {kolom} = ?
                               AND ISNULL(id_comp_area, 0) = ? AND waktu >= CAST(GETDATE() AS DATE)""", nilai, id_area or 0)
            pertama_hari_ini = cursor.fetchone()[0] == 0
            cursor.execute(f"""INSERT INTO blacklist_deteksi (id_comp_area, {kolom}, no_plat, sumber, tindakan, jarak_wajah,
                                                              keterangan, no_tiket, id_user)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                           id_area, nilai, (d.get("no_plat") or None), sumber, tindakan, jarak,
                           (d.get("keterangan") or "")[:300] or None, no_tiket, user_id)
            if pertama_hari_ini:
                baru.append((kolom, nilai))
        conn.commit()
    finally:
        conn.close()
    for kolom, nilai in baru:
        _notifikasi(kolom, nilai, id_area, SUMBER[sumber])


def _notifikasi(kolom, nilai, id_area, sumber):
    from utils import notifikasi
    from utils.db_organisasi import company_area
    from utils.hak_akses import jabatan_dengan
    rows = _query("SELECT nama_personel AS nama FROM personel WHERE id_personel = ?" if kolom == "id_personel"
                  else "SELECT no_plat AS nama FROM kendaraan WHERE id_kendaraan = ?", nilai)
    nama = rows[0]["nama"] if rows else "-"
    kode = f"{'P' if kolom == 'id_personel' else 'K'}{nilai}"
    judul, isi = f"Blacklist terdeteksi: {nama}", f"{sumber} · pertama kali hari ini"
    tautan = f"/blacklist?tab=log&target={kode}"
    penerima = jabatan_dengan("BLACKLIST", "setujui")
    for id_level in penerima:
        notifikasi.buat("BLACKLIST", judul, isi, tautan, id_area, id_level=id_level, id_company=company_area().get(id_area))
    if not penerima:            # belum ada jabatan dengan hak Setujui: ke semua yang punya hak di menu Blacklist
        notifikasi.buat("BLACKLIST", judul, isi, tautan, id_area)


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


# ===== Halaman Log Validasi =====
def log_hari(tanggal, id_area):
    """Kejadian satu hari + ringkasan per target (jumlah percobaan, jam pertama / terakhir, kunjungan ke berapa)."""
    from utils.area_filter import sql_area
    f_area, a_area = sql_area("d.id_comp_area", id_area)
    awal = datetime.combine(tanggal, datetime.min.time())
    rows = _query(f"""SELECT d.id_deteksi, d.waktu, d.id_comp_area, d.id_personel, d.id_kendaraan, d.no_plat, d.sumber,
                             d.tindakan, d.jarak_wajah, d.keterangan, d.no_tiket, u.Nama AS petugas,
                             c.CompID + ' · ' + ar.AreaName AS site, c.CompID AS company,
                             p.kode_personel, p.nama_personel, p.kategori, k.no_plat AS plat_kendaraan
                      FROM blacklist_deteksi d
                      LEFT JOIN Users u ON u.UserID = d.id_user
                      LEFT JOIN CompanyArea ar ON ar.CompAreaID = d.id_comp_area
                      LEFT JOIN Company c ON c.CompID = ar.CompID
                      LEFT JOIN personel p ON p.id_personel = d.id_personel
                      LEFT JOIN kendaraan k ON k.id_kendaraan = d.id_kendaraan
                      WHERE d.waktu >= ? AND d.waktu < ?{f_area}
                      ORDER BY d.waktu""", awal, awal + timedelta(days=1), *a_area)
    target = {}
    for r in rows:
        kode = f"P{r['id_personel']}" if r["id_personel"] else f"K{r['id_kendaraan']}"
        t = target.setdefault(kode, {
            "kode": kode, "tipe": "PERSONEL" if r["id_personel"] else "KENDARAAN",
            "nama": r["nama_personel"] if r["id_personel"] else r["plat_kendaraan"],
            "kode_personel": r["kode_personel"], "kategori": r["kategori"],
            "jumlah": 0, "ditolak": 0, "pertama": r["waktu"], "terakhir": r["waktu"], "site": set()})
        t["jumlah"] += 1
        t["ditolak"] += r["tindakan"] == "DITOLAK"
        t["terakhir"] = r["waktu"]
        if r["site"]:
            t["site"].add(r["site"])
    kunjungan = _kunjungan(list(target.values()), tanggal, id_area)
    hasil_target = []
    for t in sorted(target.values(), key=lambda x: x["terakhir"], reverse=True):
        k = kunjungan.get(t["kode"], {})
        hasil_target.append({**t, "pertama": t["pertama"].strftime("%H:%M"), "terakhir": t["terakhir"].strftime("%H:%M"),
                             "site": sorted(t["site"]), "kunjungan_ke": k.get("ke", 1), "sebelumnya": k.get("sebelumnya", [])})
    kejadian = [{"id": r["id_deteksi"], "jam": r["waktu"].strftime("%H:%M:%S"),
                 "target": f"P{r['id_personel']}" if r["id_personel"] else f"K{r['id_kendaraan']}",
                 "sumber": SUMBER.get(r["sumber"], r["sumber"]), "tindakan": r["tindakan"],
                 "kemiripan": round(max(0.0, 1 - r["jarak_wajah"]) * 100) if r["jarak_wajah"] is not None else None,
                 "keterangan": r["keterangan"], "no_tiket": r["no_tiket"], "petugas": r["petugas"],
                 "site": r["site"], "company": r["company"], "no_plat": r["no_plat"]} for r in rows]
    return {
        "ringkas": {"deteksi": len(rows), "target": len(target),
                    "ditolak": sum(1 for r in rows if r["tindakan"] == "DITOLAK"),
                    "diloloskan": sum(1 for r in rows if r["tindakan"] == "DILOLOSKAN")},
        "target": hasil_target, "kejadian": kejadian,
    }


def _kunjungan(daftar_target, tanggal, id_area):
    """Kunjungan = hari berbeda target terdeteksi (di site yang sama bila disaring). Kunjungan ke-N sampai tanggal itu,
    plus 5 tanggal kunjungan sebelumnya."""
    from utils.area_filter import sql_area
    hasil = {}
    f_area, a_area = sql_area("id_comp_area", id_area)
    batas = datetime.combine(tanggal + timedelta(days=1), datetime.min.time())
    for t in daftar_target:
        kolom, nilai = ("id_personel", int(t["kode"][1:])) if t["kode"][0] == "P" else ("id_kendaraan", int(t["kode"][1:]))
        rows = _query(f"""SELECT DISTINCT CAST(waktu AS DATE) AS hari FROM blacklist_deteksi
                          WHERE {kolom} = ? AND waktu < ?{f_area} ORDER BY hari DESC""", nilai, batas, *a_area)
        hari = [r["hari"] for r in rows]
        sebelumnya = [h for h in hari if h != tanggal][:5]
        hasil[t["kode"]] = {"ke": len(hari) or 1,
                            "sebelumnya": [h.strftime("%d-%m-%Y") if isinstance(h, date) else str(h) for h in sebelumnya]}
    return hasil
