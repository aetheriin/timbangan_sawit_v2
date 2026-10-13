// ===== ADMIN > SESI AKTIF =====
// Diperbarui otomatis tiap 10 detik (selama tab browser terlihat): login dari PC lain dan kunci login baru langsung muncul.
const pollingSesi = new Poller(() => muatSesi({ polling: true }), 10000);

document.addEventListener('DOMContentLoaded', () => pollingSesi.start());

// "Mozilla/5.0 (Windows NT 10.0; ...) Chrome/140.0..." -> "Chrome 140 · Windows"
function ringkasBrowser(agen) {
    const browser = [['Edg/', 'Edge'], ['OPR/', 'Opera'], ['Firefox/', 'Firefox'], ['Chrome/', 'Chrome'], ['Version/', 'Safari']]
        .map(([kode, nama]) => { const m = agen.match(new RegExp(kode.replace('/', '\\/') + '(\\d+)')); return m && `${nama} ${m[1]}`; })
        .find(Boolean) || 'Browser lain';
    const os = /Windows/.test(agen) ? 'Windows' : /Android/.test(agen) ? 'Android' : /iPhone|iPad/.test(agen) ? 'iOS'
        : /Mac OS/.test(agen) ? 'macOS' : /Linux/.test(agen) ? 'Linux' : '';
    return os ? `${browser} · ${os}` : browser;
}

async function muatSesi(opsi = {}) {
    const data = await ambilJson('/api/admin/sesi', opsi);
    const tSesi = document.getElementById('tabelSesi');
    const tKunci = document.getElementById('tabelTerkunci');
    if (data.error) {
        tSesi.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(data.error)}</p>`;
        tKunci.innerHTML = barisKosong(5, data.error);
        return false;
    }
    const inisial = n => (n || '?').split(/\s+/).map(x => x[0]).join('').slice(0, 2).toUpperCase();
    const info = (ikon, label, nilai, mono = false) => `<div class="flex items-center justify-between gap-3 text-sm">
        <span class="text-slate-500"><i class="fa-solid ${ikon} w-4 text-slate-400"></i> ${label}</span>
        <span class="${mono ? 'font-mono font-semibold ' : ''}text-slate-800 truncate text-right">${nilai}</span></div>`;
    tSesi.innerHTML = data.sesi.map(s => `
        <div class="card ${s.is_saya ? 'border-blue-300 ring-1 ring-blue-100' : ''}">
            <div class="flex items-start justify-between gap-3">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="w-10 h-10 rounded-lg bg-slate-100 text-slate-700 font-mono font-bold flex items-center justify-center">${escapeHtml(inisial(s.nama))}</div>
                    <div class="min-w-0">
                        <p class="font-bold text-slate-900">${escapeHtml(s.nama)} ${s.is_saya ? '<span class="ml-1 text-[11px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-1.5 rounded">Sesi Anda</span>' : ''}</p>
                        <p class="text-xs font-mono text-slate-500">${escapeHtml(s.username)} · ${badgeRole(s.role)}</p>
                    </div>
                </div>
                <span class="w-2.5 h-2.5 rounded-full ${s.idle_menit < 1 ? 'bg-emerald-500' : 'bg-amber-400'} mt-1" title="${s.idle_menit < 1 ? 'Aktif' : 'Tidak aktif'}"></span>
            </div>
            <div class="mt-4 rounded-lg bg-slate-50 border border-slate-100 p-3 space-y-2">
                ${info('fa-desktop', 'Perangkat', `<span title="${escapeHtml(s.agen)}">${escapeHtml(ringkasBrowser(s.agen))}</span>`)}
                ${info('fa-network-wired', 'IP', escapeHtml(s.ip), true)}
                ${info('fa-right-to-bracket', 'Login sejak', escapeHtml(s.login), true)}
            </div>
            <div class="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-slate-100 text-sm">
                <span class="text-slate-500"><i class="fa-regular fa-clock mr-1"></i>Tidak aktif:
                    <b class="font-mono text-slate-800">${s.idle_menit < 1 ? 'aktif' : `${s.idle_menit} menit`}</b></span>
                ${s.is_saya ? '' : `<button type="button" class="link-aksi text-red-600" data-on-click="paksaKeluar"
                    data-arg="${s.user_id}|${escapeHtml(s.username)}"><i class="fa-solid fa-right-from-bracket mr-1"></i>Paksa Keluar</button>`}
            </div>
        </div>`).join('') || '<div class="card text-center text-sm text-slate-400 lg:col-span-2">Tidak ada sesi aktif</div>';

    tKunci.innerHTML = data.terkunci.map(k => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${badge(k.jenis, k.jenis === 'IP' ? WARNA_BADGE.biru : WARNA_BADGE.oranye)}</td>
            <td class="table-cell font-mono">${escapeHtml(k.nama)}</td>
            <td class="table-cell text-xs text-slate-500">${k.dicoba.length ? escapeHtml(k.dicoba.join(', ')) : '-'}</td>
            <td class="table-cell">${durasiSingkat(k.sisa_detik)}</td>
            <td class="table-cell text-right"><button type="button" class="link-aksi text-emerald-600"
                data-on-click="bukaKunciLogin" data-arg="${escapeHtml(k.kunci)}">Buka Kunci</button></td>
        </tr>`).join('') || barisKosong(5, 'Tidak ada login yang terkunci');

    document.getElementById('infoSesiOtomatis').textContent =
        `Diperbarui otomatis tiap 10 detik · terakhir ${new Date().toLocaleTimeString('id-ID')}`;
    return true;
}

async function paksaKeluar(idUser, username) {
    const ok = await Dialog.konfirmasi({
        judul: 'Paksa keluar?', pesan: `Semua sesi ${username} di semua PC akan diakhiri. Ia harus login ulang.`,
        teksYa: 'Paksa Keluar', bahaya: true,
    });
    if (!ok) return;
    if (tampilkanHasil(await kirimForm('/api/admin/sesi/paksa-keluar', { id_user: idUser }))) muatSesi();
}

async function bukaKunciLogin(kunci) {
    if (tampilkanHasil(await kirimForm('/api/admin/sesi/buka-kunci', { kunci }))) muatSesi();
}

document.getElementById('formBukaKunci').addEventListener('submit', async e => {
    e.preventDefault();
    const data = await kirimFormAdmin(e.target, '/api/admin/sesi/buka-kunci', { setelahnya: muatSesi });
    if (data) e.target.reset();
});

async function bukaSemuaKunci() {
    const ok = await Dialog.konfirmasi({
        judul: 'Buka semua kunci login?', pesan: 'Semua username dan IP yang terkunci bisa langsung mencoba login lagi.',
        teksYa: 'Buka Semua',
    });
    if (ok && tampilkanHasil(await kirimForm('/api/admin/sesi/buka-semua', {}))) muatSesi();
}
