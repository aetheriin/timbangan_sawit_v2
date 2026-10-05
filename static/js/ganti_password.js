// Popup "Password Anda sudah kedaluwarsa" -> tutup lalu langsung isi password lama
(function () {
    const popup = document.getElementById('popupKedaluwarsa');
    const tombol = document.getElementById('btnTutupPopup');
    if (!popup || !tombol) return;
    tombol.focus();
    tombol.addEventListener('click', () => {
        popup.remove();
        const pertama = document.querySelector('input[name="password_lama"]');
        if (pertama) pertama.focus();
    });
})();
