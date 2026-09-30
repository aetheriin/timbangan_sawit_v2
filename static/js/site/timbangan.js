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
    } else {
        noTiketAktif = null;
        idSupplierAktif = null;
        ['tbJenisTransaksi', 'tbSupplier', 'tbProduk'].forEach(id => document.getElementById(id).value = '');
        ['tbBruto', 'tbTara', 'tbNetto', 'tbPotongan', 'tbNettoAkhir'].forEach(id => document.getElementById(id).textContent = '-');
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
    if (data.message) muatDataTimbanganTersimpan(noTiketAktif);
}

async function muatDataTimbanganTersimpan(noTiket) {
    const res = await fetch(`/api/timbang/data/${noTiket}`);
    const data = await res.json();
    document.getElementById('tbBruto').textContent = data.berat_bruto ?? '-';
    document.getElementById('tbTara').textContent = data.berat_tara ?? '-';
    document.getElementById('tbNetto').textContent = data.berat_netto ?? '-';
    document.getElementById('tbPotongan').textContent = data.potongan_kg ?? '-';
    document.getElementById('tbNettoAkhir').textContent = data.netto_akhir ?? '-';
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
        <tr><td class="table-cell">${r.nama_supplier}</td><td class="table-cell">${r.berat_bruto ?? '-'}</td>
        <td class="table-cell">${r.berat_tara ?? '-'}</td><td class="table-cell">${r.berat_netto ?? '-'}</td></tr>
    `).join('');
}

// ===== SCAN QR TIKET =====
// Kamera (library html5-qrcode disimpan lokal di static/vendor, tidak butuh internet)
// atau scanner barcode USB (mengetik No. Tiket + Enter ke kotak input).
let qrScanner = null;
let sedangProsesScan = false;

async function bukaScanQRTimbangan() {
    const status = document.getElementById('statusScanQR');
    const input = document.getElementById('inputScanTiket');
    input.value = '';
    sedangProsesScan = false;
    openModal('modalScanQRTimbangan');
    input.focus();

    if (typeof Html5Qrcode === 'undefined') {
        status.textContent = 'Library kamera tidak termuat. Gunakan scanner barcode atau ketik No. Tiket.';
        return;
    }
    status.textContent = 'Menyalakan kamera...';
    try {
        qrScanner = new Html5Qrcode('qr-reader-timbang');
        await qrScanner.start({ facingMode: 'environment' }, { fps: 15, qrbox: 250 }, teks => prosesScanTiket(teks));
        status.textContent = 'Arahkan QR tiket ke kamera, atau gunakan scanner barcode.';
    } catch (err) {
        qrScanner = null;
        status.textContent = `Kamera tidak bisa dipakai (${err}). Gunakan scanner barcode atau ketik No. Tiket.`;
        input.focus();
    }
}

async function hentikanKameraQR() {
    if (!qrScanner) return;
    try { await qrScanner.stop(); } catch (e) { /* kamera sudah berhenti */ }
    try { qrScanner.clear(); } catch (e) { /* abaikan */ }
    qrScanner = null;
}

async function tutupScanQR() {
    await hentikanKameraQR();
    closeModal('modalScanQRTimbangan');
}

async function prosesScanTiket(teks) {
    const noTiket = (teks || '').trim().toUpperCase();
    if (!noTiket || sedangProsesScan) return;     // kamera bisa membaca QR yang sama berkali-kali
    sedangProsesScan = true;
    await tutupScanQR();
    await lookupTiket(noTiket);
}