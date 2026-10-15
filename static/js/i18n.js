// ===== BAHASA TAMPILAN (ID / EN) =====
// Teks aplikasi ditulis dalam bahasa Indonesia. Bila pilihan bahasa = EN (cookie "bahasa", diatur tombol ID/EN di
// sidebar & halaman login), kamus static/js/i18n/en.js dimuat sebelum file ini dan teks di halaman diganti ke
// bahasa Inggris di browser: teks biasa, placeholder/title/aria-label, judul tab, serta teks yang muncul belakangan
// (pop-up, tabel, pesan server) lewat MutationObserver. Data dari database (nama, plat, angka) tidak ada di kamus
// sehingga tidak berubah. Hanya nodeValue/atribut yang diganti; elemen tidak dibuat ulang, jadi kamera, tombol,
// dan event tetap utuh (berbeda dengan Chrome Translate).
// Kunci kamus berisi {0} = bagian yang berubah-ubah (angka/nama); nilai memakai {0}, {1}, ... sesuai urutan.
// Dimuat di <head> (bukan defer) supaya halaman disembunyikan sebentar sampai selesai diterjemahkan (tidak berkedip).
(function () {
    const kamus = window.KAMUS_EN;
    const aktif = !!kamus && /(?:^|;\s*)bahasa=en(?:;|$)/.test(document.cookie);
    const I18N = { bahasa: aktif ? 'en' : 'id', lokal: aktif ? 'en-GB' : 'id-ID' };
    window.I18N = I18N;

    // Tanpa kamus: t() mengembalikan teks apa adanya
    if (!aktif) { I18N.t = s => s; window.t = I18N.t; return; }

    const pola = [];                                   // kunci ber-{0} -> [regex, nilai]
    const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // Pola yang teks tetapnya paling panjang dicoba lebih dulu ("Jembatan Timbang {0}" sebelum "Jembatan {0}")
    const panjangTetap = k => k.replace(/\{0\}/g, '').length;
    Object.keys(kamus).sort((a, b) => panjangTetap(b) - panjangTetap(a)).forEach(k => {
        if (k.includes('{0}')) {
            pola.push([new RegExp('^' + k.split('{0}').map(escape).join('([\\s\\S]+?)') + '$'), kamus[k]]);
        }
    });
    const cache = new Map();

    function cocokPola(s) {
        for (const [re, nilai] of pola) {
            const m = re.exec(s);
            // Bagian yang berubah biasanya angka / nama pendek; tangkapan panjang = kalimat lain yang kebetulan cocok
            if (m && m.slice(1).every(v => kamus[v] != null || (v.length <= 32 && !v.includes(', ')))) {
                // Bagian yang berubah ikut diterjemahkan bila ada di kamus (mis. "berhasil dinonaktifkan"),
                // kecuali yang memuat angka (nama / kode seperti "Jembatan Timbang 1" tetap apa adanya)
                return nilai.replace(/\{(\d+)\}/g, (_, i) => {
                    const v = m[+i + 1] ?? '';
                    if (kamus[v] != null && !/\d/.test(v)) return kamus[v];
                    return (v.length > 15 && cocokPola(v)) || v;     // kalimat di dalam kalimat
                });
            }
        }
        return null;
    }

    function cari(s) {
        if (kamus[s] != null) return kamus[s];
        // Pesan pop-up dirapikan (huruf awal besar + titik di akhir), jadi coba juga tanpa titik / huruf awal kecil
        const titik = /[.!]$/.test(s) ? s.slice(0, -1) : null;
        if (titik && kamus[titik] != null) return kamus[titik].replace(/([^.!?])$/, '$1' + s.slice(-1));
        const kecil = s.charAt(0).toLowerCase() + s.slice(1);
        const besar = v => v.charAt(0).toUpperCase() + v.slice(1);
        if (kecil !== s && kamus[kecil] != null) return besar(kamus[kecil]);
        let h = null;
        if (titik) { h = cocokPola(titik); if (h != null) h = h.replace(/([^.!?])$/, '$1' + s.slice(-1)); }
        if (h == null) h = cocokPola(s);
        if (h == null && kecil !== s) { h = cocokPola(kecil); if (h != null) h = besar(h); }
        // "(teks)"
        const kurung = h == null && /^\((.+)\)$/.exec(s);
        if (kurung) { const k = cari(kurung[1]); if (k != null) h = `(${k})`; }
        // "KODE: keterangan" (mis. pilihan format indikator)
        const kode = h == null && /^([A-Z0-9_]{2,}): (.+)$/.exec(s);
        if (kode) { const k = cari(kode[2]); if (k != null) h = `${kode[1]}: ${k}`; }
        // Gabungan beberapa teks: "Stasiun Timbang › Sortasi", "Truk · Supir"
        if (h == null && / [›·] /.test(s)) {
            const bagian = s.split(/( [›·] )/);
            const hasil = bagian.map((b, i) => (i % 2 ? b : (cari(b) ?? b)));
            if (hasil.some((b, i) => b !== bagian[i])) h = hasil.join('');
        }
        return h;
    }

    // Terjemahkan satu teks; spasi di awal/akhir dipertahankan. null = tidak ada di kamus.
    function terjemah(teks) {
        if (!teks || !/[A-Za-z]/.test(teks)) return null;
        const inti = teks.replace(/\s+/g, ' ').trim();
        if (!inti || inti.length > 400) return null;
        let h = cache.get(inti);
        if (h === undefined) { h = cari(inti); cache.set(inti, h); }
        if (h == null || h === inti) return null;
        return teks.match(/^\s*/)[0] + h + teks.match(/\s*$/)[0];
    }
    I18N.t = s => terjemah(String(s)) || s;
    window.t = I18N.t;

    const LEWATI = 'script, style, textarea, code, [data-tanpa-terjemah], .kode-plat';
    const LEWATI_ATRIBUT = '[data-tanpa-terjemah]';     // placeholder di textarea / kotak kode tetap diterjemahkan
    const ATRIBUT = ['placeholder', 'title', 'aria-label'];

    function terjemahAtribut(el) {
        if (el.closest(LEWATI_ATRIBUT)) return;
        ATRIBUT.forEach(a => {
            const v = el.getAttribute(a);
            const h = v && terjemah(v);
            if (h) el.setAttribute(a, h);
        });
        if (el.tagName === 'INPUT' && /^(button|submit|reset)$/.test(el.type) && el.value) {
            const h = terjemah(el.value);
            if (h) el.value = h;
        }
    }

    function terjemahTeks(node) {
        const p = node.parentElement;
        if (!p || p.closest(LEWATI)) return;
        // <span data-en="..."> = terjemahan khusus untuk teks yang artinya beda menurut tempatnya
        if (p.dataset.en) { if (node.nodeValue.trim() !== p.dataset.en) node.nodeValue = p.dataset.en; return; }
        const h = terjemah(node.nodeValue);
        if (h) node.nodeValue = h;
    }

    function terjemahPohon(akar) {
        if (akar.nodeType === 3) { terjemahTeks(akar); return; }
        if (akar.nodeType !== 1) return;
        terjemahAtribut(akar);
        akar.querySelectorAll('[placeholder], [title], [aria-label], input[type=button], input[type=submit]')
            .forEach(terjemahAtribut);
        if (akar.closest(LEWATI)) return;
        const jalan = document.createTreeWalker(akar, NodeFilter.SHOW_TEXT);
        for (let n = jalan.nextNode(); n; n = jalan.nextNode()) terjemahTeks(n);
    }
    I18N.terjemahPohon = terjemahPohon;

    function terjemahJudul() {
        const h = terjemah(document.title);
        if (h) document.title = h;
    }

    // Sembunyikan halaman sampai terjemahan pertama selesai (paling lama 1,5 detik)
    const gaya = document.createElement('style');
    gaya.textContent = 'html.i18n-memuat body { visibility: hidden; }';
    document.head.appendChild(gaya);
    document.documentElement.classList.add('i18n-memuat');
    document.documentElement.lang = 'en';
    const tampilkan = () => document.documentElement.classList.remove('i18n-memuat');
    setTimeout(tampilkan, 1500);

    document.addEventListener('DOMContentLoaded', () => {
        terjemahJudul();
        terjemahPohon(document.body);
        tampilkan();
        new MutationObserver(daftar => daftar.forEach(m => {
            if (m.type === 'childList') m.addedNodes.forEach(terjemahPohon);
            else if (m.type === 'characterData') terjemahTeks(m.target);
            else if (m.type === 'attributes') terjemahAtribut(m.target);
        })).observe(document.body, {
            childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATRIBUT,
        });
        const judul = document.querySelector('title');
        if (judul) new MutationObserver(terjemahJudul).observe(judul, { childList: true, characterData: true, subtree: true });
    });
})();

// Ganti bahasa: disimpan 1 tahun di cookie (dibaca server untuk memuat kamus), lalu halaman dimuat ulang
function gantiBahasa() {
    const baru = (window.I18N && I18N.bahasa === 'en') ? 'id' : 'en';
    document.cookie = `bahasa=${baru}; path=/; max-age=31536000; SameSite=Lax`;
    location.reload();
}
document.addEventListener('click', e => { if (e.target.closest('[data-ganti-bahasa]')) gantiBahasa(); });
