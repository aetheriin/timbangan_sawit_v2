"""Menu Face Recognition > Personel & Data Master > Driver: daftar, tambah, update, hapus (soft delete)."""
from datetime import date
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from utils.face_utils import extract_embedding_tunggal, embedding_to_binary
from utils.db_utils import cek_nik_ada, cari_wajah_mirip_driver
from utils.db_personel import (get_daftar_personel, get_personel, cek_kode_ada, saran_kode_personel,
                               insert_personel, update_personel, hapus_personel, daftar_kategori, daftar_jenis_sim,
                               sim_dipakai)
from utils.personel_utils import validasi_personel, format_nama_personel
from utils.upload_utils import simpan_upload, hapus_file
from utils.audit_utils import catat_security_audit
from utils.face_cache import slot_proses_wajah
from utils.hak_akses import izin, boleh

personel_bp = Blueprint('personel', __name__)

SUMBER_VALID = ("UPLOAD", "KAMERA")


def _cek_foto(file, exclude_id=None):
    """Simpan foto lalu jalankan 3 pengecekan. Kembalikan (hasil, embedding, path_disk, path_relatif).
    hasil = {satu_wajah, tidak_mirip_personel, tidak_mirip_blacklist, jumlah_wajah, pesan}."""
    path_disk, relatif = simpan_upload(file, "personel")
    with slot_proses_wajah():
        embedding, jumlah = extract_embedding_tunggal(path_disk)
    hasil = {"jumlah_wajah": jumlah, "satu_wajah": jumlah == 1,
             "tidak_mirip_personel": None, "tidak_mirip_blacklist": None, "pesan": None}
    if jumlah != 1:
        hasil["pesan"] = "Wajah tidak terdeteksi" if jumlah == 0 else f"Terdeteksi {jumlah} wajah, foto harus berisi 1 orang"
        return hasil, None, path_disk, relatif

    mirip = cari_wajah_mirip_driver(embedding, exclude_id=exclude_id)
    target = get_personel(mirip[0]) if mirip else None
    hasil["tidak_mirip_blacklist"] = not (target and target["is_blacklisted"])
    hasil["tidak_mirip_personel"] = target is None or target["is_blacklisted"]
    if target:
        nama = format_nama_personel(target["kode_personel"], target["id_personel"], target["nama_personel"])
        hasil["pesan"] = (f"Wajah cocok dengan personel BLACKLIST: {nama}" if target["is_blacklisted"]
                          else f"Wajah sudah terdaftar sebagai {nama}")
        hasil["id_mirip"] = target["id_personel"]
    return hasil, embedding, path_disk, relatif


def _lolos(hasil):
    return hasil["satu_wajah"] and hasil["tidak_mirip_personel"] and hasil["tidak_mirip_blacklist"]


def _catat_jika_blacklist(hasil):
    if hasil.get("tidak_mirip_blacklist") is False:
        catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST",
                             details={"keterangan": f"Pendaftaran personel: {hasil.get('pesan')}",
                                      "id_personel": hasil.get("id_mirip")},
                             ip_address=request.remote_addr)


def _data_form():
    f = request.form
    data = {"kode": f.get("kode_personel", "").strip().upper() or None, "nik": f.get("nik", "").strip(),
            "nama": f.get("nama", "").strip(), "kategori": f.get("kategori", "").strip().upper(),
            "no_sim": f.get("no_sim", "").strip().upper() or None,
            "id_jenis_sim": int(f["id_jenis_sim"]) if (f.get("id_jenis_sim") or "").isdigit() else None,
            "sim_berlaku": f.get("sim_berlaku", "").strip() or None,
            "foto_sumber": f.get("foto_sumber", "UPLOAD").strip().upper()}
    if data["foto_sumber"] not in SUMBER_VALID:
        data["foto_sumber"] = "UPLOAD"
    return data


def _cek_role_kategori(aksi, *kategori):
    """Hak PERSONEL = semua kategori; hak MASTER_DRIVER saja (Data Master > Driver) = hanya kategori Driver."""
    if boleh("PERSONEL", aksi) or all(k == "DRIVER" for k in kategori):
        return None
    return jsonify({"error": "Level Anda hanya bisa mengelola personel kategori Driver"}), 403


def _validasi(data, exclude_id=None):
    kategori = daftar_kategori()
    error = validasi_personel(data["nik"], data["nama"], data["kategori"], data["no_sim"], kategori_valid=kategori,
                              wajib_sim=[k for k, v in kategori.items() if v["wajib_sim"]])
    if error:
        return error
    if data["no_sim"]:              # SIM diisi -> jenis & masa berlaku wajib, nomor tidak dipakai orang lain
        if data["id_jenis_sim"] not in {j["id_jenis_sim"] for j in daftar_jenis_sim()}:
            return "Pilih jenis SIM"
        try:
            data["sim_berlaku"] = date.fromisoformat(data["sim_berlaku"] or "")
        except ValueError:
            return "Isi tanggal berlaku SIM"
        if data["sim_berlaku"] < date.today():
            return f"SIM sudah kedaluwarsa ({data['sim_berlaku']:%d-%m-%Y})"
        if len(data["no_sim"]) > 30:
            return "No. SIM maksimal 30 karakter"
        if sim_dipakai(data["no_sim"], exclude_id):
            return f"No. SIM {data['no_sim']} sudah dipakai personel lain"
    if cek_nik_ada(data["nik"], exclude_id=exclude_id):
        return f"NIK '{data['nik']}' sudah terdaftar (termasuk personel yang sudah dihapus)"
    if data["kode"] and cek_kode_ada(data["kode"], exclude_id):
        return f"Kode '{data['kode']}' sudah dipakai personel lain"
    return None


