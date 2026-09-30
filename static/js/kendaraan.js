// ===== MODAL UPDATE: tab "Supir Truk" & "Kontrak Truk" =====
// Truk yang diatur = plat di Form Pendaftaran Tiket (formNoPlat)
let platTrukAktif = null;
let supirDitemukan = null;

const LABEL_STATUS_KONTRAK = {
    AKTIF: ['Aktif', 'bg-emerald-100 text-emerald-700'],
    BELUM_MULAI: ['Belum mulai', 'bg-blue-100 text-blue-700'],
    BERAKHIR: ['Berakhir', 'bg-slate-200 text-slate-600'],
    NONAKTIF: ['Diakhiri', 'bg-red-100 text-red-700'],
};

async function muatDataKendaraan(plat) {
    platTrukAktif = null;
    renderSupirTruk([]);
    renderKontrakTruk([]);
    if (!plat.trim()) return;
    const data = await (await fetch(`/api/kendaraan?no_plat=${encodeURIComponent(plat)}`)).json();
    if (data.error) { alert(data.error); return; }
    tampilkanDataKendaraan(data);
}

function tampilkanDataKendaraan(data) {
    platTrukAktif = data.no_plat;
    document.getElementById('updJudulPlat').textContent = `(${data.no_plat})`;
    if (!document.getElementById('kkMulai').value) {
        document.getElementById('kkMulai').value = new Date().toISOString().slice(0, 10);
    }
    renderSupirTruk(data.supir);
    renderKontrakTruk(data.kontrak);
    sinkronKontrakKeForm(data.kontrak.filter(k => k.status === 'AKTIF'));
}

