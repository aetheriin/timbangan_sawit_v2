// ===== MUAT DATA LIST SAAT TAB SECURITY DIBUKA =====
document.addEventListener('DOMContentLoaded', muatListTicketAktif);

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
let idDriverHasilCari = null;

function mulaiValidasiAwal() {
    const wajib = ['formNoPlat', 'formNoDo', 'formJenisTransaksi', 'formSupplier', 'formProduk'];
    for (const id of wajib) {
        if (!document.getElementById(id).value.trim()) {
            alert('Lengkapi semua field di bagian 1 dulu');
            return;
        }
    }
    document.getElementById('sectionInfoDriver').classList.remove('section-disabled');

    const btn = document.getElementById('btnMulaiValidasi');
    btn.textContent = 'Sudah Validasi';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-secondary');
    btn.disabled = true;
    document.getElementById('btnCetakQR').classList.remove('hidden');
}

// ===== SCAN WAJAH (reuse pola kiosk trigger dari project sebelumnya) =====
let pollingScanWajah = null;

async function mulaiScanWajah() {
    document.getElementById('statusScanWajah').textContent = 'Menunggu kamera kiosk...';
    await fetch('/api/kamera/start', { method: 'POST' });

    if (pollingScanWajah) clearInterval(pollingScanWajah);
    pollingScanWajah = setInterval(async () => {
        const res = await fetch('/api/status-verifikasi');
        const data = await res.json();

        if (data.terverifikasi) {
            clearInterval(pollingScanWajah);
            document.getElementById('driverIdDriver').value = data.id_driver;
            document.getElementById('driverNama').value = data.nama;
            document.getElementById('driverNik').value = data.nik;
            document.getElementById('driverSim').value = data.no_sim;
            document.getElementById('statusScanWajah').textContent = 'Terverifikasi: ' + data.nama;

            if (data.is_updated) {
                document.getElementById('statusScanWajah').innerHTML += ' <span class="text-amber-600">⚠ Data Pernah Diperbarui</span>';
            }
            return;
        }

        const resKamera = await fetch('/api/kamera/status');
        const dataKamera = await resKamera.json();
        if (dataKamera.is_active === false) {
            clearInterval(pollingScanWajah);
            document.getElementById('statusScanWajah').textContent = 'Tidak dikenali. Klik "Tambah" untuk daftar baru.';
        }
    }, 1000);

    document.getElementById('fotoDriverBox').classList.add('border-emerald-500', 'border-2');
    document.getElementById('btnValidasi').classList.add('hidden');
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
        document.getElementById('driverIdDriver').value = data.id_driver;
        document.getElementById('driverNama').value = document.getElementById('tambahNama').value;
        document.getElementById('driverNik').value = document.getElementById('tambahNik').value;
        document.getElementById('driverSim').value = document.getElementById('tambahSim').value;
    }
}

async function cariSupirByNik(inputEl) {
    const nik = inputEl.value.trim();
    if (!nik) return;
    const formData = new FormData();
    formData.append('nik', nik);

    const res = await fetch('/api/driver/cari-by-nik', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.status === 'DITEMUKAN') {
        idDriverHasilCari = data.id_driver;
        document.getElementById('hasilNama').textContent = data.nama;
        document.getElementById('hasilNik').textContent = data.nik;
        document.getElementById('hasilSim').textContent = data.no_sim;
        document.getElementById('hasilBadgeUpdate').classList.toggle('hidden', !data.is_updated);
        document.getElementById('hasilCariNik').classList.remove('hidden');
        document.getElementById('tidakDitemukan').classList.add('hidden');
        document.getElementById('btnPakaiSupirIni').disabled = false;
    } else {
        document.getElementById('hasilCariNik').classList.add('hidden');
        document.getElementById('tidakDitemukan').classList.remove('hidden');
        document.getElementById('btnPakaiSupirIni').disabled = true;
    }
}

