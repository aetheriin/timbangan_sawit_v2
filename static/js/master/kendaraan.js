// ===== DATA MASTER > KENDARAAN (tambah / ubah: SECURITY & HO) =====
let daftarKendaraan = [];
let filterAktifKendaraan = '';
let timerCariKendaraan = null;
let kendaraanDimuat = false;
const bolehUbahKendaraan = () => document.getElementById('tabelKendaraan').dataset.bolehUbah === '1';

window.addEventListener('tabChange', e => {
    if (e.detail === 'kendaraan' && !kendaraanDimuat) {
        kendaraanDimuat = true;
        muatKendaraan();
        muatJenisKendaraan();
    }
});

async function muatKendaraan() {
    const q = document.getElementById('cariKendaraan').value.trim();
    const data = await ambilJson(`/api/master/kendaraan?cari=${encodeURIComponent(q)}`);
    const tbody = document.getElementById('tabelKendaraan');
    if (data.error) { tbody.innerHTML = barisKosong(8, data.error); return; }
    daftarKendaraan = data;
    tampilkanKendaraan();
}

function tampilkanKendaraan() {
    const baris = daftarKendaraan.filter(k => filterAktifKendaraan === '' || String(Number(k.is_active)) === filterAktifKendaraan);
    document.getElementById('tabelKendaraan').innerHTML = baris.map(k => `
        <tr class="hover:bg-slate-50${k.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono whitespace-nowrap">${escapeHtml(k.no_plat)}</td>
            <td class="table-cell">${k.no_stnk ? escapeHtml(k.no_stnk) : badge('Belum diisi', WARNA_BADGE.oranye)}</td>
            <td class="table-cell">${escapeHtml(k.jenis_kendaraan || '-')}</td>
            <td class="table-cell">${k.id_supir_utama ? escapeHtml(formatNamaPersonel(k.kode_supir_utama, k.id_supir_utama, k.nama_supir_utama))
                                                      : '<span class="text-slate-400">Belum ada</span>'}</td>
            <td class="table-cell">${Number(k.jumlah_supir)}</td>
            <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(k.transaksi_terakhir || '-')}</td>
            <td class="table-cell space-x-1">${badgeAktif(k.is_active)}${k.is_blacklisted ? badge('BLACKLIST', WARNA_BADGE.merah) : ''}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">${bolehUbahKendaraan() ? `
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaKendaraan" data-arg="${k.id_kendaraan}">Ubah</button>
                <button type="button" class="link-aksi ${k.is_active ? 'text-red-600' : 'text-emerald-600'}"
                    data-on-click="ubahAktifKendaraan" data-arg="${k.id_kendaraan}">${k.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>` : ''}
            </td>
        </tr>`).join('') || barisKosong(8, 'Belum ada kendaraan', aksiKosong('bukaKendaraan', 'Tambah Kendaraan'));
}

function filterStatusKendaraan(el) {
    aktifkanChip(el);
    filterAktifKendaraan = el.dataset.status;
    tampilkanKendaraan();
}

function cariDaftarKendaraan() {
    clearTimeout(timerCariKendaraan);
    timerCariKendaraan = setTimeout(muatKendaraan, 300);
}

function bukaKendaraan(id) {
    const form = document.getElementById('formKendaraan');
    const k = daftarKendaraan.find(x => x.id_kendaraan === id);
    form.reset();
    isiForm(form, k ? { id_kendaraan: k.id_kendaraan, no_plat: k.no_plat, no_stnk: k.no_stnk || '', id_supir_utama: k.id_supir_utama || '',
                     id_jenis_kendaraan: k.id_jenis_kendaraan || '' }
                    : { id_kendaraan: '', id_supir_utama: '' });
    document.getElementById('judulModalKendaraan').textContent = k ? `Ubah Kendaraan ${k.no_plat}` : 'Tambah Kendaraan';
    openModal('modalKendaraan');
    document.getElementById('kendNoPlat').focus();
}

document.getElementById('formKendaraan')?.addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/master/kendaraan/simpan', { modal: 'modalKendaraan', setelahnya: muatKendaraan });
});

function ubahAktifKendaraan(id) {
    const k = daftarKendaraan.find(x => x.id_kendaraan === id);
    konfirmasiAktif({
        url: `/api/master/kendaraan/${id}/aktif`, aktif: !k.is_active, nama: `Kendaraan ${k.no_plat}`, jenis: 'kendaraan',
        pesanNonaktif: 'Security tidak bisa membuat tiket untuk plat ini.', setelahnya: muatKendaraan,
    });
}

// ===== JENIS KENDARAAN & KAPASITAS =====
let daftarJenisKendaraan = [];

async function muatJenisKendaraan() {
    const data = await ambilJson('/api/master/jenis-kendaraan');
    const tbody = document.getElementById('tabelJenisKendaraan');
    if (data.error) { tbody.innerHTML = barisKosong(8, data.error); return; }
    daftarJenisKendaraan = data;
    const kg = v => v == null ? '<span class="text-slate-400">-</span>' : Number(v).toLocaleString('id-ID');
    tbody.innerHTML = data.map(j => `
        <tr class="hover:bg-slate-50${j.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono">${escapeHtml(j.kode)}</td>
            <td class="table-cell">${escapeHtml(j.nama)}</td>
            <td class="table-cell text-right">${kg(j.berat_kosong_kg)}</td>
            <td class="table-cell text-right">${kg(j.muatan_maks_kg)}</td>
            <td class="table-cell text-right">${kg(j.kursi)}</td>
            <td class="table-cell text-right">${Number(j.jumlah_kendaraan)}</td>
            <td class="table-cell">${badgeAktif(j.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">${bolehUbahKendaraan() ? `
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaJenisKendaraan" data-arg="${j.id_jenis_kendaraan}">Ubah</button>
                <button type="button" class="link-aksi ${j.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifJenisKendaraan"
                    data-arg="${j.id_jenis_kendaraan}">${j.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>` : ''}
            </td>
        </tr>`).join('') || barisKosong(8, 'Belum ada jenis kendaraan');
}

function bukaJenisKendaraan(id) {
    const form = document.getElementById('formJenisKendaraan');
    const j = typeof id === 'number' ? daftarJenisKendaraan.find(x => x.id_jenis_kendaraan === id) : null;
    form.reset();
    isiForm(form, j ? { ...j, berat_kosong_kg: j.berat_kosong_kg ?? '', muatan_maks_kg: j.muatan_maks_kg ?? '', kursi: j.kursi ?? '' }
                    : { id_jenis_kendaraan: '' });
    document.getElementById('judulJenisKendaraan').textContent = j ? `Ubah Jenis Kendaraan ${j.nama}` : 'Tambah Jenis Kendaraan';
    openModal('modalJenisKendaraan');
    document.getElementById(j ? 'jkNama' : 'jkKode').focus();
}

document.getElementById('formJenisKendaraan')?.addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/master/jenis-kendaraan/simpan', { modal: 'modalJenisKendaraan', setelahnya: muatJenisKendaraan });
});

function ubahAktifJenisKendaraan(id) {
    const j = daftarJenisKendaraan.find(x => x.id_jenis_kendaraan === id);
    konfirmasiAktif({
        url: `/api/master/jenis-kendaraan/${id}/aktif`, aktif: !j.is_active, nama: j.nama, jenis: 'jenis kendaraan',
        pesanNonaktif: 'Tidak muncul lagi di pilihan saat menambah / mengubah kendaraan.', setelahnya: muatJenisKendaraan,
    });
}
