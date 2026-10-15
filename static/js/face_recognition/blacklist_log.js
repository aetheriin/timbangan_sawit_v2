// ===== TAB LOG VALIDASI BLACKLIST =====
// Ringkasan hari itu, daftar orang / kendaraan yang terdeteksi (berapa kali, jam pertama & terakhir, kunjungan ke
// berapa di site ini), timeline percobaan, dan tabel semua kejadian. ?tab=log&target=P12 (dari notifikasi) memilih target.
let dataLog = null;
let targetLog = new URLSearchParams(location.search).get('target');
let logDimuat = false;

const WARNA_TINDAKAN = { DITOLAK: WARNA_BADGE.merah, PERINGATAN: WARNA_BADGE.oranye, DILOLOSKAN: WARNA_BADGE.biru };
const LABEL_TINDAKAN = { DITOLAK: 'Ditolak', PERINGATAN: 'Peringatan', DILOLOSKAN: 'Diloloskan' };
const WARNA_TITIK = { DITOLAK: 'bg-red-500', PERINGATAN: 'bg-amber-500', DILOLOSKAN: 'bg-blue-500' };

window.addEventListener('tabChange', e => {
    if (e.detail !== 'log' || logDimuat) return;
    logDimuat = true;
    const tgl = document.getElementById('logTanggal');
    if (!tgl.value) tgl.value = new Date().toLocaleDateString('sv-SE');
    muatLogBlacklist();
});

async function muatLogBlacklist() {
    const params = new URLSearchParams({ tanggal: document.getElementById('logTanggal').value });
    const area = document.getElementById('logArea');
    if (area && area.value) params.set('area', area.value);
    const data = await ambilJson(`/api/blacklist/deteksi?${params}`);
    if (data.error) { Notif.gagal(data.error); return; }
    dataLog = data;
    const r = data.ringkas;
    document.getElementById('logJmlDeteksi').textContent = r.deteksi;
    document.getElementById('logJmlTarget').textContent = r.target;
    document.getElementById('logJmlDitolak').textContent = r.ditolak;
    document.getElementById('logJmlLolos').textContent = r.diloloskan;
    tampilTargetLog();
    tampilTabelLog();
    if (!data.target.some(t => t.kode === targetLog)) targetLog = data.target[0] ? data.target[0].kode : null;
    tampilTimelineLog();
}

function tampilTargetLog() {
    document.getElementById('logTarget').innerHTML = dataLog.target.map(t => `
        <button type="button" class="w-full text-left px-4 py-3 flex items-start justify-between gap-3
            ${t.kode === targetLog ? 'bg-slate-900 text-white' : 'hover:bg-slate-50'}" data-on-click="pilihTargetLog" data-arg="${t.kode}">
            <span class="min-w-0">
                <span class="font-semibold ${t.tipe === 'KENDARAAN' ? 'font-mono' : ''}">${escapeHtml(t.tipe === 'PERSONEL'
                    ? formatNamaPersonel(t.kode_personel, Number(t.kode.slice(1)), t.nama) : t.nama)}</span>
                <span class="block text-xs ${t.kode === targetLog ? 'text-slate-300' : 'text-slate-500'}">
                    ${t.tipe === 'PERSONEL' ? 'Personel' : 'Kendaraan'} · ${t.jumlah}× terdeteksi · pertama ${t.pertama} · terakhir ${t.terakhir}</span>
            </span>
            <span class="text-xs whitespace-nowrap ${t.kode === targetLog ? 'text-slate-300' : 'text-slate-500'}">Kunjungan ke-${t.kunjungan_ke}</span>
        </button>`).join('') || '<p class="p-4 text-sm text-slate-400">Tidak ada blacklist yang terdeteksi pada tanggal ini</p>';
}

function pilihTargetLog(kode) {
    targetLog = kode;
    tampilTargetLog();
    tampilTimelineLog();
}

function tampilTimelineLog() {
    const t = dataLog.target.find(x => x.kode === targetLog);
    const judul = document.getElementById('logJudulTarget');
    const wadah = document.getElementById('logTimeline');
    if (!t) {
        judul.textContent = 'Pilih orang / kendaraan';
        document.getElementById('logKunjungan').textContent = '';
        wadah.innerHTML = '<p class="text-slate-400">Tidak ada data.</p>';
        return;
    }
    judul.textContent = `${t.nama} · ${document.getElementById('logTanggal').value.split('-').reverse().join('-')}`;
    document.getElementById('logKunjungan').textContent = `Kunjungan ke-${t.kunjungan_ke}${t.site.length ? ` · ${t.site.join(', ')}` : ''}`;
    const kejadian = dataLog.kejadian.filter(k => k.target === t.kode);
    wadah.innerHTML = `<ol class="space-y-2">${kejadian.map(k => `
        <li class="grid grid-cols-[4.5rem_0.75rem_1fr] gap-2 items-start">
            <span class="font-mono text-xs text-slate-500 pt-0.5">${escapeHtml(k.jam)}</span>
            <span class="w-2.5 h-2.5 rounded-full mt-1 ${WARNA_TITIK[k.tindakan] || 'bg-slate-400'}"></span>
            <span class="text-slate-700">${escapeHtml(k.sumber)}${k.kemiripan != null ? ` · kemiripan ±${k.kemiripan}%` : ''}
                · <b>${escapeHtml((LABEL_TINDAKAN[k.tindakan] || k.tindakan).toLowerCase())}</b>
                <span class="block text-xs text-slate-500">${escapeHtml(k.petugas || '-')}${k.site ? ` · ${escapeHtml(k.site)}` : ''}${k.no_tiket ? ` · tiket ${escapeHtml(k.no_tiket)}` : ''}</span></span>
        </li>`).join('')}</ol>
        <p class="mt-4 text-xs text-slate-500">${t.sebelumnya.length ? `Kunjungan sebelumnya: ${t.sebelumnya.map(escapeHtml).join(', ')}` : 'Belum pernah terdeteksi sebelumnya.'}</p>`;
}

function tampilTabelLog() {
    const nama = Object.fromEntries(dataLog.target.map(t => [t.kode, t.nama]));
    document.getElementById('tabelLogBlacklist').innerHTML = [...dataLog.kejadian].reverse().map(k => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell font-mono text-xs whitespace-nowrap">${escapeHtml(k.jam)}</td>
            <td class="table-cell font-semibold">${escapeHtml(nama[k.target] || '-')}</td>
            <td class="table-cell">${escapeHtml(k.sumber)}</td>
            <td class="table-cell">${badge(LABEL_TINDAKAN[k.tindakan] || k.tindakan, WARNA_TINDAKAN[k.tindakan])}</td>
            <td class="table-cell font-mono text-xs">${k.kemiripan != null ? `±${k.kemiripan}%` : '-'}</td>
            <td class="table-cell text-xs">${escapeHtml(k.site || '-')}</td>
            <td class="table-cell text-xs">${escapeHtml(k.petugas || '-')}</td>
            <td class="table-cell text-xs text-slate-600">${escapeHtml(k.keterangan || '')}</td>
        </tr>`).join('') || barisKosong(8, 'Belum ada kejadian pada tanggal ini');
}
