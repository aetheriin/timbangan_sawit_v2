# Rancangan Perbaikan Tahap 1 (uji coba lapangan: Form Security, Blacklist, Tamu)

Draf untuk ditinjau sebelum dikerjakan. Setiap poin berisi: **kondisi kode sekarang** (sudah dicek ke kode di branch ini),
**rancangan**, dan **keputusan yang perlu Anda pilih**. Bagian yang ditandai ★ adalah rekomendasi saya.

## 0. Temuan dari log uji coba

| Log | Penyebab | Tindakan |
|---|---|---|
| `AttributeError: 'AnonymousUserMixin' object has no attribute 'id'` di `/api/verifikasi-wajah` (500) | Kiosk memanggil tanpa login, kode membaca area dari akun login | **Sudah diperbaiki** (area diambil dari pos kiosk). Hilang sepenuhnya bila kiosk dihapus (poin 1) |
| `can't grab frame ... MSMF` di jendela kiosk | Kamera dipakai dua program (browser & kiosk) / driver webcam | Alasan kuat menghapus kiosk (poin 1) |
| `Frame tidak cukup untuk analisis EAR` → 400 | Wajah tidak terbaca di cukup banyak frame (cahaya / posisi) | Poin 1: mode tanpa tantangan per area; pesan lebih jelas |
| `/api/absensi/scan -> 404` | Normal: wajah tidak dikenali (belum terdaftar) | – |
| Path `D:\VsCode\Timbangan_Sawit\...` | Server dijalankan dari folder **lain** (bukan `D:\Vscode\timbangan_sawit_v2`) | Pastikan menjalankan `serve.py` dari folder yang di-`git pull` |

---

## 1. Hapus kiosk kamera, scan wajah lewat webcam browser + pengaturan tantangan per area

**Kondisi sekarang**
- Absensi & Kunjungan sudah memakai webcam browser + tantangan acak (kedip / menoleh kiri / kanan).
- Form Security memakai **kiosk** (`kiosk_timbang.py`, pilih "Pos kamera", `verifikasi_state`).
- Pengaturan per area sudah ada (`pengaturan_area`): `WAJIB_SCAN_WAJAH`, `AMBANG_WAJAH`.
- Tabel `perangkat_kiosk` (Pos) **tetap dibutuhkan** untuk token agen timbangan.

**Rancangan**
1. Form Security › Informasi Driver memakai komponen kamera yang sama dengan Absensi (webcam di PC Security).
   Dihapus: `kiosk_timbang.py`, pilihan "Pos kamera", endpoint `/api/kamera/*` & `/api/verifikasi-wajah` versi kiosk,
   `verifikasi_state` bagian kiosk. Admin "Perangkat / Kiosk" menjadi **"Perangkat"** (Pos untuk agen + Jembatan).
2. Pengaturan baru per area di Admin › Pengaturan Site (pilih area):

   | Kunci | Pilihan | Arti |
   |---|---|---|
   | `TANTANGAN_SECURITY` | Wajib / Tidak | Wajib = supir mengikuti tantangan acak; Tidak = cukup hadap kamera (diambil beberapa frame, harus tepat 1 wajah) |
   | `TANTANGAN_ABSENSI` | Wajib / Tidak | Sama untuk absensi & kunjungan |
   | `WAJIB_SCAN_WAJAH` (sudah ada) | Ya / Tidak | Tiket boleh dibuat tanpa scan (tercatat MANUAL_INPUT) |

   Tanpa tantangan lebih cepat tetapi foto / layar HP bisa lolos; tetap tercatat foto & jarak wajah di log.

**Syarat teknis penting**: browser hanya mengizinkan kamera di **HTTPS** atau **localhost**. PC Security yang membuka
`http://IP-SERVER:5000` **tidak bisa** memakai kamera tanpa salah satu:

