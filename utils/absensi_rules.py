"""Aturan absensi: jenis MASUK/PULANG dan status waktu terhadap jadwal_kerja (tanpa database)."""
from datetime import datetime, timedelta

JEDA_DUPLIKAT_MENIT = 5


def _menit(t):
    return t.hour * 60 + t.minute


def tentukan_jenis(sudah_masuk_hari_ini):
    """Scan pertama hari itu = MASUK, berikutnya = PULANG (rekap pakai PULANG terakhir)."""
    return "PULANG" if sudah_masuk_hari_ini else "MASUK"


def is_duplikat(waktu_scan_terakhir, sekarang, menit=JEDA_DUPLIKAT_MENIT):
    """Scan berulang < 5 menit diabaikan supaya satu orang tidak tercatat MASUK lalu langsung PULANG."""
    return waktu_scan_terakhir is not None and sekarang - waktu_scan_terakhir < timedelta(minutes=menit)


def hitung_status_waktu(jenis, waktu, jadwal):
    """
    jadwal: dict jadwal_kerja hari itu {is_libur, jam_masuk, jam_pulang, toleransi_menit} atau None.
    Kembalikan (status_waktu, selisih_menit):
    - MASUK : selisih = waktu - jam_masuk (+ terlambat, - lebih awal). 08:01 sudah terlambat bila toleransi 0.
    - PULANG: selisih = jam_pulang - waktu (+ pulang awal, - lembur).
    Detik diabaikan: 08:00:59 masih dihitung 08:00.
    """
    if jadwal is None or jadwal.get("is_libur") or not jadwal.get("jam_masuk") or not jadwal.get("jam_pulang"):
        return "HARI_LIBUR", None

    toleransi = jadwal.get("toleransi_menit") or 0
    if jenis == "MASUK":
        selisih = _menit(waktu) - _menit(jadwal["jam_masuk"])
        return ("TERLAMBAT" if selisih > toleransi else "TEPAT_WAKTU"), selisih

    selisih = _menit(jadwal["jam_pulang"]) - _menit(waktu)
    return ("PULANG_AWAL" if selisih > 0 else "TEPAT_WAKTU"), selisih


def hari_iso(waktu: datetime):
    """1 = Senin ... 7 = Minggu (tidak bergantung SET DATEFIRST SQL Server)."""
    return waktu.isoweekday()
