// ===== ADMIN > VOID TIKET =====
let hariVoid = 1;
let timerCariVoid = null;

document.addEventListener('DOMContentLoaded', muatTiketVoid);

function filterHariVoid(el) {
    aktifkanChip(el);
    hariVoid = Number(el.dataset.hari);
    muatTiketVoid();
}

function cariTiketVoid() {
    clearTimeout(timerCariVoid);
    timerCariVoid = setTimeout(muatTiketVoid, 300);
}

async function muatTiketVoid() {
    const q = document.getElementById('cariTiketVoid').value.trim();
    const data = await ambilJson(`/api/admin/tiket?hari=${hariVoid}&cari=${encodeURIComponent(q)}`);
    const tbody = document.getElementById('tabelTiketVoid');
    if (data.error) { tbody.innerHTML = barisKosong(8, data.error); return false; }
    tbody.innerHTML = data.map(t => `
        <tr class="hover:bg-slate-50${t.status_alur === 'VOID' ? ' text-slate-400' : ''}">
            <td class="table-cell whitespace-nowrap">${escapeHtml(t.created_at)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(t.no_tiket)}</td>
            <td class="table-cell">${escapeHtml(t.no_plat)}</td>
            <td class="table-cell">${escapeHtml(t.customer)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(t.no_do || '-')}</td>
            <td class="table-cell">${badgeStatusTiket(t.status_alur)}</td>
            <td class="table-cell text-xs">${t.status_alur === 'VOID'
                ? `${escapeHtml(t.alasan_void || '')}<div class="text-slate-400">${escapeHtml(t.void_oleh || '')} · ${escapeHtml(t.void_at || '')}</div>` : '-'}</td>
            <td class="table-cell text-right">${t.status_alur === 'VOID' ? '' : `<button type="button" class="link-aksi text-red-600"
                data-on-click="bukaVoid" data-arg="${escapeHtml(t.no_tiket)}">Void</button>`}</td>
        </tr>`).join('') || barisKosong(8, 'Tidak ada tiket pada rentang ini');
    catatanBatas(tbody, data.length, 500, 8);
}

function bukaVoid(noTiket) {
    const form = document.getElementById('formVoid');
    form.reset();
    form.elements.no_tiket.value = noTiket;
    document.getElementById('voidNoTiket').textContent = noTiket;
    openModal('modalVoid');
    document.getElementById('voidAlasan').focus();
}

document.getElementById('formVoid').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/tiket/void', { modal: 'modalVoid', setelahnya: muatTiketVoid });
});
