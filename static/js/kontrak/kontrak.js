// ===== KONTRAK & DO (HO) =====
let daftarDO = [];
let filterAktifDO = '';
let timerCariDO = null;
const bolehUbahDO = () => document.getElementById('tabelDO').dataset.bolehUbah === '1';

document.addEventListener('DOMContentLoaded', muatDO);

async function muatDO() {
    const q = document.getElementById('cariDO').value.trim();
    const data = await ambilJson(`/api/kontrak/do?cari=${encodeURIComponent(q)}`);
    const tbody = document.getElementById('tabelDO');
    if (data.error) { tbody.innerHTML = barisKosong(11, data.error); return false; }
    daftarDO = data;
    tampilkanDO();
}

const fmtKg = v => v == null ? '-' : Number(v).toLocaleString('id-ID');

function tampilkanDO() {
    const baris = daftarDO.filter(d => filterAktifDO === '' || String(Number(d.is_active)) === filterAktifDO);
    document.getElementById('tabelDO').innerHTML = baris.map(d => `
        <tr class="hover:bg-slate-50${d.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono">${escapeHtml(d.no_do)}</td>
            <td class="table-cell font-mono">${escapeHtml(d.no_kontrak)}</td>
            <td class="table-cell">${badge(labelKode(d.jenis_transaksi), d.jenis_transaksi === 'PENJUALAN' ? WARNA_BADGE.biru : WARNA_BADGE.hijau)}</td>
            <td class="table-cell">${escapeHtml(d.nama_customer)}</td>
            <td class="table-cell">${escapeHtml(d.nama_produk)}</td>
            <td class="table-cell text-right">${fmtKg(d.qty_kg)}</td>
            <td class="table-cell">${d.angkutan.map(a => `<div>${escapeHtml(a.label)}${a.qty_kg ? ` <span class="text-xs text-slate-500">${fmtKg(a.qty_kg)} kg</span>` : ''}</div>`).join('')}</td>
            <td class="table-cell whitespace-nowrap">${escapeHtml(d.tanggal_do)}</td>
            <td class="table-cell whitespace-nowrap">${escapeHtml(d.berlaku_sampai || '-')}</td>
            <td class="table-cell">${badgeAktif(d.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">${bolehUbahDO() ? `
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaDO" data-arg="${d.id_do}">Ubah</button>
                <button type="button" class="link-aksi ${d.is_active ? 'text-red-600' : 'text-emerald-600'}"
                    data-on-click="ubahAktifDO" data-arg="${d.id_do}">${d.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>` : ''}
            </td>
        </tr>`).join('') || barisKosong(11, 'Belum ada kontrak & DO');
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
                           keterangan: d.keterangan || '' });
    else isiForm(form, { id_do: '', tanggal_do: hariIni, tanggal_kontrak: hariIni });
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
