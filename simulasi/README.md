# Simulasi Alur Truk (mode demo)

Halaman simulasi proses truk di pabrik kelapa sawit, dari gerbang masuk sampai keluar. Berdiri sendiri: **tidak
terhubung** ke aplikasi Flask, database, atau timbangan. Tidak ada file sistem yang diubah atau dipakai.

## Cara membuka

Klik dua kali `simulasi/index.html` (Chrome / Edge). Tidak perlu server, Python, atau internet
(tanpa internet hanya hurufnya yang memakai huruf bawaan Windows).

## Yang ditampilkan

- Denah pabrik dari atas: gerbang & pos security, 4 jembatan timbang (JT-1 s.d. JT-4) + kantor timbangan,
  loading ramp & sortasi TBS, pabrik (rebusan, press, boiler), tangki CPO, bunker kernel, laboratorium, kolam limbah.
- Truk bergerak di jalur satu arah dan antre sendiri bila tempat di depan masih terisi.
- Alur sesuai sistem (`alur` / `alur_tahap`):

| Jenis | Transaksi | Tahap |
|---|---|---|
| TBS | PEMBELIAN | Security → Timbang masuk (bruto) → Bongkar & sortasi → Timbang keluar (tara) |
| CPO / Kernel | PENJUALAN | Security → Timbang masuk (tara) → Muat → Lab → Timbang keluar (bruto) |
| Timbang saja | PENIMBANGAN_SAJA | Security → Timbang sekali |

- Aturan sistem yang ikut disimulasikan: status `status_alur` (SECURITY_REGISTER → TIMBANG_1 → TIMBANG_2 → SELESAI /
  REJECTED), berat disimpan hanya saat **Stabil**, timbang keluar **wajib di jembatan yang sama**, potongan sortasi
  = (mentah + tangkai + sampah) % × netto, peringatan blacklist (tiket tetap dibuat, tercatat TRY_SCAN_BLACKLIST),
  lab REJECT menutup tiket tanpa timbang keluar, no. tiket `TKT-{PLAT}-{yyyyMMddHHmmss}`.

## Kontrol

Jeda / Jalankan, kecepatan 1×–8×, tambah truk per jenis, truk datang otomatis, skenario blacklist & lab reject,
Ulang. Klik truk (atau baris tabel) untuk melihat perjalanan tiketnya.

Semua angka (plat, supir, mitra, berat, hasil sortasi & lab) dibuat acak untuk demo.
