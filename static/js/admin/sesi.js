// ===== ADMIN > SESI AKTIF =====
document.addEventListener('DOMContentLoaded', muatSesi);

async function muatSesi() {
    const data = await ambilJson('/api/admin/sesi');
    const tSesi = document.getElementById('tabelSesi');
    const tKunci = document.getElementById('tabelTerkunci');
    if (data.error) {
        tSesi.innerHTML = barisKosong(7, data.error);
        tKunci.innerHTML = barisKosong(4, data.error);
        return;
    }
    tSesi.innerHTML = data.sesi.map(s => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell"><div class="font-medium">${escapeHtml(s.nama)}</div>
                <div class="text-xs text-slate-500 font-mono">${escapeHtml(s.username)}${s.is_saya ? ' · <span class="text-blue-600">Anda</span>' : ''}</div></td>
            <td class="table-cell">${badgeRole(s.role)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(s.ip)}</td>
            <td class="table-cell">${escapeHtml(s.login)}</td>
            <td class="table-cell">${s.idle_menit < 1 ? badge('Aktif', WARNA_BADGE.hijau) : escapeHtml(`${s.idle_menit} menit`)}</td>
            <td class="table-cell text-xs text-slate-500 max-w-xs truncate" title="${escapeHtml(s.agen)}">${escapeHtml(s.agen)}</td>
            <td class="table-cell text-right">${s.is_saya ? '' : `<button type="button" class="link-aksi text-red-600"
                data-on-click="paksaKeluar" data-arg="${s.user_id}|${escapeHtml(s.username)}">Paksa Keluar</button>`}</td>
        </tr>`).join('') || barisKosong(7, 'Tidak ada sesi aktif');

    tKunci.innerHTML = data.terkunci.map(k => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${badge(k.jenis, k.jenis === 'IP' ? WARNA_BADGE.biru : WARNA_BADGE.oranye)}</td>
            <td class="table-cell font-mono">${escapeHtml(k.nama)}</td>
            <td class="table-cell">${durasiSingkat(k.sisa_detik)}</td>
            <td class="table-cell text-right"><button type="button" class="link-aksi text-emerald-600"
                data-on-click="bukaKunciLogin" data-arg="${escapeHtml(k.kunci)}">Buka Kunci</button></td>
        </tr>`).join('') || barisKosong(4, 'Tidak ada login yang terkunci');
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