| Cara | Kapan |
|---|---|
| ★ Chrome PC Security: `chrome://flags/#unsafely-treat-insecure-origin-as-secure` isi `http://IP-SERVER:5000` → Enabled → Relaunch | Uji coba (5 menit per PC) |
| HTTPS dengan Caddy (`deploy/Caddyfile`) + pasang sertifikat di tiap PC | Produksi |
| PC Security = PC server (buka `http://localhost:5000`) | Bila hanya 1 pos |

**Keputusan**
- 1a. Pengaturan per **area** ★ (sudah ada mekanismenya) atau per **company** (tabel baru)? Usul: per area, plus tombol
  "terapkan ke semua area company ini".
- 1b. Tantangan Security & Absensi dipisah (★) atau satu pengaturan untuk keduanya?

---

## 2. Halaman Blacklist sendiri di sidebar + hak akses KTU

**Kondisi sekarang**
- Blacklist = tab di menu Face Recognition (kode menu `BLACKLIST`, induk `FACE_RECOGNITION`), aksi tambah hanya HO.
- Wajib **No. surat + tanggal + alasan + file surat** (upload).
- Blacklist berlaku **semua area** (tidak ada kolom area di `blacklist`).

**Rancangan**
- Menu baru di sidebar **Blacklist** (`/blacklist`, ikon `fa-ban`), dikeluarkan dari tab Face Recognition (migrasi 020:
  `menu.BLACKLIST` jadi menu utama + url). Isi halaman: daftar, tambah (cari personel / plat / foto wajah), detail surat.
- Level **KTU** dibuat Admin di Level & Hak Akses, lalu centang Blacklist › Tambah. Tidak ada kode khusus KTU.
- Dicatat area & akun yang menetapkan (sudah: `ditetapkan_oleh`; ditambah tampilan area).

**Keputusan**
- 2a. Blacklist dari site (KTU) berlaku **semua area / PT** ★ atau hanya area KTU itu?
- 2b. No. surat & file surat **wajib** saat KTU menetapkan, atau boleh **menyusul** (seperti BA void) ★?
- 2c. Siapa yang boleh mencabut? Sekarang **permanen** (trigger database). Tetap permanen ★?

---

## 3. Form Tambah Personel: kategori, SIM, kode per kategori

**Kondisi sekarang**
- Kategori langsung terisi DRIVER (pilihan pertama). Field SIM selalu tampil.
- Kategori di database: DRIVER (wajib SIM), SECURITY, EMPLOYEE, TAMU. Belum ada kategori HO.
- Kode personel satu format: `PRGBS-###`, disarankan otomatis, unik.

**Rancangan**
1. Kategori dimulai kosong **"-- Pilih kategori --"** (wajib dipilih).
2. No. SIM, Jenis SIM, SIM berlaku **hanya tampil bila kategori wajib SIM** (diambil dari `kategori_personel.wajib_sim`,
   bukan ditulis "DRIVER" di kode), otomatis wajib diisi; kategori lain disembunyikan & dikosongkan.
3. Kode per kategori: kolom baru `kategori_personel.prefix_kode` (migrasi 020), diatur di Admin:

   | Kategori | Prefix (usulan) | Contoh |
   |---|---|---|
   | DRIVER | `DRV` | DRV-001 |
   | SECURITY | `SEC` | SEC-001 |
   | EMPLOYEE | `KRY` | KRY-001 |
   | HO (kategori baru?) | `HO` | HO-001 |
   | TAMU | `TMU` | TMU-001 |

   Nomor = urutan terbesar prefix itu + 1, dibuat **server saat simpan** (di dalam transaksi, jadi dua orang menyimpan
   bersamaan tidak dapat nomor sama; kode tetap UNIQUE). Di form tampil sebagai saran (read-only).
4. Form Security › Tambah Supir juga menampilkan Kode Personel (otomatis DRV-xxx).

**Keputusan**
- 3a. Kode lama `PRGBS-###`: **dibiarkan** ★ (personel baru pakai prefix baru) atau diganti massal?
- 3b. HO dijadikan **kategori sendiri** atau tetap EMPLOYEE dengan prefix `HO`?
- 3c. Kode boleh diubah manual oleh HO (★ hanya HO) atau selalu otomatis?
- 3d. Ganti kategori (mis. TAMU jadi DRIVER) → kode ikut berganti prefix, atau tetap kode lama?

