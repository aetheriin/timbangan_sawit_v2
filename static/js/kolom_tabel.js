// ===== TAMPILKAN / SEMBUNYIKAN KOLOM TABEL =====
// <table id="tabelX" data-atur-kolom> + <th data-kolom="nama"> (data-kolom-wajib = selalu tampil,
// data-kolom-sembunyi = tersembunyi bawaan). Tombol "Kolom" dipasang di <div data-tombol-kolom="tabelX">.
// Kolom disembunyikan lewat CSS nth-child, jadi isi tbody yang dibuat ulang (innerHTML) tetap ikut.
// Pilihan disimpan per user & halaman (Pilihan di common.js), ekspor Excel/PDF ikut melewati kolom tersembunyi.
const KolomTabel = {
    pasang(tabel) {
        if (tabel._kolom) return;
        const th = [...tabel.tHead.rows[0].cells];
        const kolom = th.map((h, i) => ({ i, kunci: h.dataset.kolom || `k${i}`, label: h.textContent.trim() || h.title || `Kolom ${i + 1}`,
            wajib: h.hasAttribute('data-kolom-wajib'), bawaan: !h.hasAttribute('data-kolom-sembunyi') }));
        let simpanan = null;
        try { simpanan = JSON.parse(Pilihan.ambil(`kolom:${tabel.id}`) || 'null'); } catch (e) { simpanan = null; }
        const tampil = new Set(kolom.filter(k => k.wajib || (simpanan ? simpanan.includes(k.kunci) : k.bawaan)).map(k => k.kunci));
        const gaya = document.createElement('style');
        document.head.appendChild(gaya);
        tabel._kolom = { kolom, tampil, gaya };
        this.terapkan(tabel);
        const wadah = document.querySelector(`[data-tombol-kolom="${tabel.id}"]`);
        if (wadah) this.tombol(tabel, wadah);
    },

    terapkan(tabel) {
        const { kolom, tampil, gaya } = tabel._kolom;
        gaya.textContent = kolom.filter(k => !tampil.has(k.kunci))
            .map(k => `#${tabel.id} tr > :nth-child(${k.i + 1}):not([colspan]) { display: none; }`).join('\n');
        Pilihan.simpan(`kolom:${tabel.id}`, JSON.stringify([...tampil]));
        const jumlah = document.querySelector(`[data-tombol-kolom="${tabel.id}"] [data-jumlah-kolom]`);
        if (jumlah) jumlah.textContent = `${tampil.size}/${kolom.length}`;
    },

    tombol(tabel, wadah) {
        const { kolom, tampil } = tabel._kolom;
        wadah.classList.add('relative');
        wadah.innerHTML = `<button type="button" class="btn-secondary btn-sm" data-buka-kolom aria-haspopup="true">
                <i class="fa-solid fa-table-columns"></i> Kolom <span data-jumlah-kolom class="text-slate-400"></span></button>
            <div data-panel-kolom class="hidden absolute right-0 z-30 mt-1 w-60 rounded-lg border border-slate-200 bg-white p-2 shadow-lg text-sm">
                <p class="px-2 pb-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">Tampilkan kolom</p>
                <div class="max-h-72 overflow-y-auto">${kolom.map(k => `<label class="flex items-center gap-2 rounded px-2 py-1.5 ${k.wajib ? 'text-slate-400' : 'hover:bg-slate-50 cursor-pointer'}">
                    <input type="checkbox" data-kunci="${escapeHtml(k.kunci)}" ${tampil.has(k.kunci) ? 'checked' : ''} ${k.wajib ? 'disabled' : ''}>
                    ${escapeHtml(k.label)}${k.wajib ? ' <span class="text-[10px]">(wajib)</span>' : ''}</label>`).join('')}</div>
                <div class="mt-1 flex justify-between border-t border-slate-100 px-2 pt-2 text-xs">
                    <button type="button" class="link-aksi text-blue-600" data-semua-kolom>Tampilkan semua</button>
                    <button type="button" class="link-aksi text-slate-600" data-bawaan-kolom>Bawaan</button></div>
            </div>`;
        const panel = wadah.querySelector('[data-panel-kolom]');
        const segarkanCentang = () => panel.querySelectorAll('[data-kunci]').forEach(c => c.checked = tampil.has(c.dataset.kunci));
        wadah.querySelector('[data-buka-kolom]').addEventListener('click', () => panel.classList.toggle('hidden'));
        document.addEventListener('click', e => { if (!wadah.contains(e.target)) panel.classList.add('hidden'); });
        document.addEventListener('keydown', e => { if (e.key === 'Escape') panel.classList.add('hidden'); });
        panel.addEventListener('change', e => {
            const c = e.target.closest('[data-kunci]');
            if (!c) return;
            if (c.checked) tampil.add(c.dataset.kunci); else tampil.delete(c.dataset.kunci);
            this.terapkan(tabel);
        });
        panel.querySelector('[data-semua-kolom]').addEventListener('click', () => {
            kolom.forEach(k => tampil.add(k.kunci));
            segarkanCentang();
            this.terapkan(tabel);
        });
        panel.querySelector('[data-bawaan-kolom]').addEventListener('click', () => {
            tampil.clear();
            kolom.filter(k => k.wajib || k.bawaan).forEach(k => tampil.add(k.kunci));
            segarkanCentang();
            this.terapkan(tabel);
        });
        this.terapkan(tabel);
    },
};

document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('table[data-atur-kolom]').forEach(t => KolomTabel.pasang(t)));
