"""Tahap 1 Security: Pos Security (kendaraan masuk tanpa tiket) dan Logbook Kendaraan (masih di dalam / sudah keluar).

Langkah 1 = tampilan untuk disetujui: halaman memakai data master sungguhan (customer, produk, transportir sesuai PT
pengguna) tetapi isi Logbook masih data contoh di static/js/pos/logbook.js. Penyimpanan menyusul di langkah 2."""
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from utils import pengaturan
from utils.area import company_user
from utils.db_admin import supplier_boleh
from utils.db_kontrak import daftar_mitra
from utils.db_kunjungan import area_akun
from utils.db_utils import get_semua_supplier, get_semua_produk
from utils.hak_akses import boleh, halaman as lihat_halaman

pos_bp = Blueprint("pos", __name__)


@pos_bp.route("/pos-security")
@login_required
@lihat_halaman("POS_SECURITY")
def pos_security():
    pt = company_user(current_user.id)
    return render_template("pos/pos_security.html", halaman="pos",
                           supplier_list=[s for s in get_semua_supplier()
                                          if s.is_customer and supplier_boleh(s.id_supplier, pt)],
                           produk_list=get_semua_produk(),
                           transportir_list=[m for m in daftar_mitra()
                                             if m["peran"] == "PENGANGKUTAN" and supplier_boleh(m["id_supplier"], pt)],
                           boleh_simpan=boleh("POS_SECURITY", "tambah"), boleh_ubah_supir=boleh("POS_SECURITY", "ubah"),
                           boleh_blacklist=boleh("BLACKLIST", "tambah"), boleh_keluar=boleh("LOGBOOK", "ubah"))


@pos_bp.route("/logbook")
@login_required
@lihat_halaman("LOGBOOK")
def logbook():
    return render_template("pos/logbook.html", halaman="logbook", boleh_keluar=boleh("LOGBOOK", "ubah"),
                           batas_jam=pengaturan.nilai("BATAS_LAMA_DI_DALAM_JAM", area_akun(current_user.id)))
