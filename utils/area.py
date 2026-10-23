"""Data per area: akun di area biasa hanya melihat areanya; akun di area bertipe Mill kantor pusat (Admin › Organisasi ›
Mill, centang "Kantor pusat") melihat dan mengelola semua PT, atau hanya PT yang dipilih di Kelola Pengguna.
Aturannya ada di database (dbo.fn_UserScopeInfo / fn_UserScope / sp_UserScope) supaya sama untuk semua aplikasi."""
from utils.db_organisasi import cakupan_user, pt_kelola


def area_data(user_id):
    """None = semua area (kantor pusat) · int = site sendiri · tuple = site-site milik PT yang dikelola."""
    c = cakupan_user(user_id)
    if c is None or c["AllAreas"]:
        return None
    if c["IsHeadOffice"]:
        return c["areas"]
    return c["OwnAreaID"]


def company_user(user_id):
    """PT user: id company site-nya. Kantor pusat: None = semua PT, atau frozenset PT yang dikelola."""
    c = cakupan_user(user_id)
    if c is not None and c["IsHeadOffice"]:
        return None if c["AllAreas"] else (pt_kelola(user_id) or None)
    return frozenset({c["OwnCompID"] if c else None})
