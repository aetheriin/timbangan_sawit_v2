"""Data per area: akun di area biasa hanya melihat areanya; akun di area bertipe Mill kantor pusat (Admin › Organisasi ›
Mill, centang "Kantor pusat") melihat dan mengelola semua PT, atau hanya PT yang dipilih di Kelola Pengguna."""
from utils.db_kunjungan import area_akun
from utils.db_organisasi import area_pusat, area_per_company, company_area, pt_kelola


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


def company_user(user_id):
    """PT user: id company site-nya. Kantor pusat: None = semua PT, atau frozenset PT yang dikelola."""
    area = area_akun(user_id)
    if area in area_pusat():
        return pt_kelola(user_id) or None
    return frozenset({company_area().get(area)})
