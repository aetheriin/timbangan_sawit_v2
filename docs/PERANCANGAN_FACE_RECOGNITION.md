# Perancangan Sistem Face Recognition Personel (clone dari timbangan_sawit_v2)

Dokumen ini adalah rancangan untuk versi **face recognition saja** yang diturunkan dari
`timbangan_sawit_v2`. Isinya: ruang lingkup, perubahan dari v2, arsitektur, workflow,
ERD (Mermaid), rancangan tampilan, daftar API, dan rencana implementasi.

Draf SQL-nya ada di `database/migrations/002_personel_blacklist.sql`.

---

## 1. Ruang lingkup

| | v2 (sekarang) | Clone face recognition |
|---|---|---|
| Subjek wajah | Supir saja (`driver`) | Semua personel (`personel`): **DRIVER**, **SECURITY**, **EMPLOYEE** (orang HO) |
| Tahapan | Security → Timbang 1 → Sortasi/Lab → Timbang 2 | Hanya **Security / Validasi Wajah** |
| Role login | ADMIN, SECURITY, OPERATOR_TIMBANG, SORTASI, LAB | **HO** dan **SECURITY** |
| Blacklist | Tidak ada | Ada, untuk **personel** dan **kendaraan**, ditetapkan HO dengan surat |
| Audit | `driver_audit_logs` | `personel_audit_logs` + `security_audit_logs` (aktivitas security dipantau HO) |
| Master data | plat, supplier, produk, kontrak | **Tetap ada**, karena tiket supir tetap mencatat truk, supplier, dan produk |
| Tampilan | 4 tab (Security, Timbangan, Sortasi, Lab) | **1 tab**, isinya bagian yang bisa dibuka/ditutup (show/hide) |

Yang **dibuang** dari aplikasi: tab & route Timbangan, Sortasi, Lab, pembacaan serial
timbangan (`serial_reader.py`, `timbang_state.py`). Tabel `timbangan`, `sortasi`, `lab_hasil`,
`standar_mutu`, `timeline_monitoring` **tidak dihapus** dari database (data lama aman), hanya
tidak dipakai lagi.

---

## 2. Aktor dan hak akses

| Aktor | Login? | Bisa apa |
|---|---|---|
| **SECURITY** (user) | Ya | Input plat, scan wajah, buat tiket supir, daftar personel baru (kategori DRIVER), ganti supir, cetak QR |
| **HO** (user) | Ya | Semua yang bisa Security, plus: isi/ubah **kode_personel**, ubah kategori, **menetapkan blacklist**, melihat **audit log** security & personel |
| **Personel** | Tidak | Orang yang wajahnya dipindai: supir, petugas security, karyawan HO |

Catatan: satu akun `users` bisa dihubungkan ke satu data `personel` lewat `users.id_personel`
(misalnya petugas security yang login juga terdaftar wajahnya sebagai personel SECURITY).

---

## 3. Arsitektur

```mermaid
flowchart LR
    subgraph Pos_Security["Pos Security"]
        B["Browser (Flask UI)<br/>1 tab: Validasi"]
        K["kiosk_timbang.py<br/>(kamera + liveness)"]
    end
    subgraph Server["Server Flask"]
        R1["routes/security.py<br/>tiket, scan wajah"]
        R2["routes/personel.py<br/>CRUD personel"]
        R3["routes/blacklist.py<br/>blacklist (HO)"]
        R4["routes/audit.py<br/>audit log (HO)"]
        F["utils/face_utils.py<br/>embedding + liveness"]
        A["utils/audit_utils.py<br/>catat security_audit_logs"]
    end
    DB[("SQL Server")]
    UP[("static/uploads<br/>foto wajah, surat blacklist")]

    B -- "HTTP / JSON" --> R1 & R2 & R3 & R4
    K -- "poll /api/kamera/status<br/>POST frames" --> R1
    R1 & R2 --> F
    R1 & R2 & R3 --> A
    R1 & R2 & R3 & R4 --> DB
    R2 & R3 --> UP
```

