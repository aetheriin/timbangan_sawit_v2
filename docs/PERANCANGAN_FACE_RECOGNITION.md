# Perancangan Face Recognition, Blacklist & Absensi di Weighbridge (main)

Fitur face recognition **digabung ke aplikasi Weighbridge (main)**. Komposisi dan desain main
menjadi acuan: fitur baru menyesuaikan diri ke main, bukan sebaliknya.

- Desain Figma: <https://www.figma.com/design/wrygHwLrs9aZjCDDCul5CJ>, file & halaman
  **"Weighbridge + Face Recognition"** (10 layar, sidebar menu per fitur; lihat bagian 9).
  File lama (`MYtNtlrszccggmaS5iUIus`) tidak dipakai lagi.
- Draf SQL: `database/migrations/002_personel_blacklist.sql` (hanya menambah ke skema main).

---

## 1. Prinsip penggabungan

| Bagian main | Perlakuan |
|---|---|
| Sidebar **List / Form**, topbar **Weighbridge**, **info bar** (No Tiket, Plat, DO, Supplier, Supir, foto) | **Tetap** |
| Tab **Security, Timbangan, Sortasi, Laboratorium** (untuk site) | **Tetap**, isi dan alurnya sama |
| Section abu-abu yang bisa dibuka/ditutup (`toggleSection`), kartu putih, tombol biru/hijau/abu | **Tetap**, dipakai juga oleh fitur baru |
| Alur tiket `SECURITY_REGISTER → … → SELESAI`, tabel timbangan/sortasi/lab | **Tetap**, tidak diubah |
| Role ADMIN, SECURITY, OPERATOR_TIMBANG, SORTASI, LAB | **Tetap**, ditambah **HO** |

Yang **ditambahkan**:

1. **Menu Face Recognition** di sidebar (List · Form · Face Recognition): satu halaman dengan tab
   **Absensi | Personel | Blacklist | Audit Log**, tanpa info bar.
2. **Form Create Ticket** (tanpa header tab): "2. Informasi Driver" menampilkan **ID Personel + Kode Personel**,
   status blacklist, dan banner merah bila kendaraan / supir diblacklist.
3. **Personel** dikelola HO: Tambah / Update / Hapus (soft delete) dengan foto **Upload** atau **Kamera**.

Untuk sekarang semua tab tampil (dipakai HO). Pembatasan per role menyusul.

---

## 2. Dua identitas personel: ID dan Kode

| | `id_personel` | `kode_personel` |
|---|---|---|
| Contoh | `006` | `PRGBS-001` |
| Dibuat oleh | Database (IDENTITY, otomatis) | HO, lewat tab Personel |
| Bisa berubah? | **Tidak pernah** | Ya, tercatat di `personel_audit_logs` |
| Wajib? | Ya | Boleh kosong dulu, unik bila diisi |
| Dipakai untuk | **Semua relasi** (tiket, blacklist, absensi, audit, supir truk, akun login) | Tampilan & pencarian |

Format tampilan di seluruh UI: `Kode · Nama`, atau `ID 014 · Nama` bila kode masih kosong.
Personel mencakup **DRIVER**, **SECURITY**, dan **EMPLOYEE** (orang HO, termasuk karyawan baru).

---

## 3. Workflow

### 3.1 Security: buat tiket (alur main + face recognition + blacklist)

