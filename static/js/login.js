// Halaman login dipulihkan dari cache Back/Forward -> muat ulang, supaya server bisa mengarahkan
// user yang masih login ke halaman kerjanya dan token CSRF selalu baru.
window.addEventListener('pageshow', e => { if (e.persisted) window.location.reload(); });
