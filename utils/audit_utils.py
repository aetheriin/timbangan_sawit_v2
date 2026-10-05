"""Aktivitas security yang dipantau HO (menu Face Recognition > Audit Log), kategori SECURITY di log_aktivitas."""
from utils import log_aktivitas

AKSI_VALID = ("TRY_SCAN_BLACKLIST", "OVERRIDE_DRIVER", "MANUAL_INPUT")


def catat_security_audit(user_id, action_type, no_tiket=None, details=None, ip_address=None):
    """Gagal mencatat audit tidak boleh menggagalkan proses utama (tiket tetap dibuat / ditolak)."""
    if action_type not in AKSI_VALID or not user_id:
        return
    log_aktivitas.catat("SECURITY", action_type, tabel="transaksi" if no_tiket else None, id_baris=no_tiket,
                        baru=details or None, user_id=user_id, ip=ip_address)


def get_security_audit(hari=1, batas=300):
    return [{"id_log": r["id_log"], "created_at": r["waktu"].strftime("%Y-%m-%d %H:%M:%S"), "action_type": r["aksi"],
             "no_tiket": r["id_baris"], "details": r["nilai_baru"], "ip_address": r["ip"], "nama_user": r["oleh"],
             "role": r["role_oleh"], "kode_personel": r["kode_oleh"]}
            for r in log_aktivitas.daftar("SECURITY", hari, batas)]
