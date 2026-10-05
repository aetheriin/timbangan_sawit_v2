# Handoff: desain Figma Weighbridge + Face Recognition

Ringkasan untuk sesi baru. **Cukup baca file ini**; jangan jelajahi ulang kode/template.
Detail ERD & workflow (kalau perlu saja): `docs/PERANCANGAN_FACE_RECOGNITION.md`.

## Konteks singkat
- Repo `aetheriin/timbangan_sawit_v2`, branch kerja `claude/zen-hamilton-du3ult`. Main = aplikasi Weighbridge (Flask).
- Face recognition digabung ke main. Personel = DRIVER / SECURITY / EMPLOYEE (orang HO).
- Dua identitas: **ID Personel** otomatis & tidak pernah berubah (misal `006`); **Kode Personel** diisi/diubah HO,
  format sementara `PRGBS-###`, boleh kosong. Tampilan nama: `Kode · Nama`, atau `ID 014 · Nama` bila kode kosong.
- Pendaftaran personel: **upload foto** atau kamera (wajib tepat 1 wajah). Absensi: **scan wajah live + liveness**.
- Jadwal absensi (semua kategori, tanpa toleransi): masuk Sen–Sab 08:00; pulang Sen–Jum 17:00, Sab 12:00; Minggu libur.
  Jadwal shift security menyusul.
- Blacklist personel/kendaraan oleh HO, **permanen** (tidak bisa dicabut), wajib no. surat + upload surat.
- Semua menu tampil untuk sekarang (dipakai HO); pembatasan role menyusul.

## Tugas
1. `whoami` → `create_new_file` (design) nama **"Weighbridge + Face Recognition"** di plan akun ini. File baru, jangan salin file lama.
2. Buat layar di bawah (1 halaman, lebar 1360, jarak antar layar 100 px, susun 3–4 per baris).
3. Ganti link Figma di `docs/PERANCANGAN_FACE_RECOGNITION.md` (bagian atas + bagian 9) dengan file baru, commit, push.

## Struktur tampilan (keputusan terbaru)
Sidebar **menu per fitur** (seperti rancangan face recognition awal), **bukan** semua dijadikan tab:

```
MENU
SITE
  ☰ List        → halaman site ala main: info bar + tab Security | Timbangan | Sortasi | Laboratorium
  ✎ Form        → Create Ticket (form Security main + ID/Kode personel + cek blacklist)
FACE RECOGNITION
  ◷ Absensi
  ◉ Personel
  ⊘ Blacklist
  ⧗ Audit Log
```
- **Base (`templates/base.html` main) = kerangka default semua halaman**: Sidebar (MENU, List/Form + grup
  FACE RECOGNITION) · Topbar hitam (☰ Weighbridge, kanan `Nama (ROLE) ⏻`) · **Info bar** (kontainer putih di atas tab:
  No Tiket, No. Plat [ketik lalu Tab], Nomor DO / Supplier, Supir + kotak foto 112 putus-putus + tombol Validasi) ·
  **Tab header** (slate-900, tab aktif = sel penuh putih teks biru, bukan pil) · **Tab body** abu `slate-100` berisi section putih.
  Halaman hanya mengisi `{% block tab_content %}`. Frame Figma `00 · Base (base.html)` menunjukkan kerangka ini.
- Sidebar: **List · Form · Face Recognition** (3 menu).
  - List: info bar + tab Security | Timbangan | Sortasi | Laboratorium.
  - Form: info bar + form Create Ticket, **tanpa tab**.
  - Face Recognition: satu halaman tanpa info bar, tab **Absensi | Personel | Blacklist | Audit Log**.
- Modal (frame `M01`–`M13`, ditumpuk di atas layar asalnya):
  - Site, meniru `security_modals.html` / `cetak_tiket.html` / `lab.js` main: Cetak QR Code, Cetak Tiket 80 mm,
    Tambah Supir Baru, Update Supir & Truk (Ganti Supir / Edit Data Supir / Supir Truk / Kontrak Truk),
    Update Standar Mutu, Cetak COA.
  - Face Recognition: Personel Tambah / Update / Hapus; Blacklist hanya Tambah (permanen, tanpa Update/Hapus).
    Absensi & Audit Log tidak punya tambah/update/hapus.
- Aksi List Ticket Aktif mengikuti main: link **Buka** (biru, membuka Form) dan **Cetak QR** (hijau); status = badge amber `status_alur`
  (SECURITY_REGISTER, TIMBANG_1, TIMBANG_2).
