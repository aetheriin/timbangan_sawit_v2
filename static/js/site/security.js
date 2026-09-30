// ===== MUAT DATA LIST SAAT TAB SECURITY DIBUKA =====
document.addEventListener('DOMContentLoaded', () => {
    aturStatusForm('draft');
    muatListTicketAktif();
    muatHistoryDriver();
});

async function muatHistoryDriver() {
    const data = await ambilJson('/api/security/history-driver');
    const tbody = document.getElementById('tabelHistoryDriver');
    if (data.error) { tbody.innerHTML = barisKosong(7, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${escapeHtml(r.no_plat)}</td>
            <td class="table-cell">${formatIdPersonel(r.id_driver)}</td>
            <td class="table-cell">${kodeAtauKosong(r.kode_personel)}</td>
            <td class="table-cell">${escapeHtml(r.nama_driver)}</td>
            <td class="table-cell">${escapeHtml(r.nik)}</td><td class="table-cell">${escapeHtml(r.no_sim || '-')}</td>
            <td class="table-cell">${badgeStatusPersonel(r.is_blacklisted)}</td>
        </tr>`).join('') || barisKosong(7, 'Belum ada riwayat');
    saringTabel(document.getElementById('searchTiket').value);
}

// ===== SEARCH: saring List Ticket Aktif & History Driver =====
function saringTabel(kata) {
    const cari = kata.toUpperCase().replace(/\s+/g, '');       // "bm1455" cocok dengan "BM 1455 JJ"
    ['tabelTicketAktif', 'tabelHistoryDriver'].forEach(id => {
        document.querySelectorAll(`#${id} tr`).forEach(tr => {
            if (tr.children.length < 2) return;                 // baris "belum ada data"
            tr.classList.toggle('hidden', !!cari && !tr.textContent.toUpperCase().replace(/\s+/g, '').includes(cari));
        });
    });
}

// ===== SINKRON FORM DENGAN HASIL LOOKUP PLAT =====
let saranDriver = null;

function badgeStatusPersonel(isBlacklisted) {
    return isBlacklisted ? badge('BLACKLIST', WARNA_BADGE.merah) : badge('Aktif', WARNA_BADGE.hijau);
}

// Banner merah di atas form: info = { judul, detail, file } atau null untuk menyembunyikan
function tampilkanBannerBlacklist(info) {
    const banner = document.getElementById('bannerBlacklist');
    banner.classList.toggle('hidden', !info);
    banner.classList.toggle('flex', !!info);
    document.getElementById('formNoPlat').classList.toggle('border-red-500', !!info);
    if (!info) return;
    document.getElementById('bannerBlacklistJudul').textContent = info.judul;
    document.getElementById('bannerBlacklistDetail').textContent = info.detail || '';
    const surat = document.getElementById('bannerBlacklistSurat');
    surat.classList.toggle('hidden', !info.file);
    if (info.file) surat.href = urlBerkas(info.file);
}

function infoBlacklistKendaraan(noPlat, bl) {
    return {
        judul: `PERINGATAN: KENDARAAN ${noPlat} MASUK BLACKLIST`,
        detail: `No. surat ${bl.no_surat_blacklist} · ditetapkan ${bl.tgl_blacklist} oleh ${bl.oleh} · permanen. ` +
                'Tiket tetap bisa dibuat, dan tercatat di Audit Log untuk HO.',
        file: bl.file_surat_blacklist,
    };
}

