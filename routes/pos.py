"""Tahap 1 Security: Pos Security (kendaraan masuk tanpa tiket timbang) dan Logbook Kendaraan (masih di dalam / sudah keluar).

Disimpan di tabel transaksi (migrasi 039): Pos Security membuat transaksi beralur POS_SAJA; jam masuk = created_at,
jam keluar = waktu_keluar. Aturan masuk sama dengan Buat Tiket di Stasiun Timbang (plat, STNK, customer, produk,
supir + scan wajah, blacklist = peringatan yang tercatat). Tahap 2 cukup mematikan menu Pos Security."""
from datetime import date, datetime
from functools import wraps

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from utils import pengaturan, alur
from utils import verifikasi_state as verif
from utils import db_pos
from utils.area import area_data, company_user
from utils.audit_utils import catat_security_audit
from utils.db_admin import supplier_boleh
from utils.db_kontrak import daftar_mitra, id_pengangkutan_dari_nama
from utils.db_kunjungan import area_akun
from utils.db_master import stnk_dipakai
from utils.db_utils import (get_semua_supplier, get_semua_produk, get_driver_by_id, cari_transaksi_aktif,
                            buat_transaksi_full, generate_no_tiket)
from utils.hak_akses import boleh, boleh_lihat, izin, halaman as lihat_halaman
from utils.keamanan import id_pos
from utils.personel_utils import format_nama_personel
from utils.plat_utils import normalisasi_plat
from utils.serializers import serialisasi_driver

pos_bp = Blueprint("pos", __name__)

JENIS_TRANSAKSI = ("PEMBELIAN", "PENJUALAN", "PENIMBANGAN_SAJA")
SIM_SEGERA_HARI = 30


def _boleh_lihat(*kode_menu):
    """API baca halaman Pos / Logbook: cukup hak Lihat salah satu menu."""
    def dekorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not any(boleh_lihat(k) for k in kode_menu):
                return jsonify({"error": "Level Anda tidak memiliki akses untuk tindakan ini"}), 403
            return f(*args, **kwargs)
        return wrapped
    return dekorator


def _waktu(v):
    return v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, datetime) else v


def _baris(r):
    return {**r, "waktu_masuk": _waktu(r["waktu_masuk"]), "waktu_keluar": _waktu(r["waktu_keluar"]),
            "pos": r.get("kode_alur") == "POS_SAJA"}


def _blacklist(tipe, id_target):
    b = db_pos.blacklist_aktif(tipe, id_target)
    return b and {**b, "sejak": b["sejak"].strftime("%d-%m-%Y")}


def _transportir(pt):
    return [m for m in daftar_mitra() if m["peran"] == "PENGANGKUTAN" and supplier_boleh(m["id_supplier"], pt)]


@pos_bp.route("/pos-security")
@login_required
@lihat_halaman("POS_SECURITY")
def pos_security():
    pt = company_user(current_user.id)
    return render_template("pos/pos_security.html", halaman="pos",
                           supplier_list=[s for s in get_semua_supplier()
                                          if s.is_customer and supplier_boleh(s.id_supplier, pt)],
                           produk_list=get_semua_produk(), transportir_list=_transportir(pt),
                           wajib_scan_wajah=pengaturan.nilai("WAJIB_SCAN_WAJAH", area_akun(current_user.id)),
                           boleh_simpan=boleh("POS_SECURITY", "tambah"), boleh_ubah_supir=boleh("POS_SECURITY", "ubah"),
                           boleh_blacklist=boleh("BLACKLIST", "tambah"), boleh_keluar=boleh("LOGBOOK", "ubah"))


@pos_bp.route("/logbook")
@login_required
@lihat_halaman("LOGBOOK")
def logbook():
    return render_template("pos/logbook.html", halaman="logbook", boleh_keluar=boleh("LOGBOOK", "ubah"),
                           batas_jam=pengaturan.nilai("BATAS_LAMA_DI_DALAM_JAM", area_akun(current_user.id)))


