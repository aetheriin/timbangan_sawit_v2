// ===== TAB AUDIT LOG: aktivitas security & perubahan data personel =====
let auditDimuat = false;
let hariAudit = 1;

const LABEL_AKSI_SECURITY = {
    TRY_SCAN_BLACKLIST: WARNA_BADGE.merah,
    OVERRIDE_DRIVER: WARNA_BADGE.oranye,
    MANUAL_INPUT: WARNA_BADGE.abu,
};
const LABEL_AKSI_PERSONEL = {
    TAMBAH: WARNA_BADGE.hijau,
    UPDATE: WARNA_BADGE.biru,
    HAPUS: WARNA_BADGE.merah,
};

window.addEventListener('tabChange', e => {
    if (e.detail === 'audit' && !auditDimuat) {
        auditDimuat = true;
        muatAudit();
    }
});

function filterAudit(el) {
    aktifkanChip(el);
    hariAudit = Number(el.dataset.hari);
    document.getElementById('btnExportAudit').href = `/api/audit/export?hari=${hariAudit}`;
    muatAudit();
}

function muatAudit() {
    muatAuditSecurity();
    muatAuditPersonel();
}

async function muatAuditSecurity() {
    const data = await ambilJson(`/api/audit/security?hari=${hariAudit}`);
    const tbody = document.getElementById('tabelAuditSecurity');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell whitespace-nowrap">${escapeHtml(hariAudit === 1 ? r.created_at.slice(11) : r.created_at)}</td>
            <td class="table-cell">${escapeHtml(r.nama_user)}${r.kode_personel ? ` (${escapeHtml(r.kode_personel)})` : ` <span class="text-slate-400">${escapeHtml(r.role)}</span>`}</td>
            <td class="table-cell">${badge(r.action_type, LABEL_AKSI_SECURITY[r.action_type] || WARNA_BADGE.abu)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.no_tiket || '—')}</td>
            <td class="table-cell">${escapeHtml(r.details.keterangan || Object.entries(r.details).map(([k, v]) => `${k}: ${v}`).join(', '))}</td>
            <td class="table-cell">${escapeHtml(r.ip_address || '-')}</td>
        </tr>`).join('') || barisKosong(6, 'Tidak ada aktivitas pada rentang ini');
}

async function muatAuditPersonel() {
    const data = await ambilJson(`/api/audit/personel?hari=${hariAudit}`);
    const tbody = document.getElementById('tabelAuditPersonel');
    if (data.error) { tbody.innerHTML = barisKosong(5, data.error); return; }
    tbody.innerHTML = data.map(r => {
        let perubahan;
        if (r.aksi === 'TAMBAH') perubahan = `Personel baru: ${escapeHtml(formatNamaPersonel(r.kode_personel, r.id_personel, r.nama_personel))}`;
        else if (r.aksi === 'HAPUS') perubahan = `Dihapus: ${escapeHtml(formatNamaPersonel(r.kode_personel, r.id_personel, r.nama_personel))}`;
        else perubahan = r.perubahan.map(p => `<div><span class="text-slate-500">${escapeHtml(p.kolom)}:</span>
                ${escapeHtml(p.lama || '—')} → <b>${escapeHtml(p.baru || '—')}</b></div>`).join('') || 'Foto / kategori diperbarui';
        return `<tr class="hover:bg-slate-50 align-top">
            <td class="table-cell whitespace-nowrap">${escapeHtml(r.waktu)}</td>
            <td class="table-cell">${escapeHtml(r.id_personel)}</td>
            <td class="table-cell">${badge(r.aksi, LABEL_AKSI_PERSONEL[r.aksi] || WARNA_BADGE.abu)}</td>
            <td class="table-cell">${perubahan}</td>
            <td class="table-cell">${escapeHtml(r.oleh)}</td>
        </tr>`;
    }).join('') || barisKosong(5, 'Tidak ada perubahan pada rentang ini');
}
