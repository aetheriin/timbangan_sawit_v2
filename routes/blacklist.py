"""Menu Face Recognition > Blacklist: riwayat & tambah. Permanen, tidak ada update / hapus."""
from datetime import date
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from utils.db_blacklist import TIPE_VALID, get_riwayat_blacklist, cari_target, tambah_blacklist, get_target_personel
from utils.face_utils import extract_embedding_tunggal
from utils.face_cache import slot_proses_wajah, cari_terdekat
from utils.plat_utils import normalisasi_plat
from utils import pengaturan
from utils.upload_utils import simpan_upload, hapus_file
from utils.hak_akses import izin
from utils.dokumen import simpan_file, hapus_file_info

blacklist_bp = Blueprint('blacklist', __name__)


@blacklist_bp.route("/api/blacklist")
@login_required
def blacklist_riwayat():
    tipe = request.args.get("tipe", "").upper()
    return jsonify(get_riwayat_blacklist(tipe if tipe in TIPE_VALID else None,
                                         request.args.get("cari", "").strip() or None))


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
        return jsonify({"error": "Wajah tidak terdeteksi" if jumlah == 0 else f"Terdeteksi {jumlah} wajah, harus 1 orang"}), 400
    id_personel, _, jarak = cari_terdekat(embedding, pengaturan.nilai("AMBANG_WAJAH"))
    target = get_target_personel(id_personel) if id_personel else None
    if not target:
        return jsonify({"error": "Wajah tidak cocok dengan personel mana pun. Daftarkan dulu di menu Personel."}), 404
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
        return jsonify({"error": "Pilih target blacklist dulu"}), 400
    if not no_surat or not alasan:
        return jsonify({"error": "No. surat dan alasan wajib diisi"}), 400
    try:
        tgl = date.fromisoformat(f.get("tgl_blacklist", "").strip())
    except ValueError:
        return jsonify({"error": "Tanggal surat tidak valid"}), 400
    if tgl > date.today():
        return jsonify({"error": "Tanggal surat tidak boleh setelah hari ini"}), 400

    try:
        terkait = _terkait(f) if tipe == "PERSONEL" else None
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if len(no_surat) > 100:
        return jsonify({"error": "No. surat maksimal 100 karakter"}), 400
    try:
        info = simpan_file(request.files.get("file_surat"), "SURAT_BLACKLIST")
    except ValueError as e:
        return jsonify({"error": f"Surat: {e}"}), 400

    try:
        tambah_blacklist(tipe, id_target, no_surat, alasan, info, tgl, current_user.id, terkait)
    except Exception as e:
        hapus_file_info([info])
        if isinstance(e, ValueError):
            return jsonify({"error": str(e)}), 400
        raise
    return jsonify({"message": "Blacklist ditetapkan (permanen)"})
