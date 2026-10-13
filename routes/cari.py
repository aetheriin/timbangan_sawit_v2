"""Pencarian global di header (Ctrl+K). Admin hanya area Admin -> endpoint terpisah /api/admin/cari."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from utils import db_cari
from utils.area import area_data
from utils.hak_akses import admin_required

cari_bp = Blueprint("cari", __name__)
MIN_HURUF = 2


def _kata():
    return (request.args.get("q") or "").strip()[:50]


BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def _waktu(r):
    w = r.get("created_at")
    return {**r, "created_at": f"{w.day} {BULAN[w.month - 1]} {w.year}, {w:%H:%M}" if w else None}


@cari_bp.route("/api/cari")
@login_required
def cari():
    kata = _kata()
    if len(kata) < MIN_HURUF:
        return jsonify({"tiket": [], "personel": [], "kendaraan": []})
    return jsonify({
        "tiket": [_waktu({**r, "netto": float(r["netto"]) if r["netto"] is not None else None})
                  for r in db_cari.cari_tiket(kata, area_data(current_user.id))],
        "personel": db_cari.cari_personel(kata),
        "kendaraan": db_cari.cari_kendaraan(kata),
    })


@cari_bp.route("/api/admin/cari")
@login_required
@admin_required
def cari_admin():
    kata = _kata()
    return jsonify({"akun": db_cari.cari_akun(kata) if len(kata) >= MIN_HURUF else []})
