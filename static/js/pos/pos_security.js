// ===== POS SECURITY (tahap 1): kendaraan masuk tanpa tiket timbang =====
// Plat -> /api/pos/cek-plat (kendaraan, blacklist, supir terakhir, masih di dalam). Supir dari scan wajah
// (/api/security/scan-wajah), supir baru, atau cari NIK. Simpan Masuk -> /api/pos/masuk (jam masuk = waktu simpan).
const POS = { plat: '', kendaraan: null, terakhir: null, dalam: null, supir: null, terverifikasi: false };
const WAJIB_SCAN = document.getElementById('posSecurity').dataset.wajibScan === '1';
const JENIS_DARI_KATEGORI = { TBS: 'PEMBELIAN', PRODUK_PKS: 'PENJUALAN' };
const FOTO = {};                      // foto modal: { psb: {stream, blob}, pus: {...} }

document.addEventListener('DOMContentLoaded', () => {
    const jam = () => { document.getElementById('jamSekarang').textContent = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }); };
    jam(); setInterval(jam, 15000);
    document.getElementById('posProduk').addEventListener('change', e => {
        const kategori = e.target.selectedOptions[0]?.dataset.kategori;
        if (kategori) document.getElementById('posJenisTrx').value = JENIS_DARI_KATEGORI[kategori] || '';
        ringkasPos();
    });
    ['posCustomer', 'posJenisTrx', 'posAngkut', 'posStnk'].forEach(id => document.getElementById(id).addEventListener('change', ringkasPos));
    document.getElementById('posPlat').addEventListener('input', e => {
        if (POS.plat && e.target.value.replace(/\s+/g, '').toUpperCase() !== POS.plat.replace(/\s+/g, '')) lepasPlat();
    });
    kosongkanPos();
});

const fmtWaktu = s => s ? `${s.slice(8, 10)}-${s.slice(5, 7)}-${s.slice(0, 4)} ${s.slice(11, 16)}` : '-';
const teksPilihan = id => { const o = document.getElementById(id).selectedOptions[0]; return o && o.value ? o.textContent.trim() : ''; };
const namaSupir = d => formatNamaPersonel(d.kode_personel, d.id_driver, d.nama);

function lamaSejak(teks) {
    const menit = Math.max(0, Math.floor((Date.now() - new Date(teks.replace(' ', 'T'))) / 60000));
    return `${Math.floor(menit / 60)} jam ${menit % 60} menit`;
}

// ===== PLAT =====
async function cekPlatPos() {
    const input = document.getElementById('posPlat');
    if (!input.value.trim()) { input.focus(); return; }
    const d = await kirimForm('/api/pos/cek-plat', { no_plat: input.value });
    if (d.error) { Notif.gagal(d.error); return; }
    input.value = d.no_plat;
    Object.assign(POS, { plat: d.no_plat, kendaraan: d.kendaraan, terakhir: d.terakhir, dalam: d.di_dalam });
    const stnk = document.getElementById('posStnk');
    if (d.kendaraan && d.kendaraan.no_stnk) stnk.value = d.kendaraan.no_stnk;
    document.getElementById('posJenis').value = (d.kendaraan && d.kendaraan.jenis) || '';
    document.getElementById('badgePlat').innerHTML = d.kendaraan && d.kendaraan.blacklist
        ? '<span class="badge-status bg-red-600 text-white"><i class="fa-solid fa-ban mr-1"></i>BLACKLIST</span>'
        : d.di_dalam ? '<span class="badge-status bg-amber-100 text-amber-800">Masih di dalam</span>'
        : d.kendaraan ? '' : '<span class="badge-status bg-blue-100 text-blue-700">Kendaraan baru</span>';
    tampilTerakhir();
    perbarui();
    (stnk.value ? document.getElementById('posCustomer') : stnk).focus();
}

function lepasPlat() {
    Object.assign(POS, { plat: '', kendaraan: null, terakhir: null, dalam: null });
    document.getElementById('posJenis').value = '';
    document.getElementById('badgePlat').innerHTML = '';
    tampilTerakhir();
    perbarui();
}

