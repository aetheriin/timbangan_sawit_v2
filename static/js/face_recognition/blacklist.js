// ===== TAB BLACKLIST: riwayat & tambah (permanen, tanpa update / hapus) =====
let dataBlacklist = [];          // baris daftar terakhir (lampirkan surat menyusul)
let idSuratBlacklist = null;
let blacklistDimuat = false;
let tipeFilterBlacklist = '';
let timerCariBlacklist = null;

// state modal Tambah
let tipeBlacklistBaru = 'PERSONEL';
let targetBlacklist = null;
let hasilCariTarget = [];
let timerCariTarget = null;

window.addEventListener('tabChange', e => {
    if (e.detail === 'blacklist' && !blacklistDimuat) {
        blacklistDimuat = true;
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

function cariBlacklistTunda() {
    clearTimeout(timerCariBlacklist);
    timerCariBlacklist = setTimeout(muatBlacklist, 300);
}

async function muatBlacklist() {
    const params = new URLSearchParams({ tipe: tipeFilterBlacklist, cari: document.getElementById('cariBlacklist').value.trim() });
    const data = await ambilJson(`/api/blacklist?${params}`);
    const tbody = document.getElementById('kartuBlacklist');
    if (data.error) { tbody.innerHTML = barisKosong(5, data.error); return; }
    dataBlacklist = data;
    const bolehTambah = tbody.dataset.bolehTambah === '1';
    document.getElementById('totalBlacklist').innerHTML = `Total terblokir: <b class="text-red-600">${data.length}</b> · berlaku <b>permanen</b> di semua area`;
    // Tabel ringkas (data bisa ratusan): target 2 baris, alasan maks 2 baris, aksi berupa ikon
    tbody.innerHTML = data.map(r => {
        const terkait = [r.no_plat_terkait, r.customer_terkait, r.pengangkutan_terkait].filter(Boolean).join(' · ');
        return `<tr class="hover:bg-slate-50 align-top">
            <td class="table-cell">
                <div class="flex items-center gap-2"><span class="w-1.5 h-8 rounded-full bg-red-500 flex-shrink-0"></span>
                <div class="min-w-0"><p class="font-mono font-bold text-slate-900 whitespace-nowrap">${escapeHtml(namaTarget(r))}</p>
                <p class="text-xs text-slate-500">${r.tipe_entitas === 'PERSONEL' ? 'Personel' : 'Kendaraan'}${terkait ? ` · ${escapeHtml(terkait)}` : ''}</p></div></div></td>
            <td class="table-cell max-w-md"><p class="text-slate-700 line-clamp-2" title="${escapeHtml(r.alasan_blacklist)}">${escapeHtml(r.alasan_blacklist)}</p></td>
            <td class="table-cell whitespace-nowrap">${r.no_surat_blacklist ? `<span class="font-mono text-xs">${escapeHtml(r.no_surat_blacklist)}</span>` : badge('Menyusul', WARNA_BADGE.oranye)}</td>
            <td class="table-cell whitespace-nowrap"><p class="font-mono text-xs text-slate-700">${escapeHtml(r.tgl_blacklist)}</p>
                <p class="text-xs text-slate-500">${escapeHtml(r.oleh)}${r.area_oleh ? ` · ${escapeHtml(r.area_oleh)}` : ''}</p></td>
            <td class="table-cell text-right whitespace-nowrap">${r.file_surat_blacklist
                ? `<a href="${escapeHtml(urlBerkas(r.file_surat_blacklist))}" target="_blank" class="link-aksi text-blue-600">Lihat Surat</a>`
                : (!r.id_dokumen && bolehTambah ? `<button type="button" class="link-aksi text-blue-600" data-on-click="bukaSuratBlacklist" data-arg="${r.id_blacklist}">Lampirkan Surat</button>` : '')}</td>
        </tr>`;
    }).join('') || barisKosong(5, 'Belum ada blacklist', aksiKosong('bukaTambahBlacklist', 'Tambah Blacklist'));
    catatanBatas(tbody, data.length, 200, 5);
}

// ===== MODAL TAMBAH =====
function bukaTambahBlacklist() {
    ['blCari', 'blNoSurat', 'blAlasan', 'blFile', 'blFotoWajah'].forEach(id => document.getElementById(id).value = '');
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
    tampilkanTerkait(tipeBlacklistBaru === 'PERSONEL' ? targetBlacklist : null);
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

// Customer & pengangkutan hanya tampil bila orang ini tercatat sebagai supir (punya transaksi); plat selalu bisa diisi
function tampilkanTerkait(t) {
    document.getElementById('blTerkait').classList.toggle('hidden', !t);
    if (!t) return;
    const supir = !!t.plat_terakhir;
    document.getElementById('blPlatTerkait').value = t.plat_terakhir || '';
    document.getElementById('blCustomerBox').classList.toggle('hidden', !supir);
    document.getElementById('blAngkutBox').classList.toggle('hidden', !supir);
    document.getElementById('blCustomerTerkait').value = t.customer_terakhir || '';
    document.getElementById('blAngkutTerkait').value = supir ? (t.pengangkutan_terakhir || 'Customer sendiri') : '';
}

async function simpanBlacklist(btn) {
    if (!targetBlacklist) { Notif.peringatan('Silakan pilih target blacklist'); return; }
    const file = document.getElementById('blFile').files[0];
    const noSurat = document.getElementById('blNoSurat').value.trim();
    const alasan = document.getElementById('blAlasan').value.trim();
    if (!alasan) { Notif.peringatan('Alasan wajib diisi'); return; }
    if (!!noSurat !== !!file) { Notif.peringatan('Isi No. surat dan file surat sekaligus, atau kosongkan keduanya bila surat menyusul'); return; }
    const nama = tipeBlacklistBaru === 'PERSONEL' ? targetBlacklist.nama_personel : targetBlacklist.no_plat;
    const ok = await Dialog.konfirmasi({ judul: 'Tetapkan blacklist permanen?', teksYa: 'Tetapkan Blacklist', bahaya: true,
        pesan: `${nama} akan masuk blacklist secara PERMANEN dan tidak bisa dicabut.\nWajah / kendaraan ini ditolak di semua site.` });
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
        if (targetBlacklist.plat_terakhir) {
            formData.append('id_customer_terkait', targetBlacklist.id_customer_terakhir || '');
            formData.append('id_pengangkutan_terkait', targetBlacklist.id_pengangkutan_terakhir || '');
        }
    }

    const data = await denganTombol(btn, () => kirimForm('/api/blacklist/tambah', formData), 'Menyimpan...');
    if (!tampilkanHasil(data)) return;
    closeModal('modalBlacklist');
    Kamera.stop();
    muatBlacklist();
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
