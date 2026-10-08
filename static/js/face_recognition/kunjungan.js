// ===== TAB KUNJUNGAN TAMU: scan wajah, daftarkan tamu baru, catat masuk / keluar =====
let kunjunganDimuat = false;
let statusKunjungan = '';
let fotoTamu = null;              // Blob foto terakhir (dipakai untuk daftar tamu baru & snapshot kunjungan)

window.addEventListener('tabChange', async e => {
    if (e.detail !== 'kunjungan') {
        if (typeof Kamera !== 'undefined') Kamera.stop();
        return;
    }
    if (kunjunganDimuat) return;
    kunjunganDimuat = true;
    document.getElementById('kunjTanggal').value = tanggalLokalKunjungan();
    muatKunjungan();
    const pilih = document.getElementById('kunjDituju');
    if (pilih) {
        const data = await ambilJson('/api/kunjungan/dituju');
        if (Array.isArray(data)) pilih.insertAdjacentHTML('beforeend', data.map(d =>
            `<option value="${d.id_personel}">${escapeHtml(formatNamaPersonel(d.kode_personel, d.id_personel, d.nama_personel))} (${escapeHtml(d.kategori)})</option>`).join(''));
    }
});

function tanggalLokalKunjungan() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// ===== DAFTAR =====
function filterKunjungan(el) {
    aktifkanChip(el);
    statusKunjungan = el.dataset.status;
    document.getElementById('kunjTanggal').classList.toggle('hidden', statusKunjungan === 'DIDALAM');
    muatKunjungan();
}