```mermaid
flowchart TD
    S([Truk datang]) --> P[Tab Security › Form<br/>ketik No. Plat + Tab]
    P --> CEKPLAT{kendaraan<br/>is_blacklisted?}
    CEKPLAT -- Ya --> BLK1[Banner merah + no surat<br/>form terkunci]
    BLK1 --> LOG1[/security_audit_logs:<br/>TRY_SCAN_BLACKLIST/]
    CEKPLAT -- Tidak --> AKTIF{Sudah ada<br/>tiket aktif?}
    AKTIF -- Ya --> TAMPIL[Tampilkan tiket / cetak ulang QR]
    AKTIF -- Tidak --> DRAFT[1. Informasi Kendaraan Produk<br/>DO, jenis, supplier, produk, kontrak]
    DRAFT --> SCAN[2. Informasi Driver: Mulai Scan Wajah<br/>liveness kedip / menoleh]
    SCAN --> KENAL{Wajah cocok<br/>personel?}
    KENAL -- Tidak --> BARU[Tambah: daftarkan personel<br/>upload foto / kamera]
    BARU --> OK
    KENAL -- Ya --> CEKORANG{personel<br/>is_blacklisted?}
    CEKORANG -- Ya --> BLK3[Banner merah, Submit terkunci]
    BLK3 --> LOG1
    CEKORANG -- Tidak --> OK[Supir terverifikasi<br/>snapshot foto disimpan]
    OK --> GANTI{Beda dari<br/>supir utama?}
    GANTI -- Ya --> OVR[is_driver_changed = 1<br/>prev_driver_id]
    OVR --> LOG2[/security_audit_logs:<br/>OVERRIDE_DRIVER/]
    LOG2 --> SUBMIT
    GANTI -- Tidak --> SUBMIT[Submit → status SECURITY_REGISTER]
    SUBMIT --> QR[Cetak QR]
    QR --> LANJUT([Lanjut Timbangan → Sortasi / Lab → Timbangan 2,<br/>sama seperti main])
```

- Pemeriksaan blacklist juga dilakukan **di server** (`buat-tiket`), bukan hanya di tampilan.
- Tiket dibuat tanpa scan wajah (bila `WAJIB_SCAN_WAJAH=false`) dicatat `MANUAL_INPUT`.
- Setelah tiket dibuat, tab Timbangan, Sortasi, dan Lab berjalan **persis seperti main**.

### 3.2 Pendaftaran personel (upload foto)

```mermaid
flowchart TD
    A[Tab Personel › Form<br/>atau tombol Tambah di Security] --> B[Isi nama, NIK, kategori,<br/>SIM jika DRIVER, kode opsional]
    B --> C{Sumber foto}
    C -- Upload --> D[File JPG/PNG maks 5 MB]
    C -- Kamera --> E[Ambil dari webcam]
    D & E --> F{Tepat 1 wajah?}
    F -- Tidak --> X[Tolak: minta foto lain]
    F -- Ya --> G{Mirip personel lain?}
    G -- Ya --> Y[Tolak: sudah terdaftar sebagai ...]
    G -- Tidak --> H{Mirip personel blacklist?}
    H -- Ya --> Z[Tolak + TRY_SCAN_BLACKLIST]
    H -- Tidak --> I[INSERT personel<br/>embedding, foto_path, foto_sumber]
```

Foto upload **hanya untuk pendaftaran**. `extract_embedding` di main mengambil wajah pertama saja,
jadi perlu diubah agar menolak foto dengan 0 atau lebih dari 1 wajah.

### 3.3 Absensi dengan face recognition

Jadwal kerja (tabel `jadwal_kerja`, bisa diubah tanpa ubah kode):

| Hari | Masuk | Pulang |
|---|---|---|
| Senin – Jumat | 08:00 | 17:00 |
| Sabtu | 08:00 | 12:00 |
| Minggu | libur | libur |