---

## 4. Kapan tiket dibuat / dicetak

**Kondisi sekarang (dicek ke kode)**
- Plat diketik → validasi (cek blacklist, tiket aktif). Tiket dibuat saat **Submit** setelah data lengkap + scan wajah
  (bila `WAJIB_SCAN_WAJAH`), lalu cetak QR. Status `SECURITY_REGISTER`.
- Database: tiket **wajib** punya supir, mitra, produk, kendaraan (`NOT NULL`). DO **boleh kosong** (`no_do`/`id_do` NULL).
- List: tiket `SECURITY_REGISTER` tampil di tab Security (selesai) **dan** Timbangan (menunggu Timbang 1), karena itu
  terlihat "sama".

**Pilihan**

| | Cara | Kelebihan | Kekurangan / syarat |
|---|---|---|---|
| A | (sekarang) Tiket saat Submit setelah lengkap + scan wajah | Data tiket selalu lengkap, sederhana | Antre di pos bila scan lama |
| B ★ | A, tetapi **DO boleh menyusul**: tiket dibuat tanpa DO (TBS manual), ditandai "DO belum ada"; DO dilengkapi Security / KTU sebelum Timbang 2 (atau sebelum cetak final) | Cocok untuk TBS tanpa DO; truk tidak tertahan | Perlu tombol "Lengkapi DO" + notifikasi tiket tanpa DO |
| C | Tiket **draft** saat plat divalidasi (nomor tiket langsung keluar & tercetak), data dilengkapi belakangan | Nomor tiket paling cepat | Kolom supir / mitra / produk harus boleh kosong; banyak draft batal → perlu batal otomatis (mis. > 2 jam) dan nomor tiket "bolong" |
| D | **Kartu antre / gate pass** saat plat masuk (bukan tiket), tiket resmi dibuat saat data lengkap | Nomor tiket tetap berurutan & bersih | Dua dokumen (antre + tiket) |
| E | Scan wajah dimatikan per area (poin 1) → tiket langsung dibuat setelah data | Paling cepat | Identitas supir hanya dari input |

Tambahan untuk List: tab **Security** hanya menampilkan tiket yang **masih perlu tindakan Security** (draft / DO belum
ada), sedangkan tiket yang menunggu timbang hanya tampil di tab Timbangan. Kolom "Menunggu" tetap.

**Keputusan**: 4a. Pilih A / B ★ / C / D / E (boleh gabungan B + E per area). 4b. Siapa yang boleh melengkapi DO menyusul
(Security, KTU, keduanya ★)? 4c. Batas: DO wajib ada sebelum Timbang 2 ★ atau boleh sampai selesai?

---

## 5. Kuota DO, tiket berlebih & split tiket

**Kondisi sekarang**
- `kontrak.qty_kg` (kuota) dan `do_pengangkutan.qty_kg` (alokasi per pengangkut). **Belum ada** hitungan realisasi,
  peringatan kuota, maupun split tiket. Belum ada notifikasi di top bar.

**Istilah**: Realisasi DO = jumlah **netto** tiket SELESAI dengan DO itu. Sisa = kuota − realisasi.

**Contoh kasus**: DO 500 t, 29 truk sudah 470 t, truk ke-30 netto 35 t → lebih 5 t.

**Skema**

