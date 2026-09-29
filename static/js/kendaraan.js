// ===== MENU UPDATE TRUK: supir truk & kontrak supplier =====
let platTrukAktif = null;
let supirDitemukan = null;

const LABEL_STATUS_KONTRAK = {
    AKTIF: ['Aktif', 'bg-emerald-100 text-emerald-700'],
    BELUM_MULAI: ['Belum mulai', 'bg-blue-100 text-blue-700'],
    BERAKHIR: ['Berakhir', 'bg-slate-200 text-slate-600'],
    NONAKTIF: ['Diakhiri', 'bg-red-100 text-red-700'],
};

function kirimForm(url, data) {
    const formData = new FormData();
    Object.entries(data).forEach(([k, v]) => formData.append(k, v ?? ''));
    return fetch(url, { method: 'POST', body: formData }).then(r => r.json());
}

async function muatDataKendaraan(plat) {
    if (!plat.trim()) return;
    const data = await (await fetch(`/api/kendaraan?no_plat=${encodeURIComponent(plat)}`)).json();
    if (data.error) { alert(data.error); return; }
    tampilkanDataKendaraan(data);
}

function tampilkanDataKendaraan(data) {
    platTrukAktif = data.no_plat;
    document.getElementById('updPlat').value = data.no_plat;
    document.getElementById('updStnk').value = data.no_stnk || '';
    document.getElementById('updStatusTruk').textContent = data.terdaftar
        ? `Truk ${data.no_plat}: ${data.supir.length} supir, ${data.kontrak.filter(k => k.status === 'AKTIF').length} kontrak aktif`
        : `Truk ${data.no_plat} belum terdaftar. Otomatis terdaftar saat menyimpan supir / kontrak.`;
    document.getElementById('updKonten').classList.remove('section-disabled');
    if (!document.getElementById('kkMulai').value) {
        document.getElementById('kkMulai').value = new Date().toISOString().slice(0, 10);
    }
    renderSupirTruk(data.supir);
    renderKontrakTruk(data.kontrak);
}