function tampilkanPengemudiTerakhir(dr, utama = null) {
    const info = document.getElementById('pengemudiTerakhirInfo');
    const foto = document.getElementById('pengemudiFotoBox');
    const barisUtama = utama && (!dr || String(utama.id_driver) !== String(dr.id_driver))
        ? `<p class="text-xs text-blue-600">Supir utama: ${escapeHtml(utama.nama)}</p>` : '';
    if (!dr) {
        info.innerHTML = 'Belum ada riwayat' + barisUtama;
        foto.innerHTML = '<i class="fa-solid fa-user text-slate-300"></i>';
        return;
    }
    info.innerHTML = `<p class="text-xs text-slate-500">${escapeHtml(dr.kode_personel || 'belum ada kode')} · ID ${formatIdPersonel(dr.id_driver)}</p>` +
        `<p class="font-semibold text-slate-700">${escapeHtml(dr.nama)}</p><p>NIK: ${escapeHtml(dr.nik)}</p>` +
        (dr.is_blacklisted ? `<p>${badge('BLACKLIST', WARNA_BADGE.merah)}</p>` : '') +
        (dr.is_updated ? '<p class="text-amber-600 text-xs">⚠ Data Pernah Diperbarui</p>' : '') + barisUtama;
    foto.innerHTML = dr.foto_path
        ? `<img src="${escapeHtml(urlBerkas(dr.foto_path))}" class="w-full h-full object-cover" alt="">`
        : '<i class="fa-solid fa-user text-slate-300"></i>';
}

// ===== STATUS FORM PENDAFTARAN TIKET =====
// draft    : isi data kendaraan, tombol "Mulai Validasi Awal" aktif
// validasi : data kendaraan dikunci, tombol validasi beku, Informasi Driver aktif (scan wajah -> Submit)
// selesai  : tiket sudah dibuat, tombol berubah jadi "Sudah Validasi"
let statusForm = 'draft';
let supirTerverifikasi = false;
const FIELD_KENDARAAN = ['formNoPlat', 'formNoStnk', 'formNoDo', 'formJenisTransaksi', 'formSupplier', 'formProduk'];

// blacklist: plat masuk blacklist, hanya kolom plat yang bisa diganti
function aturStatusForm(status) {
    statusForm = status;
    FIELD_KENDARAAN.forEach(id => {
        document.getElementById(id).disabled = status !== 'draft';
    });
    document.getElementById('sectionInfoDriver').classList.toggle('section-disabled', status === 'draft');

    const btn = document.getElementById('btnMulaiValidasi');
    const beku = status === 'validasi';      // beku sampai scan wajah + Submit
    btn.textContent = status === 'selesai' ? 'Sudah Validasi' : 'Mulai Validasi Awal';
    btn.disabled = status !== 'draft';
    btn.classList.toggle('btn-primary', status !== 'selesai');
    btn.classList.toggle('btn-secondary', status === 'selesai');
    btn.classList.toggle('opacity-60', beku);
    btn.classList.toggle('cursor-not-allowed', beku);

    ['btnTambahSupir', 'btnUpdateSupir', 'btnScanWajah']
        .forEach(id => document.getElementById(id).disabled = status !== 'validasi');
    document.getElementById('btnCetakQR').classList.toggle('hidden', status !== 'selesai');
    perbaruiTombolSubmit();
}

function perbaruiTombolSubmit() {
    const adaSupir = !!document.getElementById('driverIdDriver').value;
    const siap = statusForm === 'validasi' && adaSupir && (supirTerverifikasi || !WAJIB_SCAN_WAJAH);
    document.getElementById('btnSubmitTiket').disabled = !siap;

    let hint = '';
    if (statusForm === 'selesai') hint = 'Tiket sudah dibuat. Gunakan tombol Cetak QR Code di atas.';
    else if (statusForm === 'validasi' && !adaSupir) hint = 'Pilih supir: Mulai Scan Wajah, Tambah (supir baru), atau Update.';
    else if (statusForm === 'validasi' && !siap) hint = 'Scan wajah supir dulu, setelah terverifikasi tombol Submit aktif.';
    else if (siap) hint = supirTerverifikasi ? 'Supir terverifikasi. Klik Submit untuk membuat tiket.'
                                            : 'Scan wajah tidak diwajibkan (WAJIB_SCAN_WAJAH=false).';
    document.getElementById('hintSubmit').textContent = hint;
}

function setSupirTerverifikasi(ok) {
    supirTerverifikasi = ok;
    perbaruiTombolSubmit();
}

