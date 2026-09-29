// ===== MUAT DATA LIST SAAT TAB SECURITY DIBUKA =====
document.addEventListener('DOMContentLoaded', () => {
    muatListTicketAktif();
    muatHistoryDriver();
});

async function muatHistoryDriver() {
    const res = await fetch('/api/security/history-driver');
    const data = await res.json();
    document.getElementById('tabelHistoryDriver').innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${r.no_plat}</td><td class="table-cell">${r.nama_driver}</td>
            <td class="table-cell">${r.nik}</td><td class="table-cell">${r.no_sim}</td>
        </tr>`).join('') || `<tr><td colspan="4" class="table-cell text-slate-400 text-center py-8">Belum ada riwayat</td></tr>`;
}

// ===== SINKRON FORM DENGAN HASIL LOOKUP PLAT =====
let saranDriver = null;

function tampilkanPengemudiTerakhir(dr) {
    const info = document.getElementById('pengemudiTerakhirInfo');
    const foto = document.getElementById('pengemudiFotoBox');
    if (!dr) {
        info.textContent = 'Belum ada riwayat';
        foto.innerHTML = '<i class="fa-solid fa-user text-slate-300"></i>';
        return;
    }
    info.innerHTML = `<p class="font-semibold text-slate-700">${dr.nama}</p><p>NIK: ${dr.nik}</p>` +
        (dr.is_updated ? '<p class="text-amber-600 text-xs">⚠ Data Pernah Diperbarui</p>' : '');
    foto.innerHTML = dr.foto_path
        ? `<img src="/static/${dr.foto_path}" class="w-full h-full object-cover">`
        : '<i class="fa-solid fa-user text-slate-300"></i>';
}

function resetValidasiForm() {
    saranDriver = null;
    document.getElementById('sectionInfoDriver').classList.add('section-disabled');
    ['driverIdDriver', 'driverNama', 'driverNik', 'driverSim'].forEach(id => document.getElementById(id).value = '');
    const btn = document.getElementById('btnMulaiValidasi');
    btn.textContent = 'Mulai Validasi Awal';
    btn.disabled = false;
    btn.classList.add('btn-primary');
    btn.classList.remove('btn-secondary');
    document.getElementById('btnCetakQR').classList.add('hidden');
    tandaiBorderDriver(null);
    document.getElementById('driverBadgeUpdate').classList.add('hidden');
}

function tandaiSudahValidasi() {
    document.getElementById('sectionInfoDriver').classList.remove('section-disabled');
    const btn = document.getElementById('btnMulaiValidasi');
    btn.textContent = 'Sudah Validasi';
    btn.disabled = true;
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-secondary');
    document.getElementById('btnCetakQR').classList.remove('hidden');
}

window.addEventListener('platLookup', (e) => {
    const d = e.detail;
    if (d.status !== 'ADA_TIKET' && d.status !== 'DRAFT') return;

    document.getElementById('formNoPlat').value = d.no_plat;
    document.getElementById('formNoTiket').value = d.no_tiket || d.no_tiket_reserved || '';
    document.getElementById('formNoStnk').value = d.no_stnk || '';
    tampilkanPengemudiTerakhir(d.driver);

    if (d.status === 'ADA_TIKET') {
        document.getElementById('formNoDo').value = d.no_do || '';
        document.getElementById('formJenisTransaksi').value = d.jenis_transaksi;
        document.getElementById('formSupplier').value = d.id_supplier;
        document.getElementById('formProduk').value = d.id_produk;
        if (d.driver) isiDriver(d.driver);
        tandaiSudahValidasi();
    } else {
        resetValidasiForm();       // DO/Supplier/Produk tetap manual (dropdown)
        saranDriver = d.driver;
    }
});

async function muatListTicketAktif() {
    const res = await fetch('/api/security/list-tiket-aktif');
    const data = await res.json();

    const tbody = document.getElementById('tabelTicketAktif');
    if (!data.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="table-cell text-slate-400 text-center py-8">Belum ada tiket aktif</td></tr>`;
        return;
    }

    tbody.innerHTML = data.map(t => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell font-mono text-xs">${t.no_tiket}</td>
            <td class="table-cell">${t.no_plat}</td>
            <td class="table-cell">${t.supplier}</td>
            <td class="table-cell"><span class="badge-status bg-amber-100 text-amber-700">${t.status_alur}</span></td>
            <td class="table-cell text-right space-x-2">
                <button onclick="bukaFormDariTabel('${t.no_plat}')" class="text-blue-600 hover:underline text-xs">Buka</button>
                <button onclick="openCetakQRDariTabel('${t.no_plat}')" class="text-emerald-600 hover:underline text-xs">Cetak QR</button>
            </td>
        </tr>
    `).join('');
}

// ===== VALIDASI AWAL (buka section Informasi Driver) =====
function mulaiValidasiAwal() {
    const wajib = ['formNoPlat', 'formNoTiket', 'formJenisTransaksi', 'formSupplier', 'formProduk'];
    for (const id of wajib) {
        if (!document.getElementById(id).value.trim()) {
            alert('Lengkapi plat (tekan Tab), jenis transaksi, supplier, dan produk dulu');
            return;
        }
    }
    tandaiSudahValidasi();
    if (saranDriver) isiDriver(saranDriver);   // saran supir dari riwayat, readonly
}

// ===== SCAN WAJAH (reuse pola kiosk trigger dari project sebelumnya) =====
// ===== SCAN WAJAH =====
let pollingScanWajah = null;

async function mulaiScanWajah() {
    const status = document.getElementById('statusScanWajah');
    const btn = document.getElementById('btnScanWajah');
    btn.disabled = true;
    status.textContent = 'Menunggu kamera kiosk... minta supir menghadap kamera.';
    await fetch('/api/kamera/start', { method: 'POST' });

    const cekVerifikasi = async () => (await fetch('/api/status-verifikasi')).json();

    if (pollingScanWajah) clearInterval(pollingScanWajah);
    pollingScanWajah = setInterval(async () => {
        let data = await cekVerifikasi();

        if (!data.terverifikasi) {
            const kamera = await (await fetch('/api/kamera/status')).json();
            if (kamera.is_active) return;            // kiosk masih bekerja
            data = await cekVerifikasi();            // cek ulang supaya tidak kalah cepat dengan server
            if (!data.terverifikasi) {
                clearInterval(pollingScanWajah);
                btn.disabled = false;
                status.textContent = 'Tidak dikenali atau dibatalkan. Klik "Tambah" untuk daftar supir baru.';
                return;
            }
        }

        clearInterval(pollingScanWajah);
        btn.disabled = false;

        const dipilih = document.getElementById('driverIdDriver').value;
        if (dipilih && String(dipilih) !== String(data.id_driver)) {
            status.innerHTML = `<span class="text-red-600">Wajah terbaca sebagai <b>${data.nama}</b>, tidak cocok dengan supir terpilih. Pilih supir yang benar lewat "Update", lalu scan ulang.</span>`;
            return;
        }
        isiDriver(data);
        tandaiBorderDriver('hijau');
        status.textContent = 'Terverifikasi: ' + data.nama;
    }, 1000);
}


// ===== REKAM WAJAH SEDERHANA (modal Tambah/Update) =====
const streamState = {};

async function toggleRekamWajah(konteks) {
    const btn = document.getElementById(`btnRekam${konteks === 'tambah' ? 'Tambah' : 'Update'}`);
    const video = document.getElementById(`${konteks}Video`);
    const canvas = document.getElementById(`${konteks}Canvas`);
    const preview = document.getElementById(`${konteks}FotoPreview`);

    if (btn.textContent.trim() === 'Rekam Wajah') {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        streamState[konteks] = stream;
        video.srcObject = stream;
        video.classList.remove('hidden');
        preview.classList.add('hidden');
        btn.textContent = 'Ambil Foto';
    } else {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        canvas.toBlob(blob => {
            streamState[`${konteks}Blob`] = blob;
            const url = URL.createObjectURL(blob);
            preview.innerHTML = `<img src="${url}" class="w-full h-full object-cover rounded-full">`;
            preview.classList.remove('hidden');
        }, 'image/jpeg');

        streamState[konteks].getTracks().forEach(t => t.stop());
        video.classList.add('hidden');
        btn.textContent = 'Rekam Wajah';
    }
}

// ===== SIMPAN SUPIR BARU =====
async function simpanSupirBaru() {
    const formData = new FormData();
    formData.append('nama', document.getElementById('tambahNama').value.trim());
    formData.append('nik', document.getElementById('tambahNik').value.trim());
    formData.append('no_sim', document.getElementById('tambahSim').value.trim());
    if (streamState['tambahBlob']) {
        formData.append('foto', streamState['tambahBlob'], 'capture.jpg');
    }

    const res = await fetch('/api/driver/tambah', { method: 'POST', body: formData });
    const data = await res.json();
    alert(data.message || data.error);
    if (data.message) {
        closeModal('modalTambahSupir');
        isiDriver({ id_driver: data.id_driver, nik: document.getElementById('tambahNik').value.trim(),
                    nama: document.getElementById('tambahNama').value.trim(),
                    no_sim: document.getElementById('tambahSim').value.trim(),
                    is_updated: false, foto_path: data.foto_path });
        tandaiBorderDriver('hijau');
    }
}

// ===== MODAL UPDATE =====
function bukaModalUpdate() {
    document.getElementById('cariNik').value = '';
    document.getElementById('hasilCariNik').classList.add('hidden');
    document.getElementById('tidakDitemukan').classList.add('hidden');
    document.getElementById('btnPakaiSupirIni').disabled = true;
    driverHasilCari = null;

    const id = document.getElementById('driverIdDriver').value;
    document.getElementById('updateNama').value = document.getElementById('driverNama').value;
    document.getElementById('updateNik').value = document.getElementById('driverNik').value;
    document.getElementById('updateSim').value = document.getElementById('driverSim').value;
    document.getElementById('editTanpaDriver').classList.toggle('hidden', !!id);
    document.getElementById('btnSimpanEdit').disabled = !id;
    resetFotoUpdate();

    setModeUpdate('cari');
    openModal('modalUpdateData');
}

function setModeUpdate(mode) {
    document.getElementById('tabModeCari').className = 'modal-tab ' + (mode === 'cari' ? 'modal-tab-active' : '');
    document.getElementById('tabModeEdit').className = 'modal-tab ' + (mode === 'edit' ? 'modal-tab-active' : '');
    document.getElementById('panelModeCari').classList.toggle('hidden', mode !== 'cari');
    document.getElementById('panelModeEdit').classList.toggle('hidden', mode !== 'edit');
}

function resetFotoUpdate() {
    if (streamState['update']) {
        streamState['update'].getTracks().forEach(t => t.stop());
        streamState['update'] = null;
    }
    streamState['updateBlob'] = null;
    document.getElementById('updateVideo').classList.add('hidden');
    const preview = document.getElementById('updateFotoPreview');
    preview.classList.remove('hidden');
    preview.innerHTML = '<i class="fa-solid fa-camera text-slate-300 text-2xl"></i>';
    document.getElementById('btnRekamUpdate').textContent = 'Rekam Wajah';
}

function tutupModalUpdate() {
    resetFotoUpdate();
    closeModal('modalUpdateData');
}

// --- mode Ganti Supir ---
let driverHasilCari = null;

async function cariSupirByNik(inputEl) {
    const nik = inputEl.value.trim();
    if (!nik) return;
    const formData = new FormData();
    formData.append('nik', nik);
    const data = await (await fetch('/api/driver/cari-by-nik', { method: 'POST', body: formData })).json();

    if (data.status === 'DITEMUKAN') {
        driverHasilCari = { id_driver: data.id_driver, nik: data.nik, nama: data.nama,
                            no_sim: data.no_sim, is_updated: data.is_updated, foto_path: data.foto_path };
        document.getElementById('hasilNama').textContent = data.nama;
        document.getElementById('hasilNik').textContent = data.nik;
        document.getElementById('hasilSim').textContent = data.no_sim;
        document.getElementById('hasilBadgeUpdate').classList.toggle('hidden', !data.is_updated);
        document.getElementById('hasilCariNik').classList.remove('hidden');
        document.getElementById('tidakDitemukan').classList.add('hidden');
        document.getElementById('btnPakaiSupirIni').disabled = false;
    } else {
        driverHasilCari = null;
        document.getElementById('hasilCariNik').classList.add('hidden');
        document.getElementById('tidakDitemukan').classList.remove('hidden');
        document.getElementById('btnPakaiSupirIni').disabled = true;
    }
}

function pakaiSupirIni() {
    if (!driverHasilCari) return;
    isiDriver(driverHasilCari);
    tandaiBorderDriver('biru');      // biru = supir diganti dari riwayat, wajib scan wajah ulang
    document.getElementById('statusScanWajah').textContent = 'Supir diganti. Lakukan scan wajah untuk verifikasi.';
    tutupModalUpdate();
}

// --- mode Edit Data Diri / SIM ---
async function simpanEditIdentitas() {
    const idDriver = document.getElementById('driverIdDriver').value;
    if (!idDriver) return;

    const nama = document.getElementById('updateNama').value.trim();
    const nik = document.getElementById('updateNik').value.trim();
    const sim = document.getElementById('updateSim').value.trim();
    if (!nama || !nik || !sim) { alert('Nama, NIK, dan SIM wajib diisi'); return; }

    const berubah = nama !== document.getElementById('driverNama').value
        || nik !== document.getElementById('driverNik').value
        || sim !== document.getElementById('driverSim').value
        || streamState['updateBlob'];
    if (!berubah) { alert('Tidak ada perubahan untuk disimpan'); return; }
    if (!confirm('Perubahan identitas tercatat permanen di audit log. Lanjutkan?')) return;

    const formData = new FormData();
    formData.append('id_driver', idDriver);
    formData.append('nama', nama);
    formData.append('nik', nik);
    formData.append('no_sim', sim);
    if (streamState['updateBlob']) formData.append('foto', streamState['updateBlob'], 'capture.jpg');

    const data = await (await fetch('/api/driver/update-identitas', { method: 'POST', body: formData })).json();
    if (!data.driver) { alert(data.error); return; }

    alert(data.message);
    isiDriver(data.driver);
    document.getElementById('infoSupir').value = data.driver.nama;
    tampilkanFotoDriver(data.driver.foto_path);
    tampilkanPengemudiTerakhir(data.driver);
    tutupModalUpdate();
}

// ===== SUBMIT CREATE TICKET =====
async function submitCreateTiket() {
    const idDriver = document.getElementById('driverIdDriver').value;
    if (!idDriver) { alert('Scan wajah / pilih supir dulu'); return; }

    const formData = new FormData();
    ['no_tiket:formNoTiket', 'no_plat:formNoPlat', 'no_stnk:formNoStnk', 'no_do:formNoDo',
     'jenis_transaksi:formJenisTransaksi', 'id_supplier:formSupplier', 'id_produk:formProduk']
        .forEach(p => { const [k, id] = p.split(':'); formData.append(k, document.getElementById(id).value.trim()); });
    formData.append('id_driver', idDriver);

    const res = await fetch('/api/security/buat-tiket', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.no_tiket) {
        alert(data.message);
        muatListTicketAktif();
        muatHistoryDriver();
        lookupPlat(document.getElementById('formNoPlat').value);  // base bar jadi ADA_TIKET lengkap
    } else {
        alert(data.error);
    }
}

// ===== TAMPILAN DRIVER (Section 2) =====
function tandaiBorderDriver(warna) {   // 'biru' | 'hijau' | null
    const box = document.getElementById('fotoDriverBox');
    box.classList.remove('border-blue-500', 'border-emerald-500', 'border-slate-300', 'border-dashed', 'border-solid');
    if (warna === 'biru') box.classList.add('border-blue-500', 'border-solid');
    else if (warna === 'hijau') box.classList.add('border-emerald-500', 'border-solid');
    else box.classList.add('border-slate-300', 'border-dashed');
}

function isiDriver(dr) {
    document.getElementById('driverIdDriver').value = dr.id_driver;
    document.getElementById('driverNama').value = dr.nama;
    document.getElementById('driverNik').value = dr.nik;
    document.getElementById('driverSim').value = dr.no_sim;
    document.getElementById('fotoDriverBox').innerHTML = dr.foto_path
        ? `<img src="/static/${dr.foto_path}" class="w-full h-full object-cover">`
        : '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
    document.getElementById('driverBadgeUpdate').classList.toggle('hidden', !dr.is_updated);
}

// ===== CETAK QR =====
function openCetakQRDariTabel(noPlat) {
    document.getElementById('qrNoPlat').value = noPlat;
    lookupPlatUntukQR(document.getElementById('qrNoPlat'));
    openModal('modalCetakQR');
}

async function lookupPlatUntukQR(inputEl) {
    const noPlat = inputEl.value.trim().toUpperCase();
    const formData = new FormData();
    formData.append('no_plat', noPlat);

    const res = await fetch('/api/plat/lookup', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.status === 'ADA_TIKET') {
        document.getElementById('qrNama').textContent = data.driver.nama;
        document.getElementById('qrNik').textContent = data.driver.nik;
        document.getElementById('qrSim').textContent = data.driver.no_sim;
        document.getElementById('qrStnk').textContent = data.no_stnk || '-';
        document.getElementById('qrStatus').textContent = data.status_alur;

        document.getElementById('printAreaQR').classList.remove('hidden');
        document.getElementById('qrTiketText').textContent = data.no_tiket;

        const container = document.getElementById('qrcodeContainer');
        container.innerHTML = '';
        new QRCode(container, { text: data.no_tiket, width: 150, height: 150 });
    } else {
        alert('Plat tidak ditemukan / belum ada tiket aktif');
    }
}

function cetakQR() {
    window.print();
}