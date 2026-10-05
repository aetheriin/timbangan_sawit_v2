// ===== PILIHAN BISA DIKETIK & DICARI =====
// <select data-cari> tetap ada (tersembunyi) sebagai sumber nilai, di atasnya kotak ketik + daftar saran.
// Mengubah select.value / .disabled / isi <option> lewat JS otomatis ikut tampil di kotak ketik.
function pasangPilihCari(sel) {
    if (sel.dataset.cariTerpasang) return;
    sel.dataset.cariTerpasang = '1';

    const bungkus = document.createElement('div');
    bungkus.className = 'relative';
    sel.parentNode.insertBefore(bungkus, sel);
    bungkus.appendChild(sel);
    sel.classList.add('hidden');

    const input = document.createElement('input');
    input.type = 'text';
    input.autocomplete = 'off';
    input.className = 'input-field pr-8';
    input.placeholder = 'Ketik untuk mencari...';
    if (sel.id) input.id = sel.id + 'Cari';
    const ikon = document.createElement('i');
    ikon.className = 'fa-solid fa-chevron-down absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none';
    const daftar = document.createElement('div');
    daftar.className = 'absolute z-40 left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-auto hidden';
    bungkus.append(input, ikon, daftar);

    let sorot = -1, cocok = [];
    const opsi = () => Array.from(sel.options).filter(o => o.value !== '');
    const labelTerpilih = () => (sel.value && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].text : '');
    const tampil = () => { input.value = labelTerpilih(); };

    function render(kata) {
        const k = (kata || '').trim().toLowerCase();
        cocok = opsi().filter(o => !k || o.text.toLowerCase().includes(k));
        sorot = cocok.length ? 0 : -1;
        daftar.innerHTML = cocok.length
            ? cocok.map((o, i) => `<div data-i="${i}" class="px-3 py-2 text-sm cursor-pointer hover:bg-blue-50">${escapeHtml(o.text)}</div>`).join('')
            : '<div class="px-3 py-2 text-sm text-slate-400">Tidak ditemukan</div>';
        tandai();
        daftar.classList.remove('hidden');
    }
    function tandai() {
        daftar.querySelectorAll('[data-i]').forEach(el => el.classList.toggle('bg-blue-100', Number(el.dataset.i) === sorot));
        const el = daftar.querySelector(`[data-i="${sorot}"]`);
        if (el) el.scrollIntoView({ block: 'nearest' });
    }
    function tutup() { daftar.classList.add('hidden'); }
    function pilih(o) {
        const lama = sel.value;
        nilaiAsli.set.call(sel, o ? o.value : '');
        tampil();
        tutup();
        if (sel.value !== lama) sel.dispatchEvent(new Event('change', { bubbles: true }));
    }

    input.addEventListener('focus', () => { input.select(); render(''); });
    input.addEventListener('input', () => render(input.value));
    input.addEventListener('keydown', e => {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            if (daftar.classList.contains('hidden')) { render(''); return; }
            if (cocok.length) sorot = (sorot + (e.key === 'ArrowDown' ? 1 : -1) + cocok.length) % cocok.length;
            tandai();
        } else if (e.key === 'Enter' && !daftar.classList.contains('hidden')) {
            e.preventDefault();
            if (cocok[sorot]) pilih(cocok[sorot]);
        } else if (e.key === 'Escape') {
            tampil();
            tutup();
        }
    });
    // mousedown (bukan click) supaya terpilih sebelum kotak ketik kehilangan fokus
    daftar.addEventListener('mousedown', e => {
        e.preventDefault();
        const el = e.target.closest('[data-i]');
        if (el) pilih(cocok[Number(el.dataset.i)]);
    });
    input.addEventListener('blur', () => {
        if (daftar.classList.contains('hidden')) return;
        const teks = input.value.trim().toLowerCase();
        if (!teks) pilih(null);                               // dikosongkan = belum memilih
        else {
            const sama = opsi().find(o => o.text.toLowerCase() === teks) || (cocok.length === 1 ? cocok[0] : null);
            if (sama) pilih(sama); else { tampil(); tutup(); }   // ketikan tidak cocok -> kembali ke pilihan lama
        }
    });

    // select.value = ... dari JS lain (mis. terisi dari DO) -> kotak ketik ikut berubah
    const nilaiAsli = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
    Object.defineProperty(sel, 'value', {
        configurable: true,
        get() { return nilaiAsli.get.call(sel); },
        set(v) { nilaiAsli.set.call(sel, v); tampil(); },
    });
    sel.addEventListener('change', tampil);
    const aturDisabled = () => { input.disabled = sel.disabled; input.classList.toggle('bg-slate-50', sel.disabled); };
    new MutationObserver(() => { aturDisabled(); tampil(); })
        .observe(sel, { attributes: true, attributeFilter: ['disabled'], childList: true, subtree: true });
    aturDisabled();
    tampil();
}

document.querySelectorAll('select[data-cari]').forEach(pasangPilihCari);
