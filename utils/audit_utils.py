"""security_audit_logs: aktivitas security yang dipantau HO (menu Face Recognition > Audit Log)."""
import json
from datetime import datetime
from utils.db_utils import get_connection, _rows_to_dicts

AKSI_VALID = ("TRY_SCAN_BLACKLIST", "OVERRIDE_DRIVER", "MANUAL_INPUT")


def catat_security_audit(user_id, action_type, no_tiket=None, details=None, ip_address=None):
    """Gagal mencatat audit tidak boleh menggagalkan proses utama (tiket tetap dibuat / ditolak)."""
    if action_type not in AKSI_VALID or not user_id:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO security_audit_logs (user_id, action_type, no_tiket, details, ip_address)
                          VALUES (?, ?, ?, ?, ?)""",
                       user_id, action_type, no_tiket,
                       json.dumps(details, ensure_ascii=False) if details else None, ip_address)
        conn.commit()
        conn.close()
    except Exception as e:      # noqa: BLE001 - audit tidak boleh memutus alur
        print(f"[AUDIT] gagal mencatat {action_type}: {e}")


def get_security_audit(hari=1, batas=300):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP (?) s.id_log, s.created_at, s.action_type, s.no_tiket, s.details, s.ip_address,
               u.nama AS nama_user, lv.kode AS role, p.kode_personel
        FROM security_audit_logs s
        JOIN users u ON s.user_id = u.id_user
        JOIN level lv ON lv.id_level = u.id_level
        LEFT JOIN personel p ON u.id_personel = p.id_personel
        WHERE s.created_at >= DATEADD(day, ?, CAST(GETDATE() AS DATE))
        ORDER BY s.created_at DESC
    """, batas, -(hari - 1))
    data = _rows_to_dicts(cursor)
    conn.close()
    for r in data:
        r["details"] = json.loads(r["details"]) if r["details"] else {}
        if isinstance(r["created_at"], datetime):
            r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
    return data
