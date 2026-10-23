// ===== TAB BLACKLIST: riwayat, ajukan tambah & ajukan hapus (lewat menu Persetujuan) =====
let dataBlacklist = [];          // baris daftar terakhir (lampirkan surat menyusul)
let idSuratBlacklist = null;
let blacklistDimuat = false;
let tipeFilterBlacklist = '';
let statusFilterBlacklist = 'AKTIF';
let idHapusBlacklist = null;
let timerCariBlacklist = null;

// state modal Tambah
let tipeBlacklistBaru = 'PERSONEL';
let targetBlacklist = null;
let hasilCariTarget = [];
let timerCariTarget = null;

window.addEventListener('tabChange', e => {
    if (e.detail === 'blacklist' && !blacklistDimuat) {
        blacklistDimuat = true;
        // Sub-menu navbar: Visitor & Staff Blacklist (?tipe=PERSONEL) / Vehicle Blacklist (?tipe=KENDARAAN)
        const tipe = new URLSearchParams(location.search).get('tipe');
        const chip = tipe && document.querySelector(`#chipTipeBlacklist [data-tipe="${CSS.escape(tipe)}"]`);
        if (chip) { aktifkanChip(chip); tipeFilterBlacklist = tipe; }
        muatBlacklist();
    }
});

function namaTarget(r) {
    return r.tipe_entitas === 'KENDARAAN' ? r.no_plat : formatNamaPersonel(r.kode_personel, r.id_personel, r.nama_personel);
}

// ===== RIWAYAT =====
function filterBlacklist(el) {
    aktifkanChip(el);
    tipeFilterBlacklist = el.dataset.tipe;
    muatBlacklist();
}

function filterStatusBlacklist(el) {
    aktifkanChip(el);
    statusFilterBlacklist = el.dataset.status;
    muatBlacklist();
}

function cariBlacklistTunda() {
    clearTimeout(timerCariBlacklist);
    timerCariBlacklist = setTimeout(muatBlacklist, 300);
}

const KOLOM_BLACKLIST = 14;

