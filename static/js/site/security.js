// Pengaturan site dari server (.env WAJIB_SCAN_WAJAH), dikirim lewat <meta> di weighbridge.html
const WAJIB_SCAN_WAJAH = document.querySelector('meta[name="wajib-scan-wajah"]')?.content !== 'false';

document.addEventListener('DOMContentLoaded', () => aturStatusForm('draft'));

// ===== SINKRON FORM DENGAN HASIL LOOKUP PLAT =====
let saranDriver = null;

function badgeStatusPersonel(isBlacklisted) {
    return isBlacklisted ? badge('BLACKLIST', WARNA_BADGE.merah) : badge('Aktif', WARNA_BADGE.hijau);
}

// ===== PERINGATAN BLACKLIST (kendaraan dan / atau supir) =====
// Blacklist berlaku di semua area: banner menyebut siapa yang diblacklist dan siapa / area mana yang menetapkan.
const blacklistForm = { kendaraan: null, supir: null };     // { siapa, info: hasil /api/blacklist/info }

function aturBlacklist(jenis, data) {
    blacklistForm[jenis] = data;
    const isi = ['kendaraan', 'supir'].filter(j => blacklistForm[j]);
    const banner = document.getElementById('bannerBlacklist');
    banner.classList.toggle('hidden', !isi.length);
    banner.classList.toggle('flex', isi.length > 0);
    document.getElementById('formNoPlat').classList.toggle('border-red-500', !!blacklistForm.kendaraan);
    document.getElementById('bannerBlacklistIsi').innerHTML = isi.map(j => {
        const { siapa, info } = blacklistForm[j];
        const penetap = info && info.oleh ? `oleh ${escapeHtml(info.oleh)}${info.area_oleh ? ` (${escapeHtml(info.area_oleh)})` : ''}` : '';
        return `<div class="text-sm">
            <p class="font-semibold text-red-700">${j === 'kendaraan' ? 'Kendaraan' : 'Supir'}: ${escapeHtml(siapa)}</p>
            <p class="text-xs text-slate-700">${info && info.no_surat_blacklist ? `No. surat ${escapeHtml(info.no_surat_blacklist)} · ` : ''}` +
            `${info && info.tgl_blacklist ? `ditetapkan ${escapeHtml(info.tgl_blacklist)} ` : ''}${penetap} · berlaku di semua area · permanen` +
            `${info && info.file_surat_blacklist ? ` · <a href="${escapeHtml(urlBerkas(info.file_surat_blacklist))}" target="_blank" class="underline text-red-700">Lihat surat</a>` : ''}</p>
        </div>`;
    }).join('');
}

async function aturBlacklistSupir(dr) {
    if (!dr || !dr.is_blacklisted) { aturBlacklist('supir', null); return; }
    const siapa = formatNamaPersonel(dr.kode_personel, dr.id_driver, dr.nama);
    aturBlacklist('supir', { siapa, info: null });
    const info = await ambilJson(`/api/blacklist/info/PERSONEL/${dr.id_driver}`);
    if (blacklistForm.supir && blacklistForm.supir.siapa === siapa && !info.error) aturBlacklist('supir', { siapa, info });
}

function kotakMerah(el, aktif) {
    el.classList.toggle('ring-4', aktif);
    el.classList.toggle('ring-red-600', aktif);
}

function tampilkanPengemudiTerakhir(dr, utama = null) {
    const info = document.getElementById('pengemudiTerakhirInfo');
    const foto = document.getElementById('pengemudiFotoBox');
    const kartu = document.getElementById('pengemudiKartu');
    kotakMerah(foto, !!(dr && dr.is_blacklisted));
    kartu.classList.toggle('border-red-500', !!(dr && dr.is_blacklisted));
    kartu.classList.toggle('bg-red-50', !!(dr && dr.is_blacklisted));
    kartu.classList.toggle('bg-slate-50', !(dr && dr.is_blacklisted));
    const barisUtama = utama && (!dr || String(utama.id_driver) !== String(dr.id_driver))
        ? `<p class="text-xs text-blue-600">Supir utama: ${escapeHtml(utama.nama)}</p>` : '';
    if (!dr) {
        info.innerHTML = 'Belum ada riwayat' + barisUtama;
        foto.innerHTML = '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
        return;
    }
    info.innerHTML = `<p class="text-xs text-slate-500">${escapeHtml(dr.kode_personel || 'Belum ada kode')} · ID ${formatIdPersonel(dr.id_driver)}</p>` +
        `<p class="font-semibold text-slate-700">${escapeHtml(dr.nama)}</p><p>NIK: ${escapeHtml(dr.nik)}</p>` +
        (dr.is_blacklisted ? '<p class="mt-1"><span class="px-2 py-0.5 rounded bg-red-600 text-white text-xs font-bold">BLACKLIST</span></p>' : '') +
        (dr.is_updated ? '<p class="text-amber-600 text-xs">⚠ Data Pernah Diperbarui</p>' : '') + barisUtama;
    foto.innerHTML = dr.foto_path
        ? `<img src="${escapeHtml(urlBerkas(dr.foto_path))}" class="w-full h-full object-cover" alt="">`
        : '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
}