function tampilTerakhir() {
    const t = POS.terakhir;
    const el = document.getElementById('supirTerakhir');
    if (!t) {
        el.innerHTML = `<p class="text-sm text-slate-400">${POS.plat ? 'Belum ada riwayat masuk untuk truk ini.' : 'Ketik plat lalu Enter.'}</p>`;
        return;
    }
    const sama = POS.supir && String(POS.supir.id_driver) === String(t.id_driver);
    el.innerHTML = `
        <div class="info-photo-box w-20 h-20 flex-shrink-0">${t.foto_path
            ? `<img src="${escapeHtml(urlBerkas(t.foto_path))}" class="w-full h-full object-cover" alt="">`
            : '<i class="fa-solid fa-user text-slate-300 text-2xl"></i>'}</div>
        <div class="min-w-0">
            <p class="font-semibold text-slate-900">${escapeHtml(t.nama)}${t.is_blacklisted ? ' <span class="badge-status bg-red-600 text-white">BLACKLIST</span>' : ''}</p>
            <p class="text-xs text-slate-500 font-mono">${escapeHtml(t.kode_personel || formatIdPersonel(t.id_driver))}</p>
            <p class="text-xs text-slate-500 mt-1"><i class="fa-regular fa-clock mr-1"></i>Terakhir masuk ${escapeHtml(fmtWaktu(t.waktu))}</p>
            ${!POS.supir ? `<button type="button" class="link-aksi text-blue-600 text-xs mt-2" data-on-click="pakaiTerakhirPos">Pakai supir ini (perlu scan wajah)</button>`
              : sama ? '<p class="mt-2 text-xs font-semibold px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 inline-block"><i class="fa-solid fa-check mr-1"></i>Sama dengan supir sekarang</p>'
              : `<p class="mt-2 text-xs font-semibold px-2 py-1 rounded-md bg-amber-50 text-amber-700 inline-block"><i class="fa-solid fa-triangle-exclamation mr-1"></i>Supir berbeda dari supir terakhir</p>`}
        </div>`;
}

function pakaiTerakhirPos() {
    if (POS.terakhir) pilihSupir(POS.terakhir, false, 'Supir terakhir dipilih. Scan wajah untuk verifikasi.');
}

// ===== SUPIR =====
async function pilihSupir(dr, terverifikasi, pesan) {
    const info = await ambilJson(`/api/pos/supir/${dr.id_driver}`);
    if (info.error) { Notif.gagal(info.error); return; }
    POS.supir = info;
    POS.terverifikasi = terverifikasi;
    document.getElementById('posIdDriver').value = info.id_driver;
    document.getElementById('posFoto').innerHTML = info.foto_path
        ? `<img src="${escapeHtml(urlBerkas(info.foto_path))}" class="w-full h-full object-contain" alt="">`
        : '<div class="text-center"><i class="fa-solid fa-user text-3xl mb-2"></i></div>';
    if (pesan) document.getElementById('posStatusScan').innerHTML = terverifikasi
        ? `<span class="text-emerald-700"><i class="fa-solid fa-circle-check mr-1"></i>${escapeHtml(pesan)}</span>` : escapeHtml(pesan);
    tampilSupir();
    tampilTerakhir();
    perbarui();
}

