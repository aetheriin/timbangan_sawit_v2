"""Dokumen umum (tabel jenis_dokumen -> dokumen -> dokumen_file): surat blacklist, berita acara void, COA, dll.

Pemakaian (dalam satu transaksi dengan data pemiliknya):
    info = simpan_file(request.files.get("file"), "SURAT_BLACKLIST")      # simpan ke disk + sha256
    id_dok = buat_dokumen(cursor, "SURAT_BLACKLIST", no, tanggal, perihal, [info], user_id)
Bila transaksi DB gagal, panggil hapus_file_info([info]) supaya file tidak menggantung."""
import hashlib
import mimetypes

from utils.upload_utils import simpan_upload, hapus_file, SURAT_EKSTENSI


def simpan_file(file, kode_jenis, ekstensi=SURAT_EKSTENSI):
    """Simpan file upload ke uploads/dokumen/<jenis>/. Kembalikan info untuk dokumen_file. ValueError bila tidak valid."""
    nama_asli = (getattr(file, "filename", "") or "")[:255] or None
    path_disk, relatif = simpan_upload(file, f"dokumen/{kode_jenis.lower()}", ekstensi)
    with open(path_disk, "rb") as f:
        isi = f.read()
    return {"path_disk": path_disk, "file_path": relatif, "nama_asli": nama_asli,
            "mime": mimetypes.guess_type(relatif)[0] or "application/octet-stream",
            "ukuran_byte": len(isi), "sha256": hashlib.sha256(isi).hexdigest()}


def hapus_file_info(daftar):
    for info in daftar or []:
        hapus_file(info.get("path_disk"))


def buat_dokumen(cursor, kode_jenis, no_dokumen, tanggal, perihal, file_info, user_id):
    """INSERT dokumen + file-nya (pakai cursor pemanggil, commit oleh pemanggil). Kembalikan id_dokumen."""
    cursor.execute("SELECT id_jenis, wajib_file FROM jenis_dokumen WHERE kode = ? AND is_active = 1", kode_jenis)
    jenis = cursor.fetchone()
    if jenis is None:
        raise ValueError(f"Jenis dokumen {kode_jenis} tidak dikenal")
    if jenis.wajib_file and not file_info:
        raise ValueError("File dokumen wajib diunggah")
    cursor.execute("""INSERT INTO dokumen (id_jenis, no_dokumen, tanggal, perihal, created_by)
                      OUTPUT INSERTED.id_dokumen VALUES (?, ?, ?, ?, ?)""",
                   jenis.id_jenis, no_dokumen, tanggal, perihal, user_id)
    id_dokumen = cursor.fetchone()[0]
    for urutan, info in enumerate(file_info or [], 1):
        cursor.execute("""INSERT INTO dokumen_file (id_dokumen, file_path, nama_asli, mime, ukuran_byte, sha256, urutan)
                          VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       id_dokumen, info["file_path"], info["nama_asli"], info["mime"], info["ukuran_byte"],
                       info["sha256"], urutan)
    return id_dokumen
