// ===== TAB PERSETUJUAN (Blacklist): setujui / tolak pengajuan tambah & hapus blacklist =====
// Penyetuju = jabatan dengan hak Setujui di menu Blacklist, PT yang sama. ?tab=persetujuan&id=<id> (dari
// notifikasi): pengajuan itu disorot; bila tidak ada di daftar awal, daftar "Semua pengajuan" yang dibuka.
let modePersetujuan = document.getElementById('daftarPengajuan')?.dataset.modeAwal || 'saya';
let persetujuanDimuat = false;
let dataPengajuan = [];
let putusan = null;              // { id, aksi: 'setujui' | 'tolak' }
const idSorot = Number(new URLSearchParams(location.search).get('id')) || null;

const WARNA_STATUS = { MENUNGGU: WARNA_BADGE.oranye, DISETUJUI: WARNA_BADGE.hijau, DITOLAK: WARNA_BADGE.merah, DIBATALKAN: WARNA_BADGE.abu };
const LABEL_STATUS = { MENUNGGU: 'Menunggu', DISETUJUI: 'Disetujui', DITOLAK: 'Ditolak', DIBATALKAN: 'Dibatalkan' };
const LABEL_AKSI = { DIAJUKAN: 'Diajukan', DISETUJUI: 'Disetujui', DITOLAK: 'Ditolak', DIBATALKAN: 'Dibatalkan' };

window.addEventListener('tabChange', async e => {
    if (e.detail !== 'persetujuan' || persetujuanDimuat) return;
    persetujuanDimuat = true;
    await muatPengajuan();
    if (idSorot && !dataPengajuan.some(p => p.id_pengajuan === idSorot)) {
        pilihModePersetujuan(document.querySelector('[data-mode="semua"]'));
    }
});

function pilihModePersetujuan(el) {
    aktifkanChip(el);
    modePersetujuan = el.dataset.mode;
    muatPengajuan();
}

async function muatPengajuan() {
    const data = await ambilJson(`/api/persetujuan?menu=BLACKLIST&mode=${modePersetujuan}`);
    const wadah = document.getElementById('daftarPengajuan');
    if (data.error) { wadah.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(data.error)}</p>`; return; }
    dataPengajuan = data;
    const jml = document.getElementById('jmlMenunggu');
    if (modePersetujuan === 'menunggu' && jml) jml.textContent = data.length ? `(${data.length})` : '';
    wadah.innerHTML = data.map(kartuPengajuan).join('') || `<div class="card p-8 text-center text-sm text-slate-400">
        ${modePersetujuan === 'menunggu' ? 'Tidak ada pengajuan yang menunggu persetujuan Anda' : 'Belum ada pengajuan'}</div>`;
    const sorot = idSorot && document.getElementById(`pengajuan-${idSorot}`);
    if (sorot) { sorot.classList.add('ring-2', 'ring-blue-400'); sorot.scrollIntoView({ block: 'center' }); }
}

function kartuPengajuan(p) {
    const riwayat = p.riwayat.map(r => `<li><span class="font-mono text-slate-400">${escapeHtml(r.waktu)}</span> ·
        ${escapeHtml(LABEL_AKSI[r.aksi] || r.aksi)}${r.langkah ? ` (langkah ${r.langkah})` : ''} oleh ${escapeHtml(r.oleh)}${r.catatan ? ` — ${escapeHtml(r.catatan)}` : ''}</li>`).join('');
    const jenisBahaya = p.jenis === 'BLACKLIST_TAMBAH';
    return `<div id="pengajuan-${p.id_pengajuan}" class="card p-4 space-y-3">
        <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                    ${badge(p.nama_jenis, jenisBahaya ? WARNA_BADGE.merah : WARNA_BADGE.biru)} ${badge(LABEL_STATUS[p.status] || p.status, WARNA_STATUS[p.status])}
                    <span class="text-xs text-slate-400 font-mono">#${p.id_pengajuan}</span>
                </div>
                <p class="font-bold text-slate-900">${escapeHtml(p.judul)}</p>
                ${p.alasan ? `<p class="text-sm text-slate-600">Alasan: ${escapeHtml(p.alasan)}</p>` : ''}
                <p class="text-xs text-slate-500">Diajukan ${escapeHtml(p.pengaju)} · ${escapeHtml(p.company)} · ${escapeHtml(p.site)} · ${escapeHtml(p.waktu)}</p>
            </div>
            <div class="flex gap-2 flex-shrink-0">
                ${p.bisa_batal ? `<button type="button" class="btn-secondary btn-sm" data-on-click="batalkanPengajuan" data-arg="${p.id_pengajuan}">Batalkan</button>` : ''}
                ${p.bisa_setujui ? `<button type="button" class="btn-secondary btn-sm text-red-600" data-on-click="bukaPutusan" data-arg="${p.id_pengajuan}|tolak">Tolak</button>
                    <button type="button" class="btn-primary btn-sm" data-on-click="bukaPutusan" data-arg="${p.id_pengajuan}|setujui">Setujui</button>` : ''}
            </div>
        </div>
        ${riwayat ? `<details class="text-xs text-slate-600"><summary class="cursor-pointer text-slate-500">Riwayat</summary><ul class="mt-1 space-y-0.5">${riwayat}</ul></details>` : ''}
    </div>`;
}

function bukaPutusan(id, aksi) {
    const p = dataPengajuan.find(x => x.id_pengajuan === Number(id));
    if (!p) return;
    putusan = { id: p.id_pengajuan, aksi };
    const tolak = aksi === 'tolak';
    document.getElementById('formPutusan').reset();
    document.getElementById('judulPutusan').textContent = tolak ? 'Tolak Pengajuan' : 'Setujui Pengajuan';
    document.getElementById('ringkasPutusan').textContent = `${p.nama_jenis}: ${p.judul}` +
        (tolak ? '' : '. Setelah disetujui, langsung berlaku.');
    document.getElementById('catatanPutusan').required = tolak;
    document.getElementById('hintPutusan').textContent = tolak ? 'Alasan penolakan wajib diisi dan dikirim ke yang mengajukan.' : 'Opsional.';
    const btn = document.getElementById('btnPutusan');
    btn.textContent = tolak ? 'Tolak' : 'Setujui';
    btn.className = tolak ? 'btn-danger' : 'btn-primary';
    openModal('modalPutusan');
    document.getElementById('catatanPutusan').focus();
}

document.getElementById('formPutusan').addEventListener('submit', async e => {
    e.preventDefault();
    if (!putusan) return;
    const data = await denganTombol(document.getElementById('btnPutusan'),
        () => kirimForm(`/api/persetujuan/${putusan.id}/${putusan.aksi}`, { catatan: document.getElementById('catatanPutusan').value }), 'Menyimpan...');
    if (!tampilkanHasil(data)) return;
    closeModal('modalPutusan');
    muatPengajuan();
    if (typeof muatBlacklist === 'function' && blacklistDimuat) muatBlacklist();
    if (typeof muatNotifikasi === 'function') muatNotifikasi();
});

async function batalkanPengajuan(id) {
    const ok = await Dialog.konfirmasi({ judul: 'Batalkan pengajuan?', pesan: 'Pengajuan ini tidak akan diproses lagi.', teksYa: 'Batalkan Pengajuan', bahaya: true });
    if (!ok) return;
    const data = await kirimForm(`/api/persetujuan/${id}/batalkan`, {});
    if (tampilkanHasil(data)) muatPengajuan();
}
