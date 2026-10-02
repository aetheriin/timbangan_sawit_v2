# Hak Akses per Role (yang berlaku sekarang)

Role di `users.role`: `ADMIN`, `HO`, `SECURITY`, `OPERATOR_TIMBANG`, `SORTASI`, `LAB`.
Pengecekan ada di server: `role_required(...)` (extensions.py) dan `pasang_batas_admin` (utils/keamanan.py).

## Halaman

| Halaman | ADMIN | Role lain |
|---|---|---|
| Admin (`/admin/...`, 9 menu) | ✅ hanya ini | ❌ 403 |
| Weighbridge (List / Form, tab Security–Lab) | ❌ dialihkan ke /admin | ✅ semua tab terlihat |
| Face Recognition (Absensi, Personel, Blacklist, Audit Log) | ❌ dialihkan ke /admin | ✅ semua tab terlihat |

Halaman awal setelah login: ADMIN → Kelola User; SECURITY / HO → tab Security; OPERATOR_TIMBANG → Timbangan;
SORTASI → Sortasi; LAB → Laboratorium. Menu & tab untuk role non-admin belum dibatasi (KEAMANAN_WEB #11 ditunda).

## Aksi yang dibatasi role (selain itu cukup login)

| Aksi | Role |
|---|---|
| Buat tiket, tambah supir, ubah identitas supir, supir & kontrak truk, mulai scan wajah kiosk | SECURITY |
| Simpan hasil timbang | OPERATOR_TIMBANG |
| Simpan sortasi | SORTASI |
| Simpan hasil lab, ubah standar mutu | LAB |
| Tambah / ubah / hapus personel, tambah blacklist | HO |
| Menu Kontrak & DO (tambah / ubah / nonaktifkan DO) | HO |
| Void tiket | ADMIN |
| Semua menu Admin | ADMIN |

ADMIN **tidak** lagi lolos otomatis untuk aksi operasional (sebelumnya bisa semua).

## Cukup login (semua role non-admin)

Melihat semua list & history, cari plat / NIK, scan QR tiket, cetak tiket / QR, berat live, nol-kan timbangan,
scan absensi, rekap & jadwal kerja, daftar personel & blacklist, Audit Log + ekspor, membuka foto / surat (`/berkas`).
