let noTiketSortasiAktif = null;
let beratAcuanSortasi = null;   // netto; null = belum timbang kedua

window.addEventListener('platLookup', (e) => {
    const data = e.detail;
    if (data.status === 'ADA_TIKET' && data.kategori_produk === 'TBS') {
        noTiketSortasiAktif = data.no_tiket;
        fetch(`/api/timbang/data/${data.no_tiket}`).then(r => r.json()).then(tb => {
            // Potongan dihitung dari netto (berat buah saja, tanpa truk)
            beratAcuanSortasi = tb.berat_netto;
            document.getElementById('srBeratAcuan').textContent = beratAcuanSortasi ?? 'menunggu timbang kedua';
            hitungPotongan();
        });
    }
    muatHistorySortasi();
});

function hitungPotongan() {
    const mentah = parseFloat(document.getElementById('srMentah').value) || 0;
    const tangkai = parseFloat(document.getElementById('srTangkai').value) || 0;
    const sampah = parseFloat(document.getElementById('srSampah').value) || 0;
    const totalPersen = mentah + tangkai + sampah;
    document.getElementById('srEstimasiPersen').textContent = totalPersen.toFixed(1) + '%';
    document.getElementById('srTotalPotongan').textContent = beratAcuanSortasi == null
        ? 'dihitung saat timbang kedua'
        : round2(beratAcuanSortasi * totalPersen / 100) + ' Kg';
    document.getElementById('srStatusMutu').textContent = totalPersen > 15 ? 'Kurang Baik' : 'Baik';
}
function round2(n) { return Math.round(n * 100) / 100; }

async function submitSortasi() {
    if (!noTiketSortasiAktif) { alert('Pilih plat/tiket dulu'); return; }
    const formData = new FormData();
    formData.append('no_tiket', noTiketSortasiAktif);
    ['mentah', 'busuk', 'tangkai', 'sampah', 'matang', 'brondolan'].forEach(k => {
        formData.append(k, document.getElementById(`sr${k.charAt(0).toUpperCase() + k.slice(1)}`).value || 0);
    });
    formData.append('catatan', document.getElementById('srCatatan').value);
    const res = await fetch('/api/sortasi/simpan', { method: 'POST', body: formData });
    const data = await res.json();
    alert(data.message || data.error);
    if (data.message) muatHistorySortasi();
}

async function muatHistorySortasi() {
    const res = await fetch('/api/history/sortasi');
    const data = await res.json();
    document.getElementById('tabelHistorySortasi').innerHTML = data.map(r => `
        <tr><td class="table-cell">${r.no_plat}</td><td class="table-cell">${r.nama_produk}</td>
        <td class="table-cell">${r.nama_supplier}</td><td class="table-cell">${r.status_val}</td></tr>
    `).join('') || `<tr><td colspan="4" class="table-cell text-center text-slate-400 py-6">Belum ada data</td></tr>`;
}