# ERD Sistem Timbangan Sawit (final, ERD v3)

Sumber kebenaran: **`database/schema.sql`** (membuat database baru dari nol; setara schema awal + migrasi 001–017).
Gambar di bawah **dibuat otomatis dari katalog SQL Server** hasil `schema.sql` dengan `tools/gen_erd.py`, jadi selalu sama
dengan database yang sebenarnya: **47 tabel, 361 kolom, 82 foreign key**.

Diuji di SQL Server 2022: `schema.sql` dari nol menghasilkan struktur yang sama dengan database lama yang dijalankan
migrasi 001–016, lalu aplikasi dijalankan ke database itu (alur admin → kontrak & DO → tiket → timbang → sortasi / lab →
timbang keluar, verifikasi rantai log) tanpa error.

Cara membaca: `PK` primary key, `FK` foreign key, `UK` unik, `"NULL"` = boleh kosong. Garis `||` wajib, `|o` boleh kosong;
`o{` banyak, `o|` paling banyak satu. Di diagram per kelompok, tabel dari kelompok lain hanya ditampilkan PK-nya.
Kolom pencatat (`created_by`, `updated_by`, `oleh`, `operator_*`, `security_id`) menunjuk ke `akun` dan hanya digambar
di diagram lengkap supaya diagram per kelompok tetap terbaca.

## Diagram lengkap

[lengkap.svg](erd/lengkap.svg) (zoom di browser) · [lengkap.pdf](erd/lengkap.pdf) · [lengkap.png](erd/lengkap.png)

## 1. Organisasi, akun & hak akses

![Organisasi](erd/01_organisasi_akses.png)

| Tabel | Isi |
|---|---|
| `company` → `comp_area` | Perusahaan dan area / site. Hampir semua data operasional menunjuk area |
| `department` | Bagian (Umum, Security, Timbangan, QC / Lab, Head Office) |
| `level` → `level_akses` ← `menu` | Pengganti role: per level, per menu boleh tambah / ubah / hapus. Semua level melihat semua menu |
| `akun` | Login (dulu `users`): level, department, area, sesi_versi, password_changed_at. `id_personel` opsional (akun dan personel terpisah) |
| `sesi_login` | Sesi dari semua PC (Admin › Sesi Aktif, 1 user 1 perangkat) |
| `pengaturan` / `pengaturan_area` | Pengaturan global; pengaturan operasional bisa ditimpa per area (keamanan selalu global) |
| `perangkat_kiosk` | Pos kamera / kiosk per area |
| `jadwal_kerja` | Jadwal per area (PK area + hari), dipakai absensi |

## 2. Personel, wajah, kunjungan, absensi, blacklist & dokumen

![Personel](erd/02_personel_dokumen.png)

| Tabel | Isi |
|---|---|
| `kategori_personel` → `personel` | DRIVER (wajib SIM), SECURITY, EMPLOYEE, TAMU. View `v_personel` memberi bentuk lama (no_sim, foto, embedding) |
| `jenis_sim` → `personel_sim` | SIM per personel dengan masa berlaku; No SIM aktif unik |
| `personel_wajah` | Embedding & foto wajah (boleh lebih dari satu per orang) |
| `keperluan_kunjungan` → `kunjungan` | Tamu = personel kategori TAMU, scan wajah tiap datang, dicatat siapa yang dituju |
| `absensi` | Scan wajah + liveness, status tepat waktu / terlambat |
| `blacklist` | Personel atau kendaraan, wajib surat (`dokumen`). Trigger membuat blacklist permanen |
| `jenis_dokumen` → `dokumen` → `dokumen_file` | Surat blacklist, berita acara void, COA lab, dll.; file dengan sha256 |

## 3. Mitra, kendaraan, produk, kontrak & DO

![Mitra & kontrak](erd/03_mitra_kontrak.png)

