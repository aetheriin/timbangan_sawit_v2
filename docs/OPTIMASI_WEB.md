# Optimasi Web: kecepatan, tanpa buffering / freeze, dan cache

Status: **semua poin sudah dikerjakan** di cabang `claude/zen-hamilton-du3ult` (disetujui setelah rapat).
Tahap berikutnya: keamanan web.

Prioritas: **P1** = paling berpengaruh ke buffering / freeze, **P2** = penting, **P3** = perapian.

## Ringkasan

| # | Prio | Poin | Status | Di mana |
|---|---|---|---|---|
| 1 | P1 | Server produksi waitress (bukan server debug Flask) | Selesai | `serve.py`, `app.py` (`FLASK_DEBUG`) |
| 2 | P1 | Proses wajah tidak menahan request lain | Selesai | `utils/face_cache.py` (`slot_proses_wajah`), frame diperkecil di browser |
| 3 | P1 | Embedding wajah di-cache di memori | Selesai | `utils/face_cache.py` |
| 4 | P2 | Serial timbangan & kiosk terpisah | Selesai (sesuai kondisi) | lihat catatan |
| 5 | P1 | Polling timbangan tidak menumpuk | Selesai | `static/js/api.js` (`Poller`), `site/timbangan.js` |
| 6 | P2 | Polling scan wajah dibatasi waktu | Selesai | `site/security.js` (90 detik) |
| 7 | P2 | Timeout fetch, indikator proses, tanpa klik ganda | Selesai | `api.js` (`Api`), `ui.js` (`setBusy`, `denganTombol`) |
| 8 | P1 | Index SQL Server | Selesai | `database/migrations/003_index_optimasi.sql` |
| 9 | P2 | Batas jumlah baris | Selesai | personel / blacklist 200, audit 300, history supplier 200 |
| 10 | P2 | Query ambil kolom yang dipakai saja (`SELECT *` dihapus) | Selesai | `utils/db_utils.py` |
| 11 | P3 | Connection pooling ODBC | Selesai | `utils/db_utils.py` (`pyodbc.pooling = True`) |
| 12 | P1 | Cache file statis 1 tahun + versi `?v=` | Selesai | `utils/web_setup.py` |
| 13 | P1 | `Cache-Control: no-store` untuk halaman & API | Selesai | `utils/web_setup.py` |
| 14 | P2 | Cache server data jarang berubah | Selesai | `utils/cache.py` (supplier, produk, jadwal, standar mutu, TTL 5 menit) |
| 15 | P2 | Kompresi gzip | Selesai | `flask-compress` via `utils/web_setup.py` |
| 16 | P1 | Font Awesome & Inter lokal (tanpa internet) | Selesai | `static/vendor/fontawesome`, `static/vendor/fonts` |
| 17 | P2 | Tailwind `--minify`, script `defer` | Selesai | `package.json`, `base.html` |
| 18 | P2 | Foto dikompres di browser sebelum upload | Selesai | `face_recognition/kamera.js` (`kecilkanFoto`) |
| 19 | P3 | Pembersihan `uploads/tmp` & foto absensi lama | Selesai | `utils/maintenance.py` (tiap jam; absensi > 90 hari) |
| 20 | P2 | Log request lambat + `/health` | Selesai | `utils/web_setup.py`, `routes/sistem.py` |
| 21 | P3 | Uji beban sederhana | Selesai (alat) | `tools/uji_beban.py` |
| + | – | Notifikasi profesional (pengganti `alert` / `confirm`) | Selesai | `static/js/ui.js`, `partials/layout/notifikasi.html` |
| + | – | Error rapi (JSON untuk API, halaman error untuk browser) | Selesai | `utils/web_setup.py`, `templates/error.html` |
| + | – | Memori JS dihemat | Selesai | lihat bagian "Memori di browser" |

## Rincian

### A. Server & proses berat

1. **waitress**: `python serve.py` untuk dipakai di site (8 thread, tanpa debug). `python app.py` tetap untuk
   development (`FLASK_DEBUG=1` default). Pengaturan: `HOST`, `PORT`, `THREADS` di `.env`.
2. **Slot proses wajah**: maksimal `MAKS_PROSES_WAJAH` (default 2) proses dlib sekaligus. Request lain menunggu
   giliran maks 30 detik; bila tetap penuh dijawab 503 "Server sedang memproses wajah lain", bukan membuat server macet.
   Frame absensi diperkecil ke lebar 480 px dan dikurangi 12 → 10 frame; foto personel ke sisi maks 1024 px.
3. **Cache embedding**: semua embedding personel aktif dimuat sekali ke memori (numpy), dicocokkan sekaligus
   (vektor), dan dimuat ulang otomatis setiap personel ditambah / diubah fotonya / dihapus.
