// ===== DATA MASTER > MITRA & PRODUK =====
let daftarMitra = [];
const bolehUbah = id => document.getElementById(id).dataset.bolehUbah === '1';
let daftarProduk = [];

document.addEventListener('DOMContentLoaded', () => {
    muatMitra();
    muatProduk();
});

async function muatMitra() {
    const data = await ambilJson('/api/master/mitra');
    const tbody = document.getElementById('tabelMitra');
    if (data.error) { tbody.innerHTML = barisKosong(7, data.error); return; }
    daftarMitra = data;
    const kodePt = JSON.parse(tbody.dataset.company || '[]'), idPt = JSON.parse(tbody.dataset.companyId || '[]');
    const labelPt = ids => ids.length ? ids.map(id => kodePt[idPt.indexOf(id)]).filter(Boolean).join(', ') : 'Semua';
    tbody.innerHTML = data.map(s => `
        <tr class="hover:bg-slate-50${s.is_active ? '' : ' text-slate-400'}" data-cari="${escapeHtml(`${s.kode_supplier} ${s.nama_supplier}`.toLowerCase())}">
            <td class="table-cell font-mono">${escapeHtml(s.kode_supplier)}</td>
            <td class="table-cell">${escapeHtml(s.nama_supplier)}${s.alamat ? `<span class="block text-[11px] text-slate-500">${escapeHtml(s.alamat)}</span>` : ''}</td>
            <td class="table-cell space-x-1">${s.is_customer ? badge('Customer', WARNA_BADGE.biru) : ''}${s.is_angkutan ? badge('Pengangkutan', WARNA_BADGE.oranye) : ''}</td>
            <td class="table-cell">${escapeHtml(labelPt(s.company))}</td>
            <td class="table-cell">${badgeAktif(s.is_active)}</td>
            <td class="table-cell">${escapeHtml(s.created_at || '-')}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">${bolehUbah('tabelMitra') ? `
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaMitra" data-arg="${s.id_supplier}">Ubah</button>
                <button type="button" class="link-aksi ${s.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifMitra"
                    data-arg="${s.id_supplier}">${s.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>` : ''}
            </td>
        </tr>`).join('') || barisKosong(7, 'Belum ada supplier', aksiKosong('bukaMitra', 'Tambah Supplier'));
    saringBaris('tabelMitra', document.getElementById('cariMitra').value);
}

function cariMitra(teks) {
    saringBaris('tabelMitra', teks);
}

function bukaMitra(id) {
    const form = document.getElementById('formMitra');
    const s = daftarMitra.find(x => x.id_supplier === id);
    form.reset();
    const { company, ...isi } = s || {};
    isiForm(form, s ? { ...isi, alamat: s.alamat || '' } : { id_supplier: '', is_customer: true });
    form.querySelectorAll('[name=company]').forEach(c => { c.checked = (company || []).includes(c.value); });
    document.getElementById('judulModalMitra').textContent = s ? 'Ubah Supplier' : 'Tambah Supplier';
    openModal('modalMitra');
    document.getElementById('mitraKode').focus();
}

document.getElementById('formMitra')?.addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/master/mitra/simpan', { modal: 'modalMitra', setelahnya: muatMitra });
});

function ubahAktifMitra(id) {
    const s = daftarMitra.find(x => x.id_supplier === id);
    konfirmasiAktif({
        url: `/api/master/mitra/${id}/aktif`, aktif: !s.is_active, nama: s.nama_supplier, jenis: 'supplier',
        pesanNonaktif: 'Tidak muncul lagi di pilihan formulir pendaftaran tiket.', setelahnya: muatMitra,
    });
}

async function muatProduk() {
    const data = await ambilJson('/api/master/produk');
    const tbody = document.getElementById('tabelProduk');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    daftarProduk = data;
    tbody.innerHTML = data.map(p => `
        <tr class="hover:bg-slate-50${p.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell">${escapeHtml(p.nama_produk)}</td>
            <td class="table-cell">${badge(labelKode(p.kategori), p.kategori === 'TBS' ? WARNA_BADGE.hijau : WARNA_BADGE.biru)}</td>
            <td class="table-cell">${escapeHtml(p.nama_alur || '-')}</td>
            <td class="table-cell">${p.kategori === 'TBS' ? '<span class="text-slate-400">-</span>'
                : (p.ada_standar ? badge('Sudah diatur', WARNA_BADGE.hijau) : badge('Belum diatur', WARNA_BADGE.oranye))}</td>
            <td class="table-cell">${badgeAktif(p.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">${bolehUbah('tabelProduk') ? `
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaProduk" data-arg="${p.id_produk}">Ubah</button>
                <button type="button" class="link-aksi ${p.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifProduk"
                    data-arg="${p.id_produk}">${p.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>` : ''}
            </td>
        </tr>`).join('') || barisKosong(6, 'Belum ada produk', aksiKosong('bukaProduk', 'Tambah Produk'));
}

function bukaProduk(id) {
    const form = document.getElementById('formProduk');
    const p = daftarProduk.find(x => x.id_produk === id);
    form.reset();
    isiForm(form, p || { id_produk: '' });
    document.getElementById('judulModalProduk').textContent = p ? 'Ubah Produk' : 'Tambah Produk';
    openModal('modalProduk');
    document.getElementById('prodNama').focus();
}

document.getElementById('formProduk')?.addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/master/produk/simpan', { modal: 'modalProduk', setelahnya: muatProduk });
});

function ubahAktifProduk(id) {
    const p = daftarProduk.find(x => x.id_produk === id);
    konfirmasiAktif({
        url: `/api/master/produk/${id}/aktif`, aktif: !p.is_active, nama: p.nama_produk, jenis: 'produk',
        pesanNonaktif: 'Tidak muncul lagi di pilihan formulir pendaftaran tiket.', setelahnya: muatProduk,
    });
}