function resetValidasiForm() {
    saranDriver = null;
    ['driverIdDriver', 'driverIdTampil', 'driverKode', 'driverNama', 'driverNik', 'driverSim']
        .forEach(id => document.getElementById(id).value = '');
    document.getElementById('driverStatusBadge').innerHTML = '';
    document.getElementById('fotoDriverBox').innerHTML = '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
    document.getElementById('statusScanWajah').textContent = '';
    tandaiBorderDriver(null);
    document.getElementById('driverBadgeUpdate').classList.add('hidden');
    supirTerverifikasi = false;
    aturStatusForm('draft');
}

function tandaiSudahValidasi() {
    supirTerverifikasi = true;
    aturStatusForm('selesai');
}

// ===== KONTRAK AKTIF TRUK (diatur di modal Update -> Kontrak Truk) =====
let kontrakAktif = [];

function tampilkanInfoKontrak() {
    const el = document.getElementById('infoKontrak');
    el.classList.toggle('hidden', !kontrakAktif.length);
    el.textContent = kontrakAktif.length
        ? 'Kontrak aktif: ' + kontrakAktif.map(k => k.nama_supplier + (k.no_kontrak ? ` (${k.no_kontrak})` : '')).join(', ')
        : '';
}

// Dipanggil setelah kontrak diubah di modal Update
function sinkronKontrakKeForm(listAktif) {
    kontrakAktif = listAktif;
    tampilkanInfoKontrak();
}

// Supplier dipilih -> kalau ada kontrak aktif dengan supplier itu, isi produk & jenis dari kontrak
function terapkanKontrak(idSupplier) {
    const k = kontrakAktif.find(x => String(x.id_supplier) === String(idSupplier));
    if (!k) return;
    if (k.id_produk) document.getElementById('formProduk').value = k.id_produk;
    if (k.jenis_transaksi) document.getElementById('formJenisTransaksi').value = k.jenis_transaksi;
}

window.addEventListener('platLookup', (e) => {
    const d = e.detail;
    if (!['ADA_TIKET', 'DRAFT'].includes(d.status)) return;

    document.getElementById('formNoPlat').value = d.no_plat;
    document.getElementById('formNoTiket').value = d.no_tiket || d.no_tiket_reserved || '';
    document.getElementById('formNoStnk').value = d.no_stnk || '';
    tampilkanPengemudiTerakhir(d.driver, d.driver_utama);
    tampilkanBannerBlacklist(d.kendaraan_blacklist && d.status !== 'ADA_TIKET'
        ? infoBlacklistKendaraan(d.no_plat, d.kendaraan_blacklist) : null);

    if (d.status === 'ADA_TIKET') {
        kontrakAktif = [];
        document.getElementById('formNoDo').value = d.no_do || '';
        document.getElementById('formJenisTransaksi').value = d.jenis_transaksi;
        document.getElementById('formSupplier').value = d.id_supplier;
        document.getElementById('formProduk').value = d.id_produk;
        if (d.driver) isiDriver(d.driver);
        tandaiSudahValidasi();
        document.getElementById('btnCetakQR').classList.remove('hidden');
    } else {
        resetValidasiForm();
        saranDriver = d.driver_utama || d.driver;   // supir utama (menu Update Truk) didahulukan
        kontrakAktif = d.kontrak_aktif || [];
        if (kontrakAktif.length) {                 // isi otomatis dari kontrak terbaru, tetap bisa diganti
            document.getElementById('formSupplier').value = kontrakAktif[0].id_supplier;
            terapkanKontrak(kontrakAktif[0].id_supplier);
        }
    }
    tampilkanInfoKontrak();
});