```mermaid
flowchart TD
    S([Tab Absensi › Form]) --> L[Mulai Scan Absen<br/>kamera live + liveness]
    L --> LV{Liveness lolos?}
    LV -- Tidak --> R0[Ulangi, tidak dicatat]
    LV -- Ya --> M{Cocok personel aktif?<br/>jarak ≤ 0.55}
    M -- Tidak --> R1[/absensi: TIDAK_DIKENALI/]
    M -- Ya --> BL{is_blacklisted?}
    BL -- Ya --> R2[/absensi: DITOLAK_BLACKLIST/]
    BL -- Tidak --> DUP{Scan terakhir<br/>< 5 menit?}
    DUP -- Ya --> R3[Abaikan]
    DUP -- Tidak --> J{Sudah MASUK<br/>hari ini?}
    J -- Belum --> IN[MASUK<br/>bandingkan jam_masuk]
    J -- Sudah --> OUT[PULANG<br/>bandingkan jam_pulang]
    IN --> W1{> jam_masuk + toleransi?}
    W1 -- Ya --> T1[/TERLAMBAT, selisih menit/]
    W1 -- Tidak --> T2[/TEPAT_WAKTU/]
    OUT --> W2{< jam_pulang?}
    W2 -- Ya --> T3[/PULANG_AWAL, selisih menit/]
    W2 -- Tidak --> T4[/TEPAT_WAKTU/]
```

- Hari libur (Minggu) tetap dicatat dengan `status_waktu = HARI_LIBUR`.
- Hari dihitung di aplikasi dengan `date.isoweekday()` (1 = Senin), bukan `DATEPART`, supaya tidak
  bergantung pada `SET DATEFIRST` di SQL Server.
- Absensi **selalu live + liveness**, jadi foto cetak / layar HP tidak bisa dipakai untuk absen.
- Rekap memakai MASUK pertama dan PULANG terakhir per hari.

### 3.4 Blacklist oleh HO

```mermaid
sequenceDiagram
    actor HO
    participant UI as Tab Blacklist › Form
    participant API as /api/blacklist/tambah
    participant DB as SQL Server
    HO->>UI: Pilih Personel / Kendaraan, cari kode / NIK / plat
    HO->>UI: No surat, tanggal, alasan, upload surat
    UI->>API: POST multipart
    API->>DB: BEGIN TRAN
    API->>DB: INSERT blacklist
    API->>DB: UPDATE personel / kendaraan SET is_blacklisted = 1
    API->>DB: COMMIT
    Note over DB: Permanen: trigger menolak is_blacklisted 1 → 0
```

---

## 4. ERD (main + tambahan)

ERD lengkap (gambar, tabel relasi, kode Mermaid & DBML) ada di **[docs/ERD.md](ERD.md)** dan dibuat dari
`schema.sql` + migrasi 001 + migrasi 002. Ringkasan tambahan dari migrasi 002 ada di bagian
"Perubahan dari migrasi 002" pada dokumen tersebut.

![ERD](erd/lengkap.png) (ERD final terbaru: [ERD.md](ERD.md))

### 4.1 Perbedaan dengan ERD usulan awal

| Usulan awal | Keputusan (ikut main) | Alasan |
|---|---|---|
| `transaksi.no_do_manual` | Tetap `no_do` | Nama kolom main, sudah dipakai kode |
| `transaksi.hash_keamanan` | Tetap di `timbangan.hash_keamanan` | Main sudah menyimpan hash anti-tamper di timbangan |
| `transaksi.security_id` → personel | Tetap → `users` | Yang bertanggung jawab adalah akun login; personelnya lewat `users.id_personel` |
| Role hanya HO / SECURITY | Role main tetap + HO | Tab Timbangan, Sortasi, Lab tetap dipakai site |
| Tabel timbangan/sortasi/lab tidak dipakai | Tetap dipakai | Tab site tetap ada |
| Tidak ada absensi | `absensi` + `jadwal_kerja` | Face recognition dipakai untuk absensi |

---

## 5. Tampilan (Figma, ikut main)

Desain terbaru ada di bagian 9. Ringkasnya: sidebar **List · Form · Face Recognition**; List = info bar + tab
Security | Timbangan | Sortasi | Laboratorium; Form = info bar + form Create Ticket tanpa tab;
Face Recognition = tab Absensi | Personel | Blacklist | Audit Log tanpa info bar.

## 6. API