async function muatBlacklist() {
    const params = new URLSearchParams({ tipe: tipeFilterBlacklist, status: statusFilterBlacklist,
        kategori: document.getElementById('kategoriBlacklist').value, cari: document.getElementById('cariBlacklist').value.trim() });
    const data = await ambilJson(`/api/blacklist?${params}`);
    const tbody = document.getElementById('kartuBlacklist');
    if (data.error) { tbody.innerHTML = barisKosong(KOLOM_BLACKLIST, data.error); return; }
    dataBlacklist = data;
    const bolehTambah = tbody.dataset.bolehTambah === '1';
    const bolehHapus = tbody.dataset.bolehHapus === '1';
    const dicabut = statusFilterBlacklist === 'DICABUT';
    document.getElementById('totalBlacklist').innerHTML = dicabut
        ? `Blacklist yang sudah dicabut: <b>${data.length}</b>`
        : `Total terblokir: <b class="text-red-600">${data.length}</b> · berlaku di semua area`;
    const sel = (teks, kelas = '') => `<td class="table-cell ${kelas}">${teks ? escapeHtml(teks) : '<span class="text-slate-300">-</span>'}</td>`;
    const tempat = (area, pt) => area ? `${pt ? `${pt} · ` : ''}${area}` : '';
    tbody.innerHTML = data.map(r => {
        const kendaraan = r.tipe_entitas === 'KENDARAAN';
        return `<tr class="hover:bg-slate-50 align-top">
            <td class="table-cell"><div class="flex items-center gap-2">
                <span class="w-1.5 h-8 rounded-full ${r.dicabut_at ? 'bg-slate-300' : 'bg-red-500'} flex-shrink-0"></span>
                <div class="min-w-0"><p class="font-semibold text-slate-900 whitespace-nowrap ${kendaraan ? 'font-mono' : ''}">${escapeHtml(kendaraan ? r.no_plat : r.nama_personel)}</p>
                <p class="text-xs text-slate-500">${kendaraan ? 'Kendaraan' : escapeHtml(r.kode_personel || formatIdPersonel(r.id_personel))}</p>
                ${r.dicabut_at ? `<p class="text-xs text-emerald-700">Dicabut ${escapeHtml(r.dicabut_at)} oleh ${escapeHtml(r.dicabut_oleh || '-')}</p>` : ''}</div></div></td>
            ${sel(r.nama_alias)}
            ${sel(r.nik, 'font-mono text-xs')}
            <td class="table-cell">${r.nama_kategori ? badge(r.nama_kategori, kendaraan ? WARNA_BADGE.abu : WARNA_BADGE.biru) : '-'}</td>
            ${sel(r.customer_terkait)}
            ${sel(kendaraan ? r.no_plat : r.no_plat_terkait, 'font-mono text-xs whitespace-nowrap')}
            <td class="table-cell max-w-xs"><p class="line-clamp-2 text-slate-700" title="${escapeHtml(r.alasan_blacklist)}">${escapeHtml(r.alasan_blacklist)}</p></td>
            ${sel(r.tgl_blacklist, 'font-mono text-xs whitespace-nowrap')}
            ${sel(tempat(r.lokasi_blacklist, r.company_blacklist), 'whitespace-nowrap')}
            ${sel(r.scan_terakhir, 'font-mono text-xs whitespace-nowrap')}
            ${sel(tempat(r.lokasi_scan, r.company_scan), 'whitespace-nowrap')}
            <td class="table-cell whitespace-nowrap">${r.no_surat_blacklist ? `<span class="font-mono text-xs">${escapeHtml(r.no_surat_blacklist)}</span>` : badge('Menyusul', WARNA_BADGE.oranye)}</td>
            ${sel(r.oleh, 'whitespace-nowrap')}
            <td class="table-cell text-right whitespace-nowrap">${r.file_surat_blacklist
                ? `<a href="${escapeHtml(urlBerkas(r.file_surat_blacklist))}" target="_blank" class="link-aksi text-blue-600">Lihat Surat</a>`
                : (!r.id_dokumen && bolehTambah && !r.dicabut_at ? `<button type="button" class="link-aksi text-blue-600" data-on-click="bukaSuratBlacklist" data-arg="${r.id_blacklist}">Lampirkan Surat</button>` : '')}
                ${r.dicabut_at ? '' : r.id_pengajuan_hapus
                    ? `<a href="/blacklist?tab=persetujuan&id=${r.id_pengajuan_hapus}" class="ml-3">${badge('Menunggu persetujuan hapus', WARNA_BADGE.oranye)}</a>`
                    : (bolehHapus ? `<button type="button" class="link-aksi text-red-600 ml-3" data-on-click="bukaHapusBlacklist" data-arg="${r.id_blacklist}">Ajukan Hapus</button>` : '')}</td>
        </tr>`;
    }).join('') || barisKosong(KOLOM_BLACKLIST, dicabut ? 'Belum ada blacklist yang dicabut' : 'Belum ada blacklist',
        dicabut || !bolehTambah ? null : { fungsi: 'bukaTambahBlacklist', label: 'Request Blacklist' });
    catatanBatas(tbody, data.length, 200, KOLOM_BLACKLIST);
}

