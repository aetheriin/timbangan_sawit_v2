// ===== AKSI: pengganti onclick="..." / oninput="..." di HTML =====
// CSP melarang script inline (docs/DOKUMENTASI.md bagian 8), jadi elemen cukup menyebut NAMA fungsinya:
//   <button data-on-click="switchTab" data-arg="security">       -> switchTab('security')
//   <button data-on-click="filterAudit" data-arg="$el">           -> filterAudit(tombol itu)
//   <input  data-on-enter="cariSupirByNik" data-arg="$el">        -> Tab / Enter -> cariSupirByNik(input)
//   <input  data-on-change="pilihFoto" data-arg="$file">          -> pilihFoto(file pertama)
// Event: click, input, change, enter (Tab/Enter saat kotak terisi), drop.
// Argumen dipisah "|". Token: $el, $event, $value, $file, $true, $false; angka bulat -> Number.
// Tanpa data-arg = fungsi dipanggil tanpa argumen. Fungsi harus berupa `function nama()` global.
// data-henti-klik: klik di dalam elemen ini tidak ikut memicu aksi elemen induknya (mis. header section).

function argumenAksi(el, e) {
    if (!el.hasAttribute('data-arg')) return [];
    return el.dataset.arg.split('|').map(a => {
        switch (a) {
            case '$el': return el;
            case '$event': return e;
            case '$value': return el.value;
            case '$file': return el.files ? el.files[0] : undefined;
            case '$true': return true;
            case '$false': return false;
            default: return /^-?\d+$/.test(a) ? Number(a) : a;
        }
    });
}

function jalankanAksi(el, nama, e) {
    const fn = window[nama];
    if (typeof fn !== 'function') {
        console.error(`Aksi "${nama}" tidak ditemukan`);
        return;
    }
    fn(...argumenAksi(el, e));
}

document.addEventListener('click', e => {
    const el = e.target.closest('[data-on-click], [data-henti-klik]');
    if (!el || !el.dataset.onClick) return;
    jalankanAksi(el, el.dataset.onClick, e);
});

document.addEventListener('input', e => {
    const el = e.target.closest('[data-on-input]');
    if (el) jalankanAksi(el, el.dataset.onInput, e);
});

document.addEventListener('change', e => {
    const el = e.target.closest('[data-on-change]');
    if (el) jalankanAksi(el, el.dataset.onChange, e);
});

// Tab / Enter di kotak isian = "cari". Shift+Tab dan kotak kosong tetap berperilaku normal.
document.addEventListener('keydown', e => {
    const el = e.target.closest('[data-on-enter]');
    if (!el || !(e.key === 'Enter' || (e.key === 'Tab' && !e.shiftKey))) return;
    if (!el.value.trim()) return;
    e.preventDefault();
    jalankanAksi(el, el.dataset.onEnter, e);
});

document.addEventListener('dragover', e => {
    if (e.target.closest('[data-on-drop]')) e.preventDefault();      // wajib agar drop diizinkan
});

document.addEventListener('drop', e => {
    const el = e.target.closest('[data-on-drop]');
    if (!el) return;
    e.preventDefault();
    jalankanAksi(el, el.dataset.onDrop, e);
});