function renderSupirTruk(list) {
    document.getElementById('tabelSupirTruk').innerHTML = list.map(s => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(formatNamaPersonel(s.kode_personel, s.id_driver, s.nama_driver))}${s.is_updated ? ' <span class="text-amber-600 text-xs">⚠</span>' : ''}${s.is_blacklisted ? ' ' + badge('BLACKLIST', WARNA_BADGE.merah) : ''}
                <div class="text-xs text-slate-400">SIM ${escapeHtml(s.no_sim)}</div></td>
            <td class="table-cell">${escapeHtml(s.nik)}</td>
            <td class="table-cell">${s.is_utama
                ? '<span class="badge-status bg-blue-100 text-blue-700">Utama</span>'
                : '<span class="badge-status bg-slate-200 text-slate-600">Cadangan</span>'}</td>
            <td class="table-cell text-right space-x-2 whitespace-nowrap">
                <button onclick="pakaiSupirDariTruk(${s.id_driver})" class="text-emerald-600 hover:underline text-xs">Pakai</button>
                ${s.is_utama ? '' : `<button onclick="jadikanSupirUtama(${s.id_driver})" class="text-blue-600 hover:underline text-xs">Jadikan Utama</button>`}
                <button onclick="lepasSupirTruk(${s.id_driver})" class="text-red-600 hover:underline text-xs">Lepas</button>
            </td>
        </tr>`).join('')
        || `<tr><td colspan="4" class="table-cell text-slate-400 text-center py-6">Belum ada supir terdaftar untuk truk ini</td></tr>`;
    supirTrukTerakhir = list;
}
let supirTrukTerakhir = [];

function renderKontrakTruk(list) {
    document.getElementById('tabelKontrakTruk').innerHTML = list.map(k => {
        const [label, warna] = LABEL_STATUS_KONTRAK[k.status];
        const bisaDiakhiri = k.status === 'AKTIF' || k.status === 'BELUM_MULAI';
        return `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(k.no_kontrak || '-')}</td>
            <td class="table-cell">${escapeHtml(k.nama_supplier)}</td>
            <td class="table-cell">${escapeHtml(k.nama_produk || 'Semua')}
                <div class="text-xs text-slate-400">${k.jenis_transaksi ? k.jenis_transaksi.replace('_', ' ') : 'Semua jenis'}</div></td>
            <td class="table-cell whitespace-nowrap">${k.tanggal_mulai} s/d ${k.tanggal_selesai || '...'}</td>
            <td class="table-cell"><span class="badge-status ${warna}">${label}</span></td>
            <td class="table-cell text-right">${bisaDiakhiri
                ? `<button onclick="akhiriKontrak(${k.id_kontrak})" class="text-red-600 hover:underline text-xs">Akhiri</button>` : ''}</td>
        </tr>`;
    }).join('') || `<tr><td colspan="6" class="table-cell text-slate-400 text-center py-6">Belum ada kontrak</td></tr>`;
}

function pastikanTrukDipilih() {
    if (!platTrukAktif) { alert('Isi No. Plat di form lalu tekan Tab dulu'); return false; }
    return true;
}

function prosesHasil(data) {
    if (data.error) { alert(data.error); return false; }
    tampilkanDataKendaraan(data);
    return true;
}

// ----- Supir truk -----
async function cariSupirUntukTruk(nik) {
    const el = document.getElementById('updHasilNik');
    const btn = document.getElementById('btnDaftarkanSupir');
    if (!nik.trim()) return;
    const data = await kirimForm('/api/driver/cari-by-nik', { nik: nik.trim() });
    if (data.status === 'DITEMUKAN') {
        supirDitemukan = data;
        el.innerHTML = `<b>${escapeHtml(data.nama)}</b> &middot; SIM ${escapeHtml(data.no_sim)}`;
        btn.disabled = false;
    } else {
        supirDitemukan = null;
        el.innerHTML = '<span class="text-red-600">Tidak ditemukan. Klik "Supir Baru" untuk mendaftarkan.</span>';
        btn.disabled = true;
    }
}

// Dari tombol "Daftarkan", atau setelah supir baru disimpan lewat modal Tambah (konteks 'kendaraan')
async function daftarkanSupirKeTruk(idDriverBaru = null) {
    if (!pastikanTrukDipilih()) return false;
    const idDriver = idDriverBaru || (supirDitemukan && supirDitemukan.id_driver);
    if (!idDriver) return false;
    const data = await kirimForm('/api/kendaraan/supir/tambah', {
        no_plat: platTrukAktif, id_driver: idDriver,
        is_utama: document.getElementById('updJadikanUtama').checked ? '1' : '0',
    });
    if (!prosesHasil(data)) return false;
    alert(data.message);
    supirDitemukan = null;
    document.getElementById('updCariNik').value = '';
    document.getElementById('updJadikanUtama').checked = false;
    document.getElementById('updHasilNik').textContent = 'Cari supir yang sudah terdaftar lewat NIK.';
    document.getElementById('btnDaftarkanSupir').disabled = true;
    return true;
}

async function jadikanSupirUtama(idDriver) {
    prosesHasil(await kirimForm('/api/kendaraan/supir/utama', { no_plat: platTrukAktif, id_driver: idDriver }));
}

async function lepasSupirTruk(idDriver) {
    const s = supirTrukTerakhir.find(x => x.id_driver === idDriver);
    if (!confirm(`Lepas ${s ? s.nama_driver : 'supir ini'} dari truk ${platTrukAktif}? Data supir tidak dihapus.`)) return;
    prosesHasil(await kirimForm('/api/kendaraan/supir/hapus', { no_plat: platTrukAktif, id_driver: idDriver }));
}

// Pakai supir dari daftar truk untuk tiket ini (tetap wajib scan wajah)
function pakaiSupirDariTruk(idDriver) {
    const s = supirTrukTerakhir.find(x => x.id_driver === idDriver);
    if (!s) return;
    gantiSupirTiket({ id_driver: s.id_driver, kode_personel: s.kode_personel, nik: s.nik, nama: s.nama_driver,
                      no_sim: s.no_sim, is_blacklisted: s.is_blacklisted, is_updated: s.is_updated, foto_path: s.foto_path });
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
    if (prosesHasil(data)) {
        alert(data.message);
        ['kkSupplier', 'kkProduk', 'kkJenis', 'kkNoKontrak', 'kkSelesai', 'kkKeterangan']
            .forEach(id => document.getElementById(id).value = '');
    }
}

async function akhiriKontrak(idKontrak) {
    if (!confirm('Akhiri kontrak ini mulai hari ini?')) return;
    prosesHasil(await kirimForm('/api/kendaraan/kontrak/akhiri', { no_plat: platTrukAktif, id_kontrak: idKontrak }));
}
