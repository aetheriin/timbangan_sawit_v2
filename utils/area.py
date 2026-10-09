"""Data per area: akun di area site hanya melihat site-nya; akun di area kantor pusat (Admin › Pengaturan Site ›
AREA_PUSAT) melihat semua area."""
from utils import pengaturan
from utils.db_kunjungan import area_akun


def area_data(user_id):
    """id area untuk menyaring data, atau None = semua area (kantor pusat)."""
    area = area_akun(user_id)
    pusat = pengaturan.nilai("AREA_PUSAT")
    return None if pusat and area == pusat else area
