import io
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import qrcode
import qrcode.image.svg
from flask import Blueprint, request, jsonify, render_template, Response, abort
from utils.area_filter import area_cocok
from utils.db_organisasi import daftar_area
from utils.area import area_data, company_user
from utils.db_admin import supplier_boleh
from flask_login import login_required, current_user
from utils.db_utils import (
    periksa_tiket,
    get_semua_supplier, get_semua_produk, get_history_produk, cari_transaksi_aktif,
    cari_riwayat_driver_by_plat, generate_no_tiket,
    get_kendaraan_by_plat, get_supir_kendaraan, get_kontrak_kendaraan, catat_cetak_qr
)
from utils.serializers import serialisasi_tiket, serialisasi_driver
from utils.db_blacklist import get_surat_blacklist
from utils.audit_utils import catat_security_audit
from utils.plat_utils import normalisasi_plat
from utils import pengaturan
from utils.hak_akses import boleh, izin, halaman as lihat_halaman
from utils import log_aktivitas, koreksi_tiket, alur
from utils.db_master import daftar_driver_aktif
from utils.db_jembatan import daftar_jembatan, jembatan_dipilih
from utils.db_personel import daftar_jenis_sim, daftar_kategori
from utils.db_kunjungan import daftar_keperluan, area_akun

main_bp = Blueprint('main', __name__)

# Tahap yang ditangani tiap role: halaman List default ke tahap ini, Form default ke tab ini
def _jembatan_aktif():
    try:
        return [j for j in daftar_jembatan() if j["is_active"]]
    except Exception:       # noqa: BLE001 - migrasi 011 belum dijalankan
        return []


def _jembatan_pc():
    try:
        return jembatan_dipilih(request)
    except Exception:       # noqa: BLE001
        return None


def _tab_awal():
    """Tab / tahap awal dari halaman awal level (mis. /weighbridge?tab=timbangan, Admin › Hak Akses)."""
    return parse_qs(urlparse(current_user.halaman_awal or "").query).get("tab", [""])[0]


@main_bp.route("/weighbridge")
@login_required
@lihat_halaman(lambda r: "FORM" if r.args.get("view") == "form" else "LIST")
def weighbridge():
    """List = daftar tiket aktif per tahap (tanpa info bar & tab). Form = info bar + tab Security..Lab."""
    if request.args.get("view") != "form":
        return render_template("site/list.html", halaman="site", view="list", produk_list=get_semua_produk(),
                               tahap_awal=_tab_awal(), boleh_periksa=boleh("LIST", "setujui"),
                               boleh_koreksi=boleh("LIST", "ubah"))
    return render_template("site/weighbridge.html", halaman="site", view="form",
                           tab_awal=_tab_awal() or "security",
                           supplier_list=[s for s in get_semua_supplier()
                                          if s.is_customer and supplier_boleh(s.id_supplier, company_user(current_user.id))],
                           produk_list=get_semua_produk(),
                           wajib_scan_wajah=pengaturan.nilai("WAJIB_SCAN_WAJAH", area_akun(current_user.id)),
                           jembatan_list=_jembatan_aktif(), jembatan_dipilih=_jembatan_pc())

@main_bp.route("/api/list/history-produk")
@login_required
def history_produk():
    id_produk = request.args.get("id_produk", "")
    rows = get_history_produk(int(id_produk) if id_produk.isdigit() else None, id_area=area_data(current_user.id))
    return jsonify([{**r, "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M"),
                     "diperiksa_pada": r["diperiksa_pada"].strftime("%Y-%m-%d %H:%M") if r["diperiksa_pada"] else None}
                    for r in rows])


@main_bp.route("/api/tiket/<no_tiket>/koreksi")
@login_required
@izin("LIST", "ubah")
def tiket_koreksi_data(no_tiket):
    """Isi tiket sekarang + pilihan untuk form Ajukan Koreksi."""
    t = koreksi_tiket.data_tiket(no_tiket, area_data(current_user.id))
    if not t:
        return jsonify({"error": "Tiket tidak ditemukan atau sudah dibatalkan."}), 404
    return jsonify({"tiket": t, **_pilihan_koreksi(t)})


