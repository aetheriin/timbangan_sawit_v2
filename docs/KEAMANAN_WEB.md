# Keamanan Web

Status per poin di cabang `claude/zen-hamilton-du3ult`. **P1** = paling penting, **P2** = penting, **P3** = perapian.
Poin yang ditandai **Ditunda** sengaja belum dikerjakan (keputusan rapat).

## Ringkasan

| # | Prio | Poin | Status | Di mana |
|---|---|---|---|---|
| 1 | P1 | `/login` saat sudah login → langsung ke halaman kerja (tombol Back ke login tidak menampilkan form) | Selesai | `routes/auth.py` |
| 2 | P1 | Logout via `POST` + token CSRF, sesi dibersihkan total; Back/Forward setelah logout tetap di login | Selesai | `routes/auth.py`, `partials/layout/topbar.html`, `ui.js`, `login.js` |
| 3 | P1 | Cookie sesi `HttpOnly`, `SameSite=Lax`, `Secure` (bila HTTPS), nama `wb_sesi` | Selesai | `utils/keamanan.py` |
| 4 | P1 | Sesi idle (default 120 menit) + umur maks 12 jam, peringatan 2 menit sebelum habis | Selesai | `utils/keamanan.py`, `ui.js` (`SesiIdle`) |
| 5 | P1 | 5x login gagal / 15 menit → dikunci 15 menit (per username & per IP), dicatat | Selesai | `utils/login_guard.py` |
| 6 | P2 | Aplikasi menolak start bila `SECRET_KEY` / `HASH_SECRET_KEY` kosong / contoh / < 32 karakter | Selesai | `utils/keamanan.py` |
| 7 | P2 | Ganti password sendiri | **Ditunda** | reset password oleh super admin: Admin › Kelola User ([ADMIN.md](ADMIN.md)) |
| 8 | P2 | User nonaktif langsung kehilangan sesi | Selesai | `get_user_by_id` cek `is_active` |
| 9 | P1 | Endpoint tanpa login ditutup: kamera & verifikasi → login atau token kiosk; status timbangan & status verifikasi → wajib login | Selesai | `routes/security.py`, `routes/timbangan.py` |
| 10 | P1 | State scan wajah per pos, hanya untuk user yang meminta, kedaluwarsa 5 menit | Selesai | `utils/verifikasi_state.py` |
| 11 | P2 | Pembatasan menu per role | **Sebagian** | ADMIN hanya menu Admin; role lain belum dibatasi. Kondisi: [HAK_AKSES_ROLE.md](HAK_AKSES_ROLE.md) |
| 12 | P2 | Endpoint data sensitif per role | **Ditunda** (ikut #11) | |
| 13 | P1 | Proteksi CSRF semua `POST` (form & `fetch`) | Selesai | Flask-WTF `CSRFProtect`, `api.js` (header `X-CSRFToken`) |
| 14 | P1 | Header keamanan: CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy, COOP, HSTS (bila HTTPS) | Selesai | `utils/keamanan.py` |
| 15 | P2 | Audit XSS: data server di `innerHTML` lewat `escapeHtml`. CSP `script-src 'self'` (tanpa `unsafe-inline`): tidak ada `onclick="..."` / `<script>` inline, tombol memakai `data-on-click` | Selesai | `static/js/aksi.js`, semua template |
| 16 | P1 | Validasi isi file (signature JPG/PNG/PDF), gambar dibuka ulang (buang metadata), batas resolusi | Selesai | `utils/upload_utils.py` |
| 17 | P1 | File upload privat di `data/uploads`, dibuka lewat `/berkas/...` (wajib login); `/static/uploads` diblok | Selesai | `extensions.py`, `routes/sistem.py` |
| 18 | P2 | Batas frame kamera (3–20 per request, maks 2 MB per frame) | Selesai | `simpan_frames` |
| 19 | P2 | Akun SQL khusus aplikasi dengan hak minimal | Selesai (skrip) | `database/keamanan/01_user_aplikasi.sql`, `DB_USER` / `DB_PASSWORD` |
| 20 | P2 | Query dinamis: nama tabel hanya dari daftar tetap | Selesai | `get_history_umum`, `tambah_blacklist` |
| 21 | P2 | NIK disamarkan untuk non-HO & kebijakan lama simpan | **Ditunda** | |
| 22 | P3 | Backup harian + verifikasi | Selesai (skrip) | `database/keamanan/02_backup_harian.sql` |
| 23 | P1 | HTTPS di jaringan site | Selesai (konfigurasi) | `deploy/Caddyfile`, `BEHIND_PROXY`, `COOKIE_SECURE` |
| 24 | P1 | Mode debug mati di site | Selesai | `serve.py`; `app.py` hanya untuk PC sendiri (127.0.0.1) |
| 25 | P2 | Firewall: hanya port aplikasi terbuka | Panduan | bagian "Firewall" di bawah |
| 26 | P2 | Log keamanan (login, gagal, terkunci, logout, 403, CSRF, kiosk ditolak, sesi habis) | Selesai | `logs/keamanan.log` (rotasi 5 x 5 MB) |
| 27 | P3 | Cek celah library | Panduan | `pip install pip-audit && pip-audit -r requirements.txt` |

## Perubahan perilaku yang terlihat user

- **Back / Forward**: setelah login, Back ke halaman login langsung kembali ke halaman kerja. Setelah logout,
  Back / Forward tetap di halaman login (halaman konten tidak disimpan browser: `Cache-Control: no-store`,
  dan halaman yang dipulihkan dari cache Back/Forward dimuat ulang).
- **Logout otomatis** setelah 120 menit tanpa aktivitas (`SESI_IDLE_MENIT`). 2 menit sebelumnya muncul dialog
  "Tetap masuk / Keluar". Polling otomatis (berat timbangan, status scan) tidak dihitung sebagai aktivitas.
- **Login dikunci** 15 menit setelah 5x salah password.
- **Blacklist = peringatan**: kendaraan / supir blacklist tetap bisa dibuatkan tiket. Form menampilkan banner
  peringatan, dan setiap deteksi serta tiket yang dibuat untuk blacklist tercatat di Audit Log
  (`TRY_SCAN_BLACKLIST`) untuk HO.
- **Foto & surat** dibuka lewat `/berkas/...`; file lama di `static/uploads` dipindah otomatis ke `data/uploads`
  saat aplikasi start (path di database tidak berubah).

## Wajib diisi di `.env` (lihat `.env.example`)

```
SECRET_KEY=<acak 64 karakter>
HASH_SECRET_KEY=<acak 64 karakter, BERBEDA>
```
Buat nilainya dengan: `python -c "import secrets; print(secrets.token_hex(32))"`

Catatan: `HASH_SECRET_KEY` dipakai untuk hash anti-ubah data timbangan & personel. Bila database sudah berisi data
dengan hash dari nilai lama, tetap pakai nilai lama (hanya pastikan panjangnya >= 32 karakter).

## Kiosk kamera

- Kiosk di **PC yang sama** dengan server: tidak perlu apa-apa.
- Kiosk di **PC lain**: isi `KIOSK_TOKEN=<acak>` di `.env` server **dan** `.env` PC kiosk (nilai sama), serta
  `WEIGHBRIDGE_URL=http://<IP-server>:5000` di PC kiosk.
- Hasil scan hanya bisa dipakai user yang menekan "Mulai Scan Wajah", berlaku 5 menit.

## Akses dari PC lain di LAN

`0.0.0.0` adalah alamat *bind* ("dengarkan di semua kartu jaringan"), **bukan** alamat yang diketik di browser.
Docker **tidak** diperlukan.

1. PC server: jalankan `python serve.py` (bukan `python app.py`; `app.py` sengaja hanya untuk PC itu sendiri).
2. Cari IP LAN PC server: `ipconfig` → "IPv4 Address", misalnya `192.168.1.10`.
3. Buka port di Windows Firewall PC server (PowerShell / CMD sebagai Administrator):
   `netsh advfirewall firewall add rule name="Weighbridge 5000" dir=in action=allow protocol=TCP localport=5000 profile=private,domain`
4. Di PC lain buka `http://192.168.1.10:5000`. Pastikan jaringan Windows diset **Private**, bukan Public.
5. **Kamera browser** (Absensi, foto Personel) dari PC lain hanya diizinkan browser lewat **HTTPS** →
   pasang HTTPS dengan `deploy/Caddyfile`. Kiosk kamera tidak terpengaruh.

## Firewall (#25)

- Buka hanya port aplikasi (5000, atau 443 bila memakai Caddy) untuk jaringan site.
- Port SQL Server (1433) hanya untuk PC server aplikasi, tidak untuk PC operator.
- Bila memakai Caddy: set `HOST=127.0.0.1` di `.env` supaya waitress hanya menerima dari Caddy.

## Batasan yang masih ada

- CSP masih `style-src 'unsafe-inline'` (atribut `style="..."` & library kamera). Risikonya kecil; script sudah ketat.
- Pembatas login & state scan wajah disimpan di memori proses: berlaku untuk satu proses `serve.py`
  (restart = hitungan kembali nol).

## Aturan menulis tombol / event baru (CSP)

Browser menolak `onclick="..."`, `oninput="..."`, `<script>...</script>` dan `href="javascript:..."`.
Pakai atribut data (dibaca `static/js/aksi.js`), dan fungsinya ditulis sebagai `function nama()` global di file `.js`:

| Dulu | Sekarang |
|---|---|
| `onclick="simpan()"` | `data-on-click="simpan"` |
| `onclick="switchTab('form')"` | `data-on-click="switchTab" data-arg="form"` |
| `onclick="filter(this)"` | `data-on-click="filter" data-arg="$el"` |
| `onclick="toggle(5, 1)"` | `data-on-click="toggle" data-arg="5\|1"` (angka otomatis jadi Number) |
| `oninput="cari(this.value)"` | `data-on-input="cari" data-arg="$value"` |
| `onchange="pilih(this.files[0])"` | `data-on-change="pilih" data-arg="$file"` |
| `onkeydown="if(Tab/Enter) cari(this)"` | `data-on-enter="cari" data-arg="$el"` |
| `ondrop="drop(event)"` | `data-on-drop="drop" data-arg="$event"` |
| `onclick="event.stopPropagation()"` | `data-henti-klik` |
| `<script>const X = {{ nilai }}</script>` | `<meta name="x" content="{{ nilai }}">` lalu dibaca di file `.js` |
