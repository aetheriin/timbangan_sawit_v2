"""Menu Kelebihan DO + notifikasi lonceng. Hak: KELEBIHAN_DO tambah = krani (isi No. DO baru dari Ascend),
ubah = KTU / HO (tetapkan / kembalikan). Diatur di Admin › Level & Hak Akses."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from utils import db_kelebihan_do as db, notifikasi
from utils.hak_akses import izin, boleh

kelebihan_do_bp = Blueprint("kelebihan_do", __name__)


@kelebihan_do_bp.route("/kelebihan-do")
@login_required
def halaman():
    return render_template("kelebihan_do/kelebihan_do.html", halaman="kelebihan_do",
                           boleh_ajukan=boleh(db.MENU, "tambah"), boleh_tetapkan=boleh(db.MENU, "ubah"))


@kelebihan_do_bp.route("/api/kelebihan-do")
@login_required
def daftar():
    status = (request.args.get("status") or "").upper()
    return jsonify(db.daftar(status if status in db.STATUS else None))


def _jalankan(fn):
    try:
        fn()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return None


@kelebihan_do_bp.route("/api/kelebihan-do/<int:id_kelebihan>/ajukan", methods=["POST"])
@login_required
@izin(db.MENU, "tambah")
def ajukan(id_kelebihan):
    no_do = (request.form.get("no_do_baru") or "").strip().upper()
    catatan = (request.form.get("catatan") or "").strip()[:255] or None
    if not no_do or len(no_do) > 50:
        return jsonify({"error": "No. DO baru wajib diisi (maks 50 karakter)"}), 400
    return _jalankan(lambda: db.ajukan(id_kelebihan, no_do, catatan, current_user.id)) or \
        jsonify({"message": f"No. DO {no_do} diajukan, menunggu KTU / HO"})


@kelebihan_do_bp.route("/api/kelebihan-do/<int:id_kelebihan>/tetapkan", methods=["POST"])
@login_required
@izin(db.MENU, "ubah")
def tetapkan(id_kelebihan):
    return _jalankan(lambda: db.tetapkan(id_kelebihan, current_user.id)) or jsonify({"message": "Kelebihan DO ditetapkan"})


@kelebihan_do_bp.route("/api/kelebihan-do/<int:id_kelebihan>/kembalikan", methods=["POST"])
@login_required
@izin(db.MENU, "ubah")
def kembalikan(id_kelebihan):
    alasan = (request.form.get("alasan") or "").strip()[:255]
    if not alasan:
        return jsonify({"error": "Alasan wajib diisi"}), 400
    return _jalankan(lambda: db.kembalikan(id_kelebihan, alasan, current_user.id)) or \
        jsonify({"message": "Dikembalikan ke krani"})


# ===== NOTIFIKASI (lonceng top bar) =====
@kelebihan_do_bp.route("/api/notifikasi")
@login_required
def notifikasi_daftar():
    rows, belum = notifikasi.daftar(current_user)
    return jsonify({"notifikasi": rows, "belum_dibaca": belum})


@kelebihan_do_bp.route("/api/notifikasi/baca", methods=["POST"])
@login_required
def notifikasi_baca():
    teks = (request.form.get("id_notifikasi") or "").strip()
    notifikasi.tandai_baca(current_user, int(teks) if teks.isdigit() else None)
    return jsonify({"message": "OK"})