function renderSupirTruk(list) {
    document.getElementById('tabelSupirTruk').innerHTML = list.map(s => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${s.nama_driver}${s.is_updated ? ' <span class="text-amber-600 text-xs">⚠</span>' : ''}</td>
            <td class="table-cell">${s.nik}</td><td class="table-cell">${s.no_sim}</td>
            <td class="table-cell">${s.is_utama
                ? '<span class="badge-status bg-blue-100 text-blue-700">Utama</span>'
                : '<span class="badge-status bg-slate-200 text-slate-600">Cadangan</span>'}</td>
            <td class="table-cell text-right space-x-2 whitespace-nowrap">
                ${s.is_utama ? '' : `<button onclick="jadikanSupirUtama(${s.id_driver})" class="text-blue-600 hover:underline text-xs">Jadikan Utama</button>`}
                <button onclick="lepasSupirTruk(${s.id_driver}, '${s.nama_driver.replace(/'/g, "\\'")}')" class="text-red-600 hover:underline text-xs">Lepas</button>
            </td>
        </tr>`).join('')
        || `<tr><td colspan="5" class="table-cell text-slate-400 text-center py-6">Belum ada supir terdaftar untuk truk ini</td></tr>`;
}

function renderKontrakTruk(list) {
    document.getElementById('tabelKontrakTruk').innerHTML = list.map(k => {
        const [label, warna] = LABEL_STATUS_KONTRAK[k.status];
        const bisaDiakhiri = k.status === 'AKTIF' || k.status === 'BELUM_MULAI';
        return `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${k.no_kontrak || '-'}</td>
            <td class="table-cell">${k.nama_supplier}</td>
            <td class="table-cell">${k.nama_produk || 'Semua'}</td>
            <td class="table-cell">${k.jenis_transaksi ? k.jenis_transaksi.replace('_', ' ') : 'Semua'}</td>
            <td class="table-cell whitespace-nowrap">${k.tanggal_mulai} s/d ${k.tanggal_selesai || '...'}</td>
            <td class="table-cell"><span class="badge-status ${warna}">${label}</span></td>
            <td class="table-cell text-right">${bisaDiakhiri
                ? `<button onclick="akhiriKontrak(${k.id_kontrak})" class="text-red-600 hover:underline text-xs">Akhiri</button>` : ''}</td>
        </tr>`;
    }).join('') || `<tr><td colspan="7" class="table-cell text-slate-400 text-center py-6">Belum ada kontrak</td></tr>`;
}

function pastikanTrukDipilih() {
    if (!platTrukAktif) { alert('Ketik plat truk lalu tekan Tab dulu'); return false; }
    return true;
}

async function prosesHasil(data) {
    if (data.error) { alert(data.error); return false; }
    tampilkanDataKendaraan(data);
    return true;
}

async function simpanKendaraan() {
    const plat = document.getElementById('updPlat').value;
    if (!plat.trim()) { alert('Ketik plat truk dulu'); return; }
    const data = await kirimForm('/api/kendaraan/simpan', { no_plat: plat, no_stnk: document.getElementById('updStnk').value.trim() });
    if (await prosesHasil(data)) alert(data.message);
}

// ----- Supir -----
async function cariSupirUntukTruk(nik) {
    const el = document.getElementById('updHasilNik');
    const btn = document.getElementById('btnDaftarkanSupir');
    if (!nik.trim()) return;
    const data = await kirimForm('/api/driver/cari-by-nik', { nik: nik.trim() });
    if (data.status === 'DITEMUKAN') {
        supirDitemukan = data;
        el.innerHTML = `<b>${data.nama}</b> &middot; SIM ${data.no_sim}`;
        btn.disabled = false;
    } else {
        supirDitemukan = null;
        el.innerHTML = '<span class="text-red-600">Tidak ditemukan. Klik "Supir Baru" untuk mendaftarkan.</span>';
        btn.disabled = true;
    }
}

// Dipanggil dari tombol "Daftarkan" atau setelah supir baru disimpan lewat modal Tambah
async function daftarkanSupirKeTruk(idDriverBaru = null) {
    if (!pastikanTrukDipilih()) return;
    const idDriver = idDriverBaru || (supirDitemukan && supirDitemukan.id_driver);
    if (!idDriver) return;
    const data = await kirimForm('/api/kendaraan/supir/tambah', {
        no_plat: platTrukAktif, id_driver: idDriver,
        is_utama: document.getElementById('updJadikanUtama').checked ? '1' : '0',
    });
    if (await prosesHasil(data)) {
        alert(data.message);
        supirDitemukan = null;
        document.getElementById('updCariNik').value = '';
        document.getElementById('updJadikanUtama').checked = false;
        document.getElementById('updHasilNik').textContent = 'Cari supir yang sudah terdaftar lewat NIK.';
        document.getElementById('btnDaftarkanSupir').disabled = true;
    }
}

async function jadikanSupirUtama(idDriver) {
    await prosesHasil(await kirimForm('/api/kendaraan/supir/utama', { no_plat: platTrukAktif, id_driver: idDriver }));
}

async function lepasSupirTruk(idDriver, nama) {
    if (!confirm(`Lepas ${nama} dari truk ${platTrukAktif}? Data supir tidak dihapus.`)) return;
    await prosesHasil(await kirimForm('/api/kendaraan/supir/hapus', { no_plat: platTrukAktif, id_driver: idDriver }));
}

// ----- Kontrak -----
async function simpanKontrak() {
    if (!pastikanTrukDipilih()) return;
    const nilai = id => document.getElementById(id).value.trim();
    const data = await kirimForm('/api/kendaraan/kontrak/tambah', {
        no_plat: platTrukAktif, id_supplier: nilai('kkSupplier'), id_produk: nilai('kkProduk'),
        jenis_transaksi: nilai('kkJenis'), no_kontrak: nilai('kkNoKontrak'),
        tanggal_mulai: nilai('kkMulai'), tanggal_selesai: nilai('kkSelesai'), keterangan: nilai('kkKeterangan'),
    });
    if (await prosesHasil(data)) {
        alert(data.message);
        ['kkSupplier', 'kkProduk', 'kkJenis', 'kkNoKontrak', 'kkSelesai', 'kkKeterangan']
            .forEach(id => document.getElementById(id).value = '');
    }
}

async function akhiriKontrak(idKontrak) {
    if (!confirm('Akhiri kontrak ini mulai hari ini?')) return;
    await prosesHasil(await kirimForm('/api/kendaraan/kontrak/akhiri', { no_plat: platTrukAktif, id_kontrak: idKontrak }));
}

// Plat yang diketik di bar atas ikut dibawa ke menu Update Truk
window.addEventListener('platLookup', (e) => {
    if (e.detail.no_plat && !document.getElementById('updPlat').value) {
        document.getElementById('updPlat').value = e.detail.no_plat;
    }
});