---

## 4. Workflow

### 4.1 Validasi supir & buat tiket (alur utama, dipakai SECURITY dan HO)

```mermaid
flowchart TD
    S([Truk datang]) --> P[Security ketik No. Plat + Tab]
    P --> CEKPLAT{Kendaraan<br/>is_blacklisted?}
    CEKPLAT -- Ya --> BLK1[Tampil peringatan merah + no surat blacklist<br/>Tiket TIDAK bisa dibuat]
    BLK1 --> LOG1[/security_audit_logs:<br/>TRY_SCAN_BLACKLIST/]
    CEKPLAT -- Tidak --> AKTIF{Sudah ada<br/>tiket aktif?}
    AKTIF -- Ya --> TAMPIL[Tampilkan tiket aktif / cetak ulang QR]
    AKTIF -- Tidak --> DRAFT[Isi supplier, produk, jenis, No. DO manual<br/>saran supir utama & kontrak ditampilkan]
    DRAFT --> SCAN[Scan wajah di kiosk<br/>liveness: kedip / menoleh]
    SCAN --> KENAL{Wajah cocok<br/>dengan personel?}
    KENAL -- Tidak --> BARU[Tambah personel baru<br/>kategori DRIVER]
    BARU --> CEKMIRIP{Wajah/NIK mirip<br/>personel blacklist?}
    CEKMIRIP -- Ya --> BLK2[Tolak pendaftaran]
    BLK2 --> LOG1
    CEKMIRIP -- Tidak --> OK
    KENAL -- Ya --> CEKORANG{personel<br/>is_blacklisted?}
    CEKORANG -- Ya --> BLK3[Peringatan merah, tiket tidak bisa dibuat]
    BLK3 --> LOG1
    CEKORANG -- Tidak --> KAT{kategori = DRIVER?}
    KAT -- Tidak --> INFO[Tampil identitas saja<br/>SECURITY / EMPLOYEE bukan pembawa truk]
    KAT -- Ya --> OK[Supir terverifikasi<br/>snapshot foto disimpan]
    OK --> GANTI{Beda dengan supir<br/>utama / sebelumnya?}
    GANTI -- Ya --> OVR[is_driver_changed = 1<br/>prev_driver_id diisi]
    OVR --> LOG2[/security_audit_logs:<br/>OVERRIDE_DRIVER/]
    LOG2 --> SUBMIT
    GANTI -- Tidak --> SUBMIT[Submit tiket<br/>hash_keamanan dihitung]
    SUBMIT --> QR[Cetak QR tiket]
    QR --> E([Selesai])
```

Aturan penting:

- **Pemeriksaan blacklist dilakukan di server**, bukan hanya di tampilan: `buat-tiket` menolak
  kalau kendaraan atau supir berstatus blacklist, walaupun form dikirim paksa.
- **Input manual** (wajah gagal dikenali tetapi tiket tetap dibuat, bila `WAJIB_SCAN_WAJAH=false`)
  dicatat sebagai `MANUAL_INPUT`.
- `hash_keamanan` = HMAC-SHA256 dari `no_tiket|id_kendaraan|id_driver|id_supplier|id_produk|created_at`
  memakai `HASH_SECRET_KEY`. HO bisa memverifikasi bahwa baris tiket tidak diubah langsung di database.

### 4.2 Blacklist oleh HO

```mermaid
sequenceDiagram
    actor HO
    participant UI as UI (panel Blacklist)
    participant API as /api/blacklist
    participant DB as SQL Server

    HO->>UI: Pilih entitas (Personel / Kendaraan), cari NIK / plat
    HO->>UI: Isi no surat, alasan, tanggal, upload surat (PDF/JPG)
    UI->>API: POST multipart
    API->>API: role_required('HO'), validasi file & field
    API->>DB: BEGIN TRAN
    API->>DB: INSERT blacklist (...)
    API->>DB: UPDATE personel/kendaraan SET is_blacklisted = 1
    API->>DB: COMMIT
    API-->>UI: 200 OK
    Note over DB: Permanen: tidak ada endpoint untuk membatalkan,<br/>trigger DB menolak is_blacklisted 1 -> 0
```

