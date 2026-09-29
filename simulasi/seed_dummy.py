"""Isi database dengan data dummy lalu jalankan simulasi alur lewat API Flask sungguhan.

Cara pakai (dari folder project):
    python -m simulasi.seed_dummy            # hapus dummy lama, isi ulang, jalankan simulasi
    python -m simulasi.seed_dummy --hapus    # hanya hapus semua data dummy

Penanda data dummy (dipakai saat menghapus):
    users    : username diawali 'dummy_'
    supplier : nama diawali 'DUMMY '
    produk   : nama diawali 'DUMMY '
    driver   : NIK diawali '9999'
    transaksi: semua transaksi milik driver dummy

Timbangan (port COM) dan scan wajah TIDAK dipakai: berat disuntik lewat mock,
dan WAJIB_SCAN_WAJAH dimatikan hanya selama script ini berjalan.
"""
import os
import sys
from unittest.mock import patch

import numpy as np
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()   # muat .env dulu supaya SECRET_KEY / HASH_SECRET_KEY asli tetap dipakai
os.environ["WAJIB_SCAN_WAJAH"] = "false"
os.environ.setdefault("SECRET_KEY", "dummy-secret-untuk-simulasi")
os.environ.setdefault("HASH_SECRET_KEY", "dummy-hash-secret-untuk-simulasi")

from app import app  # noqa: E402
from utils.db_utils import get_connection, insert_user, insert_driver, get_standar_mutu, update_standar_mutu  # noqa: E402
from utils.face_utils import embedding_to_binary  # noqa: E402
from utils.plat_utils import normalisasi_plat  # noqa: E402

PASSWORD_DUMMY = "dummy123"

USERS = [
    ("dummy_security", "Dummy Security", "SECURITY"),
    ("dummy_timbang", "Dummy Operator Timbang", "OPERATOR_TIMBANG"),
    ("dummy_sortasi", "Dummy Sortasi", "SORTASI"),
    ("dummy_lab", "Dummy Lab", "LAB"),
    ("dummy_admin", "Dummy Admin", "ADMIN"),
]

# (kode_supplier, nama_supplier, tipe)
SUPPLIERS = [
    ("DMY-001", "DUMMY KUD Sawit Makmur", "SUPPLIER_PEMBELIAN"),
    ("DMY-002", "DUMMY CV Tani Jaya", "SUPPLIER_PEMBELIAN"),
    ("DMY-003", "DUMMY PT Agro Riau", "BUYER_PENJUALAN"),
]

PRODUK = [("DUMMY TBS", "TBS"), ("DUMMY CPO", "PRODUK_PKS"), ("DUMMY Kernel", "PRODUK_PKS")]

DRIVERS = [
    ("9999000000000001", "Budi Santoso", "SIM-B2-0001"),
    ("9999000000000002", "Ahmad Yani", "SIM-B2-0002"),
    ("9999000000000003", "Siti Rahma", "SIM-B2-0003"),
    ("9999000000000004", "Joko Susilo", "SIM-B2-0004"),
    ("9999000000000005", "Rudi Hartono", "SIM-B2-0005"),
    ("9999000000000006", "Dedi Kurnia", "SIM-B2-0006"),
    ("9999000000000007", "Hendra Saputra", "SIM-B2-0007"),
]


# ===================== HAPUS DATA DUMMY =====================

def hapus_dummy():
    conn = get_connection()
    cur = conn.cursor()
    sub_tiket = """SELECT t.no_tiket FROM transaksi t JOIN driver d ON t.id_driver = d.id_driver
                   WHERE d.nik LIKE '9999%'"""
    for tabel in ("timeline_monitoring", "sortasi", "lab_hasil", "timbangan"):
        cur.execute(f"DELETE FROM {tabel} WHERE no_tiket IN ({sub_tiket})")
    cur.execute("DELETE FROM transaksi WHERE id_driver IN (SELECT id_driver FROM driver WHERE nik LIKE '9999%')")
    cur.execute("DELETE FROM driver_audit_logs WHERE id_driver IN (SELECT id_driver FROM driver WHERE nik LIKE '9999%')")
    cur.execute("DELETE FROM driver WHERE nik LIKE '9999%'")
    # Kendaraan hanya dihapus kalau sudah tidak dipakai transaksi manapun
    plat_dummy = [normalisasi_plat(s["plat"])[0] for s in SKENARIO]
    cur.execute(f"""DELETE FROM kendaraan WHERE no_plat IN ({','.join('?' * len(plat_dummy))})
                    AND id_kendaraan NOT IN (SELECT id_kendaraan FROM transaksi WHERE id_kendaraan IS NOT NULL)""", *plat_dummy)
    cur.execute("DELETE FROM standar_mutu WHERE id_produk IN (SELECT id_produk FROM produk WHERE nama_produk LIKE 'DUMMY %')")
    cur.execute("DELETE FROM produk WHERE nama_produk LIKE 'DUMMY %'")
    cur.execute("DELETE FROM supplier WHERE nama_supplier LIKE 'DUMMY %'")
    cur.execute("DELETE FROM users WHERE username LIKE 'dummy[_]%'")
    conn.commit()
    conn.close()
    print("[OK] Data dummy lama dihapus")