| | Skema | Cara kerja | Catatan |
|---|---|---|---|
| S1 | Catat saja | Tiket tetap 35 t di DO itu, DO ditandai **berlebih 5 t**, notifikasi ke Timbangan & KTU | Paling sederhana; administrasi lebih diurus manual |
| S2 | Toleransi DO | Lebih sampai X% / X kg (mis. 2%) diterima di DO yang sama; di atas toleransi → S3 | Umum di kontrak CPO / kernel |
| S3a ★ | **Split tiket** saat Timbang 2 | Tiket asli dicatat **30 t** (sisa kuota) ke DO itu; dibuat **tiket baru** `NOTIKET-S1` (plat & supir sama, tanpa timbang ulang) **5 t**, diarahkan ke: DO berikutnya yang aktif untuk kontrak / customer & produk sama, atau "menunggu DO" bila belum ada | Nomor tiket per DO tetap rapi untuk penagihan; perlu kolom `no_tiket_induk` + `split_kg` |
| S3b | Satu tiket, alokasi ke beberapa DO | Tabel `tiket_alokasi_do (no_tiket, id_do, kg)`: 30 t DO-A, 5 t DO-B | Tanpa nomor tiket baru; laporan per DO dari alokasi |
| S4 ★ | Pencegahan di Security | Saat memilih DO: tampil **sisa kuota**; bila sisa < perkiraan muatan truk (mis. rata-rata netto truk itu) muncul peringatan; DO terpenuhi → tidak bisa dipilih lagi (atau peringatan saja) | Mengurangi kasus berlebih |

Rekomendasi: **S4 + S2 (toleransi diatur per kontrak) + S3a**.

**Notifikasi (top bar, ikon lonceng)**

| Kejadian | Untuk |
|---|---|
| DO mencapai 90% kuota | Timbangan, KTU |
| DO terpenuhi / berlebih / tiket di-split | Timbangan, KTU, HO |
| Tiket dibuat tanpa DO > N jam | Security, KTU |
| Kendaraan / supir blacklist masuk | KTU, HO |
| DO kedaluwarsa (berlaku_sampai) dipakai | Security, KTU |
| Agen timbangan terputus > 1 menit | Timbangan, Admin |

Rancangan data: `notifikasi (id, id_comp_area, kode_menu sasaran, judul, isi, tautan, waktu)` + `notifikasi_baca
(id_notifikasi, id_user)`. Sasaran memakai **hak akses menu** (mis. semua level yang punya akses FORM_TIMBANGAN di area
itu), bukan nama level, jadi KTU cukup dicentang di Admin. Lonceng memperbarui hitungan tiap 30 detik.

**Keputusan**: 5a. Satuan kuota DO = **kg netto** ★? 5b. Toleransi berapa (persen atau kg), per kontrak ★ atau global?
5c. Kelebihan diarahkan ke DO berikutnya **otomatis** atau **dipilih KTU** ★? 5d. S3a (nomor tiket baru) ★ atau S3b?
5e. DO terpenuhi: **blokir** pemilihan di Security atau **peringatan saja** ★?

---

## 6. Kasus lain yang perlu disepakati

| # | Kasus | Sekarang | Usulan |
|---|---|---|---|
| 1 | Truk sudah Timbang 1 lalu pergi tanpa Timbang 2 | Tiket menggantung | Tiket > 24 jam tanpa Timbang 2 → notifikasi KTU, void oleh Admin |
| 2 | Supir berganti di tengah (Timbang 2 supir lain) | Tidak dicek | Opsional scan wajah saat Timbang 2; catat OVERRIDE_DRIVER |
| 3 | Satu truk masuk 2× sehari | Ditolak bila masih ada tiket aktif | Tetap |
| 4 | DO dinonaktifkan / kedaluwarsa saat tiket berjalan | Tidak dicek | Peringatan di Timbang 2, notifikasi |
| 5 | Timbangan putus saat menimbang | Simpan ditolak (tidak terhubung) | Tetap; input manual darurat **hanya** dengan alasan + persetujuan KTU, tercatat |
| 6 | Koreksi berat (salah tiket / timbang ulang) | Hanya void | Fitur timbang ulang dengan alasan, berat lama tetap tercatat |
| 7 | Lab reject | Tiket REJECTED | Truk tetap Timbang 2 keluar untuk tara? perlu disepakati |
| 8 | Plat sementara / tanpa STNK | STNK wajib | Kendaraan "sementara" dengan masa berlaku, wajib dilengkapi |
| 9 | Server / jaringan mati | Tidak bisa input | Formulir manual + input susulan dengan tanda "susulan" |
| 10 | Blacklist ditetapkan saat tiket sedang berjalan | Tidak ada notifikasi | Notifikasi ke Timbangan & KTU |
| 11 | Tamu tanpa wajah terdaftar | Daftar tamu baru | Tetap |
| 12 | Cetak ulang tiket | Ada (hitungan reprint) | Tambah alasan cetak ulang |
| 13 | Satu DO, banyak pengangkut, alokasi per pengangkut terlewati | Alokasi tidak dihitung | Ikut S4 per pengangkut (sisa alokasi) |
| 14 | TBS tanpa DO dari petani / pemasok kecil | DO opsional | Poin 4 B; laporan per mitra |