function tampilSupir() {
    const s = POS.supir;
    document.getElementById('badgeSupir').innerHTML = s && s.blacklist
        ? '<span class="badge-status bg-red-600 text-white"><i class="fa-solid fa-ban mr-1"></i>BLACKLIST</span>' : '';
    if (!s) {
        document.getElementById('kartuSupir').innerHTML = '<p class="text-sm text-slate-400">Belum ada supir. Klik Scan Wajah Supir.</p>';
        return;
    }
    const sim = s.sim;
    const label = !sim ? '<span class="badge-status bg-amber-100 text-amber-800 ml-1">Belum ada</span>'
        : { HABIS: '<span class="badge-status bg-red-100 text-red-700 ml-1">SIM habis</span>',
            SEGERA: '<span class="badge-status bg-amber-100 text-amber-800 ml-1">Segera habis</span>',
            TANPA_TANGGAL: '<span class="badge-status bg-amber-100 text-amber-800 ml-1">Tanggal belum diisi</span>',
            BERLAKU: '<span class="badge-status bg-emerald-100 text-emerald-700 ml-1">Berlaku</span>' }[sim.status];
    const baris = (lbl, nilai) => `<div class="flex justify-between gap-3 text-sm"><span class="text-slate-500">${lbl}</span><span class="text-slate-900 text-right">${nilai}</span></div>`;
    document.getElementById('kartuSupir').innerHTML = `
        <p class="font-bold text-slate-900">${escapeHtml(s.nama)} <span class="text-xs font-mono font-normal text-slate-500">${escapeHtml(s.kode_personel || '')}</span></p>
        <p class="text-xs mt-0.5 ${POS.terverifikasi ? 'text-emerald-700' : 'text-blue-700'}">
            <i class="fa-solid ${POS.terverifikasi ? 'fa-circle-check' : 'fa-hand-pointer'} mr-1"></i>${POS.terverifikasi ? 'Terverifikasi wajah' : 'Dipilih manual, belum scan wajah'}</p>
        <div class="mt-2 space-y-1.5">
            ${baris('ID Personel', `<span class="font-mono">${escapeHtml(formatIdPersonel(s.id_driver))}</span>`)}
            ${baris('NIK', `<span class="font-mono">${escapeHtml(s.nik || '-')}</span>`)}
            ${baris('SIM', escapeHtml(sim ? `${sim.jenis} · ${sim.no_sim}` : (s.no_sim || '-')))}
            ${baris('Berlaku sampai', `${escapeHtml((sim && sim.berlaku_sampai) || '-')}${label}`)}
        </div>
        ${s.is_updated ? '<p class="text-xs text-amber-600 mt-2">⚠ Data pernah diperbarui</p>' : ''}`;
}

let scanBerjalan = false;

function selesaiScan(pesan) {
    scanBerjalan = false;
    Kamera.stop();
    document.getElementById('posVideo').classList.add('hidden');
    document.getElementById('posFoto').classList.remove('hidden');
    document.getElementById('posInstruksi').textContent = 'Posisikan wajah supir di dalam bingkai';
    const btn = document.getElementById('btnScanPos');
    if (btn) btn.disabled = false;
    if (pesan) document.getElementById('posStatusScan').innerHTML = pesan;
}

async function scanWajahPos() {
    if (scanBerjalan) return;
    scanBerjalan = true;
    const video = document.getElementById('posVideo');
    const instruksi = document.getElementById('posInstruksi');
    const status = document.getElementById('posStatusScan');
    document.getElementById('btnScanPos').disabled = true;
    status.textContent = 'Menyalakan kamera...';
    try {
        await Kamera.mulai(video);
    } catch (err) {
        selesaiScan(escapeHtml(window.isSecureContext ? 'Kamera tidak bisa dibuka. Izinkan akses kamera di browser.'
            : 'Kamera diblokir browser karena alamat bukan HTTPS / localhost.'));
        return;
    }
    document.getElementById('posFoto').classList.add('hidden');
    video.classList.remove('hidden');
    status.textContent = 'Minta supir menghadap kamera.';
    const { security: wajib } = await aturanTantangan();
    const hasil = await rekamWajah(video, {
        wajib, batal: () => !scanBerjalan,
        tampil: (teks, angka) => { instruksi.textContent = angka ? `${teks} (${angka})` : teks; },
    });
    if (!hasil) { selesaiScan('Scan dibatalkan.'); return; }
    const fd = new FormData();
    hasil.frames.forEach((b, i) => fd.append('frames', b, `frame${i}.jpg`));
    fd.append('tantangan', hasil.tantangan);
    selesaiScan('Memproses wajah...');
    document.getElementById('btnScanPos').disabled = true;
    const d = await kirimForm('/api/security/scan-wajah', fd, { timeout: TIMEOUT_WAJAH_MS });
    document.getElementById('btnScanPos').disabled = false;
    if (!d.terverifikasi) {
        status.innerHTML = `<span class="text-red-600">${escapeHtml(d.error || 'Wajah tidak dikenali')}</span>`;
        return;
    }
    if (d.is_blacklisted) Notif.peringatan(`${namaSupir(d)} terdaftar dalam daftar blacklist`);
    await pilihSupir(d, true, `Terverifikasi: ${namaSupir(d)}`);
}

