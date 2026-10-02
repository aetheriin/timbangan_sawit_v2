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
    if (data.error) { tbody.innerHTML = barisKosong(10, data.error); return false; }
    daftarDO = data;
    tampilkanDO();
}

function tampilkanDO() {
    const baris = daftarDO.filter(d => filterAktifDO === '' || String(Number(d.is_active)) === filterAktifDO);
    document.getElementById('tabelDO').innerHTML = baris.map(d => `
        <tr class="hover:bg-slate-50${d.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono">${escapeHtml(d.no_do)}</td>
            <td class="table-cell font-mono">${escapeHtml(d.no_kontrak)}</td>
            <td class="table-cell">${badge(labelKode(d.jenis_transaksi), d.jenis_transaksi === 'PENJUALAN' ? WARNA_BADGE.biru : WARNA_BADGE.hijau)}</td>
            <td class="table-cell">${escapeHtml(d.nama_customer)}</td>
            <td class="table-cell">${escapeHtml(d.nama_produk)}</td>
            <td class="table-cell">${escapeHtml(d.nama_pengangkutan)}${d.pihak_ketiga ? ' <span class="text-xs text-amber-700">(pihak ketiga)</span>' : ''}</td>
            <td class="table-cell whitespace-nowrap">${escapeHtml(d.tanggal_do)}</td>
            <td class="table-cell whitespace-nowrap">${escapeHtml(d.berlaku_sampai || '-')}</td>
            <td class="table-cell">${badgeAktif(d.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">${bolehUbahDO() ? `
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaDO" data-arg="${d.id_do}">Ubah</button>
                <button type="button" class="link-aksi ${d.is_active ? 'text-red-600' : 'text-emerald-600'}"
                    data-on-click="ubahAktifDO" data-arg="${d.id_do}">${d.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>` : ''}
            </td>
        </tr>`).join('') || barisKosong(10, 'Belum ada DO');
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
    form.reset();
    if (d) isiForm(form, { ...d, nama_pengangkutan: d.pihak_ketiga ? d.nama_pengangkutan : '', berlaku_sampai: d.berlaku_sampai || '', keterangan: d.keterangan || '' });
    else isiForm(form, { id_do: '', tanggal_do: new Date().toISOString().slice(0, 10) });
    pilihPengangkutan(d && d.pihak_ketiga ? 'PIHAK_KETIGA' : 'CUSTOMER');
    document.getElementById('judulModalDO').textContent = d ? 'Ubah DO' : 'Tambah DO';
    openModal('modalDO');
    document.getElementById('doNoKontrak').focus();
}

// No Kontrak yang sudah pernah dipakai -> customer, produk, jenis, pengangkutan ikut terisi (DO baru saja)
document.getElementById('doNoKontrak')?.addEventListener('change', async e => {
    const form = e.target.form;
    if (form.elements.id_do.value || !e.target.value.trim()) return;
    const d = await ambilJson(`/api/kontrak/terakhir?no_kontrak=${encodeURIComponent(e.target.value.trim())}`);
    if (!d || d.error || !d.id_do) return;
    isiForm(form, { jenis_transaksi: d.jenis_transaksi, id_customer: d.id_customer, id_produk: d.id_produk,
                    nama_pengangkutan: d.pihak_ketiga ? d.nama_pengangkutan : '' });
    pilihPengangkutan(d.pihak_ketiga ? 'PIHAK_KETIGA' : 'CUSTOMER');
    Notif.info(`Data diisi dari kontrak ${d.no_kontrak} (DO ${d.no_do})`);
});

// Pengangkutan: kendaraan milik customer sendiri, atau pihak ketiga (nama diketik; nama baru otomatis didaftarkan)
function pilihPengangkutan(mode) {
    const form = document.getElementById('formDO');
    form.elements.pengangkutan.value = mode;
    form.querySelectorAll('[data-angkut]').forEach(b => b.classList.toggle('seg-item-active', b.dataset.angkut === mode));
    const nama = document.getElementById('doNamaAngkut');
    nama.classList.toggle('hidden', mode !== 'PIHAK_KETIGA');
    nama.required = mode === 'PIHAK_KETIGA';
    if (mode === 'PIHAK_KETIGA') nama.focus();
}

document.getElementById('formDO')?.addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/kontrak/do/simpan', { modal: 'modalDO', setelahnya: muatDO });
});

function ubahAktifDO(id) {
    const d = daftarDO.find(x => x.id_do === id);
    konfirmasiAktif({
        url: `/api/kontrak/do/${id}/aktif`, aktif: !d.is_active, nama: `DO ${d.no_do}`, jenis: 'DO',
        pesanNonaktif: 'Security tidak bisa memakai DO ini untuk tiket baru.', setelahnya: muatDO,
    });
}
