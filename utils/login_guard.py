"""Pembatas percobaan login: LOGIN_MAKS_GAGAL kali salah dalam LOGIN_JENDELA_MENIT -> dikunci LOGIN_KUNCI_MENIT
(per username dan per IP). Nilainya diatur di Admin > Pengaturan Site (bawaan 5x / 15 menit / 15 menit).

Aturannya ada di database (dbo.sp_LoginSisaKunci, sp_LoginGagal, sp_LoginBerhasil, sp_LoginBukaKunci,
sp_LoginDaftarTerkunci) dan dicatat di tabel Log, jadi berlaku sama untuk semua aplikasi dan tetap setelah server restart."""
import logging

from utils.db_utils import get_connection, _rows_to_dicts

log = logging.getLogger("weighbridge")


def _exec(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        rows = _rows_to_dicts(cursor) if cursor.description else []
        conn.commit()
        return rows
    finally:
        conn.close()


def sisa_kunci(username, ip):
    """Detik sampai boleh login lagi (0 = boleh). Bila database tidak bisa dibaca, login tidak ditahan di sini."""
    try:
        return int(_exec("EXEC dbo.sp_LoginSisaKunci @Username = ?, @IP = ?", username or "", ip or "")[0]["SisaDetik"])
    except Exception:       # noqa: BLE001 - login tetap diperiksa password; kegagalan baca kunci dicatat
        log.exception("Gagal membaca kunci login")
        return 0


def catat_gagal(username, ip):
    """Kembalikan True bila percobaan ini membuat akun / IP terkunci."""
    try:
        return bool(_exec("EXEC dbo.sp_LoginGagal @Username = ?, @IP = ?", username or "", ip or "")[0]["Terkunci"])
    except Exception:       # noqa: BLE001
        log.exception("Gagal mencatat login gagal")
        return False


def catat_berhasil(username, ip, id_user=None):
    try:
        _exec("EXEC dbo.sp_LoginBerhasil @Username = ?, @IP = ?, @UserID = ?", username or "", ip or "", id_user)
    except Exception:       # noqa: BLE001
        log.exception("Gagal mencatat login berhasil")


def daftar_terkunci():
    """Untuk Admin > Sesi Aktif: [{kunci, jenis, nama, sisa_detik, dicoba}] yang masih terkunci."""
    return [{"kunci": r["Kunci"], "jenis": "Username" if r["Kunci"].startswith("u:") else "IP",
             "nama": r["Kunci"].split(":", 1)[1], "sisa_detik": int(r["SisaDetik"]),
             "dicoba": [u for u in (r["Dicoba"] or "").split(", ") if u]}
            for r in _exec("EXEC dbo.sp_LoginDaftarTerkunci")]


def buka_kunci(kunci, id_user=None):
    """Admin membuka kunci lebih cepat ('u:nama' / 'ip:alamat'). Kembalikan True bila memang sedang terkunci."""
    return bool(_exec("EXEC dbo.sp_LoginBukaKunci @Kunci = ?, @UserID = ?", kunci, id_user)[0]["Dibuka"])


def buka_kunci_teks(teks, id_user=None):
    """Admin mengetik username ATAU IP. Kembalikan jumlah kunci yang dibuka."""
    teks = (teks or "").strip()
    return sum(buka_kunci(k, id_user) for k in (f"u:{teks.lower()}", f"ip:{teks}"))


def buka_semua(id_user=None):
    return int(_exec("EXEC dbo.sp_LoginBukaKunci @Kunci = '*', @UserID = ?", id_user)[0]["Dibuka"])