async function muatListTicketAktif() {
    const data = await ambilJson('/api/security/list-tiket-aktif');
    const tbody = document.getElementById('tabelTicketAktif');
    if (data.error) { tbody.innerHTML = barisKosong(5, data.error); return; }
    if (!data.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="table-cell text-slate-400 text-center py-8">Belum ada tiket aktif</td></tr>`;
        return;
    }

    tbody.innerHTML = data.map(t => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell font-mono text-xs">${escapeHtml(t.no_tiket)}</td>
            <td class="table-cell">${escapeHtml(t.no_plat)}</td>
            <td class="table-cell">${escapeHtml(t.supplier)}</td>
            <td class="table-cell"><span class="badge-status bg-amber-100 text-amber-700">${escapeHtml(t.status_alur)}</span></td>
            <td class="table-cell text-right space-x-2">
                <button type="button" data-plat="${escapeHtml(t.no_plat)}" onclick="bukaFormDariTabel(this.dataset.plat)" class="text-blue-600 hover:underline text-xs">Buka</button>
                <button type="button" data-plat="${escapeHtml(t.no_plat)}" onclick="openCetakQRDariTabel(this.dataset.plat)" class="text-emerald-600 hover:underline text-xs">Cetak QR</button>
            </td>
        </tr>
    `).join('');
    saringTabel(document.getElementById('searchTiket').value);
}

// ===== VALIDASI AWAL (buka section Informasi Driver) =====
function mulaiValidasiAwal() {
    const wajib = ['formNoPlat', 'formNoTiket', 'formJenisTransaksi', 'formSupplier', 'formProduk'];
    for (const id of wajib) {
        if (!document.getElementById(id).value.trim()) {
            Notif.peringatan('Lengkapi plat (tekan Tab), jenis transaksi, supplier, dan produk dulu');
            return;
        }
    }
    supirTerverifikasi = false;
    aturStatusForm('validasi');
    if (saranDriver) {                          // saran supir (utama / terakhir), tetap wajib scan wajah
        isiDriver(saranDriver);
        tandaiBorderDriver('biru');
        document.getElementById('statusScanWajah').textContent = 'Saran supir truk ini. Lakukan scan wajah untuk verifikasi.';
    }
    perbaruiTombolSubmit();
}

// ===== SCAN WAJAH (reuse pola kiosk trigger dari project sebelumnya) =====
// ===== SCAN WAJAH (kamera kiosk) =====
// Polling berurutan tiap 1 detik, maksimal 90 detik, berhenti saat form ditinggal.
const BATAS_SCAN_WAJAH_MS = 90000;
let pollingScanWajah = null;

function hentikanScanWajah(pesan) {
    if (pollingScanWajah) pollingScanWajah.stop();
    pollingScanWajah = null;
    document.getElementById('btnScanWajah').disabled = statusForm !== 'validasi';
    if (pesan) document.getElementById('statusScanWajah').textContent = pesan;
}

async function mulaiScanWajah() {
    const status = document.getElementById('statusScanWajah');
    const btn = document.getElementById('btnScanWajah');
    const mulai = await kirimForm('/api/kamera/start', {});
    if (mulai.error) { Notif.gagal(mulai.error); return; }
    btn.disabled = true;
    status.textContent = 'Menunggu kamera kiosk... minta supir menghadap kamera.';

    if (pollingScanWajah) pollingScanWajah.stop();
    pollingScanWajah = new Poller(async () => {
        let data = await ambilJson('/api/status-verifikasi', { timeout: 5000, polling: true });
        if (data.error) return;                      // coba lagi di putaran berikutnya
        if (!data.terverifikasi) {
            const kamera = await ambilJson('/api/kamera/status', { timeout: 5000, polling: true });
            if (kamera.error || kamera.is_active) return;     // kiosk masih bekerja
            data = await ambilJson('/api/status-verifikasi', { timeout: 5000, polling: true });   // cek ulang supaya tidak kalah cepat
            if (!data.terverifikasi) {
                hentikanScanWajah('Tidak dikenali atau dibatalkan. Klik "Tambah" untuk daftar supir baru.');
                return;
            }
        }
        hentikanScanWajah();
        terapkanHasilScanWajah(data);
    }, 1000, {
        aktif: () => statusForm === 'validasi',
        maksDurasiMs: BATAS_SCAN_WAJAH_MS,
        onHabis: () => {
            hentikanScanWajah('Waktu scan habis. Klik "Mulai Scan Wajah" untuk mencoba lagi.');
            kirimForm('/api/kamera/batal', {});
        },
    });
    pollingScanWajah.start();
}

