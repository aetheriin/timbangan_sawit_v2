# Halaman Admin (Super Admin)

Hanya role `ADMIN`. Admin **hanya** melihat menu Admin (tidak bisa membuka Weighbridge / Face Recognition,
tidak bisa membuat tiket / menimbang). Role lain yang membuka `/admin` mendapat 403.
Tampilan memakai `base.html` yang sama: tanpa info bar dan tanpa tab, menu ada di sidebar.
Desain Figma: layar A01–A09 + modal M14–M15 di file Weighbridge + Face Recognition.

## Cara memasang

1. Jalankan migrasi `database/migrations/004_admin.sql` di SSMS (setelah 001–003). Migrasi ini **wajib**: login
   sekarang membaca kolom `users.sesi_versi`.
2. Pastikan ada minimal satu akun ADMIN. Contoh membuat akun `admin` / `admin12345` (ganti password setelah login
   lewat menu Kelola User › Reset Password):

   ```sql
   INSERT INTO users (nama, username, password, role)
   VALUES ('Super Admin', 'admin',
           'pbkdf2:sha256:1000000$zkbmkQ6HN9jaUBF5$c6b4177f0ac7789efa50b5d512d6b1ae6bd86963b81d2ba9b9208d3349801419',
           'ADMIN');
   ```
3. `pip install -r requirements.txt` lalu jalankan aplikasi. Login sebagai admin langsung masuk ke `/admin/users`.

## Menu

| Menu | Isi | Berlaku |
|---|---|---|
| Kelola User | Tambah user, ubah nama / role, reset password, aktif / nonaktif. User tidak dihapus | Ganti role, reset password, nonaktif → semua sesi user itu langsung berakhir |
| Sesi Aktif | Siapa yang login, IP, sejak kapan, berapa lama tidak aktif (diperbarui otomatis tiap 10 detik). Paksa keluar. Daftar login terkunci + username yang dicoba dari IP itu; Buka Kunci per baris, ketik username / IP, atau Buka Semua | Langsung |
| Supplier & Produk | Tambah / ubah / aktif / nonaktif supplier (Supplier Pembelian / Buyer Penjualan) dan produk (TBS / Produk PKS) | Langsung muncul / hilang di pilihan Form |
| Jadwal Kerja | Libur, jam masuk, jam pulang, toleransi per hari | Scan absensi berikutnya |
| Pengaturan Site | Wajib scan wajah, ambang kemiripan wajah, sesi idle, umur sesi, kunci login | ±30 detik, tanpa restart |
| Perangkat / Kiosk | Pos kiosk + token per pos (tampil sekali), status timbangan serial, kamera tiap pos | Langsung (token lama tidak berlaku) |
| Log Keamanan | Isi `logs/keamanan.log`: login, gagal, terkunci, akses ditolak, kiosk ditolak, CSRF, sesi habis | – |
| Audit Admin | Semua perubahan oleh admin (tabel `admin_audit_logs`) | – |
| Kesehatan Sistem | Koneksi & respons database, ukuran DB, backup terakhir, disk, folder upload, timbangan, versi, uptime | – |

## Di mana mengubah waktu / batas

Urutan yang dipakai aplikasi: **Admin › Pengaturan Site** → `.env` → bawaan di kode (`utils/pengaturan.py`).

| Yang diatur | Pengaturan | Bawaan | Kode |
|---|---|---|---|
| Berapa kali salah password sebelum dikunci | `LOGIN_MAKS_GAGAL` | 5 | `utils/login_guard.py` |
| Rentang menghitung salah password | `LOGIN_JENDELA_MENIT` | 15 menit | `utils/login_guard.py` |
| Lama akun / IP dikunci | `LOGIN_KUNCI_MENIT` | 15 menit | `utils/login_guard.py` |
| Logout otomatis bila tidak aktif | `SESI_IDLE_MENIT` | 120 menit | `utils/keamanan.py` (`cek_idle`) |
| Peringatan sebelum logout otomatis | – | 2 menit | `static/js/ui.js` (`SesiIdle.PERINGATAN_DETIK`) |
| Umur sesi maksimal | `SESI_MAKS_JAM` | 12 jam | `utils/keamanan.py` (`cek_idle`) |
| Wajib scan wajah supir | `WAJIB_SCAN_WAJAH` | true | `routes/security.py` |
| Ambang kemiripan wajah | `AMBANG_WAJAH` | 0.55 | `routes/absensi.py`, `routes/security.py` |
| Hasil scan wajah harus dipakai dalam | – | 5 menit | `utils/verifikasi_state.py` (`BERLAKU`) |
| Kamera kiosk dianggap selesai setelah | – | 2 menit | `utils/verifikasi_state.py` (`KAMERA_MAKS`) |
| Batas waktu request dari browser | – | 15 detik | `static/js/api.js` (`TIMEOUT_DEFAULT_MS`) |
| Polling berat timbangan | – | 0,5 detik | `static/js/site/timbangan.js` |
| Lama notifikasi tampil | – | 4 detik (gagal 7 detik) | `static/js/ui.js` (`Notif`) |
| Request lambat dicatat di log | `LOG_REQUEST_LAMBAT_MS` (.env) | 1000 ms | `utils/web_setup.py` |

Kunci login yang sedang berjalan bisa dibuka lebih cepat di **Sesi Aktif › Login Terkunci › Buka Kunci**.

## Keamanan halaman admin

- Semua aksi lewat POST + token CSRF; semua tercatat di Audit Admin (+ reset password / paksa keluar juga di log keamanan).
- Admin tidak bisa menonaktifkan / menurunkan role akunnya sendiri, dan sistem menolak bila admin aktif tinggal 0.
- Password minimal 8 karakter, disimpan sebagai hash pbkdf2.
- Token kiosk disimpan sebagai hash SHA-256; token asli hanya tampil sekali.
- "Paksa keluar" memakai `users.sesi_versi`: sesi lama ditolak di request berikutnya, di PC mana pun, walau server restart.