// ----- foto di modal (supir baru / ubah data): klik pertama nyalakan kamera, klik kedua ambil foto -----
async function rekamFotoPos(awalan) {
    const btn = document.getElementById(`${awalan}Rekam`);
    const video = document.getElementById(`${awalan}Video`);
    const preview = document.getElementById(`${awalan}Preview`);
    const f = FOTO[awalan] = FOTO[awalan] || {};
    if (!f.stream) {
        try {
            f.stream = await navigator.mediaDevices.getUserMedia({ video: true });
        } catch (err) { Notif.gagal('Kamera tidak bisa dibuka. Izinkan akses kamera di browser.'); return; }
        video.srcObject = f.stream;
        video.classList.remove('hidden');
        preview.classList.add('hidden');
        btn.textContent = 'Ambil Foto';
        return;
    }
    f.blob = await Kamera.ambilFrame(video, 0.9, 1024);
    preview.innerHTML = `<img src="${URL.createObjectURL(f.blob)}" class="w-full h-full object-cover rounded-full" alt="">`;
    hentikanFoto(awalan);
    btn.textContent = 'Foto Ulang';
}

function hentikanFoto(awalan) {
    const f = FOTO[awalan];
    if (f && f.stream) { f.stream.getTracks().forEach(t => t.stop()); f.stream = null; }
    document.getElementById(`${awalan}Video`).classList.add('hidden');
    document.getElementById(`${awalan}Preview`).classList.remove('hidden');
}

function resetFoto(awalan) {
    hentikanFoto(awalan);
    FOTO[awalan] = {};
    document.getElementById(`${awalan}Preview`).innerHTML = '<i class="fa-solid fa-camera text-slate-300 text-2xl"></i>';
    document.getElementById(`${awalan}Rekam`).textContent = 'Nyalakan Kamera';
}

function bukaSupirBaruPos() {
    ['psbNama', 'psbNik', 'psbSim', 'psbKode'].forEach(id => { document.getElementById(id).value = ''; });
    resetFoto('psb');
    openModal('modalPosSupirBaru');
    document.getElementById('psbNama').focus();
    ambilJson('/api/personel/saran-kode?kategori=DRIVER').then(s => { if (s.kode) document.getElementById('psbKode').value = s.kode; });
}

function tutupSupirBaruPos() { hentikanFoto('psb'); closeModal('modalPosSupirBaru'); }

async function simpanSupirBaruPos(btn) {
    const nilai = id => document.getElementById(id).value.trim();
    if (!nilai('psbNama') || !nilai('psbNik') || !nilai('psbSim')) { Notif.peringatan('Nama, NIK, dan SIM wajib diisi'); return; }
    if (!FOTO.psb || !FOTO.psb.blob) { Notif.peringatan('Ambil foto wajah supir terlebih dahulu'); return; }
    const fd = new FormData();
    fd.append('nama', nilai('psbNama'));
    fd.append('nik', nilai('psbNik'));
    fd.append('no_sim', nilai('psbSim'));
    fd.append('foto', FOTO.psb.blob, 'capture.jpg');
    const d = await denganTombol(btn, () => kirimForm('/api/driver/tambah', fd, { timeout: TIMEOUT_WAJAH_MS }), 'Memeriksa wajah...');
    if (!tampilkanHasil(d)) return;
    tutupSupirBaruPos();
    await pilihSupir({ id_driver: d.id_driver }, true, d.message);       // wajah baru saja direkam -> terverifikasi
}

let hasilCariNik = null;