---

## 7. Peringatan blacklist di Form Security (tiket tetap bisa dibuat)

**Kondisi sekarang**
- Kendaraan blacklist: banner merah "PERINGATAN: KENDARAAN ... MASUK BLACKLIST ... Tiket tetap bisa dibuat", kolom plat
  merah. ✓ sudah sesuai.
- Supir blacklist: hanya badge BLACKLIST kecil + toast. **Belum** ada banner & kotak merah.
- Gambar kedua (Figma lama) bertuliskan "tiket tidak dapat dibuat" → **tidak dipakai**; aturan yang berlaku: peringatan saja.

**Rancangan**
- Satu banner merah yang menyebut **siapa**: "PERINGATAN BLACKLIST: Kendaraan BM 8821 KA" / "Supir PRGBS-009 · Dedi
  Kurniawan" / keduanya, dengan no. surat, tanggal, penetap, tombol Lihat surat, dan kalimat "Tiket tetap bisa dibuat,
  tercatat di Audit Log".
- Kartu **Pengemudi Terakhir Truk** dan kartu supir hasil scan: garis **merah tebal** (border 3–4 px) pada kotak foto dan
  kartu, latar merah muda, badge BLACKLIST besar.
- Tombol Submit tetap aktif; sebelum submit muncul konfirmasi "Tetap buat tiket untuk kendaraan / supir blacklist?".
- Setiap deteksi & tiket untuk blacklist tercatat (sudah) dan masuk notifikasi KTU / HO (poin 5).

---

## 8. Tamu (kunjungan) di pos Security

**Kondisi sekarang (sudah ada, migrasi 009)**
- Tab **Face Recognition › Kunjungan Tamu**, hak akses `KUNJUNGAN` (awal: SECURITY tambah & ubah).
- Alur: scan wajah → bila dikenal (pernah datang) data langsung muncul, bila tidak → daftar tamu baru (NIK, nama, foto
  wajah) → isi **Bertemu dengan** (personel), **Keperluan**, asal perusahaan, No. plat (opsional), keterangan → catat
  masuk. Daftar "masih di dalam" → tombol **Catat keluar**.
- Tamu = personel kategori TAMU (tidak bisa punya akun). Wajah tamu juga dicocokkan dengan **blacklist**.
- Tabel `kunjungan`: tamu, dituju, keperluan, area, foto saat datang, waktu masuk / keluar, dicatat oleh.

**Pilihan letak**

| | Letak | Kelebihan | Kekurangan |
|---|---|---|---|
| T1 ★ | **Menu sendiri "Tamu"** di sidebar (`/tamu`), seperti Blacklist | Security langsung buka 1 klik, layar penuh untuk kamera & daftar "di dalam"; hak akses terpisah | Satu menu bertambah |
| T2 | Tetap tab di Face Recognition | Tanpa perubahan | Tersembunyi, bercampur dengan Absensi / Personel |
| T3 | Tab di Form Security (sebelah Create Ticket) | Satu layar kerja Security | Form Security makin padat; truk & tamu antre bersamaan |

**Rancangan (T1)**
- Halaman **Tamu** berisi 3 bagian: (1) Scan / daftar tamu masuk, (2) **Tamu di dalam** (jumlah besar di atas, lama
  berkunjung, tombol Keluar), (3) Riwayat + filter tanggal / dituju + ekspor.
