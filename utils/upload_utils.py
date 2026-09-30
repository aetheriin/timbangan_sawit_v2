"""Simpan file upload (foto wajah, surat blacklist) ke static/uploads dengan validasi jenis & ukuran."""
import os
import uuid
from extensions import UPLOAD_FOLDER

FOTO_EKSTENSI = (".jpg", ".jpeg", ".png")
SURAT_EKSTENSI = (".pdf", ".jpg", ".jpeg", ".png")
MAKS_MB = 5


def simpan_upload(file, subfolder="", ekstensi_izin=FOTO_EKSTENSI, maks_mb=MAKS_MB, nama_default=".jpg"):
    """Kembalikan (path_disk, path_relatif_static). ValueError bila file tidak valid."""
    if not file or not file.filename:
        raise ValueError("File wajib diunggah")
    ext = os.path.splitext(file.filename)[1].lower() or nama_default
    if ext not in ekstensi_izin:
        raise ValueError(f"Format file harus {', '.join(e.lstrip('.').upper() for e in ekstensi_izin)}")

    file.stream.seek(0, os.SEEK_END)
    ukuran = file.stream.tell()
    file.stream.seek(0)
    if ukuran > maks_mb * 1024 * 1024:
        raise ValueError(f"Ukuran file maksimal {maks_mb} MB")

    folder = os.path.join(UPLOAD_FOLDER, subfolder)
    os.makedirs(folder, exist_ok=True)
    nama = f"{uuid.uuid4().hex}{ext}"
    path_disk = os.path.join(folder, nama)
    file.save(path_disk)
    relatif = "/".join(p for p in ("uploads", subfolder, nama) if p)
    return path_disk, relatif


def hapus_file(path_disk):
    if path_disk and os.path.exists(path_disk):
        try:
            os.remove(path_disk)
        except OSError:
            pass
