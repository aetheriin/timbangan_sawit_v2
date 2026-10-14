// Tombol mata di kotak password: klik -> password terlihat / tersembunyi lagi
document.querySelectorAll('[data-lihat-password]').forEach(tombol => {
    const input = tombol.parentElement.querySelector('input');
    tombol.addEventListener('click', () => {
        const lihat = input.type === 'password';
        input.type = lihat ? 'text' : 'password';
        tombol.innerHTML = `<i class="fa-regular ${lihat ? 'fa-eye-slash' : 'fa-eye'}"></i>`;
        tombol.title = lihat ? 'Sembunyikan password' : 'Tampilkan password';
        tombol.setAttribute('aria-label', tombol.title);
        input.focus();
    });
});
