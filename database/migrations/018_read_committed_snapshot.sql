/* =====================================================================================
   Baca data tidak menunggu kunci tulis (READ_COMMITTED_SNAPSHOT).
   Tanpa ini, halaman yang hanya membaca (mis. Admin > Users) bisa timeout 15 detik bila ada
   koneksi lain yang sedang / masih menahan transaksi di tabel yang sama.
   Ganti nama database di bawah bila berbeda. Aman dijalankan ulang.
   WITH ROLLBACK IMMEDIATE memutus koneksi lain ke database ini: tutup serve.py dulu.
   ===================================================================================== */
DECLARE @db SYSNAME = N'DbSistemTimbangan_Test';

IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = @db AND is_read_committed_snapshot_on = 1)
    EXEC (N'ALTER DATABASE [' + @db + N'] SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;');

SELECT name, is_read_committed_snapshot_on FROM sys.databases WHERE name = @db;
GO
