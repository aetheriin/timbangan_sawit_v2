"""Data per area: akun di site hanya melihat site-nya; akun di site kantor pusat (Admin › Organisasi › Lokasi,
jenis "Kantor pusat") melihat dan mengelola semua PT, atau hanya PT yang dipilih di Kelola Pengguna."""
from utils.db_kunjungan import area_akun
from utils.db_organisasi import area_pusat, area_per_company, pt_kelola


def area_data(user_id):
    """None = semua area (kantor pusat) · int = site sendiri · tuple = site-site milik PT yang dikelola."""
    area = area_akun(user_id)
    if area not in area_pusat():
        return area
    pt = pt_kelola(user_id)
    if not pt:
        return None
    peta = area_per_company()
    return tuple(sorted(a for c in pt for a in peta.get(c, ())))