4. **Serial & kiosk**: kiosk kamera (`kiosk_timbang.py`) memang proses terpisah. Pembaca serial timbangan tetap
   thread ringan di dalam web (hanya membaca port & menyimpan angka terakhir); dipisah jadi service sendiri
   hanya bila nanti ada banyak PC timbangan. **Diperbaiki**: kiosk sebelumnya mengirim ke URL yang salah
   (`/timbang/verifikasi-wajah`, 404) sehingga scan wajah tidak pernah berhasil; sekarang `/api/verifikasi-wajah`
   dan alamat server bisa diatur lewat `WEIGHBRIDGE_URL`.

### B. Polling

5. **Berat live**: `Poller` baru meminta lagi setelah jawaban sebelumnya datang (timeout 3 detik), hanya saat tab
   Timbangan dibuka dan tab browser terlihat. Bila koneksi putus, angka jadi `— Kg` redup, bukan freeze.
6. **Scan wajah**: polling 1 detik, berhenti otomatis setelah 90 detik (kamera kiosk dibatalkan) atau saat form ditinggal.
7. **Semua request** lewat `Api` / `ambilJson` / `kirimForm`: timeout 15 detik (60 detik untuk proses wajah),
   pesan error berbahasa Indonesia, deteksi sesi habis. Tombol simpan menampilkan "Memproses..." dan nonaktif
   selama request berjalan.

### C. Database

8. Jalankan `003_index_optimasi.sql` setelah 001 & 002 (aman dijalankan ulang).
9. Daftar dibatasi; tabel menampilkan catatan "Menampilkan N data terbaru" bila batas tercapai. Export Audit Log
   tetap sampai 10.000 baris.
10–11. Query memilih kolom yang dipakai; pooling ODBC aktif dan koneksi diberi timeout 10 detik.

### D. Cache

| Jenis | Kebijakan |
|---|---|
| CSS / JS / font / gambar statis | `max-age` 1 tahun + `?v=<waktu ubah file>` → setelah update, browser otomatis mengambil versi baru |
| Foto upload (`static/uploads`) | Ikut cache statis; nama file unik (UUID) sehingga tidak pernah basi |
| Halaman & API | `Cache-Control: no-store` → data tiket / personel tidak tersimpan di browser |
| Data master di server | Supplier, produk, jadwal kerja, standar mutu: cache 5 menit; standar mutu dihapus dari cache saat diubah |
| Embedding wajah | Memori server, dimuat ulang saat personel berubah |

### E. Aset frontend

16. Tidak ada lagi CDN: Font Awesome 6.4.0 dan Inter (400–700) disimpan di `static/vendor`. Halaman login juga
    tidak lagi memakai Tailwind CDN (sebelumnya meng-compile CSS di browser setiap buka halaman).
17. `npm run build-css` sekarang menghasilkan CSS minify. Semua script `defer`.

### F. Pemantauan

20. Request > 1 detik (`LOG_REQUEST_LAMBAT_MS`) dicatat di log dengan awalan `LAMBAT`. Setiap respons membawa header
    `Server-Timing`. `GET /health` → status database, koneksi serial timbangan, cache wajah, uptime (503 bila DB putus).
21. `python tools/uji_beban.py --user ho --password ... --pc 10 --detik 30` → p50 / p95 / maks per endpoint.

## Notifikasi & dialog (pengganti alert / confirm)

- **Toast** (`Notif.sukses / gagal / peringatan / info`) di kanan atas, hilang sendiri (4 detik, error 7 detik), maks 4 sekaligus.
- **Dialog konfirmasi** (`await Dialog.konfirmasi({...})`) untuk tindakan penting: lepas supir, akhiri kontrak,
  ubah identitas, tetapkan blacklist, cetak QR setelah tiket dibuat. Esc = batal.
- Server tidak lagi mengembalikan halaman error bawaan / JSON mentah ke layar: API → `{ "error": "..." }` yang
  ditampilkan sebagai toast; halaman → `templates/error.html`. Sesi habis saat memanggil API → toast "Sesi Anda berakhir".

## Memori di browser

Aplikasi **tidak** menyimpan cache data di JavaScript (tidak ada localStorage / cache respons); data selalu diambil
dari server. Yang dijaga supaya memori tidak menumpuk:

- Kamera dimatikan saat modal ditutup, pindah tab, atau halaman ditinggal (`pagehide`).
- Object URL preview foto dilepas (`URL.revokeObjectURL`) setiap ganti foto / tutup modal.
- Canvas sementara dikosongkan setelah foto / frame diambil; array frame absensi dilepas setelah dikirim.
- Polling berhenti saat tidak dibutuhkan (`Poller.stop()`), bukan `setInterval` yang jalan terus.
- Toast lama dibuang (maks 4); daftar tabel dibatasi dari server.

## Cara menjalankan setelah update

```bash
git pull
venv\Scripts\activate
pip install -r requirements.txt          # tambahan: waitress, Flask-Compress
```
SSMS: jalankan `database/migrations/003_index_optimasi.sql` (database dummy dulu).

- Development: `python app.py`
- Dipakai di site: `python serve.py`
- Cek kesehatan: buka `http://127.0.0.1:5000/health`