function bukaUbahSupirPos() {
    document.getElementById('pusNik').value = '';
    document.getElementById('pusHasil').innerHTML = '';
    document.getElementById('pusPakai').disabled = true;
    hasilCariNik = null;
    const s = POS.supir;
    if (document.getElementById('pusNama')) {
        document.getElementById('pusNama').value = s ? s.nama : '';
        document.getElementById('pusNikUbah').value = s ? (s.nik || '') : '';
        document.getElementById('pusSim').value = s ? (s.no_sim || '') : '';
        document.getElementById('pusTanpaSupir').classList.toggle('hidden', !!s);
        document.getElementById('pusSimpan').disabled = !s;
        resetFoto('pus');
    }
    tabUbahSupirPos('cari');
    openModal('modalPosUbahSupir');
    document.getElementById('pusNik').focus();
}

function tutupUbahSupirPos() {
    if (document.getElementById('pusVideo')) hentikanFoto('pus');
    closeModal('modalPosUbahSupir');
}

function tabUbahSupirPos(tab) {
    [['cari', 'Cari'], ['ubah', 'Ubah']].forEach(([k, n]) => {
        document.getElementById(`pusTab${n}`).className = `modal-tab${k === tab ? ' modal-tab-active' : ''}`;
        document.getElementById(`pusPanel${n}`).classList.toggle('hidden', k !== tab);
    });
}

async function cariNikPos() {
    const nik = document.getElementById('pusNik').value.trim();
    if (!nik) return;
    const d = await kirimForm('/api/driver/cari-by-nik', { nik });
    const el = document.getElementById('pusHasil');
    hasilCariNik = d.status === 'DITEMUKAN' ? d : null;
    document.getElementById('pusPakai').disabled = !hasilCariNik || d.kategori !== 'DRIVER';
    el.innerHTML = d.error ? `<p class="text-red-600">${escapeHtml(d.error)}</p>`
        : !hasilCariNik ? '<p class="text-red-600">Tidak ditemukan. Daftarkan lewat Tambah Supir.</p>'
        : `<div class="border border-slate-200 rounded-lg p-3 space-y-0.5">
               <p><b>${escapeHtml(namaSupir(d))}</b>${d.is_blacklisted ? ' <span class="badge-status bg-red-600 text-white">BLACKLIST</span>' : ''}</p>
               <p class="text-slate-500">NIK ${escapeHtml(d.nik)} · SIM ${escapeHtml(d.no_sim || '-')}</p>
               ${d.kategori !== 'DRIVER' ? `<p class="text-red-600 text-xs">Terdaftar sebagai ${escapeHtml((LABEL_KATEGORI[d.kategori] || [d.kategori])[0])}, bukan supir.</p>` : ''}
           </div>`;
}

async function pakaiSupirPos() {
    if (!hasilCariNik) return;
    tutupUbahSupirPos();
    await pilihSupir(hasilCariNik, false, WAJIB_SCAN ? 'Supir dipilih manual. Scan wajah untuk verifikasi.' : 'Supir dipilih manual (tercatat di Log Audit).');
}

async function simpanUbahSupirPos(btn) {
    const s = POS.supir;
    if (!s) return;
    const nilai = id => document.getElementById(id).value.trim();
    if (!nilai('pusNama') || !nilai('pusNikUbah') || !nilai('pusSim')) { Notif.peringatan('Nama, NIK, dan SIM wajib diisi'); return; }
    const foto = FOTO.pus && FOTO.pus.blob;
    if (nilai('pusNama') === s.nama && nilai('pusNikUbah') === (s.nik || '') && nilai('pusSim').toUpperCase() === (s.no_sim || '').toUpperCase() && !foto) {
        Notif.info('Tidak ada perubahan yang perlu disimpan'); return;
    }
    if (!await Dialog.konfirmasi({ judul: 'Simpan perubahan identitas?', teksYa: 'Simpan',
        pesan: 'Perubahan identitas supir tercatat permanen di Log Audit dan supir ditandai "Pernah Diperbarui".' })) return;
    const fd = new FormData();
    fd.append('id_driver', s.id_driver);
    fd.append('nama', nilai('pusNama'));
    fd.append('nik', nilai('pusNikUbah'));
    fd.append('no_sim', nilai('pusSim'));
    if (foto) fd.append('foto', foto, 'capture.jpg');
    const d = await denganTombol(btn, () => kirimForm('/api/driver/update-identitas', fd, { timeout: TIMEOUT_WAJAH_MS }));
    if (!d.driver) { Notif.gagal(d.error || 'Gagal menyimpan perubahan'); return; }
    Notif.sukses(d.message);
    tutupUbahSupirPos();
    await pilihSupir(d.driver, POS.terverifikasi);
}

