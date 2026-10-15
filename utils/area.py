"""Data per area: akun di site hanya melihat site-nya; akun di site kantor pusat (Admin › Organisasi › Lokasi,
tanda "Kantor pusat") melihat dan mengelola semua PT & site."""
from utils.db_kunjungan import area_akun
from utils.db_organisasi import area_pusat


def area_data(user_id):
    """id area untuk menyaring data, atau None = semua area (kantor pusat)."""
    area = area_akun(user_id)
    return None if area in area_pusat() else area
