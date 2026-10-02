// Halaman cetak tiket: langsung buka dialog cetak saat halaman selesai dimuat
document.getElementById('btnCetak').addEventListener('click', () => window.print());
document.getElementById('btnTutup').addEventListener('click', () => window.close());
window.addEventListener('load', () => window.print());
