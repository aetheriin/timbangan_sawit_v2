from datetime import datetime, timedelta

JEDA_DUPLIKAT_MENIT = 5

def _menit(t):
    return t.hour * 60 + t.minute


def tentukan_jenis(sudah_masuk_hari_ini):
    return "PULANG" if sudah_masuk_hari_ini else "MASUK"


def is_duplikat(waktu_scan_terakhir, sekarang, menit=JEDA_DUPLIKAT_MENIT):
    return waktu_scan_terakhir is not None and sekarang - waktu_scan_terakhir < timedelta(minutes=menit)


def hitung_status_waktu(jenis, waktu, jadwal):
    if jadwal is None or jadwal.get("is_libur") or not jadwal.get("jam_masuk") or not jadwal.get("jam_pulang"):
        return "HARI_LIBUR", None

    toleransi = jadwal.get("toleransi_menit") or 0
    if jenis == "MASUK":
        selisih = _menit(waktu) - _menit(jadwal["jam_masuk"])
        return ("TERLAMBAT" if selisih > toleransi else "TEPAT_WAKTU"), selisih

    selisih = _menit(jadwal["jam_pulang"]) - _menit(waktu)
    return ("PULANG_AWAL" if selisih > 0 else "TEPAT_WAKTU"), selisih


def hari_iso(waktu: datetime):
    return waktu.isoweekday()