// ===== STATUS FORM PENDAFTARAN TIKET =====
let statusForm = 'draft';
let supirTerverifikasi = false;
// Jenis / customer / produk terisi otomatis dari DO tetapi tetap bisa diubah (tanpa DO diisi sendiri)
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
                                            : 'Scan wajah tidak diwajibkan di site ini.';
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
    kotakMerah(document.getElementById('fotoDriverBox'), false);
    document.getElementById('driverBadgeUpdate').classList.add('hidden');
    aturBlacklist('supir', null);
    supirTerverifikasi = false;
    aturStatusForm('draft');
}

function tandaiSudahValidasi() {
    supirTerverifikasi = true;
    aturStatusForm('selesai');
}

// ===== DO (Delivery Order, diisi HO di menu Kontrak & DO) =====
// Ada DO -> jenis transaksi, customer, produk terisi otomatis (tetap bisa diubah). Tidak ada -> isi sendiri.
let kontrakAktif = [];                 // kontrak truk (modal Update -> Kontrak Truk), hanya informasi
let doTerakhir = '';

function sinkronKontrakKeForm(listAktif) {
    kontrakAktif = listAktif;
}

function teksPilihan(id) {
    const sel = document.getElementById(id);
    return sel.value ? sel.options[sel.selectedIndex].text : '';
}

// Info bar mengikuti isian form (dari DO maupun diisi sendiri)
function sinkronInfoBarForm() {
    document.getElementById('infoNoDO').value = document.getElementById('formNoDo').value.trim().toUpperCase();
    document.getElementById('infoSupplier').value = teksPilihan('formSupplier');
    document.getElementById('infoProduk').value = teksPilihan('formProduk');
    const jenis = document.getElementById('formJenisTransaksi').value;
    document.getElementById('infoJenis').value = jenis ? labelKode(jenis) : '';
}
['formJenisTransaksi', 'formSupplier', 'formProduk']
    .forEach(id => document.getElementById(id).addEventListener('change', sinkronInfoBarForm));

function isiDariDO(d) {
    if (d) document.getElementById('formNoDo').value = d.no_do;
    document.getElementById('formJenisTransaksi').value = d ? d.jenis_transaksi : '';
    document.getElementById('formSupplier').value = d ? d.id_customer : '';
    document.getElementById('formProduk').value = d ? d.id_produk : '';
    sinkronInfoBarForm();
}

async function cariDO(noDo, diam = false) {
    noDo = (noDo || '').trim().toUpperCase();
    const info = document.getElementById('infoDO');
    if (!noDo) return;
    doTerakhir = noDo;
    const d = await ambilJson(`/api/do/${encodeURIComponent(noDo)}`);
    if (d.error) {                      // DO belum ada dari HO: isian yang sudah ada dibiarkan, diisi sendiri
        info.className = 'text-xs mt-1 text-amber-600';
        info.textContent = `No DO ${noDo} belum ada dari HO / tidak aktif. Isi jenis transaksi, customer, dan produk sendiri.`;
        sinkronInfoBarForm();
        return;
    }
    if (!diam) isiDariDO(d);
    info.className = 'text-xs mt-1 text-emerald-600';
    info.textContent = `✓ DO dari HO (kontrak ${d.no_kontrak}): ${d.nama_customer} · ${d.nama_produk}` +
        (d.berlaku_sampai ? ` · berlaku s/d ${d.berlaku_sampai}` : '') + '. Masih bisa diubah.';
}

