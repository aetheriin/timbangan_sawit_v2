"""Menu Blacklist: riwayat, ajukan tambah & ajukan hapus (cabut). Keduanya lewat persetujuan dinamis
(Admin › Persetujuan); tanpa penyetuju yang diatur, langsung berlaku. Data blacklist tidak pernah dihapus."""
from datetime import date
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from utils.db_blacklist import (TIPE_VALID, get_riwayat_blacklist, cari_target, tambah_blacklist, get_target_personel,
                                get_surat_blacklist, lampirkan_surat, nama_target, get_blacklist, cabut_blacklist)
from utils import persetujuan
from utils.face_utils import extract_embedding_tunggal
from utils.face_cache import slot_proses_wajah, cari_terdekat
from utils.plat_utils import normalisasi_plat
from utils import pengaturan
from utils.db_kunjungan import area_akun
from utils.upload_utils import simpan_upload, hapus_file
from utils.hak_akses import izin
from utils.dokumen import simpan_file, hapus_file_info

blacklist_bp = Blueprint('blacklist', __name__)


@blacklist_bp.route("/api/blacklist")
@login_required
def blacklist_riwayat():
    tipe = request.args.get("tipe", "").upper()
    status = request.args.get("status", "AKTIF").upper()
    return jsonify(get_riwayat_blacklist(tipe if tipe in TIPE_VALID else None,
                                         request.args.get("cari", "").strip() or None,
                                         status=status if status in ("AKTIF", "DICABUT") else "AKTIF"))


@blacklist_bp.route("/api/blacklist/info/<tipe>/<int:id_target>")
@login_required
def blacklist_info(tipe, id_target):
    """Surat & penetap blacklist (banner peringatan Form Security). Blacklist berlaku di semua area."""
    tipe = tipe.upper()
    if tipe not in ("PERSONEL", "KENDARAAN"):
        return jsonify({"error": "Tipe tidak dikenal"}), 400
    return jsonify(get_surat_blacklist(tipe, id_target) or {})


@blacklist_bp.route("/api/blacklist/cari-target")
@login_required
def blacklist_cari_target():
    tipe = request.args.get("tipe", "PERSONEL").upper()
    kata = request.args.get("q", "").strip()
    if tipe not in TIPE_VALID or len(kata) < 2:
        return jsonify([])
    return jsonify(cari_target(tipe, kata))


@blacklist_bp.route("/api/blacklist/cari-wajah", methods=["POST"])
@login_required
@izin('BLACKLIST', 'tambah')
def blacklist_cari_wajah():
    """Target blacklist dari wajah: foto kamera atau upload -> personel yang paling mirip. Foto tidak disimpan."""
    try:
        path_disk, _ = simpan_upload(request.files.get("foto"), "tmp")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    try:
        with slot_proses_wajah():
            embedding, jumlah = extract_embedding_tunggal(path_disk)
    finally:
        hapus_file(path_disk)
    if jumlah != 1:
        return jsonify({"error": "Wajah tidak terdeteksi" if jumlah == 0 else f"Terdeteksi {jumlah} wajah. Pastikan hanya 1 orang di depan kamera"}), 400
    id_personel, _, jarak = cari_terdekat(embedding, pengaturan.nilai("AMBANG_WAJAH", area_akun(current_user.id)))
    target = get_target_personel(id_personel) if id_personel else None
    if not target:
        return jsonify({"error": "Wajah tidak cocok dengan personel mana pun. Silakan daftarkan melalui menu Personel."}), 404
    return jsonify({**target, "jarak_wajah": round(jarak, 3)})


def _terkait(f):
    """Info saat blacklist (personel): plat (boleh untuk tamu), customer & pengangkutan bila ia supir."""
    teks_plat = (f.get("no_plat_terkait") or "").strip()
    no_plat = None
    if teks_plat:
        no_plat, error = normalisasi_plat(teks_plat)
        if error:
            raise ValueError(error)
    angka = lambda k: f.get(k, type=int) or None
    return {"no_plat": no_plat, "id_customer": angka("id_customer_terkait"), "id_pengangkutan": angka("id_pengangkutan_terkait")}


