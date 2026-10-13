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
        tSesi.innerHTML = barisKosong(6, data.error);
        tKunci.innerHTML = barisKosong(5, data.error);
        return false;
    }
    const inisial = n => (n || '?').split(/\s+/).map(x => x[0]).join('').slice(0, 2).toUpperCase();
    tSesi.innerHTML = data.sesi.map(s => `
        <tr class="hover:bg-slate-50${s.is_saya ? ' bg-blue-50/40' : ''}">
            <td class="table-cell"><div class="flex items-center gap-3">
                <div class="relative w-9 h-9 rounded-lg bg-slate-100 text-slate-700 font-mono font-bold text-xs flex items-center justify-center flex-shrink-0">${escapeHtml(inisial(s.nama))}
                    <span class="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-white ${s.idle_menit < 1 ? 'bg-emerald-500' : 'bg-amber-400'}"></span></div>
                <div><p class="font-semibold text-slate-900">${escapeHtml(s.nama)}${s.is_saya ? ' <span class="text-[11px] font-semibold text-blue-700">· Anda</span>' : ''}</p>
                    <p class="text-xs font-mono text-slate-500">${escapeHtml(s.username)} ${badgeRole(s.role)}</p></div></div></td>
            <td class="table-cell text-xs text-slate-600 max-w-xs truncate" title="${escapeHtml(s.agen)}">${escapeHtml(ringkasBrowser(s.agen))}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(s.ip)}</td>
            <td class="table-cell font-mono text-xs whitespace-nowrap">${escapeHtml(s.login)}</td>
            <td class="table-cell">${s.idle_menit < 1 ? badge('Aktif', WARNA_BADGE.hijau) : `<span class="font-mono text-xs">${escapeHtml(s.idle_menit)} menit</span>`}</td>
            <td class="table-cell text-right">${s.is_saya ? '' : `<button type="button" class="link-aksi text-red-600"
                data-on-click="paksaKeluar" data-arg="${s.user_id}|${escapeHtml(s.username)}">Paksa Keluar</button>`}</td>
        </tr>`).join('') || barisKosong(6, 'Tidak ada sesi aktif');

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
