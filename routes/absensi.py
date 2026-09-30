"""Menu Face Recognition > Absensi: scan wajah live + liveness, rekap harian/bulanan, jadwal kerja."""
import os
import uuid
import shutil
from datetime import datetime, date
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from extensions import UPLOAD_FOLDER
from utils.face_utils import extract_embedding, verifikasi_liveness
from utils.face_cache import slot_proses_wajah, cari_terdekat
from utils.db_personel import get_personel
from utils.db_absensi import (get_jadwal_kerja, get_jadwal_hari, get_scan_terakhir, insert_absensi,
                              get_absensi_harian, get_rekap_bulanan)
from utils.absensi_rules import tentukan_jenis, is_duplikat, hitung_status_waktu, hari_iso
from utils.personel_utils import KATEGORI_VALID, format_nama_personel
from utils.audit_utils import catat_security_audit

absensi_bp = Blueprint('absensi', __name__)

AMBANG_JARAK = 0.55
TANTANGAN_VALID = ("KEDIP", "MENOLEH_KIRI", "MENOLEH_KANAN")


def _personel_terdekat(embedding):
    """(id_personel, jarak) terdekat yang masih di bawah ambang, atau (None, jarak_terdekat)."""
    id_personel, _, jarak = cari_terdekat(embedding, AMBANG_JARAK)
    return id_personel, jarak


def _jam(t):
    return t.strftime("%H:%M") if t else None


@absensi_bp.route("/api/absensi/scan", methods=["POST"])
@login_required
def absensi_scan():
    files = request.files.getlist("frames")
    tantangan = request.form.get("tantangan", "KEDIP")
    if tantangan not in TANTANGAN_VALID:
        return jsonify({"error": "Tantangan liveness tidak valid"}), 400
    if len(files) < 3:
        return jsonify({"error": "Frame kamera tidak cukup, ulangi scan"}), 400

    folder_tmp = os.path.join(UPLOAD_FOLDER, "tmp")
    os.makedirs(folder_tmp, exist_ok=True)
    paths = []
    try:
        for f in files:
            path = os.path.join(folder_tmp, f"abs_{uuid.uuid4().hex}.jpg")
            f.save(path)
            paths.append(path)

        tengah = paths[len(paths) // 2]
        with slot_proses_wajah():
            if not verifikasi_liveness(paths, tantangan):      # gagal liveness tidak dicatat (bisa diulang)
                return jsonify({"error": "Liveness tidak lolos. Ikuti tantangan lalu ulangi scan."}), 400
            embedding = extract_embedding(tengah)
        if embedding is None:
            return jsonify({"error": "Wajah tidak terdeteksi, ulangi scan"}), 400

        sekarang = datetime.now()
        folder_foto = os.path.join(UPLOAD_FOLDER, "absensi")
        os.makedirs(folder_foto, exist_ok=True)
        nama_foto = f"{sekarang:%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}.jpg"
        shutil.copyfile(tengah, os.path.join(folder_foto, nama_foto))
        foto_path = f"uploads/absensi/{nama_foto}"

        perangkat, ip = request.form.get("perangkat", "Web")[:50], request.remote_addr
        id_personel, jarak = _personel_terdekat(embedding)
        if id_personel is None:
            insert_absensi(None, None, "TIDAK_DIKENALI", None, None, jarak, tantangan, foto_path, perangkat, ip, sekarang)
            return jsonify({"status": "TIDAK_DIKENALI", "error": "Wajah tidak dikenali. Hubungi HO untuk pendaftaran."}), 404

        p = get_personel(id_personel)
        nama = format_nama_personel(p["kode_personel"], id_personel, p["nama_personel"])
        if p["is_blacklisted"]:
            insert_absensi(id_personel, None, "DITOLAK_BLACKLIST", None, None, jarak, tantangan, foto_path, perangkat, ip, sekarang)
            catat_security_audit(current_user.id, "TRY_SCAN_BLACKLIST",
                                 details={"keterangan": f"Scan absensi {nama} ditolak (blacklist)",
                                          "id_personel": id_personel},
                                 ip_address=ip)
            return jsonify({"status": "DITOLAK_BLACKLIST", "error": f"{nama} masuk daftar BLACKLIST. Absensi ditolak."}), 403

        terakhir, sudah_masuk = get_scan_terakhir(id_personel, sekarang.date())
        if is_duplikat(terakhir, sekarang):
            return jsonify({"status": "DUPLIKAT", "error": f"{nama} sudah absen pukul {terakhir:%H:%M}. Scan diabaikan."}), 409

        jenis = tentukan_jenis(sudah_masuk)
        jadwal = get_jadwal_hari(hari_iso(sekarang))
        status_waktu, selisih = hitung_status_waktu(jenis, sekarang, jadwal)
        insert_absensi(id_personel, jenis, "BERHASIL", status_waktu, selisih, jarak, tantangan, foto_path, perangkat, ip, sekarang)
        return jsonify({
            "status": "BERHASIL", "id_personel": id_personel, "kode_personel": p["kode_personel"],
            "nama_personel": p["nama_personel"], "nama_tampil": nama, "kategori": p["kategori"],
            "foto_path": p["foto_path"], "foto_scan": foto_path, "jenis": jenis, "status_waktu": status_waktu,
            "selisih_menit": selisih, "waktu": sekarang.strftime("%Y-%m-%d %H:%M:%S"),
            "jadwal": None if not jadwal or jadwal["is_libur"] else
            {"nama_hari": jadwal["nama_hari"], "jam_masuk": _jam(jadwal["jam_masuk"]), "jam_pulang": _jam(jadwal["jam_pulang"])},
            "jarak_wajah": round(jarak, 3), "ambang": AMBANG_JARAK, "tantangan": tantangan,
        })
    finally:
        for path in paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


@absensi_bp.route("/api/absensi/harian")
@login_required
def absensi_harian():
    try:
        tanggal = date.fromisoformat(request.args.get("tanggal") or date.today().isoformat())
    except ValueError:
        return jsonify({"error": "Tanggal tidak valid"}), 400
    kategori = request.args.get("kategori", "").upper()
    return jsonify(get_absensi_harian(tanggal, kategori if kategori in KATEGORI_VALID else None))


@absensi_bp.route("/api/absensi/rekap")
@login_required
def absensi_rekap():
    try:
        tahun, bulan = map(int, (request.args.get("bulan") or date.today().strftime("%Y-%m")).split("-"))
        date(tahun, bulan, 1)
    except ValueError:
        return jsonify({"error": "Bulan tidak valid (YYYY-MM)"}), 400
    return jsonify(get_rekap_bulanan(tahun, bulan))


@absensi_bp.route("/api/jadwal-kerja")
@login_required
def jadwal_kerja():
    return jsonify([{**j, "jam_masuk": _jam(j["jam_masuk"]), "jam_pulang": _jam(j["jam_pulang"])}
                    for j in get_jadwal_kerja()])
