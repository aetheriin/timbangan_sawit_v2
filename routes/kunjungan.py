"""Face Recognition › Kunjungan Tamu: scan wajah tamu, daftarkan tamu baru, catat masuk / keluar.

Tamu adalah personel kategori TAMU tanpa akun login. Wajahnya dicocokkan dengan semua personel aktif,
jadi tamu yang pernah datang (atau masuk blacklist) langsung dikenali."""
from datetime import date

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from utils import pengaturan
from utils import db_kunjungan as db
from utils.audit_utils import catat_security_audit
from utils.db_personel import get_personel, insert_personel, saran_kode_personel
from utils.db_utils import cek_nik_ada
from utils.face_cache import slot_proses_wajah, cari_terdekat
from utils.face_utils import extract_embedding_tunggal, embedding_to_binary, cek_liveness
from utils.hak_akses import izin
from utils.personel_utils import format_nama_personel, validasi_personel
from utils.plat_utils import normalisasi_plat
from utils.upload_utils import simpan_upload, simpan_frames, hapus_file

kunjungan_bp = Blueprint("kunjungan", __name__)


def _info_personel(p, jarak=None):
    return {"id_personel": p["id_personel"], "kode_personel": p["kode_personel"], "nama_personel": p["nama_personel"],
            "nik": p["nik"], "kategori": p["kategori"], "is_blacklisted": p["is_blacklisted"], "foto_path": p["foto_path"],
            "nama_tampil": format_nama_personel(p["kode_personel"], p["id_personel"], p["nama_personel"]),
            "jarak_wajah": round(jarak, 3) if jarak is not None else None,
            "kunjungan_aktif": db.kunjungan_aktif(p["id_personel"]) is not None}


@kunjungan_bp.route("/api/kunjungan")
@login_required
def kunjungan_daftar():
    if request.args.get("status") == "DIDALAM":
        return jsonify(db.daftar_kunjungan(hanya_didalam=True))
    try:
        tanggal = date.fromisoformat(request.args.get("tanggal") or date.today().isoformat())
    except ValueError:
        return jsonify({"error": "Format tanggal salah"}), 400
    return jsonify(db.daftar_kunjungan(tanggal))


@kunjungan_bp.route("/api/kunjungan/dituju")
@login_required
def kunjungan_dituju():
    return jsonify(db.daftar_dituju())