- History Timbangan = **per supplier, 7 hari terakhir** (supplier dari tiket di info bar): Tanggal, No. Ticket, No. Plat, Produk,
  Bruto, Tara, Netto, Potongan, Netto Akhir (Kg) + baris Total.

## Daftar layar
| # | Layar | Isi |
|---|---|---|
| 01 | List · Security | Tab Security aktif. Toolbar: cari + "+ Create Ticket". Section "List Ticket Aktif" (No. Ticket, Plat, Supplier, Status badge, Cetak QR). Section "History Driver" (Plat, ID, Kode, Nama, NIK, SIM, Status: Aktif/BLACKLIST) |
| 02 | List · Timbangan | Seperti main: kartu "Live Weight Display" (layar hitam angka cyan `24.580 Kg`, mini Bruto/Tara/Netto, Potongan Sortasi/Netto Akhir, tombol Simpan Hasil Timbangan, link "atau Scan QR Code"), kartu "Detail DO & Produk" (Jenis, Supplier, Produk readonly), section History Timbangan |
| 03 | List · Sortasi | Seperti main: kartu "Form Input Grading & Mutu Buah" (6 field % 2 kolom + Catatan + Submit), kartu "Ringkasan Kalkulasi & Potongan" (tabel key-value), section History Sortasi |
| 04 | List · Laboratorium | Seperti main: kartu "Form Input Pengujian Sampel" (FFA, Air, Kotoran, Warna Locis, tombol Approve hijau/Reject merah bergaris, Submit), kartu "Standar Mutu & Dokumen COA" (Update Standar, Cetak COA), section History Lab |
| 05 | Form · Create Ticket | Header gelap "Form Pendaftaran Tiket" + "← Kembali ke List". Section "1. Informasi Kendaraan Produk" (Plat, No. Ticket, STNK \| kartu Pengemudi Terakhir Truk dgn Kode·ID; DO, Jenis, Supplier, Produk; teks hijau "✓ Kendaraan tidak masuk blacklist · Kontrak aktif"; Mulai Validasi Awal, Cetak QR). Section "2. Informasi Driver" (kotak scan wajah + Mulai Scan Wajah \| ID Personel 🔒, Kode Personel, Nama, NIK, SIM, badge status). Tombol Tambah / Update / Submit |
| 06 | Form · kendaraan blacklist | Sama dgn 05 tapi banner merah di atas ("KENDARAAN BM 8821 KA MASUK BLACKLIST…", no. surat, tombol Lihat surat), plat bergaris merah, section 2 opacity 0.45 & tombol abu |
| 07 | Absensi | Section "Scan Absensi": kartu kamera hitam (panduan oval putus-putus hijau, "Tantangan liveness: KEDIPKAN MATA", Mulai Scan Absen / Batal) + kartu Hasil (foto, nama, `PRGBS-002 · ID 011 · EMPLOYEE HO`, badge MASUK + TERLAMBAT 12 menit, waktu scan, jadwal masuk, jarak wajah, liveness). Section "Absensi Hari Ini" (filter chip; kolom Kode, Nama, Kategori, Masuk, Pulang, Keterangan). Section "Rekap Bulanan" (tertutup). Section "Jadwal Kerja" (tabel 3 baris) |
| 08 | Personel | Toolbar chip Semua/Driver/Security/Employee HO/Blacklist + cari + "+ Tambah Personel". Section "Daftar Personel" (ID, Kode — kosong tampil "— belum ada kode" oranye, Nama, NIK, Kategori badge, Sumber foto, Status, Edit). Section "Tambah / Edit Personel" terbuka: kartu Foto Wajah (segmen Upload Foto \| Kamera, drop zone + preview, cek hijau: 1 wajah, tidak mirip personel lain, tidak mirip blacklist) + form (ID 🔒 "otomatis, tidak pernah berubah", Kode "diisi/diubah HO" + saran `PRGBS-012`, Nama, NIK, Kategori, SIM "wajib untuk DRIVER", Simpan/Batal) |
| 09 | Blacklist | Section "Tetapkan Blacklist" (header merah muda): segmen Personel \| Kendaraan, cari kode/NIK/plat, kartu target, No. Surat, Tanggal, Alasan, Upload Surat (garis putus), peringatan "PERMANEN, tidak bisa dicabut", tombol merah. Section "Riwayat Blacklist" (Tanggal, Entitas, Target, No. Surat, Oleh, PDF) |
| 10 | Audit Log | Chip Hari ini/7 hari/30 hari + Export. Section "Aktivitas Security" (Waktu, User, Aksi badge TRY_SCAN_BLACKLIST merah / OVERRIDE_DRIVER oranye / MANUAL_INPUT abu, No. Tiket, Detail, IP). Section "Perubahan Data Personel" (Waktu, ID, Kolom, lama → baru, Oleh) |
| A01–A09 | Admin (super admin) | Hanya role ADMIN. Tanpa info bar & tanpa tab: sidebar berisi 9 menu Admin, judul halaman di posisi header tab. A01 Kelola User, A02 Sesi Aktif, A03 Supplier & Produk, A04 Jadwal Kerja, A05 Pengaturan Site, A06 Perangkat / Kiosk, A07 Log Keamanan, A08 Audit Admin, A09 Kesehatan Sistem (lihat docs/ADMIN.md) |
| M14–M15 | Modal Admin | M14 Tambah User (di atas A01), M15 Token Kiosk tampil sekali (di atas A06) |

