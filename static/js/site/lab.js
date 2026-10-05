let noTiketLabAktif = null;
let idProdukLabAktif = null;
let keputusanDipilih = null;
let standarAktif = {};

function tampilkanStandar(std) {
    standarAktif = std;
    document.getElementById('stdFfa').textContent = std.maks_ffa != null ? std.maks_ffa + '%' : '-';
    document.getElementById('stdAir').textContent = std.maks_air != null ? std.maks_air + '%' : '-';
    document.getElementById('stdKotoran').textContent = std.maks_kotoran != null ? std.maks_kotoran + '%' : '-';
    cekStandar();
}

window.addEventListener('platLookup', (e) => {
    const data = e.detail;
    // Tiket lain (TBS / belum ada tiket) -> kosongkan, supaya hasil lab tidak tersimpan ke tiket sebelumnya
    const tiketPks = data.status === 'ADA_TIKET' && tiketPunyaTahap(data, 'LAB');
    noTiketLabAktif = tiketPks ? data.no_tiket : null;
    idProdukLabAktif = tiketPks ? data.id_produk : null;
    ['labFfa', 'labAir', 'labKotoran', 'labWarna'].forEach(id => document.getElementById(id).value = '');
    keputusanDipilih = null;
    setKeputusan(null);
    if (tiketPks) {
        muatStandar(data.id_produk);
    } else {
        tampilkanStandar({});
        document.getElementById('labStatusLive').textContent = '-';
    }
    muatHistoryLab();
});

async function muatStandar(idProduk) {
    const std = await ambilJson(`/api/lab/standar/${idProduk}`);
    if (std.error) { Notif.gagal(std.error); return; }
    tampilkanStandar(std);
}

function cekStandar() {
    if (standarAktif.maks_ffa == null) return;
    const ffa = parseFloat(document.getElementById('labFfa').value) || 0;
    const air = parseFloat(document.getElementById('labAir').value) || 0;
    const kotoran = parseFloat(document.getElementById('labKotoran').value) || 0;
    const lolos = ffa <= standarAktif.maks_ffa && air <= standarAktif.maks_air && kotoran <= standarAktif.maks_kotoran;
    document.getElementById('labStatusLive').textContent = lolos ? 'MEMENUHI' : 'TIDAK MEMENUHI';
    document.getElementById('labStatusLive').className = 'py-2 text-right font-bold ' + (lolos ? 'text-emerald-600' : 'text-red-600');
}

function setKeputusan(val) {
    keputusanDipilih = val;
    const dasar = 'border-2 rounded-lg py-3 text-base font-semibold transition ';
    document.getElementById('btnApprove').className = dasar + (val === 'APPROVE'
        ? 'bg-emerald-600 text-white border-emerald-600' : 'text-emerald-600 border-emerald-300 hover:bg-emerald-50');
    document.getElementById('btnReject').className = dasar + (val === 'REJECT'
        ? 'bg-red-600 text-white border-red-600' : 'text-red-600 border-red-300 hover:bg-red-50');
}

async function submitLab(btn) {
    if (!noTiketLabAktif) { Notif.peringatan('Pilih plat/tiket dulu'); return; }
    if (!keputusanDipilih) { Notif.peringatan('Pilih Approve/Reject dulu'); return; }
    const formData = new FormData();
    formData.append('no_tiket', noTiketLabAktif);
    formData.append('ffa', document.getElementById('labFfa').value);
    formData.append('kadar_air', document.getElementById('labAir').value);
    formData.append('kadar_kotoran', document.getElementById('labKotoran').value);
    formData.append('warna_locis', document.getElementById('labWarna').value);
    formData.append('keputusan', keputusanDipilih);
    const data = await denganTombol(btn, () => kirimForm('/api/lab/simpan', formData));
    if (tampilkanHasil(data)) muatHistoryLab();
}

function bukaStandarMutu() {
    if (!idProdukLabAktif) { Notif.peringatan('Pilih tiket produk PKS dulu (ketik plat lalu Tab)'); return; }
    document.getElementById('stdInputFfa').value = standarAktif.maks_ffa ?? '';
    document.getElementById('stdInputAir').value = standarAktif.maks_air ?? '';
    document.getElementById('stdInputKotoran').value = standarAktif.maks_kotoran ?? '';
    openModal('modalStandarMutu');
}

async function simpanStandarMutu(btn) {
    if (!idProdukLabAktif) return;
    const formData = new FormData();
    formData.append('id_produk', idProdukLabAktif);
    formData.append('maks_ffa', document.getElementById('stdInputFfa').value);
    formData.append('maks_air', document.getElementById('stdInputAir').value);
    formData.append('maks_kotoran', document.getElementById('stdInputKotoran').value);
    const data = await denganTombol(btn, () => kirimForm('/api/lab/standar/update', formData));
    if (!tampilkanHasil(data)) return;
    closeModal('modalStandarMutu');
    muatStandar(idProdukLabAktif);
    muatHistoryStandar();
}

// Riwayat perubahan standar mutu 2 hari terakhir (dimuat saat tab Laboratorium dibuka)
async function muatHistoryStandar() {
    const data = await ambilJson('/api/lab/standar/history');
    const tbody = document.getElementById('tabelHistoryStandar');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    tbody.innerHTML = data.map(r => `<tr class="hover:bg-slate-50">
        <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(r.updated_at)}</td><td class="table-cell">${escapeHtml(r.nama_produk)}</td>
        <td class="table-cell text-right">${escapeHtml(r.maks_ffa)}%</td><td class="table-cell text-right">${escapeHtml(r.maks_air)}%</td>
        <td class="table-cell text-right">${escapeHtml(r.maks_kotoran)}%</td><td class="table-cell">${escapeHtml(r.oleh || '-')}</td>
    </tr>`).join('') || barisKosong(6, 'Tidak ada perubahan standar 2 hari terakhir');
}

window.addEventListener('tabChange', e => { if (e.detail === 'lab') muatHistoryStandar(); });

function cetakCOA() {
    const area = document.getElementById('printAreaCOA');
    const nilai = id => escapeHtml(document.getElementById(id).value);
    area.innerHTML = `<h2>Certificate of Analysis</h2><p>No. Tiket: ${escapeHtml(noTiketLabAktif)}</p>
        <p>FFA: ${nilai('labFfa')}%</p>
        <p>Kadar Air: ${nilai('labAir')}%</p>
        <p>Kadar Kotoran: ${nilai('labKotoran')}%</p>`;
    area.id = 'printArea';
    window.print();
}

async function muatHistoryLab() {
    const data = await ambilJson('/api/history/lab');
    const tbody = document.getElementById('tabelHistoryLab');
    if (data.error) { tbody.innerHTML = barisKosong(4, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr><td class="table-cell">${escapeHtml(r.no_plat)}</td><td class="table-cell">${escapeHtml(r.nama_produk)}</td>
        <td class="table-cell">${escapeHtml(r.nama_supplier)}</td><td class="table-cell">${escapeHtml(r.status_val || '-')}</td></tr>
    `).join('') || barisKosong(4, 'Belum ada data');
}