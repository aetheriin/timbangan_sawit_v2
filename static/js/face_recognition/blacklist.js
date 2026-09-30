// ===== TAB BLACKLIST: riwayat & tambah (permanen, tanpa update / hapus) =====
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
    const tbody = document.getElementById('tabelBlacklist');
    if (data.error) { tbody.innerHTML = barisKosong(7, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell whitespace-nowrap">${escapeHtml(r.tgl_blacklist)}</td>
            <td class="table-cell">${r.tipe_entitas === 'PERSONEL' ? badge('Personel', WARNA_BADGE.biru) : badge('Kendaraan', WARNA_BADGE.abu)}</td>
            <td class="table-cell">${escapeHtml(namaTarget(r))}</td>
            <td class="table-cell">${escapeHtml(r.no_surat_blacklist)}</td>
            <td class="table-cell max-w-xs truncate" title="${escapeHtml(r.alasan_blacklist)}">${escapeHtml(r.alasan_blacklist)}</td>
            <td class="table-cell">${escapeHtml(r.oleh)} (${escapeHtml(r.role_oleh)})</td>
            <td class="table-cell text-right">${r.file_surat_blacklist
                ? `<a href="/static/${escapeHtml(r.file_surat_blacklist)}" target="_blank" class="link-aksi text-blue-600">Lihat Surat</a>` : '-'}</td>
        </tr>`).join('') || barisKosong(7, 'Belum ada blacklist');
    catatanBatas(tbody, data.length, 200, 7);
}

// ===== MODAL TAMBAH =====
function bukaTambahBlacklist() {
    ['blCari', 'blNoSurat', 'blAlasan', 'blFile'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('blFileNama').textContent = '';
    document.getElementById('blTanggal').value = new Date().toISOString().slice(0, 10);
    setTipeBlacklist('PERSONEL');
    openModal('modalBlacklist');
}

function setTipeBlacklist(tipe) {
    tipeBlacklistBaru = tipe;
    document.getElementById('segBlPersonel').classList.toggle('seg-item-active', tipe === 'PERSONEL');
    document.getElementById('segBlKendaraan').classList.toggle('seg-item-active', tipe === 'KENDARAAN');
    document.getElementById('blCari').placeholder = tipe === 'PERSONEL' ? 'Cari kode / NIK / nama' : 'Cari plat, mis. BM 8821 KA';
    document.getElementById('blCari').value = '';
    document.getElementById('blHasilCari').classList.add('hidden');
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
            : escapeHtml(t.no_plat);
        return t.is_blacklisted
            ? `<li class="px-3 py-2 text-slate-400">${nama} ${badge('BLACKLIST', WARNA_BADGE.merah)}</li>`
            : `<li class="px-3 py-2 hover:bg-slate-50 cursor-pointer" onclick="pilihTargetBlacklist(${i})">${nama}</li>`;
    }).join('') || '<li class="px-3 py-2 text-slate-400">Tidak ditemukan</li>';
    list.classList.remove('hidden');
}

function pilihTargetBlacklist(index) {
    document.getElementById('blHasilCari').classList.add('hidden');
    targetBlacklist = index === null ? null : hasilCariTarget[index];
    const box = document.getElementById('blTarget');
    if (!targetBlacklist) {
        box.className = 'border border-slate-200 bg-slate-50 rounded-lg p-4 text-sm text-slate-400';
        box.textContent = 'Belum ada target dipilih.';
        return;
    }
    const t = targetBlacklist;
    box.className = 'border border-slate-200 bg-slate-50 rounded-lg p-4 text-sm flex items-center gap-4';
    box.innerHTML = tipeBlacklistBaru === 'PERSONEL' ? `
        <div class="w-14 h-16 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0">
            ${t.foto_path ? `<img src="/static/${escapeHtml(t.foto_path)}" class="w-full h-full object-cover" alt="">` : ''}
        </div>
        <div class="flex-1">
            <p class="font-semibold text-slate-800">${escapeHtml(t.nama_personel)}</p>
            <p class="text-xs text-slate-500">${t.kode_personel ? escapeHtml(t.kode_personel) : 'belum ada kode'} · ID ${formatIdPersonel(t.id_target)} · ${escapeHtml((LABEL_KATEGORI[t.kategori] || [t.kategori])[0])} · NIK ${escapeHtml(t.nik)}</p>
            ${t.plat_terakhir ? `<p class="text-xs text-slate-500">Truk terakhir: ${escapeHtml(t.plat_terakhir)}</p>` : ''}
        </div>
        ${badge('Aktif', WARNA_BADGE.hijau)}` : `
        <i class="fa-solid fa-truck text-2xl text-slate-500"></i>
        <div class="flex-1">
            <p class="font-semibold text-slate-800">${escapeHtml(t.no_plat)}</p>
            <p class="text-xs text-slate-500">STNK ${escapeHtml(t.no_stnk || '-')}</p>
        </div>`;
}

async function simpanBlacklist(btn) {
    if (!targetBlacklist) { Notif.peringatan('Pilih target blacklist dulu'); return; }
    const file = document.getElementById('blFile').files[0];
    const noSurat = document.getElementById('blNoSurat').value.trim();
    const alasan = document.getElementById('blAlasan').value.trim();
    if (!noSurat || !alasan || !file) { Notif.peringatan('No. surat, alasan, dan file surat wajib diisi'); return; }
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
    formData.append('file_surat', file);

    const data = await denganTombol(btn, () => kirimForm('/api/blacklist/tambah', formData), 'Menyimpan...');
    if (!tampilkanHasil(data)) return;
    closeModal('modalBlacklist');
    muatBlacklist();
    if (typeof muatPersonel === 'function' && personelDimuat) muatPersonel();
}