### 4.3 Kelola personel (HO)

```mermaid
flowchart LR
    A[HO buka panel Personel] --> B[Cari NIK / nama / kode]
    B --> C[Edit: kode_personel, nama, NIK, SIM, kategori, foto]
    C --> D[UPDATE personel<br/>is_updated = 1, current_hash baru]
    D --> E[/INSERT personel_audit_logs<br/>nilai lama & baru + hash_audit/]
```

- `kode_personel` (misal `PRGBS-001`) hanya bisa diisi/diubah HO. Security boleh mendaftarkan
  personel DRIVER baru, kodenya kosong sampai HO mengisi.
- Setiap perubahan identitas tetap membuat baris audit (seperti `driver_audit_logs` di v2).

### 4.4 Status tiket

```mermaid
stateDiagram-v2
    [*] --> SECURITY_REGISTER: plat diinput
    SECURITY_REGISTER --> SCAN_WAJAH: kamera dinyalakan
    SCAN_WAJAH --> TERVERIFIKASI: wajah cocok & tidak blacklist
    SCAN_WAJAH --> REJECTED: blacklist / dibatalkan
    TERVERIFIKASI --> SELESAI: truk keluar / tiket ditutup
    REJECTED --> [*]
    SELESAI --> [*]
```

Karena clone ini tidak punya tahap timbang/sortasi/lab, status lama (`TIMBANG_1`,
`INSPEKSI_PROSES`, `TIMBANG_2`) dipetakan ke `TERVERIFIKASI` saat migrasi.

---

## 5. ERD

### 5.1 Diagram

```mermaid
erDiagram
    users {
        int id_user PK
        string nama
        string username UK
        string password
        string role "HO / SECURITY"
        int id_personel FK "opsional, wajah akun ini"
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    personel {
        int id_personel PK
        string kode_personel UK "diisi HO, misal PRGBS-001"
        string nik UK "NIK KTP"
        string nama_personel
        string no_sim "boleh NULL untuk non-DRIVER"
        string kategori "DRIVER / SECURITY / EMPLOYEE"
        boolean is_blacklisted "permanen jika 1"
        varbinary face_embedding_data
        string foto_path
        boolean is_updated
        string current_hash
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    kendaraan {
        int id_kendaraan PK
        string no_plat UK
        string no_stnk
        boolean is_blacklisted "permanen jika 1"
        boolean is_active
        datetime created_at
    }
    supplier {
        int id_supplier PK
        string kode_supplier UK
        string nama_supplier
        string tipe
        boolean is_active
        datetime created_at
    }
    produk {
        int id_produk PK
        string nama_produk
        string kategori
        boolean is_active
    }
    kendaraan_driver {
        int id_kendaraan_driver PK
        int id_kendaraan FK
        int id_driver FK "ke personel DRIVER"
        boolean is_utama
        boolean is_active
    }
    kontrak_kendaraan {
        int id_kontrak PK
        int id_kendaraan FK
        int id_supplier FK
        int id_produk FK
        date tanggal_mulai
        date tanggal_selesai
        boolean is_active
    }
    transaksi {
        string no_tiket PK
        string jenis_transaksi
        string no_do_manual "opsional"
        int id_supplier FK
        int id_produk FK
        int id_kendaraan FK
        int id_kontrak FK
        int id_driver FK "personel DRIVER"
        int security_id FK "users SECURITY"
        boolean is_driver_changed
        int prev_driver_id FK "personel"
        string driver_photo_path "snapshot di pos"
        string status_alur
        boolean is_qr_active
        datetime qr_expired_at
        int qr_reprint_count
        string alasan_reject
        int rejected_by FK
        string hash_keamanan "anti-tamper"
        datetime created_at
    }
    blacklist {
        int id_blacklist PK
        string tipe_entitas "PERSONEL / KENDARAAN"
        int id_personel FK "NULL jika KENDARAAN"
        int id_kendaraan FK "NULL jika PERSONEL"
        string no_surat_blacklist
        string alasan_blacklist
        string file_surat_blacklist
        date tgl_blacklist
        int created_by FK "user HO"
        datetime created_at
    }
    personel_audit_logs {
        int id_log PK
        int id_personel FK
        string kode_personel_lama
        string kode_personel_baru
        string nik_lama
        string nik_baru
        string nama_lama
        string nama_baru
        string no_sim_lama
        string no_sim_baru
        string hash_audit
        int updated_by FK
        datetime updated_at
    }
    security_audit_logs {
        int id_log PK
        int user_id FK
        string action_type "TRY_SCAN_BLACKLIST / OVERRIDE_DRIVER / MANUAL_INPUT"
        string no_tiket "opsional"
        string details "JSON"
        string ip_address
        datetime created_at
    }

    personel ||--o{ transaksi : "mengemudi (id_driver)"
    personel ||--o{ transaksi : "supir sebelumnya (prev_driver_id)"
    personel ||--o{ personel_audit_logs : "riwayat perubahan"
    personel ||--o{ blacklist : "rekam jejak blacklist"
    personel |o--o| users : "wajah akun"
    personel ||--o{ kendaraan_driver : "supir truk"
    kendaraan ||--o{ kendaraan_driver : "punya supir"
    kendaraan ||--o{ kontrak_kendaraan : "dikontrak"
    kendaraan ||--o{ transaksi : "digunakan pada"
    kendaraan ||--o{ blacklist : "rekam jejak blacklist"
    supplier ||--o{ transaksi : "menyuplai"
    supplier ||--o{ kontrak_kendaraan : "kontrak"
    produk ||--o{ transaksi : "kategori barang"
    kontrak_kendaraan |o--o{ transaksi : "berlaku pada"
    users ||--o{ transaksi : "diperiksa security"
    users ||--o{ transaksi : "menolak (rejected_by)"
    users ||--o{ blacklist : "dieksekusi HO"
    users ||--o{ personel_audit_logs : "diupdate HO"
    users ||--o{ security_audit_logs : "dipantau HO"
```