// Lupa menekan Tab: DO juga dicari saat kotak ditinggalkan
document.getElementById('formNoDo').addEventListener('blur', e => {
    const v = e.target.value.trim().toUpperCase();
    if (v && v !== doTerakhir && !e.target.disabled) cariDO(v);
    if (!v) document.getElementById('infoDO').classList.add('hidden');
});
document.getElementById('formNoDo').addEventListener('input', () => { doTerakhir = ''; sinkronInfoBarForm(); });

window.addEventListener('platLookup', (e) => {
    const d = e.detail;
    if (!['ADA_TIKET', 'DRAFT'].includes(d.status)) return;

    document.getElementById('formNoPlat').value = d.no_plat;
    document.getElementById('formNoTiket').value = d.no_tiket || d.no_tiket_reserved || '';
    document.getElementById('formNoStnk').value = d.no_stnk || '';
    tampilkanPengemudiTerakhir(d.driver, d.driver_utama);
    aturBlacklist('kendaraan', d.kendaraan_blacklist && d.status !== 'ADA_TIKET'
        ? { siapa: d.no_plat, info: d.kendaraan_blacklist } : null);

    if (d.status === 'ADA_TIKET') {
        document.getElementById('formNoDo').value = d.no_do || '';
        document.getElementById('formJenisTransaksi').value = d.jenis_transaksi;
        document.getElementById('formSupplier').value = d.id_supplier;
        document.getElementById('formProduk').value = d.id_produk;
        sinkronInfoBarForm();
        if (d.no_do) cariDO(d.no_do, true);             // keterangan DO saja, isian tiket tidak ditimpa
        if (d.driver) isiDriver(d.driver);
        tandaiSudahValidasi();
        document.getElementById('btnCetakQR').classList.remove('hidden');
    } else {
        resetValidasiForm();
        saranDriver = d.driver_utama || d.driver;   // supir utama (menu Update Truk) didahulukan
        kontrakAktif = d.kontrak_aktif || [];
        isiDariDO(null);
        document.getElementById('formNoDo').value = '';
        document.getElementById('infoDO').classList.add('hidden');
    }
    // Tiket yang sudah ada: tanpa banner (sama seperti kendaraan). Draft: supir terakhir / utama blacklist ikut diperingatkan
    aturBlacklistSupir(d.status === 'ADA_TIKET' ? null : [d.driver_utama, d.driver].find(x => x && x.is_blacklisted) || null);
});

