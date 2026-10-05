# Hak Akses per Level

Sejak migrasi `008_organisasi_hak_akses.sql` (+ menu Kunjungan di `009`), hak akses **tidak lagi ditulis di kode**. Diatur Admin di
**Admin › Level & Hak Akses** dan disimpan di tabel:

| Tabel | Isi |
|---|---|
| `level` | Pengganti role: kode, nama, `is_admin`, halaman awal setelah login |
| `menu` | Menu sidebar (punya `url`) dan bagian halaman (tab, `url` kosong) |
| `level_akses` | Per level × menu: boleh **tambah / ubah / hapus** |

Aturan:
- Semua level non-admin **melihat semua menu**. Yang dibatasi hanya aksi (tombol dan API).
- Level `is_admin` hanya membuka area Admin dan tidak punya aksi operasional.
- Kode memeriksa dengan `@izin('KODE_MENU', 'aksi')` (API) dan `boleh('KODE_MENU', 'aksi')` (tombol di template),
  di `utils/hak_akses.py`. Perubahan di layar Admin berlaku ±30 detik di semua PC tanpa login ulang.
- Mengganti level seorang user mengakhiri sesinya (login ulang).

## Isi awal (sama dengan hak akses sebelum Fase 1)

| Menu (kode) | HO | SECURITY | OPERATOR_TIMBANG | SORTASI | LAB |
|---|---|---|---|---|---|
| Dashboard (`DASHBOARD`): harga harian | ubah | – | – | – | – |
| Form › Security (`FORM_SECURITY`): buat tiket, supir, supir & kontrak truk, scan wajah | – | tambah, ubah | – | – | – |
| Form › Timbangan (`FORM_TIMBANGAN`) | – | – | tambah | – | – |
| Form › Sortasi (`FORM_SORTASI`) | – | – | – | tambah | – |
| Form › Laboratorium (`FORM_LAB`): hasil lab (tambah), standar mutu (ubah) | – | – | – | – | tambah, ubah |
| Face Recognition › Personel (`PERSONEL`): semua kategori | tambah, ubah, hapus | – | – | – | – |
| Face Recognition › Blacklist (`BLACKLIST`) | tambah | – | – | – | – |
| Face Recognition › Kunjungan Tamu (`KUNJUNGAN`, migrasi 009): scan wajah, daftar tamu, catat masuk / keluar | – | tambah, ubah | – | – | – |
| Kontrak & DO (`KONTRAK_DO`) | tambah, ubah, hapus | – | – | – | – |
| Data Master › Driver (`MASTER_DRIVER`): hanya kategori Driver | tambah, ubah, hapus | tambah, ubah, hapus | – | – | – |
| Data Master › Kendaraan (`MASTER_KENDARAAN`) | tambah, ubah | tambah, ubah | – | – | – |
| List, Absensi, Audit Log | lihat | lihat | lihat | lihat | lihat |

ADMIN: semua menu Admin (Kelola User, Level & Hak Akses, Organisasi, Sesi Aktif, Supplier & Produk, Void Tiket,
Jadwal Kerja, Pengaturan Site, Perangkat / Kiosk, Log Keamanan, Audit Admin, Kesehatan Sistem).

## Cukup login (semua level non-admin)

Melihat semua list & history, cari plat / NIK, scan QR tiket, cetak tiket / QR, berat live, nol-kan timbangan,
scan absensi, rekap & jadwal kerja, daftar personel & blacklist, Audit Log + ekspor, membuka foto / surat (`/berkas`).