| Tabel | Isi |
|---|---|
| `mitra` + `mitra_peran` | Customer dan / atau pengangkutan (satu mitra boleh dua peran). Nama kolom tetap `id_supplier` |
| `jenis_kendaraan` → `kendaraan` | No plat unik, **No STNK wajib & unik** |
| `kendaraan_driver`, `kontrak_kendaraan` | Supir per truk (supir utama) dan kontrak truk ↔ mitra |
| `produk` → `standar_mutu` | Produk menentukan alur tahap (`id_alur`); standar mutu lab |
| `kontrak` → `delivery_order` → `do_pengangkutan` | **1 kontrak = 1 produk = 1 DO**; 1 DO bisa beberapa pengangkut: kendaraan PENGIRIM / PENERIMA atau PIHAK_KETIGA (mitra pengangkutan), dengan alokasi qty |
| `harga_harian` | Harga CPO / kernel untuk dashboard |

## 4. Proses tiket

![Proses tiket](erd/04_proses_tiket.png)

| Tabel | Isi |
|---|---|
| `tahap`, `alur` → `alur_tahap` | Urutan tahap per alur: TBS (sortasi), PKS (lab), penimbangan saja |
| `mill` | Per area, menunjuk alur; tiket baru memakai mill aktif di area Security sesuai alur produk |
| `jembatan_timbang` | Beberapa jembatan per area; profil indikator per jembatan (mode LOKAL / AGEN, data bit, parity, format, stabil, berat minimum). Lihat [TIMBANGAN.md](TIMBANGAN.md) |
| `transaksi` | Tiket: mitra, produk, kendaraan, supir, mill, DO (`id_do`), `cara_angkut` + `id_pengangkutan`, jembatan masuk |
| `penimbangan` | 2 baris per tiket (ke-1 masuk, ke-2 keluar); trigger: keluar **wajib di jembatan yang sama**. View `v_timbangan` memberi bruto / tara / netto |
| `sortasi`, `lab_hasil` | Inspeksi; COA lab = `dokumen` |
| `pembatalan_tiket` | VOID (Admin, berita acara boleh menyusul) / REJECT (lab) |

## 5. Log aktivitas

![Log](erd/05_log.png)

`log_aktivitas` menggantikan 5 tabel log lama. Kategori ADMIN / SECURITY / PERSONEL / STANDAR_MUTU / TIMELINE, isi lama &
baru berupa JSON. Setiap baris menyimpan hash baris sebelumnya (`hash_sebelum` → `hash_baris`, SHA-256), ditulis hanya
lewat prosedur `sp_catat_log`, dan trigger menolak UPDATE / DELETE. View `v_log_rusak` (Admin › Audit Admin ›
Verifikasi rantai log) menunjukkan baris yang diubah atau dihapus langsung di database.

## Aturan di database

| Objek | Aturan |
|---|---|
| `TR_Penimbangan_JembatanSama` | Timbang keluar harus di jembatan yang sama, dan hanya setelah timbang masuk |
| `TR_Personel_BlacklistPermanen`, `TR_Kendaraan_BlacklistPermanen` | Status blacklist tidak bisa dicabut |
| `TR_Log_HanyaTambah` | `log_aktivitas` tidak bisa diubah / dihapus |
| `CK_DoAngkut_PihakKetiga`, `CK_Trx_CaraAngkut` | `id_pengangkutan` diisi hanya bila cara angkut PIHAK_KETIGA |
| `UX_DO_Kontrak` | Satu kontrak hanya satu DO |
| `UX_Kendaraan_Stnk`, `UX_PersonelSim_NoAktif` | No STNK unik; No SIM aktif unik |
| `CK_Log_JsonLama` / `CK_Log_JsonBaru` | Isi log harus JSON valid |

## Membuat ulang gambar

```
python tools/gen_erd.py                     # baca database dari .env, tulis docs/erd/*.mmd
npx -p @mermaid-js/mermaid-cli mmdc -i docs/erd/04_proses_tiket.mmd -o docs/erd/04_proses_tiket.png -s 2
```

Rencana & keputusan desain (riwayat): [ERD_V3.md](ERD_V3.md).
