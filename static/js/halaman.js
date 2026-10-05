// ===== HALAMAN TABEL (pagination di browser) =====
// <tbody data-per-halaman="20"> -> baris dibagi per halaman + navigasi di bawah tabel. Otomatis saat isi tbody
// diganti (innerHTML), tanpa kode tambahan di tiap tab. Baris yang disembunyikan pencarian (.hidden) tidak dihitung;
// baris satu-sel (kosong / catatan batas) selalu tampil. Server tetap membatasi jumlah data yang dikirim.
const PILIHAN_PER_HALAMAN = [10, 20, 50, 100];

const Halaman = {
    pasang(tbody) {
        tbody._hal = { ke: 1, per: Number(tbody.dataset.perHalaman) || 20 };
        const nav = document.createElement('div');
        nav.className = 'flex items-center gap-3 px-5 py-2.5 text-xs text-slate-500 border-t border-slate-100 hidden';
        nav.innerHTML = `<span data-info></span><div class="flex-1"></div>
            <label class="flex items-center gap-1">Tampilkan <select data-per class="border border-slate-300 rounded px-1.5 py-1">
                ${PILIHAN_PER_HALAMAN.map(n => `<option value="${n}">${n}</option>`).join('')}</select> baris</label>
            <button type="button" data-ke="-1" class="btn-secondary py-1 px-2.5 text-xs">‹ Sebelumnya</button>
            <span data-posisi class="font-medium text-slate-700"></span>
            <button type="button" data-ke="1" class="btn-secondary py-1 px-2.5 text-xs">Berikutnya ›</button>`;
        nav.querySelector('[data-per]').value = tbody._hal.per;
        nav.querySelector('[data-per]').addEventListener('change', e => {
            tbody._hal.per = Number(e.target.value);
            tbody._hal.ke = 1;
            this.segarkan(tbody);
        });
        nav.querySelectorAll('[data-ke]').forEach(b => b.addEventListener('click', () => {
            tbody._hal.ke += Number(b.dataset.ke);
            this.segarkan(tbody);
        }));
        tbody.closest('table').insertAdjacentElement('afterend', nav);
        tbody._nav = nav;
        new MutationObserver(() => this.segarkan(tbody)).observe(tbody, { childList: true });
        this.segarkan(tbody);
    },

    segarkan(tbody) {
        if (!tbody || !tbody._hal) return;
        const data = [...tbody.rows].filter(tr => tr.cells.length > 1);
        const tampil = data.filter(tr => !tr.classList.contains('hidden'));
        const { per } = tbody._hal;
        const total = tampil.length, jumlahHal = Math.max(1, Math.ceil(total / per));
        tbody._hal.ke = Math.min(Math.max(1, tbody._hal.ke), jumlahHal);
        const awal = (tbody._hal.ke - 1) * per;
        data.forEach(tr => { tr.style.display = ''; });
        tampil.forEach((tr, i) => { if (i < awal || i >= awal + per) tr.style.display = 'none'; });

        const nav = tbody._nav;
        nav.classList.toggle('hidden', total <= PILIHAN_PER_HALAMAN[0]);
        nav.querySelector('[data-info]').textContent = total
            ? `Menampilkan ${awal + 1}–${Math.min(awal + per, total)} dari ${total}` : '';
        nav.querySelector('[data-posisi]').textContent = `${tbody._hal.ke} / ${jumlahHal}`;
        nav.querySelector('[data-ke="-1"]').disabled = tbody._hal.ke <= 1;
        nav.querySelector('[data-ke="1"]').disabled = tbody._hal.ke >= jumlahHal;
    },
};

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('tbody[data-per-halaman]').forEach(tb => Halaman.pasang(tb));
});