### 5.2 Penyesuaian terhadap ERD usulan (gambar kiri)

ERD usulan sudah bagus; ada beberapa penyesuaian supaya cocok dengan kode dan data v2:

1. **`transaksi.security_id` tetap FK ke `users`**, bukan ke `personel`.
   Yang menekan tombol Submit adalah akun yang login; akun itu yang harus bertanggung jawab
   di audit. Supaya tetap bisa ditelusuri "personel security mana", ditambahkan
   `users.id_personel` → `personel`. Jadi: `transaksi.security_id → users.id_personel → personel`.
   Data tiket lama juga tidak rusak karena nilainya memang ID user.
2. **`personel.foto_path` dipertahankan**. Kolom ini sudah ada di v2 dan dipakai untuk
   menampilkan foto di info bar dan kartu supir.
3. **`personel.no_sim` boleh NULL**. Personel SECURITY dan EMPLOYEE tidak selalu punya SIM.
   Aturan "DRIVER wajib punya SIM" dibuat sebagai CHECK constraint.
4. **`kode_personel` UNIQUE tapi boleh kosong** (filtered unique index), karena Security bisa
   mendaftarkan supir baru sebelum HO memberi kode.
5. **`blacklist` diberi CHECK**: kalau `tipe_entitas = 'PERSONEL'` maka `id_personel` wajib
   dan `id_kendaraan` harus NULL, dan sebaliknya.
6. **Blacklist permanen dijaga di database** dengan trigger yang menolak perubahan
   `is_blacklisted` dari 1 ke 0 (tidak hanya mengandalkan aplikasi).
7. **`security_audit_logs.no_tiket`** (opsional) ditambahkan supaya HO bisa langsung menautkan
   log `OVERRIDE_DRIVER` ke tiketnya.
