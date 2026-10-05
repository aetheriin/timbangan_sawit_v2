"""Aturan tampilan & kode personel (tanpa database, bisa di-unit-test)."""
import re

PREFIX_KODE = "PRGBS-"      # format sementara (keputusan 4), tidak dikunci CHECK di database
KATEGORI_VALID = ("DRIVER", "SECURITY", "EMPLOYEE")

# kolom audit -> label yang ditampilkan di menu Audit Log
KOLOM_AUDIT = (
    ("kode_personel", "kode_personel_lama", "kode_personel_baru"),
    ("nik", "nik_lama", "nik_baru"),
    ("nama", "nama_lama", "nama_baru"),
    ("no_sim", "no_sim_lama", "no_sim_baru"),
)


def format_id(id_personel):
    return f"{int(id_personel):03d}"


def format_nama_personel(kode, id_personel, nama):
    """`Kode · Nama`, atau `ID 014 · Nama` bila kode masih kosong."""
    return f"{kode} · {nama}" if kode else f"ID {format_id(id_personel)} · {nama}"


def kode_berikutnya(daftar_kode, prefix=PREFIX_KODE):
    """Saran kode berikutnya dari kode yang sudah ada, mis. ['PRGBS-001', 'PRGBS-009'] -> 'PRGBS-010'."""
    pola = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    nomor = [int(m.group(1)) for k in daftar_kode if k and (m := pola.match(k.strip().upper()))]
    return f"{prefix}{(max(nomor) if nomor else 0) + 1:03d}"


def validasi_personel(nik, nama, kategori, no_sim):
    """Kembalikan pesan error, atau None kalau data valid."""
    if not nik or not nama:
        return "NIK dan nama wajib diisi"
    if not nik.isdigit() or len(nik) != 16:
        return "NIK harus 16 digit angka"
    if kategori not in KATEGORI_VALID:
        return "Kategori tidak valid"
    if kategori == "DRIVER" and not no_sim:
        return "No. SIM wajib untuk DRIVER"
    return None


def daftar_perubahan(row):
    """Kolom yang berubah pada satu baris personel_audit_logs -> [(kolom, lama, baru)]."""
    hasil = []
    for kolom, lama, baru in KOLOM_AUDIT:
        v_lama, v_baru = row.get(lama), row.get(baru)
        if (v_lama or None) != (v_baru or None):
            hasil.append((kolom, v_lama, v_baru))
    return hasil
