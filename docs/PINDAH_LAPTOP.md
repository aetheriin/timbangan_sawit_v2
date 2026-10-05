# Pindah ke laptop / komputer baru

Tujuan: aplikasi + database + foto pindah utuh, **tanpa mengompilasi dlib** (tidak perlu CMake / Visual Studio).
Semua langkah di bawah sudah diuji: instal library dari `requirements.txt` (online & offline), wajah dikenali dengan
`dlib-bin`, backup → restore database, lalu aplikasi berjalan ke database hasil restore.

## Yang dibawa dari PC lama

| Barang | Kenapa | Ada di git? |
|---|---|---|
| Kode aplikasi | Program | Ya (`git clone` / `git pull`) |
| File `.bak` database | Semua data (akun, personel, tiket, log) | Tidak (langkah 1) |
| File `.env` | **SECRET_KEY & HASH_SECRET_KEY harus sama**; kalau berbeda, hash timbangan lama dianggap rusak dan semua sesi login putus | Tidak |
| Folder `data\uploads\` | Foto wajah, foto absensi, surat blacklist, berita acara, dokumen | Tidak |
| Folder `paket_offline\` (opsional) | Pasang library tanpa internet (±280 MB) | Tidak |

## Langkah 1: di PC lama

1. Tutup jendela `serve.py` (aplikasi berhenti).
2. Buka `database\pindah\1_backup_di_pc_lama.sql` di SSMS / VS Code, sesuaikan `@db` (= `DB_NAME` di `.env`), Execute.
   Hasilnya menampilkan lokasi file `.bak` dan **versi SQL Server PC lama**; catat versinya.
3. Salin ke flashdisk: file `.bak`, file `.env`, folder `data\uploads\`.
4. (Opsional, bila laptop tidak ada internet) jalankan `tools\unduh_paket_offline.bat`, lalu salin juga folder
   `paket_offline\`.

## Langkah 2: pasang program di laptop (sekali saja)

| Program | Unduh | Catatan |
|---|---|---|
| **Python 3.11 64-bit** | python.org → Downloads → Windows → *Python 3.11.9 Windows installer (64-bit)* | Centang **Add python.exe to PATH**. Jangan 3.12 / 3.13: `mediapipe 0.10.9` hanya ada sampai 3.11 |
| **SQL Server 2022 Express** | microsoft.com → *SQL Server Downloads* → Express → **Basic** | Gratis. Selesai instal, catat *Instance name* (biasanya `SQLEXPRESS`). Versi harus sama / lebih baru dari PC lama |
| **ODBC Driver 18 for SQL Server** | learn.microsoft.com → *Download ODBC Driver for SQL Server* → x64 | Dipakai Python (`pyodbc`) untuk konek ke database |
| **SSMS** atau VS Code + ekstensi *SQL Server (mssql)* | microsoft.com → *Download SSMS* | Untuk menjalankan file `.sql` |
| **Visual C++ Redistributable 2015–2022 x64** | learn.microsoft.com → *Latest supported Visual C++ Redistributable* (`vc_redist.x64.exe`) | Dibutuhkan opencv / dlib / mediapipe; biasanya sudah ada |
| Git (opsional) | git-scm.com | Untuk `git clone` / `git pull` |

Server SQL di laptop: `localhost\SQLEXPRESS` (atau `.\SQLEXPRESS`). Login memakai akun Windows (pilihan Basic
otomatis menjadikan akun Windows Anda admin SQL Server).

## Langkah 3: pindahkan database

1. Salin file `.bak` ke folder Backup bawaan SQL Server laptop, mis.
   `C:\Program Files\Microsoft SQL Server\MSSQL16.SQLEXPRESS\MSSQL\Backup\` (folder lain sering ditolak karena izin).
2. Buka `database\pindah\2_restore_di_laptop.sql`, isi `@file` (lokasi `.bak`) dan `@db` (nama database), Execute.
   File data & log otomatis ditaruh di folder data SQL Server laptop.

Mau database **kosong** (instal baru, tanpa data lama)? Jalankan `database\schema.sql` saja (login awal `admin` /
`admin12345`, wajib ganti password).

## Langkah 4: siapkan aplikasi

1. Ambil kode: `git clone <url repo>` (atau salin folder proyek **tanpa** folder `venv`; venv dibuat ulang).
2. Taruh `.env` di folder proyek, lalu ubah baris server:
   ```
   DB_SERVER=localhost\SQLEXPRESS
   DB_NAME=DbSistemTimbangan_Test
   DB_USER=
   DB_PASSWORD=
   ```
   `DB_USER` kosong = login Windows. **Jangan ganti SECRET_KEY / HASH_SECRET_KEY.**
3. Salin folder `uploads` ke `data\uploads\` di folder proyek.
4. (Bila membawa paket offline) taruh folder `paket_offline\` di folder proyek.
5. Klik dua kali **`tools\pasang_windows.bat`**. Skrip membuat `venv`, memasang semua library (dlib dari paket jadi
   `dlib-bin`), lalu menjalankan `tools\cek_lingkungan.py`. Semua baris harus **[OK]**.
6. Jalankan **`tools\jalankan.bat`** (atau `venv\Scripts\python serve.py`), buka `http://localhost:5000`.

## Langkah 5: perangkat & PC lain

- **Timbangan**: nomor port COM di laptop bisa berbeda. Lihat Device Manager › Ports, lalu ubah di
  Admin › Perangkat / Kiosk › Jembatan Timbang. `cek_lingkungan.py` juga menampilkan port yang terlihat.
- **PC lain / kiosk** yang membuka aplikasi: ganti alamatnya ke IP laptop (`ipconfig`), mis. `http://192.168.1.20:5000`;
  untuk `kiosk_timbang.py` ubah `WEIGHBRIDGE_URL` di `.env` kiosk. Token kiosk tetap (tersimpan di database).
- Izinkan port 5000 di firewall laptop (Command Prompt sebagai Administrator):
  `netsh advfirewall firewall add rule name="Weighbridge 5000" dir=in action=allow protocol=TCP localport=5000`

## Kalau ada masalah

| Pesan | Penyebab / solusi |
|---|---|
| `Data source name not found` / `Can't open lib 'ODBC Driver 18'` | ODBC Driver 18 belum dipasang, atau isi `DB_DRIVER={ODBC Driver 17 for SQL Server}` di `.env` bila yang ada versi 17 |
| `Login failed` / `Cannot open database` | `DB_SERVER` / `DB_NAME` salah, atau restore belum dilakukan. Cek di SSMS dengan server yang sama |
| `The database was backed up on a server running version ...` | SQL Server laptop lebih lama dari PC lama: pasang versi yang sama / lebih baru |
| `Operating system error 5 (Access is denied)` saat restore | Taruh `.bak` di folder Backup bawaan SQL Server |
| `No matching distribution found for mediapipe==0.10.9` | Python bukan 3.11 64-bit |
| `DLL load failed` saat import cv2 / dlib | Pasang Visual C++ Redistributable x64 |
| Foto wajah / surat tidak muncul | Folder `data\uploads\` belum disalin |
| `SECRET_KEY, HASH_SECRET_KEY di .env kosong` | `.env` belum disalin dari PC lama |
| Log "Rantai rusak" setelah pindah | Tidak terjadi dengan backup / restore; berarti ada perubahan data log di luar aplikasi |

Database sudah berjalan lalu ada versi aplikasi baru: jalankan migrasi baru di `database\migrations\` (yang belum
pernah dijalankan saja), lalu `tools\cek_lingkungan.py`.
