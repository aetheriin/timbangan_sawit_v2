let noTiketSortasiAktif = null;
let beratAcuanSortasi = null;   // netto; null = belum timbang kedua

window.addEventListener('platLookup', (e) => {
    const data = e.detail;
    // Tiket lain (PKS / belum ada tiket) -> kosongkan, supaya sortasi tidak tersimpan ke tiket sebelumnya
    noTiketSortasiAktif = null;
    beratAcuanSortasi = null;
    document.getElementById('srBeratAcuan').textContent = '-';
    hitungPotongan();
    if (data.status === 'ADA_TIKET' && data.kategori_produk === 'TBS') {
        noTiketSortasiAktif = data.no_tiket;
        ambilJson(`/api/timbang/data/${data.no_tiket}`).then(tb => {
            if (tb.error) { Notif.gagal(tb.error); return; }
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

async function submitSortasi(btn) {
    if (!noTiketSortasiAktif) { Notif.peringatan('Pilih plat/tiket dulu'); return; }
    const formData = new FormData();
    formData.append('no_tiket', noTiketSortasiAktif);
    ['mentah', 'busuk', 'tangkai', 'sampah', 'matang', 'brondolan'].forEach(k => {
        formData.append(k, document.getElementById(`sr${k.charAt(0).toUpperCase() + k.slice(1)}`).value || 0);
    });
    formData.append('catatan', document.getElementById('srCatatan').value);
    const data = await denganTombol(btn, () => kirimForm('/api/sortasi/simpan', formData));
    if (tampilkanHasil(data)) muatHistorySortasi();
}

async function muatHistorySortasi() {
    const data = await ambilJson('/api/history/sortasi');
    const tbody = document.getElementById('tabelHistorySortasi');
    if (data.error) { tbody.innerHTML = barisKosong(4, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr><td class="table-cell">${escapeHtml(r.no_plat)}</td><td class="table-cell">${escapeHtml(r.nama_produk)}</td>
        <td class="table-cell">${escapeHtml(r.nama_supplier)}</td><td class="table-cell">${escapeHtml(r.status_val)}</td></tr>
    `).join('') || barisKosong(4, 'Belum ada data');
}