def _pilihan_koreksi(t):
    """Pilihan customer (PT pengguna), produk aktif, dan supir aktif (+ supir tiket sekarang)."""
    pt = company_user(current_user.id)
    supir = daftar_driver_aktif()
    if t["id_driver"] not in {d["id_personel"] for d in supir}:
        supir.append({"id_personel": t["id_driver"], "nama_personel": t["nama_driver"], "kode_personel": None})
    return {"customer": [{"id": s.id_supplier, "nama": s.nama_supplier} for s in get_semua_supplier()
                         if s.is_customer and supplier_boleh(s.id_supplier, pt)],
            "produk": [{"id": p.id_produk, "nama": p.nama_produk} for p in get_semua_produk()],
            "supir": [{"id": d["id_personel"], "nama": d["nama_personel"] + (f" ({d['kode_personel']})" if d.get("kode_personel") else "")}
                      for d in supir]}


@main_bp.route("/api/tiket/<no_tiket>/koreksi", methods=["POST"])
@login_required
@izin("LIST", "ubah")
def tiket_koreksi_ajukan(no_tiket):
    """Ajukan koreksi: hanya kolom yang berubah; berlaku setelah disetujui (hak Setujui di menu Daftar Tiket)."""
    t = koreksi_tiket.data_tiket(no_tiket, area_data(current_user.id))
    if not t:
        return jsonify({"error": "Tiket tidak ditemukan atau sudah dibatalkan."}), 404
    f = request.form
    try:
        alasan = (f.get("alasan") or "").strip()
        if len(alasan) < 5:
            raise ValueError("Alasan koreksi wajib diisi (minimal 5 karakter).")
        pilihan = _pilihan_koreksi(t)
        ubah, nama = {}, {}
        for kolom, kunci in (("id_supplier", "customer"), ("id_produk", "produk"), ("id_driver", "supir")):
            teks = (f.get(kolom) or "").strip()
            if not teks.isdigit():
                continue
            cocok = next((o for o in pilihan[kunci] if o["id"] == int(teks)), None)
            if not cocok:
                raise ValueError(f"Pilih {koreksi_tiket.KOLOM[kolom].lower()} dari daftar.")
            if cocok["id"] != t[kolom]:
                ubah[kolom], nama[kolom] = cocok["id"], cocok["nama"]
        if (f.get("no_plat") or "").strip():
            no_plat, error = normalisasi_plat(f.get("no_plat"))
            if error:
                raise ValueError(error)
            k = get_kendaraan_by_plat(no_plat)
            if not k or not k.is_active:
                raise ValueError(f"Kendaraan {no_plat} belum terdaftar. Daftarkan dulu di Data Master › Kendaraan.")
            if k.id_kendaraan != t["id_kendaraan"]:
                ubah["id_kendaraan"], nama["id_kendaraan"] = k.id_kendaraan, k.no_plat
        if not ubah:
            raise ValueError("Tidak ada data yang diubah.")
        status, penyetuju = koreksi_tiket.ajukan(t, ubah, nama, alasan, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if status == "DISETUJUI":
        return jsonify({"message": f"Koreksi tiket {no_tiket} langsung berlaku karena belum ada jabatan yang berhak menyetujui."})
    return jsonify({"message": f"Koreksi tiket {no_tiket} berhasil diajukan dan menunggu persetujuan {penyetuju}."})


@main_bp.route("/api/tiket/<no_tiket>/periksa", methods=["POST"])
@login_required
@izin("LIST", "setujui")
def tiket_periksa(no_tiket):
    """Verifikasi tiket selesai (sudah diperiksa): pemeriksa & waktunya dicatat, tidak bisa diubah lagi."""
    if not periksa_tiket(no_tiket, current_user.id, area_data(current_user.id)):
        return jsonify({"error": "Tiket tidak ditemukan, belum selesai, atau sudah diperiksa."}), 400
    log_aktivitas.catat("TIKET", "TIKET_DIPERIKSA", id_baris=no_tiket, user_id=current_user.id, ip=request.remote_addr)
    return jsonify({"message": f"Tiket {no_tiket} berhasil ditandai sudah diperiksa."})


@main_bp.route("/api/tantangan-wajah")
@login_required
def tantangan_wajah():
    """Tantangan liveness wajib / tidak untuk area akun ini (Admin › Pengaturan Site, per area)."""
    area = area_akun(current_user.id)
    return jsonify({k: pengaturan.nilai(f"TANTANGAN_{k.upper()}", area) for k in ("security", "absensi", "tamu")})


@main_bp.route("/blacklist")
@login_required
@lihat_halaman("BLACKLIST")
def halaman_blacklist():
    """Menu Blacklist (dulu tab Pengenalan Wajah). Berlaku di semua area; siapa yang boleh menetapkan: hak BLACKLIST."""
    id_area = area_data(current_user.id)
    pusat = id_area is None or isinstance(id_area, tuple)       # kantor pusat bisa memilih site di Log Validasi
    from utils.db_kontrak import daftar_mitra
    from utils.alur_persetujuan import daftar_kategori as kategori_alur
    from utils import persetujuan
    pt = company_user(current_user.id)
    return render_template("face_recognition/blacklist.html", halaman="blacklist", boleh_blacklist=boleh("BLACKLIST", "tambah"),
                           boleh_hapus_blacklist=boleh("BLACKLIST", "hapus"), is_pusat=pusat,
                           supplier_list=[s for s in get_semua_supplier() if s.is_customer and supplier_boleh(s.id_supplier, pt)],
                           transportir_list=[m for m in daftar_mitra()
                                             if m["peran"] == "PENGANGKUTAN" and supplier_boleh(m["id_supplier"], pt)],
                           kategori_list=kategori_alur(),
                           penyetuju_alur=persetujuan.peran_di_alur(current_user.id_level, "BLACKLIST"),
                           area_list=[a for a in daftar_area() if a["is_active"] and area_cocok(id_area, a["id_comp_area"])] if pusat else [])


@main_bp.route("/tamu")
@login_required
@lihat_halaman("KUNJUNGAN")
def halaman_tamu():
    """Menu Tamu: scan wajah, daftar tamu baru, catat masuk / keluar (hak KUNJUNGAN)."""
    return render_template("face_recognition/tamu.html", halaman="tamu", keperluan_list=daftar_keperluan(),
                           boleh_kunjungan=boleh("KUNJUNGAN"))


@main_bp.route("/face-recognition")
@login_required
@lihat_halaman("FACE_RECOGNITION")
def face_recognition():
    """Satu halaman, tab Absensi | Personel | Log Audit (tanpa info bar). Blacklist & Tamu menu sendiri."""
    return render_template("face_recognition/face_recognition.html", halaman="face", boleh_ubah=boleh("PERSONEL"),
                           jenis_sim_list=daftar_jenis_sim(), keperluan_list=daftar_keperluan(),
                           boleh_kunjungan=boleh("KUNJUNGAN"), kategori_list=list(daftar_kategori().values()),
                           boleh_kode=boleh("PERSONEL", "ubah"))

@main_bp.route("/api/plat/lookup", methods=["POST"])
@login_required
def api_plat_lookup():
    no_plat, error = normalisasi_plat(request.form.get("no_plat"))
    if error:
        return jsonify({"error": error}), 400

    kendaraan = get_kendaraan_by_plat(no_plat)
    # Ditandai blacklist tapi data surat belum ada -> tetap diperingatkan (dict kosong, bukan None)
    blacklist = ((get_surat_blacklist("KENDARAAN", kendaraan.id_kendaraan) or {"no_surat_blacklist": None})
                 if kendaraan and kendaraan.is_blacklisted else None)

    if blacklist:      # truk diblacklist HO: hanya PERINGATAN (tiket tetap bisa dibuat), tercatat di Log Validasi (ada / belum ada tiket)
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST",
                             details={"keterangan": f"Plat {no_plat} terdeteksi blacklist (peringatan)",
                                      "no_plat": no_plat, "no_surat": blacklist["no_surat_blacklist"],
                                      "id_kendaraan": kendaraan.id_kendaraan, "sumber": "PLAT", "tindakan": "PERINGATAN"},
                             ip_address=request.remote_addr)

    row = cari_transaksi_aktif(no_plat=no_plat)
    if row and row.id_alur is not None and row.id_alur == alur.id_alur_kode("POS_SAJA"):
        return jsonify({"error": f"{no_plat} tercatat masuk lewat Pos Security (tanpa tiket timbang). "
                                 "Catat keluar di Logbook dulu."}), 400
    if row:
        return jsonify({**serialisasi_tiket(row), "kendaraan_blacklist": blacklist}), 200

    # Belum ada tiket aktif: nomor tiket cuma "dipesan", belum di-INSERT
    riwayat = cari_riwayat_driver_by_plat(no_plat)
    driver_info = serialisasi_driver(riwayat)


    # Data dari menu Update: supir terdaftar & kontrak aktif truk ini
    supir_terdaftar = get_supir_kendaraan(kendaraan.id_kendaraan) if kendaraan else []
    kontrak_aktif = get_kontrak_kendaraan(kendaraan.id_kendaraan, hanya_aktif=True) if kendaraan else []
    utama = next((s for s in supir_terdaftar if s["is_utama"]), None)
    driver_utama = None
    if utama:
        driver_utama = {"id_driver": utama["id_driver"], "kode_personel": utama["kode_personel"],
                        "nik": utama["nik"], "nama": utama["nama_driver"], "no_sim": utama["no_sim"],
                        "kategori": "DRIVER", "is_blacklisted": utama["is_blacklisted"],
                        "is_updated": utama["is_updated"], "foto_path": utama["foto_path"]}

    return jsonify({
        "status": "DRAFT",
        "no_plat": no_plat,
        "no_tiket_reserved": generate_no_tiket(no_plat),
        "no_stnk": (kendaraan.no_stnk if kendaraan and kendaraan.no_stnk else None)
                   or (riwayat.no_stnk if riwayat else None),
        "driver": driver_info,             # supir transaksi terakhir
        "driver_utama": driver_utama,      # supir utama dari menu Update
        "supir_terdaftar": supir_terdaftar,
        "kontrak_aktif": kontrak_aktif,
        "kendaraan_blacklist": blacklist,  # None = tidak blacklist
    }), 200

# ===== QR CODE TIKET (dibuat di server, tidak butuh internet) =====

def _svg_qr(teks):
    img = qrcode.make(teks, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    return svg[svg.index("<svg"):]     # buang deklarasi <?xml?> supaya bisa disisipkan langsung di HTML

@main_bp.route("/api/qr/<no_tiket>")
@login_required
def qr_tiket(no_tiket):
    return Response(_svg_qr(no_tiket), mimetype="image/svg+xml")

@main_bp.route("/cetak/tiket/<no_tiket>")
@login_required
def cetak_tiket(no_tiket):
    row = cari_transaksi_aktif(no_tiket=no_tiket)
    if not row:
        abort(404, "Tiket tidak ditemukan atau sudah selesai")
    cetakan_ke = catat_cetak_qr(no_tiket) + 1
    return render_template("site/cetak_tiket.html", t=row, qr_svg=_svg_qr(row.no_tiket), cetakan_ke=cetakan_ke,
                           now=datetime.now().strftime("%d-%m-%Y %H:%M"))