// ===== PANEL PERINGATAN: kritis (merah) di atas, perhatian (kuning) di bawahnya =====
function daftarPeringatan() {
    const p = [];
    const k = POS.kendaraan, s = POS.supir;
    const rinci = b => b && b.alasan ? `Alasan: ${b.alasan} · sejak ${b.sejak} · ditetapkan ${b.oleh}${b.no_surat ? ` · surat ${b.no_surat}` : ''}` : 'Detail surat belum tersedia.';
    if (s && s.blacklist) p.push({ kritis: true, ikon: 'fa-user-slash', judul: `Supir masuk blacklist: ${namaSupir(s)}`, isi: rinci(s.blacklist) });
    if (k && k.blacklist) p.push({ kritis: true, ikon: 'fa-truck', judul: `Kendaraan masuk blacklist: ${POS.plat}`, isi: rinci(k.blacklist) });
    if (k && !k.is_active) p.push({ kritis: true, ikon: 'fa-circle-minus', judul: `Kendaraan ${POS.plat} dinonaktifkan`, isi: 'Aktifkan dulu di Data Master › Kendaraan.' });
    if (POS.dalam) p.push({ ikon: 'fa-door-open', judul: `Truk ini tercatat masih di dalam sejak ${fmtWaktu(POS.dalam.waktu_masuk)} (${lamaSejak(POS.dalam.waktu_masuk)})`,
        isi: `Supir ${POS.dalam.supir} · ${POS.dalam.customer} · ${POS.dalam.produk}. Catat keluar dulu sebelum mencatat masuk lagi.`,
        aksi: document.getElementById('btnKeluarPos') ? ['Catat Keluar', 'keluarPos'] : null });
    if (s) {
        const sim = s.sim;
        if (!sim) p.push({ ikon: 'fa-id-card', judul: 'SIM supir belum tercatat', isi: 'Lengkapi SIM lewat Ganti / Ubah Supir atau menu Personel.' });
        else if (sim.status === 'HABIS') p.push({ ikon: 'fa-id-card', judul: 'SIM supir sudah kedaluwarsa', isi: `SIM ${sim.jenis} ${s.nama} berlaku sampai ${sim.berlaku_sampai} (${-sim.sisa_hari} hari lalu).` });
        else if (sim.status === 'SEGERA') p.push({ ikon: 'fa-id-card', judul: `SIM supir habis dalam ${sim.sisa_hari} hari`, isi: `SIM ${sim.jenis} ${s.nama} berlaku sampai ${sim.berlaku_sampai}.` });
        else if (sim.status === 'TANPA_TANGGAL') p.push({ ikon: 'fa-id-card', judul: 'Masa berlaku SIM belum diisi', isi: 'Lengkapi di menu Personel.' });
    }
    return p;
}