| Metode | Endpoint | Keterangan |
|---|---|---|
| GET | `/face-recognition` | Halaman Face Recognition (`?tab=absensi\|personel\|blacklist\|audit`) |
| POST | `/api/plat/lookup` | + `kendaraan_blacklist`; status `BLACKLIST` bila truk diblacklist (dicatat TRY_SCAN_BLACKLIST) |
| POST | `/api/security/buat-tiket` | + cek blacklist truk & supir di server, `id_driver_saran` → `prev_driver_id` + OVERRIDE_DRIVER, MANUAL_INPUT |
| POST | `/api/driver/tambah`, `/api/driver/update-identitas`, `/api/driver/cari-by-nik` | Tetap (supir = personel DRIVER), respons + `kode_personel`, `is_blacklisted` |
| GET | `/api/personel` | Daftar + filter `kategori`, `blacklist=1`, `cari` |
| GET | `/api/personel/saran-kode` | Saran kode berikutnya (`PRGBS-###`) |
| POST | `/api/personel/cek-foto` | Cek foto: tepat 1 wajah, tidak mirip personel lain, tidak mirip blacklist |
| POST | `/api/personel/tambah` | Role HO. Multipart: kode, nik, nama, kategori, no_sim, foto, foto_sumber |
| POST | `/api/personel/<id>/update` | Role HO. Foto opsional, tercatat di `personel_audit_logs` (UPDATE) |
| POST | `/api/personel/<id>/hapus` | Role HO. Soft delete, ditolak bila blacklist, tercatat (HAPUS) |
| POST | `/api/absensi/scan` | Frames + tantangan liveness → MASUK / PULANG + status waktu |
| GET | `/api/absensi/harian`, `/api/absensi/rekap` | Absensi hari ini (`tanggal`, `kategori`) & rekap bulanan (`bulan=YYYY-MM`) |
| GET | `/api/jadwal-kerja` | Jadwal kerja 7 hari |
| GET | `/api/blacklist`, `/api/blacklist/cari-target` | Riwayat & pencarian target (personel / plat) |
| POST | `/api/blacklist/tambah` | Role HO. Permanen, wajib no. surat + upload surat |
| GET | `/api/audit/security`, `/api/audit/personel`, `/api/audit/export` | `hari=1\|7\|30`; export CSV |
| — | `/api/timbang/*`, `/api/sortasi/*`, `/api/lab/*` | **Tetap seperti main** |

---

## 7. Struktur kode & cara menjalankan

```
templates/
  base.html                         kerangka: sidebar, topbar, block info_bar, block tab_header, block tab_content
  partials/layout/                  sidebar, topbar, info_bar, _macros (tab_header, section_header)
  weighbridge.html                  halaman site (List / Form; ?view=form dirender server tanpa kedip)
  partials/site/                    tab security, timbangan, sortasi, lab + modal security
  face_recognition.html             halaman Face Recognition (info_bar dikosongkan)
  partials/face_recognition/        tab absensi, personel, blacklist, audit + modal personel & blacklist
static/js/
  common.js                         helper bersama (modal, escapeHtml, format personel, badge)
  api.js                            Api (fetch + timeout + pesan error), Poller (polling berurutan)
  ui.js                             Notif (toast), Dialog.konfirmasi, tombol sibuk
  base.js                           layout: sidebar List/Form, tab, section
  info_bar.js                       kontainer atas site (plat, validasi)
  site/                             security, kendaraan, timbangan, sortasi, lab
  face_recognition/                 kamera, absensi, personel, blacklist, audit
static/css/tailwind-source.css      komponen (@apply) → build ke tailwind.css
routes/                             main, security, ..., personel, blacklist, absensi, audit
utils/                              db_utils (inti), db_personel, db_blacklist, db_absensi, audit_utils,
                                    personel_utils & absensi_rules (aturan murni, ada unit test)
```

Menjalankan di database dummy:

