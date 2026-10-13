# Simulasi Alur Truk (mode demo)

Halaman simulasi proses truk di pabrik kelapa sawit, dari gerbang masuk sampai keluar. Berdiri sendiri: **tidak
terhubung** ke aplikasi Flask, database, atau timbangan. Tidak ada file sistem yang diubah atau dipakai.

## Cara membuka

Klik dua kali `simulasi/index.html` (Chrome / Edge). Tidak perlu server, Python, atau internet
(tanpa internet hanya hurufnya yang memakai huruf bawaan Windows).

## Site

Pilihan **Site** di kanan atas berisi 4 site contoh (nama masih dummy, ganti di Edit Denah → Nama site):

| Site | Jembatan | Bay sortasi | Kernel | Bentuk |
|---|---|---|---|---|
| A · PKS Sungai Lestari | 4 | 3 | ada | gerbang di kiri |
| B · PKS Bukit Harapan | 2 | 2 | ada | dicerminkan (gerbang di kanan) |
| C · PKS Tanjung Makmur | 3 | 3 | tidak | gerbang di kiri |
| D · PKS Rantau Jaya | 2 | 2 | tidak | dicerminkan |

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
| Pos Security | samping jalan | cek plat, blacklist, scan wajah, cetak tiket |
| **Barrier gate** | di atas jalan | palang terbuka hanya bila syarat terpenuhi: sudah punya tiket / sudah timbang masuk / tiket selesai / semua truk |
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
  "objek": [ { "id": "o1", "tipe": "barrier", "x": 150, "y": 645, "w": 16, "h": 16, "rot": 0,
               "label": "Barrier Security", "syarat": "tiket" } ],
  "jalan": { "titik": [ { "id": "n1", "x": 10, "y": 738 } ],
             "ruas":  [ { "id": "r1", "a": "n1", "b": "n2", "dua": false } ] }
}
```

Koordinat denah 1280 × 760. `ruas.dua = false` berarti satu arah dari `a` ke `b`.
Tipe objek: `masuk, keluar, security, barrier, jembatan, lampu, sortasi, muat_cpo, muat_kernel, lab,
gedung, pabrik, boiler, tangki, kolam, lantai, pohon, teks`.

Semua angka (plat, supir, mitra, berat, hasil sortasi & lab) dibuat acak untuk demo.
