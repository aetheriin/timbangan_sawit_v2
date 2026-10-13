# Simulasi Alur Truk (mode demo)

Halaman simulasi proses truk di pabrik kelapa sawit, dari gerbang masuk sampai keluar. Berdiri sendiri: **tidak
terhubung** ke aplikasi Flask, database, atau timbangan. Tidak ada file sistem yang diubah atau dipakai.

## Cara membuka

Klik dua kali `simulasi/index.html` (Chrome / Edge). Tidak perlu server, Python, atau internet
(tanpa internet hanya hurufnya yang memakai huruf bawaan Windows).

## Site

Pilihan **Site** di kanan atas berisi 4 site contoh (nama masih dummy, ganti di Edit Denah → Nama site):

| Site | Jembatan | Bay sortasi | Kernel | Pos security | Bentuk |
|---|---|---|---|---|---|
| A · PKS Sungai Lestari | 4 | 3 | ada | 2 (Pos 1 scan wajah + Pos 2 pendaftaran) | gerbang di kiri |
| B · PKS Bukit Harapan | 2 | 2 | ada | 1 | dicerminkan (gerbang di kanan) |
| C · PKS Tanjung Makmur | 3 | 3 | tidak | 2 | gerbang di kiri |
| D · PKS Rantau Jaya | 2 | 2 | tidak | 1 | dicerminkan |

## Validasi wajah & Pos 2

Di Pos 1 (Pos Security) truk berhenti: cek plat & blacklist → **scan wajah supir**.

- **Wajah terdaftar** (jarak ≤ ambang 0,55, sama dengan default `AMBANG_WAJAH`): tiket langsung dicetak, palang terbuka,
  truk lanjut ke timbangan.
- **Wajah tidak terdaftar**:
  - Site **dengan Pos 2**: palang Pos 1 (syarat *Sudah scan wajah di Pos 1*) terbuka, supir diarahkan ke **Pos 2** di
    kantong samping untuk foto wajah & SIM, didaftarkan sebagai personel baru `PRGBS-###`, tiket dicetak di Pos 2,
    lalu lanjut ke timbangan. Antrean di Pos 1 tidak tertahan.
  - Site **tanpa Pos 2**: pendaftaran dilakukan di Pos 1, truk di belakangnya ikut menunggu.

Pos 2 adalah objek *Pos 2 · pendaftaran wajah* di Edit Denah; pasang atau hapus sesuai site.

## Pengaturan, skenario ramai & statistik antrean

Kartu **Pengaturan & skenario** (tersimpan per site):

- **Kedatangan truk**: Sepi 8/jam, Normal 15/jam, Ramai 25/jam, Panen raya 40/jam, atau angka sendiri.
  Kedatangan acak (Poisson) sehingga kadang beberapa truk datang berdekatan.
- **Supir sudah terdaftar wajahnya (%)**: makin kecil, makin banyak yang ke Pos 2.
- **Durasi pelayanan** (menit jam pabrik): Pos 1, Pos 2, bongkar & sortasi, muat CPO, muat kernel, uji lab.
- Tombol **+ Rombongan 10 truk**: 10 truk datang hampir bersamaan.

Kartu **Statistik antrean** menampilkan rata-rata menit **menunggu** dan **dilayani** per tahap
(Pos 1, Pos 2, timbang masuk, sortasi, muat, lab, timbang keluar), menandai **titik macet** (tunggu terlama),
jumlah & lama antre di jalan raya, rata-rata waktu di pabrik, dan tiket selesai per jam.
Di denah muncul tanda **antre N** di tempat yang sedang mengantre dan jumlah truk yang antre di jalan raya.

Tiap site punya denah sendiri, tersimpan otomatis di browser komputer itu.

## Edit Denah

Tombol **Edit Denah** menghentikan simulasi dan membuka editor:

- **Pilih & geser**: klik objek / jalan / titik jalan, seret untuk memindah. `Del` hapus, `R` putar 15° (Shift+R balik).
- **Jalan satu arah / dua arah**: klik titik demi titik searah lalu lintas. Klik titik atau jalan yang sudah ada untuk
  menyambung (jalan otomatis terbelah). `Esc`, klik kanan, atau klik dua kali untuk berhenti. Klik sebuah jalan untuk
  mengganti satu/dua arah atau membalik arahnya. Di jalan dua arah truk memakai lajur kiri.
