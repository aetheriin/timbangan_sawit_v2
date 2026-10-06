# Menyambungkan jembatan timbang

Satu PC server menjalankan aplikasi (`serve.py`). PC lain cukup membuka browser ke `http://IP-SERVER:5000`.
Berat dibaca **terus-menerus** sejak server menyala, walau belum ada tiket; berat baru tersimpan saat operator
memilih tiket lalu klik simpan.

## Pilih cara sambung (per jembatan, di Admin › Perangkat / Kiosk › Jembatan Timbang)

| Kabel indikator dicolok ke | Isi "Kabel indikator dicolok ke" | Port | Yang dijalankan |
|---|---|---|---|
| **PC jembatan** (1 PC per jembatan) | PC jembatan (dibaca agen_timbang.py) | COM di PC jembatan, mis. `COM3` | `agen\jalankan.bat` di PC jembatan |
| PC server | PC server ini / alat serial-to-LAN | COM di PC server | Tidak ada |
| Alat serial-to-LAN (USR-TCP232, Moxa, dll.) | PC server ini / alat serial-to-LAN | `socket://192.168.1.50:4001` | Tidak ada |

Kabel RS-232 hanya kuat ±15 m, jadi indikator di pos jembatan hampir selalu dicolok ke PC jembatan: pakai **agen**.

## Langkah di lokasi (contoh PT A, 4 jembatan, server di laptop)

1. **Server**: jalankan `serve.py` (atau `tools\jalankan.bat`). Catat IP laptop (`ipconfig`, mis. `192.168.1.10`)
   dan izinkan port 5000 di firewall (lihat docs/PINDAH_LAPTOP.md).
2. **Admin › Perangkat / Kiosk**
   - Tambah **Pos** untuk tiap PC jembatan (mis. `POS-JT1` ... `POS-JT4`), catat tokennya.
   - Tambah **Jembatan Timbang** JT-1 ... JT-4: kabel dicolok ke *PC jembatan*, port COM di PC itu, profil indikator
     (lihat di bawah). Catat **ID agen** yang muncul di tabel.
3. **Tiap PC jembatan**
   - Salin folder `agen\` ke PC itu.
   - Ada Python: klik `pasang.bat` sekali. Tidak ada Python: pakai `agen_timbang.exe` (dibuat sekali dengan
     `buat_exe.bat` di laptop, lalu salin exe-nya ke folder `agen\` di PC jembatan).
   - Salin `.env.contoh` menjadi `.env`, isi `WEIGHBRIDGE_URL=http://192.168.1.10:5000`, `JEMBATAN_ID` (ID agen),
     `KIOSK_ID` dan `KIOSK_TOKEN` (pos PC ini).
   - Jalankan `jalankan.bat`, biarkan jendelanya terbuka. Muncul `terhubung, mengirim ke ...` = berjalan.
   - Buka browser ke server, login operator timbang, di tab Timbangan pilih jembatan PC ini (sekali saja per PC).
4. **Cek** di Admin › Perangkat / Kiosk › tombol **Data mentah** jembatan itu.

## Menyetel indikator merk berbeda

Tiap jembatan punya profil sendiri, jadi PT A dan PT B boleh berbeda merk.

| Isian | Keterangan |
|---|---|
| Baudrate, Data bits, Parity, Stop bits | Lihat manual / menu setting indikator. Umum: **9600 7E1** atau **9600 8N1** |
| Format | `ST_GS` (`ST,GS,+00024150kg`), `ANGKA` (angka pertama di baris, mis. `WN0024150kg`), `TERBALIK` (XK3190 / A9: `=0.05142` = 24150), `POLA` (regex sendiri) |
| Faktor ke kg | `1` bila indikator mengirim kg; `1000` bila mengirim ton |
| Toleransi / lama stabil | Berat dianggap stabil bila tidak berubah lebih dari toleransi (bawaan 5 kg) selama lama stabil (bawaan 3 detik) |
| Berat minimum | Berat di bawah ini ditolak (timbangan kosong / truk belum naik penuh). Bawaan 100 kg |
| Wajib tanda ST | Centang bila indikator mengirim tanda stabil sendiri dan ingin ikut diperhitungkan |

Cara cepat di lokasi:

1. Tidak tahu baudrate / parity? Di PC jembatan jalankan `deteksi.bat COM3`. Agen mencoba kombinasi umum dan
   menampilkan yang datanya terbaca jelas.
2. Isi profil di Admin, simpan (langsung berlaku, agen menyambung ulang sendiri), lalu buka **Data mentah**:
   - teks acak / kotak-kotak → baudrate / parity / data bits salah;
   - teks jelas tetapi "Terbaca" kosong → format salah (coba `ANGKA`, atau `POLA`);
   - angka terbaca tetapi 1000× terlalu kecil / besar → ubah Faktor.
3. Naikkan truk / beban uji, bandingkan berat di layar indikator dengan kolom "Terbaca".

## Status di tab Timbangan / Admin

| Tampil | Artinya |
|---|---|
| Tidak terhubung: *Agen di PC jembatan tidak mengirim data* | Jendela agen tertutup, PC jembatan mati, atau jaringan putus |
| Tidak terhubung: *Agen: port COM3 gagal dibuka* | COM salah atau dipakai program lain (tutup program timbangan lama) |
| Berat ... di bawah minimum | Timbangan kosong / truk belum naik penuh |
| Berat belum stabil | Truk masih bergerak; tunggu angka diam |
