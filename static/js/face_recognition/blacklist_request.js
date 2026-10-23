// ===== LIST REQUEST BLACKLIST: tabel pengajuan tambah / hapus blacklist =====
// Data & aksi (Setujui / Tolak / Batalkan) dari persetujuan.js; file ini hanya menggambar tabel, filter status &
// pencarian, serta detail tahap persetujuan (riwayat siapa menyetujui kapan).
const KOLOM_REQUEST = 15;
const WARNA_TAHAP = { DISETUJUI: 'bg-emerald-500', DILEWATI: 'bg-slate-300', DITOLAK: 'bg-red-500', DIBATALKAN: 'bg-slate-400' };
let dataRequest = [];

function tampilkanPengajuanTabel(data) {
    dataRequest = data;
    saringRequest();
}

function saringRequest() {
    const tbody = document.getElementById('daftarPengajuan');
    const status = document.getElementById('statusRequest').value;
    const kata = document.getElementById('cariRequest').value.trim().toLowerCase();
    const baris = dataRequest.filter(p => (!status || p.status === status) && (!kata || [p.info.nama, p.info.nik, p.info.plat,
        p.info.alias, p.pengaju, p.alasan, p.judul].some(v => String(v || '').toLowerCase().includes(kata))));
    const menunggu = dataRequest.filter(p => p.status === 'MENUNGGU').length;
    document.getElementById('totalRequest').textContent = `${baris.length} request · ${menunggu} menunggu`;
    const sel = (teks, kelas = '') => `<td class="table-cell ${kelas}">${teks ? escapeHtml(teks) : '<span class="text-slate-300">-</span>'}</td>`;
    tbody.innerHTML = baris.map(p => {
        const i = p.info || {};
        return `<tr id="pengajuan-${p.id_pengajuan}" class="hover:bg-slate-50 align-top">
            ${sel(`#${p.id_pengajuan}`, 'font-mono text-xs')}
            ${sel(p.waktu, 'font-mono text-xs whitespace-nowrap')}
            ${sel(p.pengaju, 'whitespace-nowrap')}
            ${sel(`${p.company} · ${p.site}`, 'whitespace-nowrap')}
            <td class="table-cell">${badge(p.jenis === 'BLACKLIST_HAPUS' ? 'Hapus' : 'Tambah', p.jenis === 'BLACKLIST_HAPUS' ? WARNA_BADGE.hijau : WARNA_BADGE.merah)}</td>
            <td class="table-cell font-semibold text-slate-900 whitespace-nowrap">${escapeHtml(i.nama || p.judul.replace(/^(Tambah|Hapus) blacklist /, ''))}</td>
            ${sel(i.alias)}
            ${sel(i.nik, 'font-mono text-xs')}
            <td class="table-cell max-w-xs"><p class="line-clamp-2 text-slate-700" title="${escapeHtml(p.alasan || '')}">${escapeHtml(p.alasan || '-')}</p></td>
            ${sel(i.produk)}
            <td class="table-cell">${i.kategori || p.nama_kategori ? badge(i.kategori || p.nama_kategori, WARNA_BADGE.biru) : '-'}</td>
            ${sel(i.plat, 'font-mono text-xs whitespace-nowrap')}
            ${sel(i.supplier)}
            <td class="table-cell"><div class="min-w-[12rem]">${ringkasTahap(p)}</div></td>
            <td class="table-cell text-right whitespace-nowrap">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaDetailRequest" data-arg="${p.id_pengajuan}">Detail</button>
                ${p.bisa_setujui ? `<button type="button" class="link-aksi text-red-600 ml-3" data-on-click="bukaPutusan" data-arg="${p.id_pengajuan}|tolak">Reject</button>
                    <button type="button" class="btn-primary btn-sm ml-2" data-on-click="bukaPutusan" data-arg="${p.id_pengajuan}|setujui">Approve</button>` : ''}
                ${p.bisa_batal ? `<button type="button" class="link-aksi text-slate-600 ml-3" data-on-click="batalkanPengajuan" data-arg="${p.id_pengajuan}">Batalkan</button>` : ''}</td>
        </tr>`;
    }).join('') || barisKosong(KOLOM_REQUEST, modePersetujuan === 'menunggu' ? 'Tidak ada request yang menunggu persetujuan Anda' : 'Belum ada request');
}

// Status + posisi: "Menunggu · Tahap 2/3 Mill Manager" dan titik per tahap
function ringkasTahap(p) {
    const status = badge(LABEL_STATUS[p.status] || p.status, WARNA_STATUS[p.status]);
    if (!p.tahap.length) return `${status}${p.status === 'MENUNGGU' ? '<p class="text-xs text-slate-500 mt-1">1 tahap (hak Setujui)</p>' : ''}`;
    const titik = p.tahap.map((nama, n) => {
        const warna = WARNA_TAHAP[aksiTahap(p, n + 1)] || (p.status === 'MENUNGGU' && p.langkah === n + 1 ? 'bg-amber-400 ring-2 ring-amber-200' : 'bg-slate-200');
        return `<span class="w-2.5 h-2.5 rounded-full ${warna}" title="${n + 1}. ${escapeHtml(nama)}"></span>`;
    }).join('');
    const posisi = p.status === 'MENUNGGU' ? `Tahap ${p.langkah}/${p.total_langkah} · ${escapeHtml(p.menunggu || '-')}` : '';
    return `<div class="flex items-center gap-2">${status}<span class="flex gap-1">${titik}</span></div>
        ${posisi ? `<p class="text-xs text-slate-500 mt-1">${posisi}</p>` : ''}`;
}

// Aksi terakhir di tahap n (DISETUJUI / DITOLAK / DILEWATI / DIBATALKAN), atau undefined
function aksiTahap(p, n) {
    const r = p.riwayat.filter(x => x.langkah === n && x.aksi !== 'DIAJUKAN');
    return r.length ? r[r.length - 1].aksi : undefined;
}

function bukaDetailRequest(id) {
    const p = dataRequest.find(x => x.id_pengajuan === id);
    if (!p) return;
    const i = p.info || {};
    const baris = (label, nilai) => nilai ? `<div><dt class="text-xs text-slate-500">${label}</dt><dd class="font-medium text-slate-800">${escapeHtml(nilai)}</dd></div>` : '';
    const tahap = (p.tahap.length ? p.tahap : ['Pemegang hak Setujui']).map((nama, n) => {
        const r = p.riwayat.filter(x => x.langkah === n + 1 && x.aksi !== 'DIAJUKAN').pop();
        const sekarang = p.status === 'MENUNGGU' && p.langkah === n + 1;
        const warna = r ? (WARNA_TAHAP[r.aksi] || 'bg-slate-300') : (sekarang ? 'bg-amber-400' : 'bg-slate-200');
        return `<li class="flex gap-3"><span class="mt-1 w-3 h-3 rounded-full flex-shrink-0 ${warna}"></span><div>
            <p class="font-semibold text-slate-800">Tahap ${n + 1} · ${escapeHtml(nama)}</p>
            <p class="text-xs text-slate-500">${r ? `${escapeHtml(LABEL_AKSI[r.aksi] || r.aksi)} oleh ${escapeHtml(r.oleh)} · ${escapeHtml(r.waktu)}${r.catatan ? ` — ${escapeHtml(r.catatan)}` : ''}`
                : (sekarang ? 'Menunggu persetujuan' : (p.status === 'MENUNGGU' ? 'Belum sampai' : '-'))}</p></div></li>`;
    }).join('');
    const awal = p.riwayat.find(x => x.aksi === 'DIAJUKAN');
    document.getElementById('isiDetailRequest').innerHTML = `
        <div class="flex flex-wrap items-center gap-2">${badge(p.nama_jenis, p.jenis === 'BLACKLIST_HAPUS' ? WARNA_BADGE.hijau : WARNA_BADGE.merah)}
            ${badge(LABEL_STATUS[p.status] || p.status, WARNA_STATUS[p.status])}<span class="text-xs text-slate-400 font-mono">#${p.id_pengajuan}</span></div>
        <dl class="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            ${baris('Nama', i.nama)}${baris('Alias', i.alias)}${baris('NIK', i.nik)}${baris('Status', i.kategori || p.nama_kategori)}
            ${baris('Plat Kendaraan', i.plat)}${baris('Asal Supplier', i.supplier)}${baris('Pengangkutan', i.pengangkutan)}${baris('Produk', i.produk)}
            ${baris('Pengaju', p.pengaju)}${baris('Lokasi', `${p.company} · ${p.site}`)}${baris('Tanggal', p.waktu)}
        </dl>
        ${p.alasan ? `<div><p class="text-xs text-slate-500">Alasan</p><p class="text-sm text-slate-800 whitespace-pre-line">${escapeHtml(p.alasan)}</p></div>` : ''}
        <div><p class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Tahap Persetujuan</p>
            <ol class="space-y-3 text-sm">
                <li class="flex gap-3"><span class="mt-1 w-3 h-3 rounded-full flex-shrink-0 bg-blue-500"></span><div>
                    <p class="font-semibold text-slate-800">Diajukan</p>
                    <p class="text-xs text-slate-500">${escapeHtml(p.pengaju)}${awal ? ` · ${escapeHtml(awal.waktu)}` : ''}</p></div></li>
                ${tahap}
            </ol></div>`;
    const aksi = document.getElementById('aksiDetailRequest');
    aksi.innerHTML = p.bisa_setujui ? `<button type="button" class="btn-secondary text-red-600" data-on-click="putusanDariDetail" data-arg="${p.id_pengajuan}|tolak">Reject</button>
        <button type="button" class="btn-primary" data-on-click="putusanDariDetail" data-arg="${p.id_pengajuan}|setujui">Approve</button>` : '';
    openModal('modalDetailRequest');
}

function putusanDariDetail(id, aksi) {
    closeModal('modalDetailRequest');
    bukaPutusan(id, aksi);
}