@blacklist_bp.route("/api/blacklist/tambah", methods=["POST"])
@login_required
@izin('BLACKLIST', 'tambah')
def blacklist_tambah():
    f = request.form
    tipe = f.get("tipe_entitas", "").upper()
    id_target = f.get("id_target", type=int)
    no_surat, alasan = f.get("no_surat", "").strip(), f.get("alasan", "").strip()
    if tipe not in TIPE_VALID or not id_target:
        return jsonify({"error": "Silakan pilih target blacklist"}), 400
    if not alasan:
        return jsonify({"error": "Alasan wajib diisi"}), 400
    file = request.files.get("file_surat")
    ada_file = bool(file and file.filename)
    if not no_surat and ada_file:
        return jsonify({"error": "Isi No. surat untuk file yang diunggah, atau kosongkan keduanya (surat menyusul)"}), 400
    if no_surat and not ada_file:
        return jsonify({"error": "Unggah file surat, atau kosongkan No. surat (surat menyusul)"}), 400
    tgl, error = _tanggal_surat(f) if no_surat else (None, None)
    if error:
        return jsonify({"error": error}), 400

    try:
        terkait = _terkait(f) if tipe == "PERSONEL" else None
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if len(no_surat) > 100:
        return jsonify({"error": "No. surat maksimal 100 karakter"}), 400
    try:
        nama, sudah = nama_target(tipe, id_target)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if sudah:
        return jsonify({"error": "Target sudah masuk blacklist"}), 400
    info = None
    if no_surat:
        try:
            info = simpan_file(file, "SURAT_BLACKLIST")
        except ValueError as e:
            return jsonify({"error": f"Surat: {e}"}), 400

    data = {"tipe": tipe, "id_target": id_target, "no_surat": no_surat or None, "alasan": alasan, "file_info": info,
            "tgl": tgl.isoformat() if tgl else None, "terkait": terkait}
    try:
        status, penyetuju = persetujuan.ajukan("BLACKLIST_TAMBAH", f"{tipe}:{id_target}", f"Tambah blacklist {nama}",
                                               alasan, data, current_user.id)
    except Exception as e:
        if info:
            hapus_file_info([info])
        if isinstance(e, ValueError):
            return jsonify({"error": str(e)}), 400
        raise
    if status == "MENUNGGU":
        return jsonify({"message": f"Pengajuan blacklist {nama} berhasil dikirim dan menunggu persetujuan {penyetuju}. "
                                   "Blacklist berlaku setelah disetujui.", "menunggu": True})
    return jsonify({"message": "Blacklist berhasil ditetapkan" + ("" if no_surat else ". Surat dapat dilampirkan menyusul.")})


@blacklist_bp.route("/api/blacklist/<int:id_blacklist>/hapus", methods=["POST"])
@login_required
@izin('BLACKLIST', 'hapus')
def blacklist_hapus(id_blacklist):
    """Ajukan pencabutan blacklist. Baris blacklist tetap tersimpan sebagai riwayat."""
    alasan = (request.form.get("alasan") or "").strip()
    if not alasan:
        return jsonify({"error": "Alasan hapus blacklist wajib diisi"}), 400
    b = get_blacklist(id_blacklist)
    if not b or b["dicabut_at"]:
        return jsonify({"error": "Blacklist tidak ditemukan atau sudah dicabut"}), 400
    try:
        status, penyetuju = persetujuan.ajukan("BLACKLIST_HAPUS", f"BLACKLIST:{id_blacklist}", f"Hapus blacklist {b['nama']}",
                                               alasan[:500], {"id_blacklist": id_blacklist, "alasan": alasan[:500]}, current_user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if status == "MENUNGGU":
        return jsonify({"message": f"Pengajuan hapus blacklist {b['nama']} berhasil dikirim dan menunggu persetujuan {penyetuju}."})
    return jsonify({"message": f"Blacklist {b['nama']} berhasil dicabut."})


# ===== Pelaksana persetujuan (dijalankan saat langkah terakhir disetujui) =====
def _batal_tambah(data):
    if data.get("file_info"):
        hapus_file_info([data["file_info"]])


@persetujuan.pelaksana("BLACKLIST_TAMBAH", saat_ditolak=_batal_tambah)
def _jalankan_tambah(data, id_pengaju, id_penyetuju):
    tgl = date.fromisoformat(data["tgl"]) if data.get("tgl") else None
    tambah_blacklist(data["tipe"], data["id_target"], data.get("no_surat"), data["alasan"], data.get("file_info"), tgl,
                     id_pengaju, data.get("terkait"))


@persetujuan.pelaksana("BLACKLIST_HAPUS")
def _jalankan_hapus(data, id_pengaju, id_penyetuju):
    cabut_blacklist(data["id_blacklist"], data.get("alasan"), id_penyetuju)


def _tanggal_surat(f):
    try:
        tgl = date.fromisoformat(f.get("tgl_blacklist", "").strip())
    except ValueError:
        return None, "Tanggal surat tidak valid"
    if tgl > date.today():
        return None, "Tanggal surat tidak boleh setelah hari ini"
    return tgl, None


@blacklist_bp.route("/api/blacklist/<int:id_blacklist>/surat", methods=["POST"])
@login_required
@izin('BLACKLIST', 'tambah')
def blacklist_lampirkan_surat(id_blacklist):
    """Lampirkan surat blacklist yang menyusul (No. surat, tanggal, file)."""
    f = request.form
    no_surat = f.get("no_surat", "").strip()
    if not no_surat or len(no_surat) > 100:
        return jsonify({"error": "No. surat wajib diisi (maks 100 karakter)"}), 400
    tgl, error = _tanggal_surat(f)
    if error:
        return jsonify({"error": error}), 400
    try:
        info = simpan_file(request.files.get("file_surat"), "SURAT_BLACKLIST")
    except ValueError as e:
        return jsonify({"error": f"Surat: {e}"}), 400
    try:
        lampirkan_surat(id_blacklist, no_surat, tgl, info, current_user.id)
    except Exception as e:
        hapus_file_info([info])
        if isinstance(e, ValueError):
            return jsonify({"error": str(e)}), 400
        raise
    return jsonify({"message": "Surat blacklist berhasil dilampirkan"})
