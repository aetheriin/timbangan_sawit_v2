"""Menu Face Recognition > Audit Log: aktivitas security & perubahan data personel."""
import csv
import io
import json
from flask import Blueprint, request, jsonify, Response
from flask_login import login_required
from utils.audit_utils import get_security_audit
from utils.db_personel import get_riwayat_perubahan_personel
from utils.personel_utils import daftar_perubahan, format_id

audit_bp = Blueprint('audit', __name__)

RENTANG_VALID = (1, 7, 30)


def _hari():
    hari = request.args.get("hari", 1, type=int)
    return hari if hari in RENTANG_VALID else 1


def _perubahan_personel(hari):
    hasil = []
    for r in get_riwayat_perubahan_personel(hari):
        hasil.append({"waktu": r["updated_at"].strftime("%Y-%m-%d %H:%M"), "id_personel": format_id(r["id_personel"]),
                      "kode_personel": r["kode_personel"], "nama_personel": r["nama_personel"], "aksi": r["aksi"],
                      "perubahan": [{"kolom": k, "lama": lama, "baru": baru} for k, lama, baru in daftar_perubahan(r)],
                      "oleh": f"{r['oleh']} ({r['role_oleh']})"})
    return hasil


@audit_bp.route("/api/audit/security")
@login_required
def audit_security():
    return jsonify(get_security_audit(_hari()))


@audit_bp.route("/api/audit/personel")
@login_required
def audit_personel():
    return jsonify(_perubahan_personel(_hari()))


@audit_bp.route("/api/audit/export")
@login_required
def audit_export():
    """CSV aktivitas security + perubahan personel pada rentang yang dipilih (dibuka di Excel)."""
    hari = _hari()
    buf = io.StringIO()
    tulis = csv.writer(buf, delimiter=';')
    tulis.writerow(["AKTIVITAS SECURITY"])
    tulis.writerow(["Waktu", "User", "Role", "Aksi", "No. Tiket", "Detail", "IP"])
    for r in get_security_audit(hari):
        tulis.writerow([r["created_at"], r["nama_user"], r["role"], r["action_type"], r["no_tiket"] or "",
                        json.dumps(r["details"], ensure_ascii=False), r["ip_address"] or ""])
    tulis.writerow([])
    tulis.writerow(["PERUBAHAN DATA PERSONEL"])
    tulis.writerow(["Waktu", "ID", "Kode", "Aksi", "Perubahan", "Oleh"])
    for r in _perubahan_personel(hari):
        ubah = ", ".join(f"{p['kolom']}: {p['lama'] or '-'} -> {p['baru'] or '-'}" for p in r["perubahan"])
        tulis.writerow([r["waktu"], r["id_personel"], r["kode_personel"] or "", r["aksi"], ubah, r["oleh"]])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=audit_log_{hari}_hari.csv"})