- **Keluar dengan scan wajah** (opsional): tamu menghadap kamera saat pulang → otomatis tercatat keluar.
- **Kartu / badge tamu** dicetak saat masuk (nama, foto, dituju, jam masuk, QR) dan diminta kembali saat keluar
  (opsional, ★ untuk area pabrik).
- **Peringatan blacklist** sama seperti poin 7 (banner merah + kotak foto merah), tamu tetap bisa dicatat kecuali
  diputuskan lain.
- Tantangan wajah mengikuti pengaturan area (poin 1; usul kunci sendiri `TANTANGAN_TAMU`, karena tamu sering kesulitan
  mengikuti instruksi).
- Notifikasi (poin 5): tamu masih di dalam melewati jam pulang / > N jam → Security & KTU; opsional notifikasi ke orang
  yang dituju bila punya akun.

**Keputusan**
- 8a. Letak: T1 ★ / T2 / T3?
- 8b. "Bertemu dengan" dipilih dari **personel** (sekarang, ★) atau dari **akun** login (hanya yang punya akun)? Boleh
  ketik bebas bila orangnya tidak terdaftar?
- 8c. Keluar: tombol saja, scan wajah, atau keduanya ★?
- 8d. Cetak kartu tamu: ya / tidak?
- 8e. Foto KTP perlu disimpan, atau cukup NIK + foto wajah ★?
- 8f. Tamu blacklist: peringatan saja ★ (sama dengan truk) atau ditolak masuk?

---

## Keputusan (8 Oktober 2026)

Semua rekomendasi ★ disetujui, dengan perubahan berikut:

| Poin | Keputusan |
|---|---|
| 2a | Blacklist berlaku **semua area & company**. Di daftar dan banner peringatan selalu tampil **siapa yang menetapkan**, area asalnya, tanggal, dan no. surat |
| 8 (tamu) | Menu Tamu sendiri ★, catat masuk / keluar lewat **tombol**. Tetap dikerjakan: **peringatan blacklist tamu** (banner merah + kotak foto merah, tamu tetap bisa dicatat) dan **notifikasi** tamu masih di dalam melewati jam pulang / > N jam → Security & KTU (+ orang yang dituju bila punya akun). **Tidak dikerjakan** di tahap 1: keluar dengan scan wajah, kartu / badge tamu |
| 3b | Tidak ada kategori HO khusus di kode. **Kategori personel dikelola sendiri di Admin** (tambah / ubah: kode, nama, prefix kode, wajib SIM, boleh akun, aktif), jadi HO atau kategori lain bisa ditambah kapan saja tanpa ubah program |
| 5b | **Toleransi bawaan 0**: begitu total netto DO melewati kuota, kelebihan berapa pun dipecah ke tiket baru `-S1` untuk DO lain (dipilih KTU) + notifikasi ke KTU. Toleransi tetap bisa diatur (global di Pengaturan, bisa ditimpa per kontrak; persen atau kg) supaya bisa berubah nanti tanpa ubah program |
| 4a | B: DO boleh menyusul |
| 5c / 5d / 5e | Dipilih KTU / nomor tiket baru `-S1` / peringatan saja |

Tidak ada keputusan yang masih terbuka untuk tahap 1.

## Urutan pengerjaan yang diusulkan

| Tahap | Isi | Bergantung keputusan |
|---|---|---|
| 1a | Poin 7 (peringatan blacklist) + poin 3 (form personel, show / hide SIM, kode per kategori, Admin kategori personel) | 3a–3e |
| 1b | Poin 2 (menu Blacklist + KTU) + poin 8 (menu Tamu) | 2a–2c, 8a–8f |
| 1c | Poin 1 (hapus kiosk, webcam Security, tantangan per area) | 1a–1b, HTTPS / flag Chrome |
| 2 | Poin 4 (alur tiket & list) | 4a–4c |
| 3 | Poin 5 (kuota DO, split, notifikasi) | 5a–5e |
| 4 | Poin 6 (kasus lain) bertahap | per kasus |

Tahap 1 (1a–1c) cukup untuk uji coba Form Security, Blacklist, dan Tamu di site.