@pos_bp.route("/api/pos/cek-plat", methods=["POST"])
@login_required
@_boleh_lihat("POS_SECURITY")
def cek_plat():
    """Plat diketik: data kendaraan, blacklist, supir terakhir, dan apakah masih tercatat di dalam."""
    no_plat, error = normalisasi_plat(request.form.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400
    k = db_pos.kendaraan(no_plat)
    bl = _blacklist("KENDARAAN", k["id_kendaraan"]) if k and k["is_blacklisted"] else None
    if k and k["is_blacklisted"]:
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                             details={"keterangan": f"Plat {no_plat} terdeteksi blacklist di Pos Security (peringatan)",
                                      "no_plat": no_plat, "id_kendaraan": k["id_kendaraan"], "sumber": "PLAT",
                                      "tindakan": "PERINGATAN"})
    t = db_pos.supir_terakhir(no_plat)
    dalam = db_pos.di_dalam(no_plat)
    return jsonify({
        "no_plat": no_plat,
        "kendaraan": k and {"id_kendaraan": k["id_kendaraan"], "no_stnk": k["no_stnk"], "jenis": k["jenis"],
                            "is_active": bool(k["is_active"]), "blacklist": bl or ({} if k["is_blacklisted"] else None)},
        "terakhir": t and {**{x: t[x] for x in ("id_driver", "kode_personel", "nik", "nama", "no_sim", "kategori",
                                                 "foto_path")},
                           "is_blacklisted": bool(t["is_blacklisted"]), "is_updated": bool(t["is_updated"]),
                           "waktu": _waktu(t["waktu"])},
        "di_dalam": dalam and _baris(dalam),
    })


@pos_bp.route("/api/pos/supir/<int:id_driver>")
@login_required
@_boleh_lihat("POS_SECURITY")
def info_supir(id_driver):
    """SIM (masa berlaku) dan blacklist supir untuk kartu & panel peringatan."""
    d = get_driver_by_id(id_driver)
    if not d:
        return jsonify({"error": "Supir tidak ditemukan"}), 404
    sim = db_pos.sim_supir(id_driver)
    if sim:
        tgl = sim["berlaku_sampai"]
        sisa = (tgl - date.today()).days if tgl else None
        sim = {"jenis": sim["jenis"], "no_sim": sim["no_sim"], "berlaku_sampai": tgl.strftime("%d-%m-%Y") if tgl else None,
               "sisa_hari": sisa, "status": "TANPA_TANGGAL" if sisa is None else "HABIS" if sisa < 0
               else "SEGERA" if sisa <= SIM_SEGERA_HARI else "BERLAKU"}
    return jsonify({**serialisasi_driver(d), "sim": sim,
                    "blacklist": (_blacklist("PERSONEL", id_driver) or {}) if d.is_blacklisted else None})