function terapkanHasilScanWajah(data) {
    const status = document.getElementById('statusScanWajah');
    const nama = formatNamaPersonel(data.kode_personel, data.id_driver, data.nama);
    if (data.is_blacklisted) {
        // Blacklist = peringatan: supir tetap terverifikasi, tiket tetap bisa dibuat (tercatat di Audit Log)
        tampilkanBannerBlacklist({ judul: `PERINGATAN: SUPIR ${nama} MASUK BLACKLIST`,
            detail: 'Tiket tetap bisa dibuat, dan tercatat di Audit Log (TRY_SCAN_BLACKLIST) untuk HO.' });
        Notif.peringatan(`${nama} masuk daftar blacklist`);
    }
    if (data.kategori && data.kategori !== 'DRIVER') {
        status.innerHTML = `<span class="text-red-600">${escapeHtml(nama)} terdaftar sebagai ${escapeHtml(data.kategori)}, bukan supir.</span>`;
        return;
    }
    const dipilih = document.getElementById('driverIdDriver').value;
    if (dipilih && String(dipilih) !== String(data.id_driver)) {
        status.innerHTML = `<span class="text-red-600">Wajah terbaca sebagai <b>${escapeHtml(nama)}</b>, tidak cocok dengan supir terpilih. Pilih supir yang benar lewat "Update", lalu scan ulang.</span>`;
        return;
    }
    isiDriver(data);
    tandaiBorderDriver('hijau');
    status.textContent = 'Terverifikasi: ' + nama;
    setSupirTerverifikasi(true);
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
// Modal yang sama dipakai dari form tiket ('tiket') dan dari menu Update Truk ('kendaraan')
let konteksTambahSupir = 'tiket';

function bukaTambahSupir(konteks) {
    konteksTambahSupir = konteks;
    if (konteks === 'kendaraan') {
        if (!pastikanTrukDipilih()) return;
        tutupModalUpdate();                            // modal Tambah dibuka di atas, Update dibuka lagi setelah simpan
    }
    ['tambahNama', 'tambahNik', 'tambahSim'].forEach(id => document.getElementById(id).value = '');
    streamState['tambahBlob'] = null;
    document.getElementById('tambahFotoPreview').innerHTML = '<i class="fa-solid fa-camera text-slate-300 text-2xl"></i>';
    openModal('modalTambahSupir');
}

async function simpanSupirBaru(btn) {
    const formData = new FormData();
    formData.append('nama', document.getElementById('tambahNama').value.trim());
    formData.append('nik', document.getElementById('tambahNik').value.trim());
    formData.append('no_sim', document.getElementById('tambahSim').value.trim());
    if (streamState['tambahBlob']) {
        formData.append('foto', streamState['tambahBlob'], 'capture.jpg');
    }

    const data = await denganTombol(btn, () => kirimForm('/api/driver/tambah', formData, { timeout: TIMEOUT_WAJAH_MS }),
                                    'Memeriksa wajah...');
    if (tampilkanHasil(data)) {
        closeModal('modalTambahSupir');
        if (konteksTambahSupir === 'kendaraan') {      // dari modal Update -> tab Supir Truk
            await daftarkanSupirKeTruk(data.id_driver);
            openModal('modalUpdateData');
            setModeUpdate('truk');
            return;
        }
        isiDriver({ id_driver: data.id_driver, nik: document.getElementById('tambahNik').value.trim(),
                    nama: document.getElementById('tambahNama').value.trim(),
                    no_sim: document.getElementById('tambahSim').value.trim(),
                    is_updated: false, foto_path: data.foto_path });
        tandaiBorderDriver('hijau');                   // wajah baru saja direkam -> terverifikasi
        document.getElementById('statusScanWajah').textContent = 'Supir baru terdaftar & terverifikasi: ' + data.message;
        setSupirTerverifikasi(true);
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
    document.getElementById('updJudulPlat').textContent = '';
    muatDataKendaraan(document.getElementById('formNoPlat').value);   // untuk tab Supir Truk & Kontrak Truk
    openModal('modalUpdateData');
}

const MODE_UPDATE = { cari: 'Cari', edit: 'Edit', truk: 'Truk', kontrak: 'Kontrak' };

function setModeUpdate(mode) {
    Object.entries(MODE_UPDATE).forEach(([m, nama]) => {
        document.getElementById(`tabMode${nama}`).className = 'modal-tab ' + (m === mode ? 'modal-tab-active' : '');
        document.getElementById(`panelMode${nama}`).classList.toggle('hidden', m !== mode);
    });
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
    const data = await kirimForm('/api/driver/cari-by-nik', { nik });
    if (data.error) { Notif.gagal(data.error); return; }

    if (data.status === 'DITEMUKAN') {
        driverHasilCari = data;             // id_driver, kode_personel, nik, nama, no_sim, is_blacklisted, ...
        document.getElementById('hasilNama').textContent = formatNamaPersonel(data.kode_personel, data.id_driver, data.nama);
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
    if (driverHasilCari) gantiSupirTiket(driverHasilCari);
}

// Ganti supir untuk tiket ini (dari Cari NIK atau daftar Supir Truk). Wajib scan wajah ulang.
function gantiSupirTiket(dr) {
    isiDriver(dr);
    tandaiBorderDriver('biru');      // biru = supir dipilih manual, belum terverifikasi wajah
    document.getElementById('statusScanWajah').textContent = 'Supir diganti. Lakukan scan wajah untuk verifikasi.';
    setSupirTerverifikasi(false);
    tutupModalUpdate();
}

// --- mode Edit Data Diri / SIM ---
async function simpanEditIdentitas(btn) {
    const idDriver = document.getElementById('driverIdDriver').value;
    if (!idDriver) return;

    const nama = document.getElementById('updateNama').value.trim();
    const nik = document.getElementById('updateNik').value.trim();
    const sim = document.getElementById('updateSim').value.trim();
    if (!nama || !nik || !sim) { Notif.peringatan('Nama, NIK, dan SIM wajib diisi'); return; }

    const berubah = nama !== document.getElementById('driverNama').value
        || nik !== document.getElementById('driverNik').value
        || sim !== document.getElementById('driverSim').value
        || streamState['updateBlob'];
    if (!berubah) { Notif.info('Tidak ada perubahan untuk disimpan'); return; }
    const ok = await Dialog.konfirmasi({ judul: 'Simpan perubahan identitas?', teksYa: 'Simpan',
        pesan: 'Perubahan identitas supir tercatat permanen di Audit Log dan supir ditandai "Pernah Diperbarui".' });
    if (!ok) return;

    const formData = new FormData();
    formData.append('id_driver', idDriver);
    formData.append('nama', nama);
    formData.append('nik', nik);
    formData.append('no_sim', sim);
    if (streamState['updateBlob']) formData.append('foto', streamState['updateBlob'], 'capture.jpg');

    const data = await denganTombol(btn, () => kirimForm('/api/driver/update-identitas', formData, { timeout: TIMEOUT_WAJAH_MS }));
    if (!data.driver) { Notif.gagal(data.error || 'Gagal menyimpan perubahan'); return; }

    Notif.sukses(data.message);
    isiDriver(data.driver);
    perbaruiTombolSubmit();
    document.getElementById('infoSupir').value = data.driver.nama;
    tampilkanFotoDriver(data.driver.foto_path);
    tampilkanPengemudiTerakhir(data.driver);
    tutupModalUpdate();
}

// ===== SUBMIT CREATE TICKET =====
async function submitCreateTiket(btn) {
    const idDriver = document.getElementById('driverIdDriver').value;
    if (!idDriver) { Notif.peringatan('Scan wajah / pilih supir dulu'); return; }

    const formData = new FormData();
    ['no_tiket:formNoTiket', 'no_plat:formNoPlat', 'no_stnk:formNoStnk', 'no_do:formNoDo',
     'jenis_transaksi:formJenisTransaksi', 'id_supplier:formSupplier', 'id_produk:formProduk']
        .forEach(p => { const [k, id] = p.split(':'); formData.append(k, document.getElementById(id).value.trim()); });
    formData.append('id_driver', idDriver);
    if (saranDriver) formData.append('id_driver_saran', saranDriver.id_driver);   // beda supir -> OVERRIDE_DRIVER

    const data = await denganTombol(btn, () => kirimForm('/api/security/buat-tiket', formData), 'Membuat tiket...');
    perbaruiTombolSubmit();                  // kembalikan status aktif/nonaktif tombol Submit
    if (!data.no_tiket) { Notif.gagal(data.error || 'Tiket gagal dibuat'); return; }

    Notif.sukses(data.message);
    muatListTicketAktif();
    muatHistoryDriver();
    lookupPlat(document.getElementById('formNoPlat').value);  // base bar jadi ADA_TIKET lengkap
    const cetak = await Dialog.konfirmasi({ judul: 'Tiket berhasil dibuat', teksYa: 'Cetak QR', teksBatal: 'Nanti',
        pesan: `No. tiket ${data.no_tiket}. Cetak QR tiket sekarang?` });
    if (cetak) bukaHalamanCetak(data.no_tiket);
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
    document.getElementById('driverIdTampil').value = formatIdPersonel(dr.id_driver);
    document.getElementById('driverKode').value = dr.kode_personel || '';
    document.getElementById('driverKode').placeholder = dr.kode_personel ? '' : '— belum ada kode';
    document.getElementById('driverStatusBadge').innerHTML = badgeStatusPersonel(dr.is_blacklisted);
    document.getElementById('driverNama').value = dr.nama;
    document.getElementById('driverNik').value = dr.nik;
    document.getElementById('driverSim').value = dr.no_sim;
    document.getElementById('fotoDriverBox').innerHTML = dr.foto_path
        ? `<img src="${escapeHtml(urlBerkas(dr.foto_path))}" class="w-full h-full object-cover" alt="">`
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
    const data = await kirimForm('/api/plat/lookup', { no_plat: noPlat });
    if (data.error) { Notif.gagal(data.error); return; }
    if (data.status === 'ADA_TIKET') {
        inputEl.value = data.no_plat;
        document.getElementById('qrNama').textContent = data.driver.nama;
        document.getElementById('qrNik').textContent = data.driver.nik;
        document.getElementById('qrSim').textContent = data.driver.no_sim;
        document.getElementById('qrStnk').textContent = data.no_stnk || '-';
        document.getElementById('qrStatus').textContent = data.status_alur;

        document.getElementById('printAreaQR').classList.remove('hidden');
        document.getElementById('qrTiketText').textContent = data.no_tiket;
        // QR dibuat di server (tidak butuh internet / CDN)
        document.getElementById('qrcodeContainer').innerHTML =
            `<img src="/api/qr/${encodeURIComponent(data.no_tiket)}" alt="QR ${escapeHtml(data.no_tiket)}" width="150" height="150">`;
        qrTiketAktif = data.no_tiket;
    } else {
        qrTiketAktif = null;
        document.getElementById('printAreaQR').classList.add('hidden');
        Notif.peringatan('Plat tidak ditemukan / belum ada tiket aktif');
    }
}

let qrTiketAktif = null;

function bukaHalamanCetak(noTiket) {
    const w = window.open(`/cetak/tiket/${encodeURIComponent(noTiket)}`, '_blank', 'width=420,height=720');
    if (!w) Notif.peringatan('Pop-up diblokir browser. Izinkan pop-up untuk alamat ini, lalu klik Cetak QR lagi.');
}

function cetakQR() {
    if (!qrTiketAktif) { Notif.peringatan('Ketik plat lalu tekan Tab dulu'); return; }
    bukaHalamanCetak(qrTiketAktif);
}