# ===================== MASTER DATA =====================

def _ambil_id(cur, sql, nilai):
    cur.execute(sql, nilai)
    return cur.fetchone()[0]

def seed_master():
    for username, nama, role in USERS:
        insert_user(username, generate_password_hash(PASSWORD_DUMMY), nama, role)

    conn = get_connection()
    cur = conn.cursor()
    supplier_id = {}
    for kode, nama, tipe in SUPPLIERS:
        cur.execute("INSERT INTO supplier (kode_supplier, nama_supplier, tipe) VALUES (?, ?, ?)", kode, nama, tipe)
        supplier_id[nama] = _ambil_id(cur, "SELECT id_supplier FROM supplier WHERE nama_supplier = ?", nama)
    produk_id = {}
    for nama, kategori in PRODUK:
        cur.execute("INSERT INTO produk (nama_produk, kategori) VALUES (?, ?)", nama, kategori)
        produk_id[nama] = _ambil_id(cur, "SELECT id_produk FROM produk WHERE nama_produk = ?", nama)
    conn.commit()
    conn.close()

    for nama, kategori in PRODUK:
        if kategori == "PRODUK_PKS":
            get_standar_mutu(produk_id[nama])                        # buat baris default
            update_standar_mutu(produk_id[nama], 5.0, 0.5, 0.05)     # maks FFA / air / kotoran (%)

    # Embedding wajah acak (bukan wajah asli) supaya kolom NOT NULL terisi.
    # Jaraknya jauh dari wajah manusia sungguhan, jadi tidak akan "cocok" saat scan wajah.
    rng = np.random.default_rng(42)
    driver_id = {}
    for nik, nama, sim in DRIVERS:
        emb = rng.normal(0, 0.5, 128)
        driver_id[nama] = insert_driver(nik, nama, sim, embedding_to_binary(emb), None)

    print(f"[OK] Master: {len(USERS)} user, {len(SUPPLIERS)} supplier, {len(PRODUK)} produk, {len(DRIVERS)} driver")
    return supplier_id, produk_id, driver_id


# ===================== SKENARIO ALUR =====================
# langkah: urutan tahap setelah tiket dibuat Security.
#   ('timbang', kg) | ('sortasi', {...persen}) | ('lab', keputusan, ffa, air, kotoran)
# Plat sengaja ditulis dengan gaya berbeda-beda untuk menguji normalisasi format.