function pakaiSupirIni() {
    document.getElementById('driverIdDriver').value = idDriverHasilCari;
    document.getElementById('driverNama').value = document.getElementById('hasilNama').textContent;
    document.getElementById('driverNik').value = document.getElementById('hasilNik').textContent;
    document.getElementById('driverSim').value = document.getElementById('hasilSim').textContent;
    document.getElementById('fotoDriverBox').classList.add('border-blue-500', 'border-2'); // border biru: ganti dari riwayat
    closeModal('modalUpdateData');
}

// ===== MODAL UPDATE: toggle mode mutasi vs edit identitas =====
let modeEditIdentitas = false;

function toggleEditModeUpdate() {
    modeEditIdentitas = !modeEditIdentitas;
    ['updateNama', 'updateNik', 'updateSim'].forEach(id => {
        document.getElementById(id).readOnly = !modeEditIdentitas;
        document.getElementById(id).classList.toggle('bg-slate-50', !modeEditIdentitas);
    });
    document.getElementById('updateFotoWrapper').classList.toggle('hidden', !modeEditIdentitas);
    document.getElementById('updatePlatBaruWrapper').classList.toggle('hidden', modeEditIdentitas);
    document.getElementById('updateModeLabel').textContent = modeEditIdentitas
        ? 'Edit Identitas (akan tercatat di audit log)'
        : 'Mutasi Truk (data supir terkunci)';
}

function bukaModalUpdate() {
    document.getElementById('updateNama').value = document.getElementById('driverNama').value;
    document.getElementById('updateNik').value = document.getElementById('driverNik').value;
    document.getElementById('updateSim').value = document.getElementById('driverSim').value;
    openModal('modalUpdateData');
}

async function simpanUpdateData() {
    const idDriver = document.getElementById('driverIdDriver').value;
    const formData = new FormData();
    formData.append('id_driver', idDriver);

    if (modeEditIdentitas) {
        formData.append('nik', document.getElementById('updateNik').value.trim());
        formData.append('nama', document.getElementById('updateNama').value.trim());
        formData.append('no_sim', document.getElementById('updateSim').value.trim());
        if (streamState['updateBlob']) formData.append('foto', streamState['updateBlob'], 'capture.jpg');

        const res = await fetch('/api/driver/update-identitas', { method: 'POST', body: formData });
        const data = await res.json();
        alert(data.message || data.error);
        if (data.message) closeModal('modalUpdateData');
    } else {
        formData.append('no_plat_baru', document.getElementById('updatePlatBaru').value.trim());
        formData.append('no_tiket', document.getElementById('formNoTiket').value.trim());

        const res = await fetch('/api/driver/update-mutasi', { method: 'POST', body: formData });
        const data = await res.json();
        alert(data.message || data.error);
        if (data.message) closeModal('modalUpdateData');
    }
}

// ===== SUBMIT CREATE TICKET =====
async function submitCreateTiket() {
    const idDriver = document.getElementById('driverIdDriver').value;
    if (!idDriver) { alert('Scan wajah / pilih supir dulu'); return; }

    const formData = new FormData();
    formData.append('no_tiket', document.getElementById('formNoTiket').value.trim());
    formData.append('no_plat', document.getElementById('formNoPlat').value.trim());
    formData.append('no_stnk', document.getElementById('formNoStnk').value.trim());
    formData.append('no_do', document.getElementById('formNoDo').value.trim());
    formData.append('jenis_transaksi', document.getElementById('formJenisTransaksi').value);
    formData.append('id_supplier', document.getElementById('formSupplier').value);
    formData.append('id_produk', document.getElementById('formProduk').value);
    formData.append('id_driver', idDriver);

    const res = await fetch('/api/security/buat-tiket', { method: 'POST', body: formData });
    const data = await res.json();
    if (data.no_tiket) {
        alert(data.message);
        muatListTicketAktif();
    } else {
        alert(data.error);
    }
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