// ===== VALIDASI AWAL (buka section Informasi Driver) =====
function mulaiValidasiAwal() {
    const wajib = ['formNoPlat', 'formNoTiket', 'formNoStnk', 'formJenisTransaksi', 'formSupplier', 'formProduk'];
    for (const id of wajib) {
        if (!document.getElementById(id).value.trim()) {
            Notif.peringatan('Lengkapi plat, No. STNK, jenis transaksi, customer, dan produk (No DO + Tab mengisi otomatis).');
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

// ===== SCAN WAJAH SUPIR (webcam browser di PC Security) =====
// Tantangan wajib / tidak diatur per area (Admin › Pengaturan Site › TANTANGAN_SECURITY).
let scanWajahBerjalan = false;

function selesaiScanWajah(pesan) {
    scanWajahBerjalan = false;
    Kamera.stop();
    document.getElementById('videoScanWajah').classList.add('hidden');
    document.getElementById('fotoDriverBox').classList.remove('hidden');
    document.getElementById('instruksiScanWajah').classList.add('hidden');
    document.getElementById('btnScanWajah').disabled = statusForm !== 'validasi';
    if (pesan) document.getElementById('statusScanWajah').textContent = pesan;
}

async function mulaiScanWajah() {
    if (scanWajahBerjalan) return;
    const status = document.getElementById('statusScanWajah');
    const video = document.getElementById('videoScanWajah');
    const instruksi = document.getElementById('instruksiScanWajah');
    scanWajahBerjalan = true;
    document.getElementById('btnScanWajah').disabled = true;
    status.textContent = 'Menyalakan kamera...';
    try {
        await Kamera.mulai(video);
    } catch (err) {
        selesaiScanWajah(window.isSecureContext
            ? 'Kamera tidak bisa dibuka. Izinkan akses kamera di browser.'
            : 'Kamera diblokir browser karena alamat bukan HTTPS / localhost (lihat Dokumentasi: kamera browser).');
        return;
    }
    document.getElementById('fotoDriverBox').classList.add('hidden');
    video.classList.remove('hidden');
    instruksi.classList.remove('hidden');
    status.textContent = 'Minta supir menghadap kamera.';

    const { security: wajib } = await aturanTantangan();
    const hasil = await rekamWajah(video, {
        wajib,
        tampil: (teks, angka) => { instruksi.textContent = angka ? `${teks} (${angka})` : teks; },
        batal: () => !scanWajahBerjalan || statusForm !== 'validasi',
    });
    if (!hasil) { selesaiScanWajah('Scan dibatalkan.'); return; }
    instruksi.textContent = 'Memproses...';
    const formData = new FormData();
    hasil.frames.forEach((blob, i) => formData.append('frames', blob, `frame${i}.jpg`));
    formData.append('tantangan', hasil.tantangan);
    hasil.frames.length = 0;
    selesaiScanWajah('Memproses wajah...');
    document.getElementById('btnScanWajah').disabled = true;

    const data = await kirimForm('/api/security/scan-wajah', formData, { timeout: TIMEOUT_WAJAH_MS });
    document.getElementById('btnScanWajah').disabled = statusForm !== 'validasi';
    if (data.error && !data.terverifikasi) {
        status.innerHTML = `<span class="text-red-600">${escapeHtml(data.error)}</span>`;
        return;
    }
    terapkanHasilScanWajah(data);
}

function terapkanHasilScanWajah(data) {
    const status = document.getElementById('statusScanWajah');
    const nama = formatNamaPersonel(data.kode_personel, data.id_driver, data.nama);
    if (data.is_blacklisted) Notif.peringatan(`${nama} masuk daftar blacklist`);   // banner diisi isiDriver()
    if (data.kategori && data.kategori !== 'DRIVER') {
        status.innerHTML = `<span class="text-red-600">${escapeHtml(nama)} terdaftar sebagai ${escapeHtml((LABEL_KATEGORI[data.kategori] || [labelKode(data.kategori)])[0])}, bukan supir.</span>`;
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
    document.getElementById('tambahKode').value = '';
    openModal('modalTambahSupir');
    ambilJson('/api/personel/saran-kode?kategori=DRIVER').then(s => { if (s.kode) document.getElementById('tambahKode').value = s.kode; });
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
        isiDriver({ id_driver: data.id_driver, kode_personel: data.kode_personel, nik: document.getElementById('tambahNik').value.trim(),
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
    const kenaBlacklist = ['kendaraan', 'supir'].filter(j => blacklistForm[j]).map(j => blacklistForm[j].siapa);
    if (kenaBlacklist.length && !await Dialog.konfirmasi({
        judul: 'Masuk daftar blacklist', teksYa: 'Tetap buat tiket', teksBatal: 'Batal', bahaya: true,
        pesan: `${kenaBlacklist.join(' dan ')} masuk daftar blacklist. Tetap buat tiket? Tercatat di Audit Log.` })) return;

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
    document.getElementById('driverKode').placeholder = dr.kode_personel ? '' : 'Belum ada kode';
    document.getElementById('driverStatusBadge').innerHTML = badgeStatusPersonel(dr.is_blacklisted);
    document.getElementById('driverNama').value = dr.nama;
    document.getElementById('driverNik').value = dr.nik;
    document.getElementById('driverSim').value = dr.no_sim;
    document.getElementById('fotoDriverBox').innerHTML = dr.foto_path
        ? `<img src="${escapeHtml(urlBerkas(dr.foto_path))}" class="w-full h-full object-cover" alt="">`
        : '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';
    document.getElementById('driverBadgeUpdate').classList.toggle('hidden', !dr.is_updated);
    kotakMerah(document.getElementById('fotoDriverBox'), !!dr.is_blacklisted);
    aturBlacklistSupir(dr);
}

// ===== CETAK QR =====
// Tombol Cetak QR di Form (setelah tiket dibuat)
function cetakQRDariForm() {
    openCetakQRDariTabel(document.getElementById('formNoPlat').value);
}

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
        document.getElementById('qrStatus').textContent = labelStatusTiket(data.status_alur);

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