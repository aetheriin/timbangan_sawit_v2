let idSupplierAktif = null;
let noTiketAktif = null;

window.addEventListener('platLookup', (e) => {
    const data = e.detail;
    if (data.status === 'ADA_TIKET') {
        noTiketAktif = data.no_tiket;
        idSupplierAktif = data.id_supplier;
        document.getElementById('tbJenisTransaksi').value = labelKode(data.jenis_transaksi);
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

// ===== BERAT LIVE =====
// Polling berurutan (tidak menumpuk), hanya saat tab Timbangan dibuka dan tab browser terlihat.
const pollingBerat = new Poller(async () => {
    const r = await Api.get('/api/timbang/status', { timeout: 3000, polling: true });
    const el = document.getElementById('beratLiveDisplay');
    const st = r.data && r.data.berat !== undefined ? r.data : null;     // status putus tetap berisi data + sebabnya
    const putus = !st || !st.terhubung;
    el.textContent = st ? `${st.berat} Kg` : '— Kg';
    el.classList.toggle('opacity-40', putus);          // koneksi timbangan / server terputus
    // Status: putus (dengan sebab), di bawah berat minimum, bergerak, atau stabil siap disimpan
    const ket = document.getElementById('statusBeratLive');
    const [teks, warna] = !st ? ['Server tidak menjawab', 'text-red-400']
        : putus ? [`Tidak terhubung: ${st.error || 'cek kabel / agen timbangan'}`, 'text-red-400']
        : st.berat_min_kg && st.berat < st.berat_min_kg ? [`Kosong (di bawah ${st.berat_min_kg} kg)`, 'text-slate-400']
        : st.siap_kunci ? ['● Stabil, siap disimpan', 'text-emerald-400'] : ['○ Bergerak, tunggu stabil', 'text-amber-400'];
    ket.textContent = teks;
    ket.className = `text-sm mt-3 ${warna}`;
}, 500);

window.addEventListener('tabChange', e => {
    if (e.detail === 'timbangan') pollingBerat.start();
    else pollingBerat.stop();
});

async function simpanHasilTimbangan(btn) {
    if (!noTiketAktif) { Notif.peringatan('Pilih plat/tiket dulu di kolom atas'); return; }
    const data = await denganTombol(btn, () => kirimForm('/api/timbang/simpan', { no_tiket: noTiketAktif }));
    if (tampilkanHasil(data)) muatDataTimbanganTersimpan(noTiketAktif);
    const lebih = data.kelebihan_do;
    if (lebih) {          // DO melewati kuota: kelebihan jadi tiket baru (truk sama), KTU / HO sudah dinotifikasi
        const angka = v => Number(v).toLocaleString('id-ID');
        Dialog.konfirmasi({ judul: `DO ${lebih.no_do} melebihi kuota`, teksYa: 'Buka Kelebihan DO', teksBatal: 'Tutup',
            pesan: `Kuota ${angka(lebih.kuota_kg)} kg, realisasi ${angka(lebih.realisasi_kg)} kg.\n` +
                   `Kelebihan ${angka(lebih.kelebihan_kg)} kg menjadi tiket ${lebih.tiket_split} (truk yang sama).\n` +
                   'Isi No. DO baru dari Ascend di menu Kelebihan DO.' })
            .then(ok => { if (ok) window.location.href = '/kelebihan-do'; });
    }
}

async function muatDataTimbanganTersimpan(noTiket) {
    const data = await ambilJson(`/api/timbang/data/${encodeURIComponent(noTiket)}`);
    if (data.error) { Notif.gagal(data.error); return; }
    document.getElementById('tbBruto').textContent = data.berat_bruto ?? '-';
    document.getElementById('tbTara').textContent = data.berat_tara ?? '-';
    document.getElementById('tbNetto').textContent = data.berat_netto ?? '-';
    document.getElementById('tbPotongan').textContent = data.potongan_kg ?? '-';
    document.getElementById('tbNettoAkhir').textContent = data.netto_akhir ?? '-';
    const info = document.getElementById('tbJembatanMasuk');
    info.classList.toggle('hidden', !data.jembatan_masuk);
    info.textContent = data.jembatan_masuk ? `Timbang masuk di ${data.jembatan_masuk}. Timbang keluar harus di jembatan yang sama.` : '';
}

// Jembatan timbang PC ini: disimpan di cookie (1 tahun), dibaca server saat status berat & simpan timbang
function pilihJembatanTimbang(id) {
    if (!id) return;
    document.cookie = `jembatan_timbang=${encodeURIComponent(id)}; path=/; max-age=31536000; SameSite=Lax`;
    const opsi = document.querySelector(`#pilihJembatan option[value="${CSS.escape(id)}"]`);
    Notif.sukses(`PC ini memakai ${opsi ? opsi.textContent : 'jembatan ' + id}`);
}

// History: default 7 hari terakhir, atau satu tanggal dalam 30 hari terakhir
const HARI_HISTORY_MAKS = 30;
let idSupplierHistory = null;

function tanggalLokal(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

(function aturBatasTanggalTimbang() {
    const input = document.getElementById('filterTanggalTimbang');
    const hari = new Date();
    input.max = tanggalLokal(hari);
    hari.setDate(hari.getDate() - (HARI_HISTORY_MAKS - 1));
    input.min = tanggalLokal(hari);
})();

function resetTanggalTimbang() {
    document.getElementById('filterTanggalTimbang').value = '';
    muatHistoryTimbanganUlang();
}

function muatHistoryTimbanganUlang() {
    muatHistorySupplier(idSupplierHistory);
}

async function muatHistorySupplier(idSupplier) {
    if (!idSupplier) return;
    idSupplierHistory = idSupplier;
    const input = document.getElementById('filterTanggalTimbang');
    let tanggal = input.value;
    if (tanggal && (tanggal < input.min || tanggal > input.max)) {
        Notif.peringatan(`Tanggal hanya bisa dipilih ${HARI_HISTORY_MAKS} hari terakhir`);
        input.value = tanggal = '';
    }
    document.getElementById('keteranganHistoryTimbang').textContent =
        tanggal ? `Menampilkan tanggal ${tanggal}` : 'Menampilkan 7 hari terakhir';
    const url = `/api/history-timbangan-supplier?id_supplier=${encodeURIComponent(idSupplier)}` +
                (tanggal ? `&tanggal=${tanggal}` : '');
    const data = await ambilJson(url);
    const tbody = document.getElementById('tabelHistoryTimbangan');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    if (!data.length) {
        tbody.innerHTML = barisKosong(6, tanggal ? `Belum ada riwayat pada ${tanggal}` : 'Belum ada riwayat 7 hari terakhir');
        return;
    }
    tbody.innerHTML = data.map(r => `
        <tr><td class="table-cell whitespace-nowrap text-xs">${escapeHtml(r.created_at || '-')}</td><td class="table-cell">${escapeHtml(r.no_plat)}</td>
        <td class="table-cell">${escapeHtml(r.nama_supplier)}</td><td class="table-cell">${escapeHtml(r.berat_bruto ?? '-')}</td>
        <td class="table-cell">${escapeHtml(r.berat_tara ?? '-')}</td><td class="table-cell">${escapeHtml(r.berat_netto ?? '-')}</td></tr>
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

// Tombol "Cari Tiket" (sama dengan menekan Enter di kotak No. Tiket)
function kirimScanTiket() {
    const input = document.getElementById('inputScanTiket');
    if (!input.value.trim()) {
        Notif.peringatan('Ketik atau scan No. Tiket dulu');
        input.focus();
        return;
    }
    prosesScanTiket(input.value);
}

async function prosesScanTiket(teks) {
    const noTiket = (teks || '').trim().toUpperCase();
    if (!noTiket || sedangProsesScan) return;     // kamera bisa membaca QR yang sama berkali-kali
    sedangProsesScan = true;
    await tutupScanQR();
    await lookupTiket(noTiket);
}