# Halaman Admin (Super Admin)

Hanya level dengan tanda admin (`level.is_admin = 1`, bawaan: `ADMIN`). Admin **hanya** melihat menu Admin (tidak bisa membuka Weighbridge / Face Recognition,
tidak bisa membuat tiket / menimbang). Role lain yang membuka `/admin` mendapat 403.
Tampilan memakai `base.html` yang sama: tanpa info bar dan tanpa tab, menu ada di sidebar.
Desain Figma: layar A01–A09 + modal M14–M15 di file Weighbridge + Face Recognition.

## Cara memasang

1. Jalankan migrasi `database/migrations/` 001–013 berurutan di SSMS. **008–013 wajib** untuk versi ini: login membaca
   tabel `level` (kolom `users.role` diganti `users.id_level`), SIM & wajah dibaca dari `personel_sim` / `personel_wajah`.
2. Pastikan ada minimal satu akun ADMIN. Contoh membuat akun `admin` / `admin12345` (ganti password setelah login
   lewat menu Kelola User › Reset Password):

   ```sql
   INSERT INTO users (nama, username, password, id_level, id_department, id_comp_area)
   SELECT 'Super Admin', 'admin',
          'pbkdf2:sha256:1000000$zkbmkQ6HN9jaUBF5$c6b4177f0ac7789efa50b5d512d6b1ae6bd86963b81d2ba9b9208d3349801419',
          (SELECT id_level FROM level WHERE kode = 'ADMIN'), (SELECT MIN(id_department) FROM department),
          (SELECT MIN(id_comp_area) FROM comp_area);
   ```
3. `pip install -r requirements.txt` lalu jalankan aplikasi. Login sebagai admin langsung masuk ke `/admin/users`.

## Menu

| Menu | Isi | Berlaku |
|---|---|---|
| Kelola User | Tambah user, ubah nama / level / department / area, reset password, aktif / nonaktif. User tidak dihapus | Ganti level, reset password, nonaktif → semua sesi user itu langsung berakhir |
| Level & Hak Akses | Tambah / ubah level (pengganti role), halaman awal setelah login, aktif / nonaktif level. Matriks centang Tambah / Ubah / Hapus per menu | ±30 detik di semua PC, tanpa login ulang |
| Organisasi | Company, area (site), department, mill (alur tahap per area) | Langsung muncul di pilihan Kelola User; mill dipakai tiket baru |
| Sesi Aktif | Siapa yang login dari semua PC (tabel `sesi_login`, migrasi 007), IP, sejak kapan, berapa lama tidak aktif (diperbarui otomatis tiap 10 detik). Paksa keluar. Daftar login terkunci + username yang dicoba dari IP itu; Buka Kunci per baris, ketik username / IP, atau Buka Semua | Langsung |
| Supplier & Produk | Tambah / ubah / aktif / nonaktif mitra (peran Customer dan/atau Pengangkutan) dan produk (kategori + alur tahap) | Langsung muncul / hilang di pilihan Form |
| Void Tiket | Batalkan tiket salah input (wajib alasan). Status jadi VOID: keluar dari daftar aktif, QR tidak berlaku, tidak bisa ditimbang. Data tidak dihapus. Berita acara (No, tanggal, file) dilampirkan saat void atau menyusul lewat tombol Lampirkan BA | Langsung |
| Jadwal Kerja | Libur, jam masuk, jam pulang, toleransi per hari | Scan absensi berikutnya |
| Pengaturan Site | Wajib scan wajah, ambang kemiripan wajah, sesi idle, umur sesi, kunci login | ±30 detik, tanpa restart |
| Perangkat / Kiosk | Pos kiosk + token per pos (tampil sekali), kamera tiap pos. Jembatan timbang per area (kode, port COM, baudrate) + berat live tiap jembatan | Langsung (token lama tidak berlaku); port jembatan baru langsung dibaca, ubah port jembatan lama setelah restart |
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
| Password kedaluwarsa (wajib ganti saat login, 0 = tidak pernah) | `PASSWORD_EXPIRED_HARI` | 90 hari | `utils/keamanan.py` (`password_wajib_diganti`) |
| 1 user 1 perangkat (login baru mengeluarkan perangkat lama) | `SATU_PERANGKAT` | true | `routes/auth.py` (`login`) |
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
- Admin tidak bisa menonaktifkan / menurunkan level akunnya sendiri, dan sistem menolak bila admin aktif tinggal 0.
- Password minimal 8 karakter, disimpan sebagai hash pbkdf2. User hanya mengganti password sendiri saat login
  dengan password kedaluwarsa / baru direset (muncul popup lalu halaman ganti password). Ganti sebelum kedaluwarsa
  lewat admin (Kelola User › Reset Password).
- Token kiosk disimpan sebagai hash SHA-256; token asli hanya tampil sekali.
- "Paksa keluar" memakai `users.sesi_versi`: sesi lama ditolak di request berikutnya, di PC mana pun, walau server restart.
  Perangkat yang dikeluarkan melihat alasannya di halaman login (paksa keluar admin, login di perangkat lain, dll).
- Sesi Aktif membaca tabel `sesi_login` (jalankan `database/migrations/007_sesi_login.sql`), jadi sesi dari PC lain
  dan dari proses server mana pun (app.py / serve.py) ikut tampil.