@personel_bp.route("/api/personel")
@login_required
def personel_daftar():
    kategori = request.args.get("kategori", "").upper()
    return jsonify(get_daftar_personel(kategori if kategori in daftar_kategori(semua=True) else None,
                                       request.args.get("cari", "").strip() or None,
                                       request.args.get("blacklist") == "1"))


@personel_bp.route("/api/personel/saran-kode")
@login_required
def personel_saran_kode():
    """Saran kode per kategori (prefix di Admin › Organisasi › Kategori Personel), mis. DRV-012."""
    return jsonify({"kode": saran_kode_personel((request.args.get("kategori") or "").strip().upper() or None)})


def _rapikan(data, lama=None):
    """SIM hanya untuk kategori wajib SIM. Kode: hanya level dengan hak ubah Personel (HO) boleh mengisi sendiri;
    selain itu otomatis per kategori (tambah) atau tetap kode lama (ubah)."""
    kategori = daftar_kategori(semua=True).get(data["kategori"]) or {}
    if not kategori.get("wajib_sim"):
        data["no_sim"] = data["id_jenis_sim"] = data["sim_berlaku"] = None
    if not boleh("PERSONEL", "ubah"):
        data["kode"] = lama["kode_personel"] if lama else None
    if not data["kode"]:
        data["kode"] = saran_kode_personel(data["kategori"])


@personel_bp.route("/api/personel/<int:id_personel>")
@login_required
def personel_detail(id_personel):
    p = get_personel(id_personel)
    return (jsonify(p), 200) if p else (jsonify({"error": "Personel tidak ditemukan"}), 404)


@personel_bp.route("/api/personel/cek-foto", methods=["POST"])
@login_required
def personel_cek_foto():
    """Pengecekan foto sebelum disimpan (ditampilkan sebagai ✓ / ✕ di modal). Foto tidak disimpan."""
    exclude = request.form.get("id_personel", type=int)
    try:
        hasil, _, path_disk, _ = _cek_foto(request.files.get("foto"), exclude)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    hapus_file(path_disk)
    _catat_jika_blacklist(hasil)
    return jsonify(hasil)


@personel_bp.route("/api/personel/tambah", methods=["POST"])
@login_required
@izin(('PERSONEL', 'MASTER_DRIVER'), 'tambah')
def personel_tambah():
    data = _data_form()
    ditolak = _cek_role_kategori("tambah", data["kategori"])
    if ditolak:
        return ditolak
    _rapikan(data)
    error = _validasi(data)
    if error:
        return jsonify({"error": error}), 400
    try:
        hasil, embedding, path_disk, relatif = _cek_foto(request.files.get("foto"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not _lolos(hasil):
        hapus_file(path_disk)
        _catat_jika_blacklist(hasil)
        return jsonify({"error": hasil["pesan"], "cek": hasil}), 400

    id_baru = insert_personel(data["nik"], data["nama"], data["no_sim"], data["kategori"], data["kode"],
                              embedding_to_binary(embedding), relatif, data["foto_sumber"], current_user.id,
                              data["id_jenis_sim"], data["sim_berlaku"])
    return jsonify({"message": f"Personel '{data['nama']}' ditambahkan dengan ID {id_baru:03d}",
                    "id_personel": id_baru, "cek": hasil})


@personel_bp.route("/api/personel/<int:id_personel>/update", methods=["POST"])
@login_required
@izin(('PERSONEL', 'MASTER_DRIVER'), 'ubah')
def personel_update(id_personel):
    lama = get_personel(id_personel)
    if not lama or not lama["is_active"]:
        return jsonify({"error": "Personel tidak ditemukan"}), 404
    data = _data_form()
    ditolak = _cek_role_kategori("ubah", lama["kategori"], data["kategori"])
    if ditolak:
        return ditolak
    _rapikan(data, lama)
    error = _validasi(data, exclude_id=id_personel)
    if error:
        return jsonify({"error": error}), 400

    embedding_binary = relatif = None
    file = request.files.get("foto")
    if file and file.filename:                       # ganti foto opsional
        try:
            hasil, embedding, path_disk, relatif = _cek_foto(file, exclude_id=id_personel)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if not _lolos(hasil):
            hapus_file(path_disk)
            _catat_jika_blacklist(hasil)
            return jsonify({"error": hasil["pesan"], "cek": hasil}), 400
        embedding_binary = embedding_to_binary(embedding)

    update_personel(id_personel, data["kode"], data["nik"], data["nama"], data["no_sim"], data["kategori"],
                    current_user.id, embedding_binary, relatif, data["foto_sumber"] if relatif else None,
                    data["id_jenis_sim"], data["sim_berlaku"])
    return jsonify({"message": f"Data '{data['nama']}' diperbarui, tercatat di Audit Log",
                    "personel": get_personel(id_personel)})


@personel_bp.route("/api/personel/<int:id_personel>/hapus", methods=["POST"])
@login_required
@izin(('PERSONEL', 'MASTER_DRIVER'), 'hapus')
def personel_hapus(id_personel):
    p = get_personel(id_personel)
    if not p or not p["is_active"]:
        return jsonify({"error": "Personel tidak ditemukan"}), 404
    ditolak = _cek_role_kategori("hapus", p["kategori"])
    if ditolak:
        return ditolak
    if p["is_blacklisted"]:
        return jsonify({"error": "Personel blacklist tidak bisa dihapus (blacklist permanen)"}), 400
    hapus_personel(id_personel, current_user.id)
    return jsonify({"message": f"{format_nama_personel(p['kode_personel'], id_personel, p['nama_personel'])} dihapus. "
                               "Riwayat tiket & absensi tetap tersimpan."})