SKENARIO = [
    dict(nama="TBS pembelian lengkap", plat="bm1455jj", supir="Budi Santoso",
         jenis="PEMBELIAN", supplier="DUMMY KUD Sawit Makmur", produk="DUMMY TBS", stnk="STNK-0001",
         langkah=[("timbang", 18540), ("sortasi", dict(mentah=2, busuk=1, tangkai=1.5, sampah=0.5, matang=90, brondolan=5)),
                  ("timbang", 7260)], harapan="SELESAI",
         # netto 18540-7260 = 11280; potongan (2+1.5+0.5)% x 11280 = 451.2; netto akhir 10828.8
         cek_berat=dict(berat_netto=11280, potongan_kg=451.2, netto_akhir=10828.8)),
    dict(nama="TBS menunggu sortasi", plat="A 1234 JJ", supir="Ahmad Yani",
         jenis="PEMBELIAN", supplier="DUMMY CV Tani Jaya", produk="DUMMY TBS", stnk="STNK-0002",
         langkah=[("timbang", 21030)], harapan="TIMBANG_1"),
    dict(nama="TBS menunggu timbang keluar", plat="AA-456-SJU", supir="Siti Rahma",
         jenis="PEMBELIAN", supplier="DUMMY KUD Sawit Makmur", produk="DUMMY TBS", stnk=None,
         langkah=[("timbang", 16880), ("sortasi", dict(mentah=4, busuk=2, tangkai=3, sampah=1, matang=85, brondolan=5))],
         harapan="TIMBANG_2"),
    dict(nama="CPO penjualan, lab APPROVE lalu timbang kedua", plat="BM 8821 TU", supir="Joko Susilo",
         jenis="PENJUALAN", supplier="DUMMY PT Agro Riau", produk="DUMMY CPO", stnk="STNK-0004",
         langkah=[("timbang", 9150), ("lab", "APPROVE", 3.2, 0.2, 0.02), ("timbang", 38150)], harapan="SELESAI",
         cek_berat=dict(berat_netto=29000, potongan_kg=None, netto_akhir=29000)),
    dict(nama="CPO menunggu hasil lab", plat="BM 9012 XY", supir="Hendra Saputra",
         jenis="PENJUALAN", supplier="DUMMY PT Agro Riau", produk="DUMMY CPO", stnk=None,
         langkah=[("timbang", 8870)], harapan="TIMBANG_1"),
    dict(nama="CPO penjualan, lab REJECT", plat="bk8abc", supir="Rudi Hartono",
         jenis="PENJUALAN", supplier="DUMMY PT Agro Riau", produk="DUMMY CPO", stnk=None,
         langkah=[("timbang", 9020), ("lab", "REJECT", 6.8, 0.9, 0.1)], harapan="REJECTED"),
    dict(nama="Penimbangan saja", plat="B 9", supir="Dedi Kurnia",
         jenis="PENIMBANGAN_SAJA", supplier="DUMMY CV Tani Jaya", produk="DUMMY Kernel", stnk=None,
         langkah=[("timbang", 12400)], harapan="SELESAI"),
    dict(nama="Baru masuk pos security", plat="BM 3310 AK", supir="Budi Santoso",
         jenis="PEMBELIAN", supplier="DUMMY CV Tani Jaya", produk="DUMMY TBS", stnk="STNK-0007",
         langkah=[], harapan=None),   # status awal = default kolom di DB
]