// ===== MODAL TAMBAH =====
function bukaTambahBlacklist() {
    ['blCari', 'blNoSurat', 'blAlasan', 'blFile', 'blFotoWajah', 'blAlias'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('blPunyaAlias').checked = false;
    aturAliasBlacklist();
    document.getElementById('blFileNama').textContent = '';
    document.getElementById('blTanggal').value = new Date().toISOString().slice(0, 10);
    setTipeBlacklist('PERSONEL');
    openModal('modalBlacklist');
}

function tutupModalBlacklist() {
    Kamera.stop();
    closeModal('modalBlacklist');
}

// ===== CARA MENCARI PERSONEL: teks (nama / NIK / kode), no SIM, wajah dari kamera, wajah dari foto =====
let caraBlacklist = 'TEKS';

function setCaraBlacklist(cara) {
    caraBlacklist = cara;
    document.querySelectorAll('[data-cara]').forEach(b => b.classList.toggle('seg-item-active', b.dataset.cara === cara));
    const cari = document.getElementById('blCari');
    cari.closest('.relative').classList.toggle('hidden', cara === 'KAMERA' || cara === 'UPLOAD');
    cari.placeholder = cara === 'SIM' ? 'Ketik No SIM' : 'Cari kode / NIK / nama';
    document.getElementById('blPanelKamera').classList.toggle('hidden', cara !== 'KAMERA');
    document.getElementById('blPanelUpload').classList.toggle('hidden', cara !== 'UPLOAD');
    if (cara === 'KAMERA') Kamera.mulai(document.getElementById('blVideo')).catch(err => Notif.gagal(`Kamera tidak dapat digunakan: ${err.message}`));
    else Kamera.stop();
}

async function cocokkanWajah(foto, btn) {
    const formData = new FormData();
    formData.append('foto', foto, 'wajah.jpg');
    const kirim = () => kirimForm('/api/blacklist/cari-wajah', formData);
    const data = btn ? await denganTombol(btn, kirim, 'Mencocokkan...') : await kirim();
    if (data.error) { Notif.gagal(data.error); return; }
    hasilCariTarget = [data];
    pilihTargetBlacklist(0);
    Notif.sukses(`Wajah dikenali: ${data.nama_personel}`);
}

async function cocokkanWajahKamera(btn) {
    if (!Kamera.aktif()) { Notif.peringatan('Kamera belum aktif. Silakan nyalakan kamera'); return; }
    cocokkanWajah(await Kamera.ambilFrame(document.getElementById('blVideo')), btn);
}

async function cocokkanWajahUpload(file) {
    if (file) cocokkanWajah(await kecilkanFoto(file));
}

function setTipeBlacklist(tipe) {
    tipeBlacklistBaru = tipe;
    document.getElementById('segBlPersonel').classList.toggle('seg-item-active', tipe === 'PERSONEL');
    document.getElementById('segBlKendaraan').classList.toggle('seg-item-active', tipe === 'KENDARAAN');
    document.getElementById('blCari').placeholder = tipe === 'PERSONEL' ? 'Cari kode / NIK / nama' : 'Ketik No. Plat, mis. BM 8821 KA';
    document.getElementById('blCari').classList.toggle('uppercase', tipe === 'KENDARAAN');
    document.getElementById('blCari').value = '';
    document.getElementById('blHasilCari').classList.add('hidden');
    document.getElementById('blCaraPersonel').classList.toggle('hidden', tipe !== 'PERSONEL');
    setCaraBlacklist('TEKS');
    pilihTargetBlacklist(null);
}

function cariTargetTunda() {
    clearTimeout(timerCariTarget);
    timerCariTarget = setTimeout(cariTargetBlacklist, 300);
}

async function cariTargetBlacklist() {
    const q = document.getElementById('blCari').value.trim();
    const list = document.getElementById('blHasilCari');
    if (q.length < 2) { list.classList.add('hidden'); return; }
    const data = await ambilJson(`/api/blacklist/cari-target?tipe=${tipeBlacklistBaru}&q=${encodeURIComponent(q)}`);
    hasilCariTarget = Array.isArray(data) ? data : [];
    list.innerHTML = hasilCariTarget.map((t, i) => {
        const nama = tipeBlacklistBaru === 'PERSONEL'
            ? `${formatNamaPersonel(t.kode_personel, t.id_target, t.nama_personel)} <span class="text-slate-400">· NIK ${escapeHtml(t.nik)}</span>`
            : `<span class="font-mono font-semibold">${escapeHtml(t.no_plat)}</span> <span class="text-slate-400">· STNK ${escapeHtml(t.no_stnk || '-')}` +
              ` · ${t.id_supir_utama ? 'supir utama ' + escapeHtml(t.nama_supir_utama) : 'belum ada supir utama'}</span>`;
        return t.is_blacklisted
            ? `<li class="px-3 py-2 text-slate-400">${nama} ${badge('BLACKLIST', WARNA_BADGE.merah)}</li>`
            : `<li class="px-3 py-2 hover:bg-slate-50 cursor-pointer" data-on-click="pilihTargetBlacklist" data-arg="${i}">${nama}</li>`;
    }).join('') || '<li class="px-3 py-2 text-slate-400">Tidak ditemukan</li>';
    list.classList.remove('hidden');
}

function pilihTargetBlacklist(index) {
    document.getElementById('blHasilCari').classList.add('hidden');
    targetBlacklist = index === null ? null : hasilCariTarget[index];
    const box = document.getElementById('blTarget');
    tampilkanTerkait(targetBlacklist);
    if (!targetBlacklist) {
        box.className = 'border border-slate-200 bg-slate-50 rounded-lg p-4 text-sm text-slate-400';
        box.textContent = 'Belum ada target dipilih.';
        return;
    }
    const t = targetBlacklist;
    box.className = 'border border-slate-200 bg-slate-50 rounded-lg p-4 text-sm flex items-center gap-4';
    box.innerHTML = tipeBlacklistBaru === 'PERSONEL' ? `
        <div class="w-24 h-28 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0 flex items-center justify-center">
            ${t.foto_path ? `<img src="${escapeHtml(urlBerkas(t.foto_path))}" class="w-full h-full object-cover" alt="Foto wajah">`
                          : '<i class="fa-solid fa-user text-slate-400 text-3xl"></i>'}
        </div>
        <div class="flex-1">
            <p class="font-semibold text-slate-800">${escapeHtml(t.nama_personel)}</p>
            <p class="text-xs text-slate-500">${t.kode_personel ? escapeHtml(t.kode_personel) : 'Belum ada kode'} · ID ${formatIdPersonel(t.id_target)} · ${escapeHtml((LABEL_KATEGORI[t.kategori] || [t.kategori])[0])} · NIK ${escapeHtml(t.nik)}</p>
            <p class="text-xs text-slate-500">SIM ${escapeHtml(t.no_sim || '-')}${t.jarak_wajah != null ? ` · kemiripan wajah ${escapeHtml(t.jarak_wajah)}` : ''}</p>
            ${t.plat_terakhir ? `<p class="text-xs text-slate-500">Terakhir membawa ${escapeHtml(t.plat_terakhir)} · ${escapeHtml(t.waktu_terakhir || '')}</p>` : ''}
        </div>
        ${badge('Aktif', WARNA_BADGE.hijau)}` : `
        <i class="fa-solid fa-truck text-2xl text-slate-500"></i>
        <div class="flex-1 space-y-0.5">
            <p class="font-semibold text-slate-800 font-mono">${escapeHtml(t.no_plat)}</p>
            <p class="text-xs text-slate-500">STNK ${escapeHtml(t.no_stnk || '-')} · ${Number(t.jumlah_supir)} supir terdaftar</p>
            <p class="text-xs text-slate-500">Supir utama: ${t.id_supir_utama
                ? escapeHtml(formatNamaPersonel(t.kode_supir_utama, t.id_supir_utama, t.nama_supir_utama)) : '-'}</p>
            ${t.waktu_terakhir ? `<p class="text-xs text-slate-500">Terakhir ${escapeHtml(t.waktu_terakhir)} · supir
                ${escapeHtml(formatNamaPersonel(t.kode_supir_terakhir, t.id_supir_terakhir, t.nama_supir_terakhir))} ·
                customer ${escapeHtml(t.customer_terakhir)}${t.pengangkutan_terakhir ? ` · angkutan ${escapeHtml(t.pengangkutan_terakhir)}` : ''}</p>`
                : '<p class="text-xs text-slate-400">Belum pernah bertransaksi</p>'}
        </div>
        ${t.is_active ? badge('Aktif', WARNA_BADGE.hijau) : badge('Nonaktif', WARNA_BADGE.abu)}`;
}

// Kategori (menentukan jalur persetujuan), alias, plat, asal supplier & pengangkutan (terisi dari transaksi terakhir)
function tampilkanTerkait(t) {
    document.getElementById('blTerkait').classList.toggle('hidden', !t);
    if (!t) return;
    const personel = tipeBlacklistBaru === 'PERSONEL';
    const kategori = personel ? t.kategori : 'KENDARAAN';
    document.getElementById('blKategori').textContent = personel ? (t.nama_kategori || t.kategori || '-') : 'Kendaraan';
    document.getElementById('blAliasBox').classList.toggle('hidden', !personel);
    document.getElementById('blPlatBox').classList.toggle('hidden', !personel);
    document.getElementById('blPlatTerkait').value = personel ? (t.plat_terakhir || '') : '';
    setNilaiPilihan('blCustomerTerkait', t.id_customer_terakhir);
    setNilaiPilihan('blAngkutTerkait', t.id_pengangkutan_terakhir);
    document.getElementById('blSupplierWajib').classList.toggle('hidden', kategori !== 'DRIVER');
    document.getElementById('blProduk').textContent = t.produk_terakhir ? `Produk transaksi terakhir: ${t.produk_terakhir}` : '';
    muatJalurBlacklist(kategori);
}

// Pilih nilai <select> bila ada di daftar (supplier di luar PT user tidak ada di pilihan)
function setNilaiPilihan(id, nilai) {
    const sel = document.getElementById(id);
    sel.value = [...sel.options].some(o => o.value === String(nilai ?? '')) ? String(nilai ?? '') : '';
    sel.dispatchEvent(new Event('change'));
}

function aturAliasBlacklist() {
    const ada = document.getElementById('blPunyaAlias').checked;
    document.getElementById('blAliasIsi').classList.toggle('hidden', !ada);
    if (ada) document.getElementById('blAlias').focus();
}

async function muatJalurBlacklist(kategori) {
    const el = document.getElementById('blJalur');
    el.textContent = 'Memuat...';
    const data = await ambilJson(`/api/blacklist/jalur?jenis=BLACKLIST_TAMBAH&kategori=${encodeURIComponent(kategori || '')}`);
    if (data.error) { el.textContent = data.error; return; }
    el.textContent = data.tahap.length ? data.tahap.map((n, i) => `${i + 1}. ${n}`).join('  →  ')
        : (data.lama ? `Satu tahap: ${data.lama}` : 'Tanpa persetujuan (langsung berlaku)');
}

async function simpanBlacklist(btn) {
    if (!targetBlacklist) { Notif.peringatan('Silakan pilih target blacklist'); return; }
    const file = document.getElementById('blFile').files[0];
    const noSurat = document.getElementById('blNoSurat').value.trim();
    const alasan = document.getElementById('blAlasan').value.trim();
    if (!alasan) { Notif.peringatan('Alasan wajib diisi'); return; }
    const punyaAlias = document.getElementById('blPunyaAlias').checked && tipeBlacklistBaru === 'PERSONEL';
    const alias = document.getElementById('blAlias').value.trim();
    if (punyaAlias && !alias) { Notif.peringatan('Nama alias wajib diisi'); return; }
    const idSupplier = document.getElementById('blCustomerTerkait').value;
    if (tipeBlacklistBaru === 'PERSONEL' && targetBlacklist.kategori === 'DRIVER' && !idSupplier) {
        Notif.peringatan('Asal supplier wajib diisi untuk Driver'); return;
    }
    if (!!noSurat !== !!file) { Notif.peringatan('Isi No. surat dan file surat sekaligus, atau kosongkan keduanya bila surat menyusul'); return; }
    const nama = tipeBlacklistBaru === 'PERSONEL' ? targetBlacklist.nama_personel : targetBlacklist.no_plat;
    const ok = await Dialog.konfirmasi({ judul: 'Kirim request blacklist?', teksYa: 'Kirim Request', bahaya: true,
        pesan: `${nama} diajukan untuk masuk blacklist. Setelah disetujui semua tahap, wajah / kendaraan ini ditolak di semua area.` });
    if (!ok) return;

    const formData = new FormData();
    formData.append('tipe_entitas', tipeBlacklistBaru);
    formData.append('id_target', targetBlacklist.id_target);
    formData.append('no_surat', noSurat);
    formData.append('tgl_blacklist', document.getElementById('blTanggal').value);
    formData.append('alasan', alasan);
    if (file) formData.append('file_surat', file);
    if (tipeBlacklistBaru === 'PERSONEL') {
        formData.append('no_plat_terkait', document.getElementById('blPlatTerkait').value.trim());
        formData.append('punya_alias', punyaAlias ? '1' : '0');
        formData.append('nama_alias', punyaAlias ? alias : '');
    }
    formData.append('id_customer_terkait', idSupplier);
    formData.append('id_pengangkutan_terkait', document.getElementById('blAngkutTerkait').value);

    const data = await denganTombol(btn, () => kirimForm('/api/blacklist/tambah', formData), 'Menyimpan...');
    if (!tampilkanHasil(data)) return;
    closeModal('modalBlacklist');
    Kamera.stop();
    muatBlacklist();
    if (typeof muatPengajuan === 'function' && persetujuanDimuat) muatPengajuan();
    if (typeof muatPersonel === 'function' && personelDimuat) muatPersonel();
}

// ===== SURAT MENYUSUL =====
function bukaSuratBlacklist(id) {
    const r = dataBlacklist.find(x => x.id_blacklist === id);
    if (!r) return;
    idSuratBlacklist = id;
    document.getElementById('suratBlTarget').textContent = namaTarget(r);
    ['suratBlNo', 'suratBlFile'].forEach(i => document.getElementById(i).value = '');
    document.getElementById('suratBlTanggal').value = new Date().toISOString().slice(0, 10);
    openModal('modalSuratBlacklist');
}

async function simpanSuratBlacklist(btn) {
    const file = document.getElementById('suratBlFile').files[0];
    const no = document.getElementById('suratBlNo').value.trim();
    if (!no || !file) { Notif.peringatan('No. surat dan file surat wajib diisi'); return; }
    const formData = new FormData();
    formData.append('no_surat', no);
    formData.append('tgl_blacklist', document.getElementById('suratBlTanggal').value);
    formData.append('file_surat', file);
    const data = await denganTombol(btn, () => kirimForm(`/api/blacklist/${idSuratBlacklist}/surat`, formData), 'Menyimpan...');
    if (!tampilkanHasil(data)) return;
    closeModal('modalSuratBlacklist');
    muatBlacklist();
}

// ===== AJUKAN HAPUS (CABUT) =====
function bukaHapusBlacklist(id) {
    const r = dataBlacklist.find(x => x.id_blacklist === id);
    if (!r) return;
    idHapusBlacklist = id;
    document.getElementById('formHapusBlacklist').reset();
    document.getElementById('hapusBlTarget').textContent = namaTarget(r);
    openModal('modalHapusBlacklist');
    document.getElementById('hapusBlAlasan').focus();
}

document.getElementById('formHapusBlacklist')?.addEventListener('submit', async e => {
    e.preventDefault();
    const data = await denganTombol(document.getElementById('btnHapusBlacklist'),
        () => kirimForm(`/api/blacklist/${idHapusBlacklist}/hapus`, { alasan: document.getElementById('hapusBlAlasan').value.trim() }), 'Mengirim...');
    if (!tampilkanHasil(data)) return;
    closeModal('modalHapusBlacklist');
    muatBlacklist();
});
