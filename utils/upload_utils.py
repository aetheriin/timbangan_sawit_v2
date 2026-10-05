"""Simpan file upload (foto wajah, surat blacklist, frame kamera) ke folder PRIVAT (extensions.UPLOAD_FOLDER).

Validasi: ekstensi, ukuran, dan ISI file (signature). Gambar dibuka ulang dengan Pillow lalu disimpan
kembali, sehingga metadata (EXIF/GPS) dan data sisipan di dalam file ikut terbuang."""
import io
import os
import uuid
from PIL import Image, UnidentifiedImageError
from extensions import UPLOAD_FOLDER

FOTO_EKSTENSI = (".jpg", ".jpeg", ".png")
SURAT_EKSTENSI = (".pdf", ".jpg", ".jpeg", ".png")
MAKS_MB = 5
MAKS_PIKSEL = 40_000_000                 # tolak gambar raksasa (decompression bomb)
Image.MAX_IMAGE_PIXELS = MAKS_PIKSEL

SIGNATURE = {
    ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".pdf": (b"%PDF-",),
}


def _baca(file, maks_mb):
    data = file.read(maks_mb * 1024 * 1024 + 1)
    if len(data) > maks_mb * 1024 * 1024:
        raise ValueError(f"Ukuran file maksimal {maks_mb} MB")
    if not data:
        raise ValueError("File kosong")
    return data


def _cek_signature(data, ext):
    if not any(data.startswith(sig) for sig in SIGNATURE[ext]):
        raise ValueError("Isi file tidak sesuai formatnya (file rusak atau bukan " + ext.lstrip(".").upper() + ")")


def _bersihkan_gambar(data, ext):
    """Buka ulang & simpan kembali gambar (membuang metadata). Kembalikan (bytes, ext_baru)."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if img.width * img.height > MAKS_PIKSEL:
                raise ValueError("Resolusi gambar terlalu besar")
            png = ext == ".png"
            img = img.convert("RGBA" if png and img.mode in ("RGBA", "LA", "P") else "RGB")
            out = io.BytesIO()
            img.save(out, format="PNG" if png else "JPEG", quality=90, optimize=True)
            return out.getvalue(), ".png" if png else ".jpg"
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("File gambar rusak / tidak dikenali")


def simpan_upload(file, subfolder="", ekstensi_izin=FOTO_EKSTENSI, maks_mb=MAKS_MB, nama_default=".jpg"):
    """Kembalikan (path_disk, path_relatif 'uploads/<subfolder>/<nama>'). ValueError bila file tidak valid."""
    if not file or not file.filename:
        raise ValueError("File wajib diunggah")
    ext = os.path.splitext(file.filename)[1].lower() or nama_default
    if ext not in ekstensi_izin:
        raise ValueError(f"Format file harus {', '.join(e.lstrip('.').upper() for e in ekstensi_izin)}")

    data = _baca(file, maks_mb)
    _cek_signature(data, ext)
    if ext != ".pdf":
        data, ext = _bersihkan_gambar(data, ext)

    folder = os.path.join(UPLOAD_FOLDER, subfolder)
    os.makedirs(folder, exist_ok=True)
    nama = f"{uuid.uuid4().hex}{ext}"
    path_disk = os.path.join(folder, nama)
    with open(path_disk, "wb") as f:
        f.write(data)
    return path_disk, "/".join(p for p in ("uploads", subfolder, nama) if p)


def simpan_frames(files, maks=20, minimal=3, maks_mb=2):
    """Frame kamera (JPEG) untuk liveness -> daftar path sementara di uploads/tmp. Pemanggil wajib menghapusnya."""
    if len(files) < minimal:
        raise ValueError("Frame kamera tidak cukup, ulangi scan")
    if len(files) > maks:
        raise ValueError(f"Frame kamera terlalu banyak (maks {maks})")
    folder = os.path.join(UPLOAD_FOLDER, "tmp")
    os.makedirs(folder, exist_ok=True)
    paths = []
    try:
        for f in files:
            data = _baca(f, maks_mb)
            _cek_signature(data, ".jpg")
            path = os.path.join(folder, f"frame_{uuid.uuid4().hex}.jpg")
            with open(path, "wb") as out:
                out.write(data)
            paths.append(path)
    except ValueError:
        for p in paths:
            hapus_file(p)
        raise
    return paths


def hapus_file(path_disk):
    if path_disk and os.path.exists(path_disk):
        try:
            os.remove(path_disk)
        except OSError:
            pass


def path_disk_dari_relatif(relatif):
    """'uploads/personel/x.jpg' -> path di UPLOAD_FOLDER; None bila keluar dari folder upload (path traversal)."""
    if not relatif or not relatif.startswith("uploads/"):
        return None
    path = os.path.abspath(os.path.join(UPLOAD_FOLDER, relatif[len("uploads/"):]))
    return path if path.startswith(UPLOAD_FOLDER + os.sep) else None