class Simulasi:
    def __init__(self):
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.gagal = 0

    def cek(self, kondisi, pesan):
        print(f"   {'[LULUS]' if kondisi else '[GAGAL]'} {pesan}")
        if not kondisi:
            self.gagal += 1

    def login(self, username):
        self.client.get("/logout")
        res = self.client.post("/login", data={"username": username, "password": PASSWORD_DUMMY})
        if res.status_code != 302 or "/weighbridge" not in res.headers.get("Location", ""):
            raise RuntimeError(f"Login {username} gagal")

    def post(self, url, data):
        res = self.client.post(url, data=data)
        return res.status_code, res.get_json()

    def timbang(self, no_tiket, berat):
        status_palsu = {"berat": berat, "stabil": True, "terhubung": True, "siap_kunci": True}
        with patch("routes.timbangan.baca_status_asli", return_value=status_palsu):
            return self.post("/api/timbang/simpan", {"no_tiket": no_tiket})

    def status_alur(self, no_tiket):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status_alur FROM transaksi WHERE no_tiket = ?", no_tiket)
        row = cur.fetchone()
        conn.close()
        return row.status_alur if row else None

    def jalankan_skenario(self, sk, supplier_id, produk_id, driver_id):
        print(f"\n== {sk['nama']} (input plat: '{sk['plat']}')")
        self.login("dummy_security")
        kode, data = self.post("/api/plat/lookup", {"no_plat": sk["plat"]})
        self.cek(kode == 200 and data.get("status") == "DRAFT", f"lookup plat -> {data.get('no_plat')} (DRAFT)")
        no_tiket = data["no_tiket_reserved"]

        kode, data = self.post("/api/security/buat-tiket", {
            "no_tiket": no_tiket, "no_plat": sk["plat"], "no_stnk": sk["stnk"] or "",
            "no_do": f"DO-{no_tiket[-6:]}", "jenis_transaksi": sk["jenis"],
            "id_supplier": supplier_id[sk["supplier"]], "id_produk": produk_id[sk["produk"]],
            "id_driver": driver_id[sk["supir"]]})
        self.cek(kode == 200, f"buat tiket {no_tiket}: {data.get('message') or data.get('error')}")

        for langkah in sk["langkah"]:
            if langkah[0] == "timbang":
                self.login("dummy_timbang")
                kode, data = self.timbang(no_tiket, langkah[1])
            elif langkah[0] == "sortasi":
                self.login("dummy_sortasi")
                kode, data = self.post("/api/sortasi/simpan", {"no_tiket": no_tiket, **langkah[1], "catatan": "dummy"})
            else:
                _, keputusan, ffa, air, kotoran = langkah
                self.login("dummy_lab")
                kode, data = self.post("/api/lab/simpan", {"no_tiket": no_tiket, "ffa": ffa, "kadar_air": air,
                                                           "kadar_kotoran": kotoran, "warna_locis": "3R",
                                                           "keputusan": keputusan})
            self.cek(kode == 200, f"{langkah[0]}: {data.get('message') or data.get('error')}")

        status = self.status_alur(no_tiket)
        if sk["harapan"]:
            self.cek(status == sk["harapan"], f"status_alur = {status} (harapan {sk['harapan']})")
        else:
            print(f"   [INFO] status_alur awal = {status}")
        if sk.get("cek_berat"):
            berat = self.client.get(f"/api/timbang/data/{no_tiket}").get_json()
            hasil = {k: berat[k] for k in sk["cek_berat"]}
            self.cek(hasil == sk["cek_berat"], f"berat {hasil}")
        return no_tiket

    def uji_urutan_tahap(self, tiket):
        print("\n== Uji urutan tahap")
        self.login("dummy_timbang")
        kode, data = self.timbang(tiket["TBS menunggu sortasi"], 7000)
        self.cek(kode == 400, f"timbang kedua TBS sebelum sortasi ditolak: {data.get('error')}")
        kode, data = self.timbang(tiket["CPO menunggu hasil lab"], 37000)
        self.cek(kode == 400, f"timbang kedua CPO sebelum lab ditolak: {data.get('error')}")
        kode, data = self.timbang(tiket["CPO penjualan, lab REJECT"], 37000)
        self.cek(kode == 404, f"timbang tiket REJECTED ditolak: {data.get('error')}")

        self.login("dummy_sortasi")
        kode, data = self.post("/api/sortasi/simpan", {"no_tiket": tiket["CPO menunggu hasil lab"], "mentah": 1})
        self.cek(kode == 400, f"sortasi untuk CPO ditolak: {data.get('error')}")
        kode, data = self.post("/api/sortasi/simpan", {"no_tiket": tiket["Baru masuk pos security"], "mentah": 1})
        self.cek(kode == 400, f"sortasi sebelum timbang pertama ditolak: {data.get('error')}")

        self.login("dummy_lab")
        kode, data = self.post("/api/lab/simpan", {"no_tiket": tiket["TBS menunggu sortasi"], "keputusan": "APPROVE"})
        self.cek(kode == 400, f"lab untuk TBS ditolak: {data.get('error')}")

    def uji_negatif(self, supplier_id, produk_id, driver_id):
        print("\n== Uji negatif")
        self.login("dummy_security")
        for plat in ["1455 JJ", "BM 12345 JJ", "MB 1455 JJ", "BM 1455 ABCD"]:
            kode, data = self.post("/api/plat/lookup", {"no_plat": plat})
            self.cek(kode == 400, f"plat '{plat}' ditolak: {data.get('error')}")

        # Plat yang sama ditulis beda gaya harus dianggap SAMA -> tiket ganda ditolak
        kode, data = self.post("/api/plat/lookup", {"no_plat": "a1234jj"})
        self.cek(data.get("status") == "ADA_TIKET" and data.get("no_plat") == "A 1234 JJ",
                 "'a1234jj' menemukan tiket aktif milik 'A 1234 JJ'")
        kode, data = self.post("/api/security/buat-tiket", {
            "no_tiket": "TKT-GANDA", "no_plat": "a-1234-jj", "jenis_transaksi": "PEMBELIAN",
            "id_supplier": supplier_id["DUMMY CV Tani Jaya"], "id_produk": produk_id["DUMMY TBS"],
            "id_driver": driver_id["Ahmad Yani"]})
        self.cek(kode == 400, f"tiket ganda ditolak: {data.get('error')}")

        self.login("dummy_sortasi")
        kode, data = self.post("/api/security/buat-tiket", {"no_plat": "BM 1 A"})
        self.cek(kode == 403, "role SORTASI tidak boleh buat tiket (403)")

    def jalankan(self, supplier_id, produk_id, driver_id):
        tiket = {sk["nama"]: self.jalankan_skenario(sk, supplier_id, produk_id, driver_id) for sk in SKENARIO}
        self.uji_urutan_tahap(tiket)
        self.uji_negatif(supplier_id, produk_id, driver_id)
        print(f"\n{'=' * 50}\nSelesai: {self.gagal} pengecekan GAGAL")
        print(f"Login UI pakai: {', '.join(u[0] for u in USERS)} / password '{PASSWORD_DUMMY}'")
        return self.gagal


def main():
    hapus_dummy()
    if "--hapus" in sys.argv:
        return 0
    ids = seed_master()
    return 1 if Simulasi().jalankan(*ids) else 0


if __name__ == "__main__":
    sys.exit(main())