@pos_bp.route("/api/pos/masuk", methods=["POST"])
@login_required
@izin("POS_SECURITY", "tambah")
def simpan_masuk():
    f = request.form
    no_plat, error = normalisasi_plat(f.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400
    jenis, id_supplier, id_produk = f.get("jenis_transaksi", "").strip(), f.get("id_supplier", ""), f.get("id_produk", "")
    id_driver = f.get("id_driver", "")
    pt = company_user(current_user.id)
    if jenis not in JENIS_TRANSAKSI:
        return jsonify({"error": "Pilih jenis transaksi"}), 400
    if (not id_supplier.isdigit() or int(id_supplier) not in {s.id_supplier for s in get_semua_supplier() if s.is_customer}
            or not supplier_boleh(int(id_supplier), pt)):
        return jsonify({"error": "Pilih customer / supplier dari daftar"}), 400
    if not id_produk.isdigit() or int(id_produk) not in {p.id_produk for p in get_semua_produk()}:
        return jsonify({"error": "Pilih produk dari daftar"}), 400
    nama_angkut = " ".join(f.get("pengangkutan", "").split())
    if len(nama_angkut) > 100:
        return jsonify({"error": "Nama pengangkutan maksimal 100 karakter"}), 400

    dalam = db_pos.di_dalam(no_plat)
    if dalam:
        return jsonify({"error": f"{no_plat} masih tercatat di dalam sejak {dalam['waktu_masuk']:%d-%m-%Y %H:%M}. "
                                 "Catat keluar dulu."}), 400
    aktif = cari_transaksi_aktif(no_plat=no_plat)
    if aktif:
        return jsonify({"error": f"Plat ini masih punya tiket aktif: {aktif.no_tiket}"}), 400

    driver = get_driver_by_id(id_driver) if id_driver.isdigit() else None
    if not driver:
        return jsonify({"error": "Scan wajah atau pilih supir terlebih dahulu"}), 400
    nama_driver = format_nama_personel(driver.kode_personel, driver.id_driver, driver.nama_driver)
    if driver.kategori != "DRIVER":
        return jsonify({"error": f"{nama_driver} terdaftar sebagai {driver.kategori}, bukan supir"}), 400

    k = db_pos.kendaraan(no_plat)
    if k and not k["is_active"]:
        return jsonify({"error": f"Kendaraan {no_plat} dinonaktifkan di Data Master › Kendaraan"}), 400
    no_stnk = f.get("no_stnk", "").strip().upper()
    if not no_stnk:
        return jsonify({"error": "No. STNK wajib diisi"}), 400
    if len(no_stnk) > 50:
        return jsonify({"error": "No. STNK maksimal 50 karakter"}), 400
    plat_stnk = stnk_dipakai(no_stnk, kecuali=k["id_kendaraan"] if k else None)
    if plat_stnk:
        return jsonify({"error": f"No. STNK {no_stnk} sudah dipakai kendaraan {plat_stnk}"}), 400

    area = area_akun(current_user.id)
    v = verif.ambil(id_pos(), current_user.id)
    terverifikasi = bool(v) and str(v["id_driver"]) == str(driver.id_driver)
    if pengaturan.nilai("WAJIB_SCAN_WAJAH", area) and not terverifikasi:
        return jsonify({"error": "Supir belum terverifikasi wajah. Silakan lakukan scan wajah."}), 400

    peringatan = []
    if k and k["is_blacklisted"]:
        peringatan.append(f"kendaraan {no_plat}")
    if driver.is_blacklisted:
        peringatan.append(f"supir {nama_driver}")

    id_angkut = id_pengangkutan_dari_nama(nama_angkut) if nama_angkut else None
    no_tiket = generate_no_tiket(no_plat)
    buat_transaksi_full(no_tiket, no_plat, no_stnk, jenis, int(id_supplier), int(id_produk), driver.id_driver, None,
                        current_user.id, id_angkut, area, alur.id_alur_kode("POS_SAJA"), None,
                        "PIHAK_KETIGA" if id_angkut else "PENGIRIM")

    ip = request.remote_addr
    saran = f.get("id_driver_saran", "").strip()
    if saran.isdigit() and saran != str(driver.id_driver):
        lama = get_driver_by_id(int(saran))
        nama_lama = format_nama_personel(lama.kode_personel, lama.id_driver, lama.nama_driver) if lama else saran
        catat_security_audit(current_user.id, "OVERRIDE_DRIVER", no_tiket, ip_address=ip,
                             details={"keterangan": f"Supir berbeda dari supir terakhir: {nama_lama} → {nama_driver}",
                                      "prev_driver_id": int(saran), "id_driver": driver.id_driver})
    if not terverifikasi:
        catat_security_audit(current_user.id, "MANUAL_INPUT", no_tiket, ip_address=ip,
                             details={"keterangan": f"Kendaraan masuk tanpa scan wajah (supir {nama_driver})"})
    if peringatan:
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", no_tiket, ip_address=ip,
                             details={"keterangan": f"Kendaraan masuk walau {' & '.join(peringatan)} masuk blacklist",
                                      "no_plat": no_plat, "sumber": "POS_MASUK", "tindakan": "DILOLOSKAN",
                                      "id_personel": driver.id_driver if driver.is_blacklisted else None,
                                      "id_kendaraan": k["id_kendaraan"] if k and k["is_blacklisted"] else None})
    verif.hapus(id_pos(), current_user.id)
    pesan = f"{no_plat} tercatat masuk pukul {datetime.now():%H:%M}"
    if peringatan:
        pesan += f". Perhatian: {' & '.join(peringatan)} masuk blacklist (tercatat di Log Validasi Blacklist)"
    return jsonify({"message": pesan, "no_tiket": no_tiket, "blacklist": bool(peringatan)})


@pos_bp.route("/api/pos/keluar", methods=["POST"])
@login_required
@izin("LOGBOOK", "ubah")
def catat_keluar():
    no_tiket = request.form.get("no_tiket", "").strip()
    r = db_pos.catat_keluar(no_tiket, current_user.id, area_data(current_user.id)) if no_tiket else None
    if not r:
        return jsonify({"error": "Kendaraan tidak ditemukan di daftar Masih di Dalam (mungkin sudah dicatat keluar)"}), 404
    menit = int((datetime.now() - r["waktu_masuk"]).total_seconds() // 60)
    return jsonify({"message": f"{r['no_plat']} tercatat keluar pukul {datetime.now():%H:%M} "
                               f"({menit // 60} jam {menit % 60} menit di dalam)"})


@pos_bp.route("/api/pos/logbook")
@login_required
@_boleh_lihat("LOGBOOK", "POS_SECURITY")
def data_logbook():
    try:
        tanggal = date.fromisoformat(request.args.get("tanggal", "")) if request.args.get("tanggal") else date.today()
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid"}), 400
    data = db_pos.logbook(area_data(current_user.id), tanggal)
    return jsonify({"dalam": [_baris(r) for r in data["dalam"]], "keluar": [_baris(r) for r in data["keluar"]],
                    "masuk_hari_ini": data["masuk_hari_ini"], "sekarang": _waktu(datetime.now()),
                    "tanggal": tanggal.isoformat()})
