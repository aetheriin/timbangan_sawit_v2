// ===== PILIHAN BISA DIKETIK & DICARI =====
// Otomatis untuk semua <select class="input-field"> (juga yang ditambahkan belakangan lewat JS).
// Tidak mau? beri atribut data-tanpa-cari. <select> lama tetap ada (tak terlihat) sebagai sumber nilai, jadi
// select.value = ..., .disabled, isi <option>, form.reset(), data-on-change, dan validasi required tetap jalan.
// Select wajib (required) di dalam form diberi pilihan kosong "-- Pilih ... --": saat Tambah tidak ada yang
// langsung terpilih, user harus memilih sendiri. Daftar pilihan baru muncul saat diklik / diketik.
const PILIH_CARI = 'select.input-field:not([data-tanpa-cari]), select[data-cari]';
const KELAS_TATA_LETAK = /(^|:)(w-|min-w-|max-w-|col-span-|flex-|grow|shrink|basis-)/;

function labelPilihan(sel) {
    const label = sel.id && document.querySelector(`label[for="${sel.id}"]`);
    const teks = label ? label.textContent.replace(/[*:]/g, '').trim() : '';
    return teks ? `-- Pilih ${teks.toLowerCase()} --` : '-- Pilih --';
}

// Pilihan kosong (tak bisa dipilih ulang) sebagai bawaan form.reset(), supaya Tambah dimulai dari kosong
function pasangPilihanKosong(sel, pilihKosong = true) {
    if (!sel.required || !sel.form || Array.from(sel.options).some(o => o.value === '')) return;
    const kosong = new Option(labelPilihan(sel), '', true, false);
    kosong.disabled = kosong.hidden = true;
    const terpilih = sel.selectedIndex >= 0 && sel.options[sel.selectedIndex].defaultSelected;
    sel.insertBefore(kosong, sel.firstChild);
    if (pilihKosong && !terpilih) sel.selectedIndex = 0;
}