function tampilPeringatan() {
    const daftar = daftarPeringatan();
    const panel = document.getElementById('panelPeringatan');
    if (!daftar.length) { panel.classList.add('hidden'); panel.innerHTML = ''; return; }
    const kritis = daftar.filter(p => p.kritis), perhatian = daftar.filter(p => !p.kritis);
    const baris = (p, merah) => `
        <div class="flex items-start gap-3 px-5 py-3">
            <span class="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${merah ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-700'}">
                <i class="fa-solid ${p.ikon}"></i></span>
            <div class="flex-1 min-w-0">
                <p class="font-semibold ${merah ? 'text-red-800' : 'text-amber-900'}">${escapeHtml(p.judul)}</p>
                <p class="text-xs ${merah ? 'text-red-700' : 'text-amber-800'} mt-0.5">${escapeHtml(p.isi)}</p>
            </div>
            ${p.aksi ? `<button type="button" class="btn-secondary btn-sm flex-shrink-0" data-on-click="${p.aksi[1]}">${escapeHtml(p.aksi[0])}</button>` : ''}
        </div>`;
    panel.className = `rounded-xl border overflow-hidden shadow-sm ${kritis.length ? 'border-red-300' : 'border-amber-300'}`;
    panel.innerHTML =
        (kritis.length ? `<div class="bg-red-600 text-white px-5 py-2.5 flex flex-wrap items-center gap-2">
                <i class="fa-solid fa-triangle-exclamation"></i><span class="font-bold tracking-wide">PERINGATAN BLACKLIST</span>
                <span class="text-xs text-red-100 ml-1">Kendaraan tetap bisa dicatat masuk; setiap deteksi tercatat di Log Validasi Blacklist.</span></div>
            <div class="bg-red-50 divide-y divide-red-100">${kritis.map(p => baris(p, true)).join('')}</div>` : '') +
        (perhatian.length ? `<div class="${kritis.length ? 'border-t border-amber-200' : ''} bg-amber-50">
                ${kritis.length ? '' : '<div class="px-5 pt-3 text-xs font-bold text-amber-800 tracking-wide uppercase"><i class="fa-solid fa-circle-exclamation mr-1"></i>Perlu perhatian</div>'}
                <div class="divide-y divide-amber-100">${perhatian.map(p => baris(p, false)).join('')}</div></div>` : '');
}

function ringkasPos() {
    const bagian = [POS.plat || document.getElementById('posPlat').value.trim().toUpperCase(), POS.supir && POS.supir.nama,
                    teksPilihan('posCustomer'), teksPilihan('posProduk'), document.getElementById('posAngkut').value.trim()].filter(Boolean);
    document.getElementById('ringkasPos').textContent = bagian.join(' · ') || 'Belum ada data';
}

function perbarui() {
    tampilPeringatan();
    ringkasPos();
    document.getElementById('btnKeluarPos')?.classList.toggle('hidden', !POS.dalam);
    const simpan = document.getElementById('btnSimpanPos');
    if (simpan) simpan.disabled = !!POS.dalam;
}

function kosongkanPos() {
    Object.assign(POS, { plat: '', kendaraan: null, terakhir: null, dalam: null, supir: null, terverifikasi: false });
    ['posPlat', 'posStnk', 'posJenis', 'posAngkut', 'posIdDriver'].forEach(id => { document.getElementById(id).value = ''; });
    ['posCustomer', 'posProduk', 'posJenisTrx'].forEach(id => {
        const el = document.getElementById(id);
        el.value = '';
        el.dispatchEvent(new Event('change'));
    });
    scanBerjalan = false;
    selesaiScan('');
    document.getElementById('posStatusScan').textContent = '';
    document.getElementById('posFoto').innerHTML = '<div class="text-center"><i class="fa-solid fa-camera text-3xl mb-2"></i><p class="text-xs">Kamera belum menyala</p></div>';
    document.getElementById('badgePlat').innerHTML = '';
    tampilTerakhir();
    tampilSupir();
    perbarui();
    document.getElementById('posPlat').focus();
}

