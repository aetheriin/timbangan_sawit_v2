// ===== ADMIN > AUDIT ADMIN =====
let hariAuditAdmin = 7;

document.addEventListener('DOMContentLoaded', muatAuditAdmin);

function filterAuditAdmin(el) {
    aktifkanChip(el);
    hariAuditAdmin = Number(el.dataset.hari);
    muatAuditAdmin();
}

function warnaAksiAdmin(aksi) {
    if (/NONAKTIF|PAKSA|RESET|GANTI_TOKEN/.test(aksi)) return WARNA_BADGE.merah;
    if (/TAMBAH|AKTIF|BUKA/.test(aksi)) return WARNA_BADGE.hijau;
    return WARNA_BADGE.biru;
}

async function muatAuditAdmin() {
    const data = await ambilJson(`/api/admin/audit?hari=${hariAuditAdmin}`);
    const tbody = document.getElementById('tabelAuditAdmin');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50" data-cari="${escapeHtml(`${r.aksi} ${r.target || ''} ${r.oleh} ${r.detail || ''}`.toLowerCase())}">
            <td class="table-cell whitespace-nowrap">${escapeHtml(r.created_at)}</td>
            <td class="table-cell">${escapeHtml(r.oleh)} <span class="text-xs text-slate-400 font-mono">${escapeHtml(r.username)}</span></td>
            <td class="table-cell">${badge(labelKode(r.aksi), warnaAksiAdmin(r.aksi))}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.target || '-')}</td>
            <td class="table-cell text-xs text-slate-600">${escapeHtml(r.detail || '-')}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.ip_address || '-')}</td>
        </tr>`).join('') || barisKosong(6, 'Belum ada perubahan pada rentang ini');
    catatanBatas(tbody, data.length, 300, 6);
    saringBaris('tabelAuditAdmin', document.getElementById('cariAuditAdmin').value);
}

function cariAuditAdmin(teks) {
    saringBaris('tabelAuditAdmin', teks);
}