8. **`kendaraan_driver` dan `kontrak_kendaraan` dari migrasi 001 tetap dipakai**
   (saran supir utama dan kontrak truk–supplier). Kolom `id_driver` di tabel ini tidak diganti
   nama supaya perubahan kode tidak terlalu besar; isinya ID personel kategori DRIVER.
9. **`users.role`**: akun aktif hanya boleh HO atau SECURITY. ADMIN lama menjadi HO.
   Akun LAB / SORTASI / OPERATOR_TIMBANG dinonaktifkan (role lamanya tetap tersimpan).

### 5.3 Relasi

| Induk (1) | Anak (N) | Kolom FK | Arti |
|---|---|---|---|
| personel | transaksi | `id_driver` | Supir yang membawa truk pada tiket |
| personel | transaksi | `prev_driver_id` (opsional) | Supir sebelumnya bila terjadi pergantian |
| personel | blacklist | `id_personel` (opsional) | Rekam jejak blacklist personel |
| personel | personel_audit_logs | `id_personel` | Riwayat perubahan identitas |
| personel | users | `users.id_personel` (opsional, 0..1) | Wajah milik akun login |
| kendaraan | transaksi | `id_kendaraan` | Truk yang dipakai |
| kendaraan | blacklist | `id_kendaraan` (opsional) | Rekam jejak blacklist kendaraan |
| supplier | transaksi | `id_supplier` | Supplier/buyer tiket |
| produk | transaksi | `id_produk` | Produk yang dibawa |
| users | transaksi | `security_id`, `rejected_by` | Petugas pembuat / penolak tiket |
| users | blacklist | `created_by` | HO yang menetapkan blacklist |
| users | personel_audit_logs | `updated_by` | User yang mengubah data personel |
| users | security_audit_logs | `user_id` | Aktivitas security yang dipantau HO |

---

## 6. Rancangan tampilan (sesimpel mungkin)

Deretan 4 tab di `base.html` dihapus. Hanya ada **satu halaman** (`partials/validasi_tab.html`,
turunan `security_tab.html`). Pindah tampilan lewat sidebar yang sudah ada (`setSidebarView`),
isi per bagian dibuka/ditutup dengan `toggleSection` yang juga sudah ada.

```
┌ Sidebar ───────┐ ┌ Topbar: Face Recognition            Budi (SECURITY) ⏻ ┐
│ ▸ Validasi     │ ├──────────────────────────────────────────────────────────┤
│ ▸ Daftar Tiket │ │ Info bar: No Tiket | No Plat | Supplier | Supir | [foto] │
│ ── HO saja ──  │ ├──────────────────────────────────────────────────────────┤
│ ▸ Personel     │ │ ▼ 1. Kendaraan        (plat, STNK, supplier, produk, DO) │
│ ▸ Blacklist    │ │ ▼ 2. Scan Wajah       (kamera, hasil, identitas)         │
│ ▸ Audit Log    │ │ ▶ 3. Ganti / Tambah Supir   (tertutup, dibuka jika perlu) │
└────────────────┘ │ [!] Banner merah BLACKLIST muncul di atas jika terkena   │
                   │                                  [Submit] [Cetak QR]     │
                   └──────────────────────────────────────────────────────────┘
```

| View (sidebar) | Siapa | Isi |
|---|---|---|
| **Validasi** | SECURITY, HO | Form tiket 3 bagian di atas. Bagian 2 terkunci sampai plat valid & tidak blacklist |
| **Daftar Tiket** | SECURITY, HO | Tiket aktif + riwayat supir (isi view "List" yang sekarang) |
| **Personel** | HO | Tabel personel, filter kategori, edit kode/identitas/foto, badge blacklist |
| **Blacklist** | HO | Form penetapan (entitas, no surat, alasan, tanggal, upload surat) + tabel riwayat |
| **Audit Log** | HO | Tab kecil: Security (`security_audit_logs`) dan Personel (`personel_audit_logs`) |

Menu khusus HO disembunyikan dengan Jinja (`{% if current_user.role == 'HO' %}`) **dan**
endpoint-nya dijaga `@role_required('HO')`, jadi bukan hanya tersembunyi di tampilan.

