// ===== MODE TERANG / GELAP =====
// Dimuat di <head> (bukan defer) supaya kelas "dark" terpasang sebelum halaman tampil (tidak berkedip putih).
// Pilihan disimpan per browser (localStorage); bawaan terang.
(function () {
    let tema = 'terang';
    try { tema = localStorage.getItem('tema') || 'terang'; } catch (e) { /* storage diblokir: pakai terang */ }
    document.documentElement.classList.toggle('dark', tema === 'gelap');
})();

function gantiTema() {
    const gelap = document.documentElement.classList.toggle('dark');
    try { localStorage.setItem('tema', gelap ? 'gelap' : 'terang'); } catch (e) { /* abaikan */ }
}
