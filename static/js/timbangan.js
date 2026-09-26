let idSupplierAktif = null;
let noTiketAktif = null;

window.addEventListener('platLookup', (e) => {
    const data = e.detail;
    if (data.status === 'ADA_TIKET') {
        noTiketAktif = data.no_tiket;
        idSupplierAktif = data.id_supplier;
        document.getElementById('tbJenisTransaksi').value = data.jenis_transaksi;
        document.getElementById('tbSupplier').value = data.supplier;
        document.getElementById('tbProduk').value = data.produk;
        muatHistorySupplier(data.id_supplier);
        muatDataTimbanganTersimpan(data.no_tiket);
    }
});

setInterval(async () => {
    if (document.querySelector('.tab-btn-active').dataset.tab !== 'timbangan') return;
    const res = await fetch('/api/timbang/status');
    const data = await res.json();
    document.getElementById('beratLiveDisplay').textContent = `${data.berat} Kg`;
}, 500);

async function simpanHasilTimbangan() {
    if (!noTiketAktif) { alert('Pilih plat/tiket dulu di kolom atas'); return; }
    const formData = new FormData();
    formData.append('no_tiket', noTiketAktif);
    const res = await fetch('/api/timbang/simpan', { method: 'POST', body: formData });
    const data = await res.json();
    alert(data.message || data.error);
}

async function muatDataTimbanganTersimpan(noTiket) {
    const res = await fetch(`/api/timbang/data/${noTiket}`);
    const data = await res.json();
    document.getElementById('tbBruto').textContent = data.berat_bruto ?? '-';
    document.getElementById('tbTara').textContent = data.berat_tara ?? '-';
    document.getElementById('tbNetto').textContent = data.berat_netto ?? '-';
}

async function muatHistorySupplier(idSupplier) {
    if (!idSupplier) return;
    const res = await fetch(`/api/history-timbangan-supplier?id_supplier=${idSupplier}`);
    const data = await res.json();
    const tbody = document.getElementById('tabelHistoryTimbangan');
    if (!data.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="table-cell text-slate-400 text-center py-6">Belum ada riwayat</td></tr>`;
        return;
    }
    tbody.innerHTML = data.map(r => `
        <tr><td class="table-cell">${r.no_plat}</td><td class="table-cell">${r.berat_bruto ?? '-'}</td>
        <td class="table-cell">${r.berat_tara ?? '-'}</td><td class="table-cell">${r.berat_netto ?? '-'}</td></tr>
    `).join('');
}

let qrScanner = null;
async function bukaScanQRTimbangan() {
    openModal('modalScanQRTimbangan');
    qrScanner = new Html5Qrcode("qr-reader-timbang");
    await qrScanner.start({ facingMode: "environment" }, { fps: 15, qrbox: 250 }, async (decodedText) => {
        await qrScanner.stop();
        closeModal('modalScanQRTimbangan');
        document.getElementById('infoPlat').value = '';
        const formData = new FormData();
        formData.append('no_tiket', decodedText.trim());
        const res = await fetch('/api/timbang/scan-qr', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.status === 'ADA_TIKET') window.dispatchEvent(new CustomEvent('platLookup', { detail: data }));
        else alert(data.error || 'Tiket tidak ditemukan');
    });
}