1. Jalankan `database/migrations/001_kendaraan_driver_kontrak.sql` lalu `002_personel_blacklist.sql`
   di `DbSistemTimbangan_Test` (SSMS). Set `DB_NAME=DbSistemTimbangan_Test` di `.env`.
2. Buat user role **HO** (atau pakai ADMIN) untuk Tambah/Update/Hapus personel dan Tambah blacklist.
3. `npm run build-css` setiap mengubah kelas Tailwind / `tailwind-source.css`.
4. `python -m pytest tests` untuk unit test.
5. Development: `python app.py`. Dipakai di site: `python serve.py` (waitress). Migrasi index: `003_index_optimasi.sql`.
   Rincian optimasi & cache: [docs/OPTIMASI_WEB.md](OPTIMASI_WEB.md).
6. **Wajib** isi `SECRET_KEY` & `HASH_SECRET_KEY` (acak, >= 32 karakter) di `.env`; aplikasi menolak start bila kosong.
   Keamanan, akses LAN, HTTPS, kiosk: [docs/KEAMANAN_WEB.md](KEAMANAN_WEB.md).

---

## 8. Keputusan

1. **Tidak ada toleransi terlambat**: 08:01 sudah dihitung terlambat (`jadwal_kerja.toleransi_menit = 0`).
2. **Jadwal security (shift) menyusul**. Tahap sekarang fokus ke face recognition untuk mengenali orang;
   jadwal di atas dipakai untuk semua kategori sampai jadwal shift dibuat.
3. **Blacklist permanen**, tidak bisa dicabut (dijaga trigger di database).
4. **Format kode personel sementara**: `PRGBS-###` (misal `PRGBS-001`), nomor berikutnya disarankan
   otomatis di form. Format **tidak** dikunci dengan CHECK di database, jadi bisa diganti nanti
   tanpa migrasi; cukup ubah fungsi pembuat saran kode.
5. **Hapus personel = soft delete** (`is_active = 0`): wajah tidak dikenali lagi dan dilepas dari truk,
   riwayat tiket/absensi tetap, tercatat di `personel_audit_logs` (`aksi = HAPUS`). Personel blacklist tidak bisa dihapus.
6. **Tombol Validasi** di info bar hanya tampil di tab Security dan hilang setelah plat tervalidasi (perilaku main, tetap).

## 9. Revisi tampilan (sudah diterapkan di kode)

Sidebar kembali seperti rancangan face recognition awal (menu per fitur), tidak semua dijadikan tab:

- **List**: isi site seperti main, yaitu tab Security, Timbangan, Sortasi, Laboratorium.
- **Form**: Create Ticket tanpa header tab, disesuaikan gabungan main + face recognition (ID/Kode personel, cek blacklist).
- **Face Recognition**: satu menu, tab Absensi | Personel | Blacklist | Audit Log.

Desain Figma revisi ini: <https://www.figma.com/design/wrygHwLrs9aZjCDDCul5CJ>
(halaman "Weighbridge + Face Recognition"), berisi layar:
00 Base (base.html), 01–04 List (Security, Timbangan, Sortasi, Laboratorium), 05–06 Form (tanpa tab;
normal & kendaraan blacklist), 07–10 Face Recognition (satu halaman, tab Absensi | Personel | Blacklist | Audit Log),
M01–M09 modal/cetak site (tiru main) dan M10–M13 modal face recognition (Personel Tambah/Update/Hapus, Blacklist Tambah).

Kode: sidebar & topbar selalu dari `templates/base.html` (partial di `templates/partials/layout/`).
Info bar dan header tab adalah block default (`{% block info_bar %}`, `{% block tab_header %}`):
halaman Face Recognition mengosongkan info bar dan mengganti header tab dengan Absensi | Personel | Blacklist | Audit Log.
Form memakai halaman site yang sama; `base.js` (`setSidebarView('form')`) menyembunyikan header tab
dan membuka panel Create Ticket. Isi halaman di `{% block tab_content %}`.