async function muatKunjungan() {
    const url = statusKunjungan === 'DIDALAM' ? '/api/kunjungan?status=DIDALAM'
        : `/api/kunjungan?tanggal=${encodeURIComponent(document.getElementById('kunjTanggal').value)}`;
    const data = await ambilJson(url);
    const tbody = document.getElementById('tabelKunjungan');
    if (data.error) { tbody.innerHTML = barisKosong(8, data.error); return; }
    const bolehUbah = tbody.dataset.bolehUbah === '1';
    tbody.innerHTML = data.map(k => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(k.waktu_masuk)}</td>
            <td class="table-cell">${escapeHtml(k.nama_tamu)}<div class="text-xs text-slate-400">NIK ${escapeHtml(k.nik)}</div></td>
            <td class="table-cell">${escapeHtml(k.asal_perusahaan || '-')}</td>
            <td class="table-cell">${escapeHtml(formatNamaPersonel(k.kode_dituju, k.id_dituju, k.nama_dituju))}</td>
            <td class="table-cell">${escapeHtml(k.keperluan)}${k.keterangan ? `<div class="text-xs text-slate-400">${escapeHtml(k.keterangan)}</div>` : ''}</td>
            <td class="table-cell font-mono">${escapeHtml(k.no_plat || '-')}</td>
            <td class="table-cell whitespace-nowrap text-xs">${k.waktu_keluar ? escapeHtml(k.waktu_keluar) : badge('Di dalam', WARNA_BADGE.oranye)}</td>
            <td class="table-cell text-right">${!k.waktu_keluar && bolehUbah
                ? `<button type="button" class="link-aksi text-blue-600" data-on-click="catatKeluar" data-arg="${k.id_kunjungan}">Keluar</button>` : ''}</td>
        </tr>`).join('') || barisKosong(8, statusKunjungan === 'DIDALAM' ? 'Tidak ada tamu di dalam' : 'Belum ada kunjungan');
}

async function catatKeluar(id) {
    const data = await kirimForm(`/api/kunjungan/${id}/keluar`, {});
    if (tampilkanHasil(data)) muatKunjungan();
}

// ===== SCAN WAJAH =====
async function nyalakanKameraTamu() {
    const video = document.getElementById('tamuVideo');
    document.getElementById('tamuFoto').classList.add('hidden');
    try {
        await Kamera.mulai(video);
        document.getElementById('btnScanTamu').disabled = false;
        document.getElementById('tamuStatus').textContent = 'Minta tamu menghadap kamera, lalu Ambil & Cocokkan.';
    } catch (err) {
        document.getElementById('tamuStatus').textContent = 'Kamera tidak bisa dibuka. Izinkan akses kamera di browser.';
    }
}

function resetFormTamu() {
    document.getElementById('tamuBaru').classList.add('hidden');
    const form = document.getElementById('formKunjungan');
    form.classList.add('hidden');
    form.reset();
    form.elements.id_personel.value = '';
    form.elements.id_dituju.value = '';
}

async function scanWajahTamu(btn) {
    const video = document.getElementById('tamuVideo');
    if (!Kamera.aktif()) { Notif.peringatan('Nyalakan kamera dulu'); return; }
    fotoTamu = await Kamera.ambilFrame(video);
    const img = document.getElementById('tamuFoto');
    img.src = URL.createObjectURL(fotoTamu);
    img.classList.remove('hidden');
    Kamera.stop();
    document.getElementById('btnScanTamu').disabled = true;
    resetFormTamu();

    const fd = new FormData();
    fd.append('foto', fotoTamu, 'tamu.jpg');
    const data = await denganTombol(btn, () => kirimForm('/api/kunjungan/cari-wajah', fd, { timeout: TIMEOUT_WAJAH_MS }), 'Mencocokkan...');
    const hasil = document.getElementById('tamuHasil');
    if (data.error) {
        hasil.className = 'note-warning';
        hasil.textContent = data.error;
        return;
    }
    if (!data.dikenali) {
        hasil.className = 'border border-slate-200 bg-slate-50 rounded-lg p-4 text-sm text-slate-600';
        hasil.textContent = 'Wajah belum dikenal.';
        document.getElementById('tamuBaru').classList.remove('hidden');
        document.getElementById('tamuNik').focus();
        return;
    }
    tampilkanTamu(data);
}

let tamuBlacklist = null;        // nama tamu blacklist yang sedang dipilih (konfirmasi sebelum catat masuk)

function tampilkanTamu(p) {
    const hasil = document.getElementById('tamuHasil');
    // Blacklist = peringatan (tamu tetap bisa dicatat), bukan penghalang
    const masalah = p.kategori !== 'TAMU' ? `Terdaftar sebagai ${labelKode(p.kategori)}, bukan tamu.`
        : p.kunjungan_aktif ? 'Masih tercatat di dalam. Catat keluar dulu di tabel di bawah.' : '';
    tamuBlacklist = p.is_blacklisted ? p.nama_tampil : null;
    hasil.className = `rounded-lg p-4 text-sm flex items-center gap-4 ${p.is_blacklisted ? 'border-2 border-red-500 bg-red-50' : 'border border-slate-200 bg-white'}`;
    hasil.innerHTML = `
        <div class="w-20 h-24 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0${p.is_blacklisted ? ' ring-4 ring-red-600' : ''}">
            ${p.foto_path ? `<img src="${escapeHtml(urlBerkas(p.foto_path))}" class="w-full h-full object-cover" alt="">` : ''}
        </div>
        <div class="flex-1 space-y-1">
            <p class="font-semibold text-slate-800">${escapeHtml(p.nama_tampil)} ${badgeKategori(p.kategori)}</p>
            <p class="text-xs text-slate-500">NIK ${escapeHtml(p.nik)}${p.jarak_wajah != null ? ` · kemiripan ${escapeHtml(p.jarak_wajah)}` : ''}</p>
            ${p.is_blacklisted ? `<p><span class="px-2 py-0.5 rounded bg-red-600 text-white text-xs font-bold">BLACKLIST</span></p>
                <p id="tamuInfoBlacklist" class="text-xs text-red-700">Masuk daftar blacklist · berlaku di semua area. Tamu tetap bisa dicatat, tercatat di Audit Log.</p>` : ''}
            ${masalah ? `<p class="text-xs font-semibold text-red-600">${escapeHtml(masalah)}</p>` : ''}
        </div>`;
    if (p.is_blacklisted) {
        ambilJson(`/api/blacklist/info/PERSONEL/${p.id_personel}`).then(bl => {
            const el = document.getElementById('tamuInfoBlacklist');
            if (!el || bl.error || !bl.oleh) return;
            el.textContent = `${bl.no_surat_blacklist ? `No. surat ${bl.no_surat_blacklist} · ` : ''}ditetapkan ${bl.tgl_blacklist} oleh ` +
                `${bl.oleh}${bl.area_oleh ? ` (${bl.area_oleh})` : ''} · berlaku di semua area. Tamu tetap bisa dicatat, tercatat di Audit Log.`;
        });
    }
    const form = document.getElementById('formKunjungan');
    form.classList.toggle('hidden', !!masalah);
    form.elements.id_personel.value = masalah ? '' : p.id_personel;
}

async function daftarkanTamu(btn) {
    if (!fotoTamu) { Notif.peringatan('Ambil foto wajah dulu'); return; }
    const fd = new FormData();
    fd.append('nik', document.getElementById('tamuNik').value.trim());
    fd.append('nama', document.getElementById('tamuNama').value.trim());
    fd.append('foto', fotoTamu, 'tamu.jpg');
    const data = await denganTombol(btn, () => kirimForm('/api/kunjungan/tamu-baru', fd, { timeout: TIMEOUT_WAJAH_MS }), 'Mendaftarkan...');
    if (!tampilkanHasil(data)) return;
    document.getElementById('tamuBaru').classList.add('hidden');
    tampilkanTamu(data);
}

document.getElementById('formKunjungan')?.addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target;
    if (tamuBlacklist && !await Dialog.konfirmasi({ judul: 'Tamu masuk daftar blacklist', teksYa: 'Tetap catat masuk',
        bahaya: true, pesan: `${tamuBlacklist} masuk daftar blacklist. Tetap catat masuk? Tercatat di Audit Log.` })) return;
    const fd = new FormData(form);
    if (fotoTamu) fd.append('foto', fotoTamu, 'kunjungan.jpg');
    const data = await denganTombol(form.querySelector('[type=submit]'), () => kirimForm('/api/kunjungan/masuk', fd));
    if (!tampilkanHasil(data)) return;
    resetFormTamu();
    tamuBlacklist = null;
    fotoTamu = null;
    document.getElementById('tamuFoto').classList.add('hidden');
    document.getElementById('tamuHasil').className = 'border border-slate-200 bg-slate-50 rounded-lg p-4 text-sm text-slate-400';
    document.getElementById('tamuHasil').textContent = 'Tersimpan. Nyalakan kamera untuk tamu berikutnya.';
    muatKunjungan();
});