Modal yang tetap: Tambah Personel (dulu Tambah Supir), Update (Ganti Supir, Edit Data,
Supir Truk, Kontrak Truk), Cetak QR.

---

## 7. Daftar API

| Metode | Endpoint | Role | Keterangan |
|---|---|---|---|
| POST | `/api/plat/lookup` | semua | + `kendaraan_blacklist` di respons |
| POST | `/api/security/buat-tiket` | SECURITY, HO | + cek blacklist server-side, `is_driver_changed`, `prev_driver_id`, snapshot foto, `hash_keamanan` |
| GET | `/api/security/list-tiket-aktif` | semua | tetap |
| POST | `/api/security/tutup-tiket` | SECURITY, HO | **baru**: status `SELESAI` |
| POST | `/api/personel/cari-by-nik` | semua | dulu `/api/driver/cari-by-nik` |
| POST | `/api/personel/tambah` | SECURITY (DRIVER saja), HO (semua kategori) | dulu `/api/driver/tambah`; tolak wajah/NIK yang mirip personel blacklist |
| POST | `/api/personel/update-identitas` | SECURITY, HO | kode_personel & kategori hanya HO |
| GET | `/api/personel` | HO | **baru**: daftar + filter |
| POST | `/api/verifikasi-wajah` | kiosk | respons + `kategori`, `is_blacklisted` |
| GET | `/api/blacklist` | HO | **baru** |
| POST | `/api/blacklist/tambah` | HO | **baru**, multipart (file surat) |
| GET | `/api/audit/security` | HO | **baru** |
| GET | `/api/audit/personel` | HO | **baru** |
| — | `/api/timbang/*`, `/api/sortasi/*`, `/api/lab/*` | — | **dihapus** |

---

## 8. Rencana implementasi (bertahap)

1. **Database**: jalankan `002_personel_blacklist.sql` pada **salinan** database (misal `DbFaceRecognition`),
   lalu arahkan `DB_NAME` di `.env` ke database itu.
2. **Bersih-bersih**: hapus `routes/timbangan.py`, `sortasi.py`, `lab.py`, partial & JS-nya,
   `utils/serial_reader.py`, `utils/timbang_state.py`; hapus deretan tab di `base.html`.
3. **Rename driver → personel** di `utils/db_utils.py`, `routes/security.py`, `serializers.py`,
   `verifikasi_state.py`, `static/js/security.js`, `supir.js`, `kendaraan.js`.
4. **Blacklist**: `routes/blacklist.py`, cek di `plat/lookup`, `verifikasi-wajah`, `buat-tiket`, `personel/tambah`.
5. **Audit**: `utils/audit_utils.py` (`catat_aktivitas(user_id, action_type, details, no_tiket=None)`),
   panggil di titik TRY_SCAN_BLACKLIST / OVERRIDE_DRIVER / MANUAL_INPUT.
6. **Tampilan**: sidebar baru + panel HO (Personel, Blacklist, Audit Log).
7. **Tes**: tambah unit test untuk aturan blacklist & hash tiket (`tests/`).

---

## 9. Yang perlu dikonfirmasi

1. **Wajah personel SECURITY / EMPLOYEE dipakai untuk apa?** Saat ini dirancang hanya untuk
   identifikasi (tampil identitas, dan menautkan akun login ke wajahnya). Kalau maksudnya
   absensi atau akses masuk karyawan HO, perlu satu tabel log kunjungan tambahan.
2. **Blacklist benar-benar permanen?** Dirancang tidak bisa dicabut sama sekali. Kalau suatu saat
   HO perlu mencabut (misalnya salah input), perlu kolom `is_revoked`, `revoked_by`, dan `revoked_at`.
3. **Kapan tiket `SELESAI`?** Tanpa tahap timbang, diusulkan Security menutup tiket saat truk keluar
   (tombol "Tutup Tiket"), atau otomatis saat `qr_expired_at` lewat.