Data contoh: Budi Santoso `PRGBS-001`/006 DRIVER; Siti Rahmawati `PRGBS-002`/011 EMPLOYEE HO; Joko Susilo `PRGBS-003`/012 SECURITY;
Rudi Hartono ID 014 tanpa kode; Dedi Kurniawan `PRGBS-009`/021 DRIVER BLACKLIST (truk BM 8821 KA, surat 017/HO-SEC/VIII/2026).
Plat BM 1455 JJ, PT Sawit Makmur, TBS, DO-8812, tiket `TKT-BM1455JJ-300926-01`.

## Token desain (dari `static/css/tailwind-source.css` main)
- Font Inter (style `"Semi Bold"` pakai spasi). Teks isi 12–13, judul kartu 13 Semi Bold, topbar 17 Bold.
- Warna: slate-900 `#0f172a` (sidebar, tab header), 800 `#1e293b`, 700 `#334155`, 600 `#475569`, 500 `#64748b`,
  400 `#94a3b8`, 300 `#cbd5e1` (border input), 200 `#e2e8f0` (header section), 100 `#f1f5f9` (latar), 50 `#f8fafc` (input readonly);
  topbar `#000000`; biru aktif `#2563eb` (menu), tombol primary `#1d4ed8`; hijau `#059669`; merah `#dc2626`;
  badge: hijau `#ecfdf5/#047857`, merah `#fef2f2/#b91c1c`, oranye `#fffbeb/#b45309`, biru `#eff6ff/#1d4ed8`; angka timbangan cyan `#22d3ee`.
- Radius: kartu/section 12, input/tombol 8, badge pill. Padding input 12×9, tombol 18×10, kartu 20.
- Sidebar lebar 210; menu aktif latar biru `#2563eb` teks putih; label grup 10 Semi Bold slate-500.
- Section: box putih border slate-200, header slate-200 (▼/▶ + judul 13 Medium slate-600), body padding 20 (tabel: 0).
- Tab header: latar slate-900, sudut atas 12, tab aktif putih teks `#1d4ed8`, tab lain lebar sama.

## Aturan Figma MCP (hemat kuota & token)
- Muat skill `figma-use` sekali (resource `skill://figma/figma-use/SKILL.md`); jangan baca referensi lain kecuali error.
- Kuota panggilan MCP terbatas: target **≤ 8 panggilan `use_figma`** dan **≤ 3 screenshot** total.
  Satu panggilan boleh membuat 3–4 layar sekaligus; tulis helper (T, AL, Field, Btn, Badge, Section, Card, Table, Shell) di tiap panggilan.
- Jebakan yang sudah terjadi:
  - Spacer auto-layout kosong jadi tinggi 100 px → buat, `appendChild`, `resize(10,1)`, `layoutSizingVertical='FIXED'`, lalu `layoutSizingHorizontal='FILL'`.
  - Set `FILL`/`HUG` hanya setelah node di-append ke parent auto-layout; `resize()` sebelum set sizing.
  - Teks yang harus melebar: `textAutoResize='HEIGHT'` lalu `FILL`.
  - Warna 0–1, bukan 0–255. Selalu `return` ID node yang dibuat.
- Jangan membalas panjang: laporkan link file + daftar layar + hal yang belum dicek.
