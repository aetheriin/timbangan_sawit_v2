# Hak Akses per Role (Usulan)

Status: **usulan, menunggu persetujuan** sebelum diterapkan (lanjutan KEAMANAN_WEB.md #11 & #12).
Role yang ada di database (`users.role`): `ADMIN`, `HO`, `SECURITY`, `OPERATOR_TIMBANG`, `SORTASI`, `LAB`.

Keterangan: ✅ boleh (lihat + ubah) · 👁 lihat saja · — tidak tampil / ditolak server (403)

## 1. Ringkasan per role

| Role | Tugas | Halaman awal setelah login |
|---|---|---|
| **ADMIN** | Mengelola sistem: user, role, pengaturan, perangkat. Bukan pelaku transaksi | Kelola User |
| **HO** | Pengawas pusat: data personel, blacklist, audit, memantau semua site | Face Recognition |
| **SECURITY** | Pos depan: daftarkan truk & supir, buat tiket, scan wajah, cetak QR, absensi | Weighbridge › Security |
| **OPERATOR_TIMBANG** | Jembatan timbang: scan QR tiket, timbang masuk/keluar | Weighbridge › Timbangan |
| **SORTASI** | Grading TBS: input potongan / hasil sortasi | Weighbridge › Sortasi |
| **LAB** | Mutu produk PKS: input hasil lab, Approve/Reject, standar mutu, COA | Weighbridge › Laboratorium |

## 2. Menu & tab

| Menu / Tab | ADMIN | HO | SECURITY | OPERATOR_TIMBANG | SORTASI | LAB |
|---|---|---|---|---|---|---|
| Weighbridge › List (tiket aktif) | 👁 | 👁 | ✅ | 👁 | 👁 | 👁 |
| Weighbridge › Form (Create Ticket) | — | — | ✅ | — | — | — |
| Tab Security | 👁 | 👁 | ✅ | — | — | — |
| Tab Timbangan | 👁 | 👁 | — | ✅ | — | — |
| Tab Sortasi | 👁 | 👁 | — | — | ✅ | — |
| Tab Laboratorium | 👁 | 👁 | — | — | — | ✅ |
| Face Recognition › Absensi | 👁 | ✅ | ✅ (scan) | — | — | — |
| Face Recognition › Personel | 👁 | ✅ | 👁 | — | — | — |
| Face Recognition › Blacklist | 👁 | ✅ | 👁 | — | — | — |
| Face Recognition › Audit Log | ✅ | ✅ | — | — | — | — |
| Admin (Kelola User, Pengaturan, dst.) | ✅ | — | — | — | — | — |

Menu / tab bertanda — disembunyikan dari sidebar & header tab, **dan** server tetap menolak (403) bila
dibuka langsung lewat URL. Menyembunyikan menu saja tidak cukup.

## 3. Aksi (dicek di server)

| Aksi | Endpoint | Saat ini | Usulan |
|---|---|---|---|
| Buat tiket, cetak QR | `/api/security/buat-tiket`, `/cetak/tiket/...` | SECURITY (cetak: semua login) | SECURITY |
| Tambah supir / ubah identitas supir | `/api/driver/tambah`, `/api/driver/update-identitas` | SECURITY | SECURITY |
| Supir & kontrak truk | `/api/kendaraan/supir/*`, `/api/kendaraan/kontrak/*` | SECURITY | SECURITY |
| Mulai scan wajah (kiosk) | `/api/kamera/start` | SECURITY | SECURITY |
| Simpan timbangan | `/api/timbang/simpan` | OPERATOR_TIMBANG | OPERATOR_TIMBANG |
| ⚠️ Reset baseline timbangan (nol-kan) | `/api/timbang/reset-baseline` | **semua yang login** | OPERATOR_TIMBANG |
| Simpan sortasi | `/api/sortasi/simpan` | SORTASI | SORTASI |
| Simpan hasil lab | `/api/lab/simpan` | LAB | LAB |
| Ubah standar mutu | `/api/lab/standar/update` | LAB | LAB + HO |
| ⚠️ Scan absensi | `/api/absensi/scan` | **semua yang login** | SECURITY + HO |
| Tambah / ubah / hapus personel | `/api/personel/*` (POST) | HO | HO |
| Tambah blacklist | `/api/blacklist/tambah` | HO | HO |
| ⚠️ Lihat & ekspor Audit Log | `/api/audit/*` | **semua yang login** | HO + ADMIN |
| ⚠️ Lihat daftar personel (NIK, SIM) | `/api/personel` | **semua yang login** | HO + SECURITY + ADMIN |
| Kelola user | `/admin/users/*` (belum dibuat) | — | ADMIN |

⚠️ = celah yang ditemukan saat menyusun daftar ini: endpoint hanya mewajibkan login, belum dicek role.

## 4. Keputusan yang perlu disetujui

1. **ADMIN saat ini lolos semua pengecekan role** (`role_required` di `extensions.py`), artinya ADMIN juga
   bisa membuat tiket, menimbang, dll. Usulan: ADMIN hanya **melihat** data operasional, tidak bisa
   membuat transaksi (pemisahan tugas: yang mengatur user tidak ikut bertransaksi, jejak audit lebih jelas).
2. **HO hanya melihat** Weighbridge (tidak membuat tiket / menimbang). Bila HO kadang perlu membantu
   site, alternatifnya beri HO hak penuh, tetapi semua aksinya tercatat di Audit Log.
3. **Satu user = satu role.** Bila ada orang yang merangkap (misal Security juga Operator Timbang), pilihan:
   (a) dua akun, atau (b) kolom role diubah jadi daftar role per user (perlu migrasi database).
4. **Super admin** (yang mengatur password, sesuai rencana sebelumnya) = role `ADMIN` ini, atau dibuat
   role baru `SUPER_ADMIN` di atas ADMIN.

## 5. Cara penerapan (setelah disetujui)

1. Satu tabel hak akses di kode (`utils/hak_akses.py`): role → menu, tab, aksi. Satu sumber, dipakai
   sidebar, header tab, dan pengecekan server.
2. Semua endpoint POST & endpoint data sensitif memakai `@role_required(...)` sesuai tabel bagian 3.
3. Sidebar & tab dirender server sesuai role (tidak sekadar disembunyikan dengan JS).
4. Tombol aksi di tab yang hanya 👁 disembunyikan / dinonaktifkan.
5. Test otomatis: setiap role × setiap endpoint → 200 atau 403 sesuai tabel.
