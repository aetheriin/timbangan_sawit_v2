// ===== ADMIN > LOG KEAMANAN =====
let jenisLog = '';

const WARNA_KEJADIAN = {
    LOGIN: WARNA_BADGE.hijau, LOGOUT: WARNA_BADGE.abu,
    LOGIN_GAGAL: WARNA_BADGE.oranye, LOGIN_TERKUNCI: WARNA_BADGE.merah, AKSES_DITOLAK: WARNA_BADGE.merah,
    KIOSK_DITOLAK: WARNA_BADGE.merah, CSRF_GAGAL: WARNA_BADGE.merah, TANPA_LOGIN: WARNA_BADGE.oranye,
};

document.addEventListener('DOMContentLoaded', muatLog);

function filterLog(el) {
    aktifkanChip(el);
    jenisLog = el.dataset.jenis;
    muatLog();
}

async function muatLog() {
    const data = await ambilJson(`/api/admin/log-keamanan?jenis=${encodeURIComponent(jenisLog)}`);
    const tbody = document.getElementById('tabelLog');
    if (data.error) { tbody.innerHTML = barisKosong(5, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50" data-cari="${escapeHtml(`${r.user} ${r.ip} ${r.detail} ${r.kejadian}`.toLowerCase())}">
            <td class="table-cell whitespace-nowrap">${escapeHtml(r.waktu)}</td>
            <td class="table-cell">${badge(labelKode(r.kejadian), WARNA_KEJADIAN[r.kejadian] || WARNA_BADGE.biru)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.user)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.ip)}</td>
            <td class="table-cell text-xs text-slate-600">${escapeHtml(r.detail)}</td>
        </tr>`).join('') || barisKosong(5, 'Tidak ada kejadian');
    catatanBatas(tbody, data.length, 500, 5);
    saringBaris('tabelLog', document.getElementById('cariLog').value);
}

function cariLog(teks) {
    saringBaris('tabelLog', teks);
}
