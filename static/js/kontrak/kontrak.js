// ===== KONTRAK & DO (HO) =====
let daftarDO = [];
let filterAktifDO = '';
let timerCariDO = null;
const bolehUbahDO = () => document.getElementById('tabelDO').dataset.bolehUbah === '1';

// ?cari=NO_DO dari pencarian global (Ctrl+K) -> kotak cari langsung terisi
document.addEventListener('DOMContentLoaded', () => {
    const cari = new URLSearchParams(location.search).get('cari');
    if (cari) document.getElementById('cariDO').value = cari;
    muatDO();
});

async function muatDO() {
    const q = document.getElementById('cariDO').value.trim();
    const data = await ambilJson(`/api/kontrak/do?cari=${encodeURIComponent(q)}`);
    const tbody = document.getElementById('tabelDO');
    if (data.error) { tbody.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(data.error)}</p>`; return false; }
    daftarDO = data;
    tampilkanDO();
}

const fmtKg = v => v == null ? '-' : Number(v).toLocaleString('id-ID');

function tampilkanDO() {
    const baris = daftarDO.filter(d => filterAktifDO === '' || String(Number(d.is_active)) === filterAktifDO);
    const baris2 = (label, nilai, mono = false) => `<div class="flex items-start justify-between gap-3 text-sm">
        <span class="text-slate-500 flex-shrink-0">${label}</span><span class="${mono ? 'font-mono ' : ''}text-slate-800 text-right">${nilai}</span></div>`;
    document.getElementById('tabelDO').innerHTML = baris.map(d => {
        const persen = d.qty_kg ? Math.round((d.realisasi_kg || 0) / d.qty_kg * 100) : null;
        const warnaBar = persen == null ? 'bg-slate-300' : persen > 100 ? 'bg-red-500' : persen >= 90 ? 'bg-amber-500' : 'bg-emerald-500';
        const sisa = d.qty_kg ? d.qty_kg - (d.realisasi_kg || 0) : null;
        return `<div class="card flex flex-col${d.is_active ? '' : ' opacity-60'}">
            <div class="flex items-start justify-between gap-3 pb-3 border-b border-slate-100">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="judul-ikon judul-ikon-hijau"><i class="fa-solid fa-building"></i></div>
                    <div class="min-w-0">
                        <p class="font-bold text-slate-900 truncate">${escapeHtml(d.nama_customer)}</p>
                        <p class="font-mono text-xs text-slate-500">${escapeHtml(d.no_do)}</p>
                    </div>
                </div>
                ${badge(labelKode(d.jenis_transaksi), d.jenis_transaksi === 'PENJUALAN' ? WARNA_BADGE.biru : WARNA_BADGE.hijau)}
            </div>
            <div class="py-3 space-y-1.5 border-b border-slate-100">
                ${baris2('Produk', `<b>${escapeHtml(d.nama_produk)}</b>`)}
                ${baris2('No. Kontrak', `${escapeHtml(d.no_kontrak)}${d.kode_company ? ` · ${escapeHtml(d.kode_company)}` : ''}`, true)}
                ${d.harga_per_kg ? baris2('Harga', `Rp ${fmtKg(d.harga_per_kg)}/kg${d.ppn ? (d.harga_termasuk_ppn ? ' <span class="text-slate-500">(termasuk PPN)</span>' : ' <span class="text-slate-500">+ PPN</span>') : ''}`) : ''}
                ${baris2('Pengangkutan', d.angkutan.map(a => escapeHtml(a.label) + (a.ongkos_per_kg ? ` <span class="text-slate-500">· Rp ${fmtKg(a.ongkos_per_kg)}/kg</span>` : '')).join('<br>') || '-')}
                ${baris2('Tanggal DO', `${escapeHtml(d.tanggal_do)}${d.berlaku_sampai ? ` s/d ${escapeHtml(d.berlaku_sampai)}` : ''}`, true)}
            </div>
            <div class="pt-3 pb-3">
                <div class="flex items-center justify-between text-sm"><span class="text-slate-500">Realisasi kuota</span>
                    <span class="font-mono font-bold ${persen > 100 ? 'text-red-600' : 'text-slate-900'}">${persen == null ? '-' : persen + '%'}</span></div>
                <div class="w-full h-2 bg-slate-100 rounded-full overflow-hidden mt-1.5">
                    <div class="h-full ${warnaBar} rounded-full" style="width:${Math.min(persen || 0, 100)}%"></div></div>
                <div class="flex items-center justify-between text-[11px] font-mono text-slate-400 mt-1.5">
                    <span>Realisasi: ${fmtKg(d.realisasi_kg || 0)} kg</span><span>Kuota: ${fmtKg(d.qty_kg)} kg</span></div>
                ${sisa != null && sisa < 0 ? `<p class="text-[11px] text-red-600 mt-1">Lebih ${fmtKg(-sisa)} kg dari kuota</p>` : ''}
            </div>
            <div class="flex items-center justify-between gap-2 pt-3 mt-auto border-t border-slate-100">
                ${badgeAktif(d.is_active)}
                <span class="space-x-3">${bolehUbahDO() ? `
                    <button type="button" class="link-aksi text-blue-600" data-on-click="bukaDO" data-arg="${d.id_do}">Ubah</button>
                    <button type="button" class="link-aksi ${d.is_active ? 'text-red-600' : 'text-emerald-600'}"
                        data-on-click="ubahAktifDO" data-arg="${d.id_do}">${d.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>` : ''}</span>
            </div>
        </div>`;
    }).join('') || '<div class="card text-center text-sm text-slate-400 md:col-span-2 xl:col-span-3">Belum ada kontrak & DO</div>';
}

function filterStatusDO(el) {
    aktifkanChip(el);
    filterAktifDO = el.dataset.status;
    tampilkanDO();
}

function cariDaftarDO() {
    clearTimeout(timerCariDO);
    timerCariDO = setTimeout(muatDO, 300);
}

function bukaDO(id) {
    const form = document.getElementById('formDO');
    const d = daftarDO.find(x => x.id_do === id);
    const hariIni = new Date().toISOString().slice(0, 10);
    form.reset();
    if (d) isiForm(form, { ...d, qty_kg: d.qty_kg ?? '', harga_per_kg: d.harga_per_kg ?? '', berlaku_sampai: d.berlaku_sampai || '',
                           keterangan: d.keterangan || '', id_company: d.id_company ?? '' });
    else isiForm(form, { id_do: '', tanggal_do: hariIni, tanggal_kontrak: hariIni });
    const pt = form.elements.id_company;            // hanya satu PT yang boleh dipilih: langsung terisi
    const opsiPt = [...pt.options].filter(o => o.value);
    if (!pt.value && opsiPt.length === 1) pt.value = opsiPt[0].value;
    aturPpnDO();
    document.getElementById('daftarAngkutDO').innerHTML = '';
    (d ? d.angkutan : [{ cara_angkut: 'PENGIRIM' }]).forEach(tambahBarisAngkut);
    labelCaraAngkut();
    document.getElementById('judulModalDO').textContent = d ? 'Ubah Kontrak & DO' : 'Tambah Kontrak & DO';
    openModal('modalDO');
    document.getElementById('doNoKontrak').focus();
}

// ===== Pengangkutan DO: beberapa baris (kendaraan pengirim / penerima sendiri, atau pihak ketiga) =====
function tambahBarisAngkut(a) {
    const isi = a && a.cara_angkut ? a : { cara_angkut: 'PIHAK_KETIGA' };
    const baris = document.getElementById('tplBarisAngkut').content.firstElementChild.cloneNode(true);
    baris.querySelector('[name=angkut_cara]').value = isi.cara_angkut;
    baris.querySelector('[name=angkut_nama]').value = isi.nama_pengangkutan || '';
    baris.querySelector('[name=angkut_qty]').value = isi.qty_kg ?? '';
    baris.querySelector('[name=angkut_ongkos]').value = isi.ongkos_per_kg ?? '';
    document.getElementById('daftarAngkutDO').appendChild(baris);
    ubahCaraAngkut(baris.querySelector('[name=angkut_cara]'));
    labelCaraAngkut();
}

function hapusBarisAngkut(el) {
    el.closest('[data-baris-angkut]').remove();
}

function ubahCaraAngkut(sel) {
    const nama = sel.closest('[data-baris-angkut]').querySelector('[name=angkut_nama]');
    const pihakKetiga = sel.value === 'PIHAK_KETIGA';
    nama.classList.toggle('invisible', !pihakKetiga);
    nama.required = pihakKetiga;
}

// Pembelian: pengirim = customer, penerima = PT sendiri; penjualan sebaliknya
function labelCaraAngkut() {
    const form = document.getElementById('formDO');
    const sel = form.elements.id_customer;
    const customer = sel.value ? sel.options[sel.selectedIndex].text : 'customer';
    const jual = form.elements.jenis_transaksi.value === 'PENJUALAN';
    form.querySelectorAll('[name=angkut_cara]').forEach(s => {
        s.options[0].text = `Kendaraan ${jual ? 'PT sendiri' : customer} (pengirim)`;
        s.options[1].text = `Kendaraan ${jual ? customer : 'PT sendiri'} (penerima)`;
    });
}

document.getElementById('formDO')?.addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/kontrak/do/simpan', { modal: 'modalDO', setelahnya: muatDO });
});

function ubahAktifDO(id) {
    const d = daftarDO.find(x => x.id_do === id);
    konfirmasiAktif({
        url: `/api/kontrak/do/${id}/aktif`, aktif: !d.is_active, nama: `DO ${d.no_do}`, jenis: 'DO',
        pesanNonaktif: 'Kontrak & DO ini tidak bisa dipakai Security untuk tiket baru.', setelahnya: muatDO,
    });
}

// "Harga sudah termasuk PPN" hanya berlaku bila kontrak kena PPN
function aturPpnDO() {
    const form = document.getElementById('formDO');
    const incl = form.elements.harga_termasuk_ppn;
    incl.disabled = !form.elements.ppn.checked;
    if (incl.disabled) incl.checked = false;
}