// ===== SIMPAN MASUK / CATAT KELUAR =====
async function simpanMasukPos(btn) {
    if (!POS.plat) { await cekPlatPos(); if (!POS.plat) return; }
    if (POS.dalam) { Notif.peringatan('Truk ini masih tercatat di dalam. Catat keluar dulu.'); return; }
    const isi = { no_plat: POS.plat, no_stnk: document.getElementById('posStnk').value.trim(),
                  jenis_transaksi: document.getElementById('posJenisTrx').value, id_supplier: document.getElementById('posCustomer').value,
                  id_produk: document.getElementById('posProduk').value, pengangkutan: document.getElementById('posAngkut').value.trim(),
                  id_driver: document.getElementById('posIdDriver').value };
    const kurang = [[isi.no_stnk, 'No. STNK'], [isi.id_driver, 'supir'], [isi.id_supplier, 'customer / supplier'],
                    [isi.id_produk, 'produk'], [isi.jenis_transaksi, 'jenis transaksi']].filter(([v]) => !v).map(([, n]) => n);
    if (kurang.length) { Notif.peringatan(`Lengkapi: ${kurang.join(', ')}`); return; }
    if (WAJIB_SCAN && !POS.terverifikasi) { Notif.peringatan('Supir belum terverifikasi wajah. Klik Scan Wajah Supir.'); return; }
    if (POS.terakhir) isi.id_driver_saran = POS.terakhir.id_driver;
    const kena = [POS.kendaraan && POS.kendaraan.blacklist && `kendaraan ${POS.plat}`, POS.supir.blacklist && `supir ${POS.supir.nama}`].filter(Boolean);
    if (kena.length && !await Dialog.konfirmasi({ judul: 'Masuk daftar blacklist', teksYa: 'Tetap catat masuk', bahaya: true,
        pesan: `${kena.join(' dan ')} masuk daftar blacklist. Tetap catat masuk? Tercatat di Log Validasi Blacklist.` })) return;
    const d = await denganTombol(btn, () => kirimForm('/api/pos/masuk', isi), 'Menyimpan...');
    if (!d.no_tiket) { Notif.gagal(d.error || 'Gagal menyimpan'); perbarui(); return; }
    Notif.sukses(d.message);
    kosongkanPos();
}

async function keluarPos() {
    const t = POS.dalam;
    if (!t) return;
    if (!await Dialog.konfirmasi({ judul: `Catat keluar ${t.no_plat}?`, teksYa: 'Catat Keluar',
        pesan: `Masuk ${fmtWaktu(t.waktu_masuk)} (${lamaSejak(t.waktu_masuk)} di dalam). Jam keluar = sekarang.` })) return;
    const d = await kirimForm('/api/pos/keluar', { no_tiket: t.no_tiket });
    if (d.error) { Notif.gagal(d.error); return; }
    Notif.sukses(d.message);
    cekPlatPos();
}

// ===== AJUKAN BLACKLIST (persetujuan; surat boleh menyusul) =====
function bukaBlacklistPos() {
    const target = [];
    if (POS.supir && !POS.supir.blacklist) target.push(['PERSONEL', POS.supir.id_driver, `Supir: ${namaSupir(POS.supir)}`]);
    if (POS.kendaraan && !POS.kendaraan.blacklist) target.push(['KENDARAAN', POS.kendaraan.id_kendaraan, `Kendaraan: ${POS.plat}`]);
    if (!target.length) { Notif.info('Cek plat atau pilih supir dulu (yang belum masuk blacklist).'); return; }
    document.getElementById('pblTarget').innerHTML = target.map(([tipe, id, label], i) => `
        <label class="flex items-center gap-2"><input type="radio" name="pblTarget" value="${tipe}|${id}"${i === 0 ? ' checked' : ''}> ${escapeHtml(label)}</label>`).join('');
    document.getElementById('pblAlasan').value = '';
    openModal('modalPosBlacklist');
    document.getElementById('pblAlasan').focus();
}

async function kirimBlacklistPos(btn) {
    const pilih = document.querySelector('input[name="pblTarget"]:checked');
    const alasan = document.getElementById('pblAlasan').value.trim();
    if (!pilih || !alasan) { Notif.peringatan('Pilih target dan isi alasan'); return; }
    const [tipe, id] = pilih.value.split('|');
    const isi = { tipe_entitas: tipe, id_target: id, alasan };
    if (tipe === 'PERSONEL') {
        if (POS.plat) isi.no_plat_terkait = POS.plat;
        if (document.getElementById('posCustomer').value) isi.id_customer_terkait = document.getElementById('posCustomer').value;
    }
    const d = await denganTombol(btn, () => kirimForm('/api/blacklist/tambah', isi));
    if (!tampilkanHasil(d)) return;
    closeModal('modalPosBlacklist');
}
