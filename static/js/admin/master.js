// ===== ADMIN > SUPPLIER & PRODUK =====
let daftarSupplier = [];
let daftarProduk = [];

document.addEventListener('DOMContentLoaded', () => {
    muatSupplier();
    muatProduk();
});

async function muatSupplier() {
    const data = await ambilJson('/api/admin/supplier');
    const tbody = document.getElementById('tabelSupplier');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    daftarSupplier = data;
    tbody.innerHTML = data.map(s => `
        <tr class="hover:bg-slate-50${s.is_active ? '' : ' text-slate-400'}" data-cari="${escapeHtml(`${s.kode_supplier} ${s.nama_supplier}`.toLowerCase())}">
            <td class="table-cell font-mono">${escapeHtml(s.kode_supplier)}</td>
            <td class="table-cell">${escapeHtml(s.nama_supplier)}</td>
            <td class="table-cell">${badge(labelKode(s.tipe), s.tipe === 'PENGANGKUTAN' ? WARNA_BADGE.oranye : WARNA_BADGE.biru)}</td>
            <td class="table-cell">${badgeAktif(s.is_active)}</td>
            <td class="table-cell">${escapeHtml(s.created_at || '-')}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaSupplier" data-arg="${s.id_supplier}">Ubah</button>
                <button type="button" class="link-aksi ${s.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifSupplier"
                    data-arg="${s.id_supplier}">${s.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td>
        </tr>`).join('') || barisKosong(6, 'Belum ada supplier');
    saringBaris('tabelSupplier', document.getElementById('cariSupplier').value);
}

function cariSupplier(teks) {
    saringBaris('tabelSupplier', teks);
}

function bukaSupplier(id) {
    const form = document.getElementById('formSupplier');
    const s = daftarSupplier.find(x => x.id_supplier === id);
    form.reset();
    isiForm(form, s || { id_supplier: '' });
    document.getElementById('judulModalSupplier').textContent = s ? 'Ubah Supplier' : 'Tambah Supplier';
    openModal('modalSupplier');
    document.getElementById('supKode').focus();
}

document.getElementById('formSupplier').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/supplier/simpan', { modal: 'modalSupplier', setelahnya: muatSupplier });
});

function ubahAktifSupplier(id) {
    const s = daftarSupplier.find(x => x.id_supplier === id);
    konfirmasiAktif({
        url: `/api/admin/supplier/${id}/aktif`, aktif: !s.is_active, nama: s.nama_supplier, jenis: 'supplier',
        pesanNonaktif: 'Tidak muncul lagi di pilihan Form pendaftaran tiket.', setelahnya: muatSupplier,
    });
}

async function muatProduk() {
    const data = await ambilJson('/api/admin/produk');
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
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaProduk" data-arg="${p.id_produk}">Ubah</button>
                <button type="button" class="link-aksi ${p.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifProduk"
                    data-arg="${p.id_produk}">${p.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td>
        </tr>`).join('') || barisKosong(6, 'Belum ada produk');
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

document.getElementById('formProduk').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/produk/simpan', { modal: 'modalProduk', setelahnya: muatProduk });
});

function ubahAktifProduk(id) {
    const p = daftarProduk.find(x => x.id_produk === id);
    konfirmasiAktif({
        url: `/api/admin/produk/${id}/aktif`, aktif: !p.is_active, nama: p.nama_produk, jenis: 'produk',
        pesanNonaktif: 'Tidak muncul lagi di pilihan Form pendaftaran tiket.', setelahnya: muatProduk,
    });
}
