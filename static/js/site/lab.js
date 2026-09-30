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
    const tiketPks = data.status === 'ADA_TIKET' && data.kategori_produk === 'PRODUK_PKS';
    noTiketLabAktif = tiketPks ? data.no_tiket : null;
    idProdukLabAktif = tiketPks ? data.id_produk : null;
    ['labFfa', 'labAir', 'labKotoran', 'labWarna'].forEach(id => document.getElementById(id).value = '');
    keputusanDipilih = null;
    setKeputusan(null);
    if (tiketPks) {
        fetch(`/api/lab/standar/${data.id_produk}`).then(r => r.json()).then(tampilkanStandar);
    } else {
        tampilkanStandar({});
        document.getElementById('labStatusLive').textContent = '-';
    }
    muatHistoryLab();
});

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

async function submitLab() {
    if (!noTiketLabAktif) { alert('Pilih plat/tiket dulu'); return; }
    if (!keputusanDipilih) { alert('Pilih Approve/Reject dulu'); return; }
    const formData = new FormData();
    formData.append('no_tiket', noTiketLabAktif);
    formData.append('ffa', document.getElementById('labFfa').value);
    formData.append('kadar_air', document.getElementById('labAir').value);
    formData.append('kadar_kotoran', document.getElementById('labKotoran').value);
    formData.append('warna_locis', document.getElementById('labWarna').value);
    formData.append('keputusan', keputusanDipilih);
    const res = await fetch('/api/lab/simpan', { method: 'POST', body: formData });
    const data = await res.json();
    alert(data.message || data.error);
    if (data.message) muatHistoryLab();
}

function bukaStandarMutu() {
    if (!idProdukLabAktif) { alert('Pilih tiket produk PKS dulu (ketik plat lalu Tab)'); return; }
    document.getElementById('stdInputFfa').value = standarAktif.maks_ffa ?? '';
    document.getElementById('stdInputAir').value = standarAktif.maks_air ?? '';
    document.getElementById('stdInputKotoran').value = standarAktif.maks_kotoran ?? '';
    openModal('modalStandarMutu');
}

async function simpanStandarMutu() {
    if (!idProdukLabAktif) return;
    const formData = new FormData();
    formData.append('id_produk', idProdukLabAktif);
    formData.append('maks_ffa', document.getElementById('stdInputFfa').value);
    formData.append('maks_air', document.getElementById('stdInputAir').value);
    formData.append('maks_kotoran', document.getElementById('stdInputKotoran').value);
    const res = await fetch('/api/lab/standar/update', { method: 'POST', body: formData });
    const data = await res.json();
    alert(data.message || data.error);
    if (!data.message) return;
    closeModal('modalStandarMutu');
    fetch(`/api/lab/standar/${idProdukLabAktif}`).then(r => r.json()).then(tampilkanStandar);
}

function cetakCOA() {
    const area = document.getElementById('printAreaCOA');
    area.innerHTML = `<h2>Certificate of Analysis</h2><p>No. Tiket: ${noTiketLabAktif}</p>
        <p>FFA: ${document.getElementById('labFfa').value}%</p>
        <p>Kadar Air: ${document.getElementById('labAir').value}%</p>
        <p>Kadar Kotoran: ${document.getElementById('labKotoran').value}%</p>`;
    area.id = 'printArea';
    window.print();
}

async function muatHistoryLab() {
    const res = await fetch('/api/history/lab');
    const data = await res.json();
    document.getElementById('tabelHistoryLab').innerHTML = data.map(r => `
        <tr><td class="table-cell">${r.no_plat}</td><td class="table-cell">${r.nama_produk}</td>
        <td class="table-cell">${r.nama_supplier}</td><td class="table-cell">${r.status_val || '-'}</td></tr>
    `).join('') || `<tr><td colspan="4" class="table-cell text-center text-slate-400 py-6">Belum ada data</td></tr>`;
}