@kunjungan_bp.route("/api/kunjungan/cari-wajah", methods=["POST"])
@login_required
@izin("KUNJUNGAN", "tambah")
def kunjungan_cari_wajah():
    """Foto dari kamera -> personel yang paling mirip, atau dikenali=False (tamu baru). Foto tidak disimpan.
    Bila tantangan tamu wajib di area ini (TANTANGAN_TAMU): beberapa frame + tantangan, dicek liveness."""
    area = db.area_akun(current_user.id)
    wajib = pengaturan.nilai("TANTANGAN_TAMU", area)
    try:
        paths = (simpan_frames(request.files.getlist("frames"), maks=20) if wajib
                 else [simpan_upload(request.files.get("foto"), "tmp")[0]])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    try:
        with slot_proses_wajah():
            if not cek_liveness(paths, request.form.get("tantangan", ""), wajib):
                return jsonify({"error": "Liveness tidak lolos. Ikuti tantangan lalu ulangi scan."}), 400
            embedding, jumlah = extract_embedding_tunggal(paths[len(paths) // 2])
    finally:
        for p in paths:
            hapus_file(p)
    if jumlah != 1:
        return jsonify({"error": "Wajah tidak terdeteksi" if jumlah == 0 else f"Terdeteksi {jumlah} wajah, harus 1 orang"}), 400
    id_personel, _, jarak = cari_terdekat(embedding, pengaturan.nilai("AMBANG_WAJAH", area))
    p = get_personel(id_personel) if id_personel else None
    if not p:
        return jsonify({"dikenali": False})
    if p["is_blacklisted"]:
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                             details={"keterangan": f"Kunjungan tamu: wajah cocok dengan {format_nama_personel(p['kode_personel'], id_personel, p['nama_personel'])} (blacklist)",
                                      "id_personel": id_personel})
    return jsonify({"dikenali": True, **_info_personel(p, jarak)})


@kunjungan_bp.route("/api/kunjungan/tamu-baru", methods=["POST"])
@login_required
@izin("KUNJUNGAN", "tambah")
def kunjungan_tamu_baru():
    """Daftarkan tamu baru (personel kategori TAMU) dari foto kamera yang sama."""
    nik, nama = request.form.get("nik", "").strip(), request.form.get("nama", "").strip()
    error = validasi_personel(nik, nama, "TAMU", None)
    if error:
        return jsonify({"error": error}), 400
    if cek_nik_ada(nik):
        return jsonify({"error": f"NIK {nik} sudah terdaftar. Scan ulang wajahnya atau hubungi HO."}), 400
    try:
        path_disk, relatif = simpan_upload(request.files.get("foto"), "personel")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    with slot_proses_wajah():
        embedding, jumlah = extract_embedding_tunggal(path_disk)
    if jumlah != 1:
        hapus_file(path_disk)
        return jsonify({"error": "Wajah tidak terdeteksi" if jumlah == 0 else f"Terdeteksi {jumlah} wajah, harus 1 orang"}), 400
    id_mirip, _, _ = cari_terdekat(embedding, pengaturan.nilai("AMBANG_WAJAH", db.area_akun(current_user.id)))
    if id_mirip:
        hapus_file(path_disk)
        p = get_personel(id_mirip)
        return jsonify({"error": f"Wajah sudah terdaftar sebagai {format_nama_personel(p['kode_personel'], id_mirip, p['nama_personel'])}"}), 400
    id_baru = insert_personel(nik, nama, None, "TAMU", saran_kode_personel("TAMU"), embedding_to_binary(embedding), relatif, "KAMERA",
                              current_user.id)
    return jsonify({"message": f"Tamu {nama} didaftarkan", **_info_personel(get_personel(id_baru))})


def _id_pilihan(nama, pilihan, label):
    teks = (request.form.get(nama) or "").strip()
    if not teks.isdigit() or int(teks) not in pilihan:
        raise ValueError(f"Pilih {label}")
    return int(teks)


@kunjungan_bp.route("/api/kunjungan/masuk", methods=["POST"])
@login_required
@izin("KUNJUNGAN", "tambah")
def kunjungan_masuk():
    f = request.form
    try:
        id_tamu = int(f.get("id_personel") or 0)
        p = get_personel(id_tamu) if id_tamu else None
        if not p or not p["is_active"]:
            raise ValueError("Scan wajah tamu dulu")
        if p["kategori"] != "TAMU":
            raise ValueError(f"{p['nama_personel']} bukan tamu (kategori {p['kategori']})")
        if db.kunjungan_aktif(id_tamu):
            raise ValueError(f"{p['nama_personel']} masih tercatat di dalam. Catat keluar dulu.")
        id_dituju = _id_pilihan("id_dituju", {d["id_personel"] for d in db.daftar_dituju()}, "orang yang dituju")
        id_keperluan = _id_pilihan("id_keperluan", {k["id_keperluan"] for k in db.daftar_keperluan()}, "keperluan")
        no_plat = None
        if (f.get("no_plat") or "").strip():
            no_plat, error = normalisasi_plat(f.get("no_plat"))
            if error:
                raise ValueError(error)
        asal = (f.get("asal_perusahaan") or "").strip()[:100] or None
        keterangan = (f.get("keterangan") or "").strip()[:255] or None
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if p["is_blacklisted"]:             # blacklist = peringatan: tamu tetap dicatat, tercatat di Audit Log
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST", ip_address=request.remote_addr,
                             details={"keterangan": f"Tamu blacklist dicatat masuk: "
                                                    f"{format_nama_personel(p['kode_personel'], id_tamu, p['nama_personel'])}",
                                      "id_personel": id_tamu})
    foto = None
    if request.files.get("foto"):
        try:
            _, foto = simpan_upload(request.files["foto"], "kunjungan")
        except ValueError:
            foto = None                 # snapshot opsional, kunjungan tetap dicatat
    id_kunjungan = db.catat_masuk(id_tamu, id_dituju, id_keperluan, keterangan, asal, no_plat,
                                  db.area_akun(current_user.id), foto, current_user.id)
    return jsonify({"message": f"Kunjungan {p['nama_personel']} dicatat", "id_kunjungan": id_kunjungan})


@kunjungan_bp.route("/api/kunjungan/<int:id_kunjungan>/keluar", methods=["POST"])
@login_required
@izin("KUNJUNGAN", "ubah")
def kunjungan_keluar(id_kunjungan):
    if not db.catat_keluar(id_kunjungan):
        return jsonify({"error": "Kunjungan tidak ditemukan atau sudah keluar"}), 400
    return jsonify({"message": "Tamu dicatat keluar"})