- **Objek alur** (dipakai truk) harus menempel ke jalan, maksimal 90 px dari jalan:

| Objek | Letak | Fungsi |
|---|---|---|
| Titik masuk / keluar truk | di atas jalan | truk muncul / menghilang |
| Pos Security (Pos 1) | samping jalan | cek plat, blacklist, scan wajah, cetak tiket |
| Pos 2 · pendaftaran wajah | samping jalan | opsional; daftar supir yang wajahnya belum dikenal |
| **Barrier gate** | di atas jalan | palang terbuka hanya bila syarat terpenuhi: sudah scan wajah di Pos 1 / sudah punya tiket / sudah timbang masuk / tiket selesai / semua truk |
| Jembatan timbang | di atas jalan | arah plat otomatis mengikuti jalan |
| **Lampu lalu lintas** | di atas jalan, sebelum jembatan | merah bila jembatan terisi atau sudah dipesan truk lain; truk menunggu di garis berhenti |
| Bay sortasi TBS, Bunker kernel, Laboratorium | samping jalan | truk berhenti di titik jalan terdekat |
| Titik muat CPO | di atas jalan | gantry pengisian |

- **Hiasan**: gedung, gedung pabrik, boiler (berasap), tangki, kolam, lantai beton, pohon sawit, teks.
- **Kesiapan alur** memeriksa apakah tiap alur (TBS, CPO, Kernel, Timbang saja) bisa dijalankan: objek lengkap dan ada
  jalan dari masuk → security → jembatan → sortasi / muat → lab → kembali ke jembatan yang sama → keluar.
- **Foto latar (opsional)**: foto udara / tangkapan Google Maps sebagai alas untuk menaruh objek. Bisa diatur kejelasannya.
- **Unduh / Buka denah (.json)**: untuk menyimpan cadangan atau memindah denah ke komputer lain.
  **Kembalikan bawaan** memulihkan denah contoh site itu.

## Alur yang disimulasikan

| Jenis | Transaksi | Tahap |
|---|---|---|
| TBS | PEMBELIAN | Security → Timbang masuk (bruto) → Bongkar & sortasi → Timbang keluar (tara) |
| CPO / Kernel | PENJUALAN | Security → Timbang masuk (tara) → Muat → Lab → Timbang keluar (bruto) |
| Timbang saja | PENIMBANGAN_SAJA | Security → Timbang sekali |

Aturan sistem yang ikut disimulasikan: status `status_alur` (SECURITY_REGISTER → TIMBANG_1 → TIMBANG_2 → SELESAI /
REJECTED), berat disimpan hanya saat **Stabil**, timbang keluar **wajib di jembatan yang sama**, potongan sortasi
= (mentah + tangkai + sampah) % × netto, peringatan blacklist (tiket tetap dibuat, tercatat TRY_SCAN_BLACKLIST),
lab REJECT menutup tiket tanpa timbang keluar, no. tiket `TKT-{PLAT}-{yyyyMMddHHmmss}`.

## Format file denah (.json)

```json
{
  "versi": 1, "site": "A", "nama": "Site A · PKS Sungai Lestari",
  "latar": null, "latarOpacity": 0.6,
  "pengaturan": { "perJam": 15, "persenTerdaftar": 75, "durasi": { "scan": 1.5, "daftar": 5, "bongkar": 8, "muat_cpo": 12, "muat_kernel": 8, "lab": 6 } },
  "objek": [ { "id": "o1", "tipe": "barrier", "x": 150, "y": 645, "w": 16, "h": 16, "rot": 0,
               "label": "Barrier Security", "syarat": "tiket" } ],
  "jalan": { "titik": [ { "id": "n1", "x": 10, "y": 738 } ],
             "ruas":  [ { "id": "r1", "a": "n1", "b": "n2", "dua": false } ] }
}
```

Koordinat denah 1280 × 760. `ruas.dua = false` berarti satu arah dari `a` ke `b`.
Tipe objek: `masuk, keluar, security, pos_daftar, barrier, jembatan, lampu, sortasi, muat_cpo, muat_kernel, lab,
gedung, pabrik, boiler, tangki, kolam, lantai, pohon, teks`.

Semua angka (plat, supir, mitra, berat, hasil sortasi & lab) dibuat acak untuk demo.