function pasangPilihCari(sel) {
    if (sel.dataset.cariTerpasang || sel.multiple || Number(sel.size) > 1) return;
    sel.dataset.cariTerpasang = '1';
    pasangPilihanKosong(sel);

    // Lebar / posisi grid ikut ke pembungkus, sisanya (ukuran teks, padding) ke kotak ketik
    const kelas = sel.className.split(/\s+/).filter(Boolean);
    const bungkus = document.createElement('div');
    bungkus.className = ['relative', ...kelas.filter(k => KELAS_TATA_LETAK.test(k))].join(' ');
    if (sel.hasAttribute('data-henti-klik')) bungkus.setAttribute('data-henti-klik', '');
    sel.parentNode.insertBefore(bungkus, sel);

    const input = document.createElement('input');
    input.type = 'text';
    input.autocomplete = 'off';
    input.className = [...kelas.filter(k => !KELAS_TATA_LETAK.test(k)), 'w-full', 'pr-8'].join(' ');
    if (sel.id) input.id = sel.id + 'Cari';
    if (sel.title) input.title = sel.title;
    const ikon = document.createElement('i');
    ikon.className = 'fa-solid fa-chevron-down absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-xs pointer-events-none';
    const daftar = document.createElement('div');
    // position: fixed supaya daftar tidak terpotong modal / tabel (overflow), bisa digulir bila pilihan banyak
    daftar.className = 'bg-white border border-slate-200 rounded-lg shadow-lg overflow-y-auto hidden';
    Object.assign(daftar.style, { position: 'fixed', zIndex: '1000', maxWidth: '28rem' });
    bungkus.append(sel, input, ikon, daftar);

    // Tak terlihat tetapi tetap bisa difokus browser, supaya pesan "wajib diisi" (required) tetap muncul
    Object.assign(sel.style, { position: 'absolute', left: '0', top: '0', width: '100%', height: '100%', opacity: '0', pointerEvents: 'none' });
    sel.tabIndex = -1;
    sel.addEventListener('focus', () => input.focus());

    let sorot = -1, cocok = [];
    const opsi = () => Array.from(sel.options).filter(o => !o.disabled && !o.hidden && (o.value !== '' || o.text.trim()));
    const terpilih = () => (sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex] : null);
    const tampil = () => {
        const o = terpilih();
        const kosong = sel.options[0] && sel.options[0].value === '' ? sel.options[0].text.trim() : '';
        input.value = o && o.value !== '' ? o.text : '';
        input.placeholder = kosong || 'Ketik untuk mencari...';
    };

    function render(kata) {
        const k = (kata || '').trim().toLowerCase();
        cocok = opsi().filter(o => !k || o.text.toLowerCase().includes(k));
        sorot = Math.max(0, cocok.indexOf(terpilih()));
        if (k || !cocok.length) sorot = cocok.length ? 0 : -1;
        daftar.innerHTML = cocok.length
            ? cocok.map((o, i) => `<div data-i="${i}" class="px-3 py-2 text-sm cursor-pointer hover:bg-blue-50${o.value === '' ? ' text-slate-400' : ''}">${escapeHtml(o.text)}</div>`).join('')
            : '<div class="px-3 py-2 text-sm text-slate-400">Tidak ditemukan</div>';
        daftar.classList.remove('hidden');
        posisi();
        tandai();
    }
    // Di bawah kotak ketik; pindah ke atas bila ruang di bawah sempit. Tinggi maks 15rem / sisa layar.
    function posisi() {
        const k = input.getBoundingClientRect();
        const bawah = window.innerHeight - k.bottom - 8, atas = k.top - 8;
        const keAtas = bawah < 180 && atas > bawah;
        daftar.style.left = `${k.left}px`;
        daftar.style.minWidth = `${k.width}px`;
        daftar.style.maxHeight = `${Math.max(120, Math.min(240, keAtas ? atas : bawah))}px`;
        daftar.style.top = keAtas ? `${Math.max(8, k.top - 4 - daftar.offsetHeight)}px` : `${k.bottom + 4}px`;
    }
    const ikutiLayar = () => { if (!daftar.classList.contains('hidden')) posisi(); };
    window.addEventListener('resize', ikutiLayar);
    window.addEventListener('scroll', e => { if (e.target !== daftar) ikutiLayar(); }, true);
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
        if (sel.value !== lama) {
            sel.dispatchEvent(new Event('input', { bubbles: true }));
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    // Fokus (mis. otomatis saat modal dibuka) belum membuka daftar; klik / ketik / panah bawah yang membukanya
    input.addEventListener('focus', () => input.select());
    input.addEventListener('click', () => { if (daftar.classList.contains('hidden')) render(''); });
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
        } else if (e.key === 'Escape' && !daftar.classList.contains('hidden')) {
            e.stopPropagation();                                  // jangan ikut menutup modal
            tampil();
            tutup();
        } else if (e.key === 'Tab' && !daftar.classList.contains('hidden') && input.value.trim() && cocok[sorot]) {
            pilih(cocok[sorot]);
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
        if (!teks) pilih(opsi().find(o => o.value === '') || null);   // dikosongkan = belum memilih
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
    const indeksAsli = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'selectedIndex');
    Object.defineProperty(sel, 'selectedIndex', {
        configurable: true,
        get() { return indeksAsli.get.call(sel); },
        set(v) { indeksAsli.set.call(sel, v); tampil(); },
    });
    sel.addEventListener('change', tampil);
    sel.form?.addEventListener('reset', () => setTimeout(tampil));
    const aturDisabled = () => {
        input.disabled = sel.disabled;
        input.classList.toggle('bg-slate-50', sel.disabled);
    };
    new MutationObserver(() => { pasangPilihanKosong(sel, false); aturDisabled(); tampil(); })
        .observe(sel, { attributes: true, attributeFilter: ['disabled'], childList: true, subtree: true, characterData: true });
    aturDisabled();
    tampil();
}

function pasangSemuaPilihCari(akar) {
    if (akar.matches?.(PILIH_CARI)) pasangPilihCari(akar);
    akar.querySelectorAll?.(PILIH_CARI).forEach(pasangPilihCari);
}

pasangSemuaPilihCari(document);
// Select yang dibuat belakangan (baris tabel / form dinamis) ikut dipasang
new MutationObserver(daftar => daftar.forEach(m => m.addedNodes.forEach(n => { if (n.nodeType === 1) pasangSemuaPilihCari(n); })))
    .observe(document.body, { childList: true, subtree: true });
