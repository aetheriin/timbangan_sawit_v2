// ===== KELEBIHAN DO: krani isi No. DO baru (Ascend) -> KTU / HO tetapkan atau kembalikan =====
let dataKelebihan = [];
let statusKelebihan = '';
let idKelebihanAktif = null;

const WARNA_STATUS_LEBIH = { MENUNGGU: WARNA_BADGE.oranye, DIKEMBALIKAN: WARNA_BADGE.merah, DIAJUKAN: WARNA_BADGE.biru, SELESAI: WARNA_BADGE.hijau };
const kg = v => `${Number(v).toLocaleString('id-ID')} kg`;

window.addEventListener('tabChange', e => { if (e.detail === 'kelebihan') muatKelebihan(); });

function filterKelebihan(el) {
    document.querySelectorAll('[data-status]').forEach(c => c.classList.toggle('chip-active', c === el));
    statusKelebihan = el.dataset.status;
    muatKelebihan();
}

async function muatKelebihan() {
    const tbody = document.getElementById('tabelKelebihan');
    const data = await ambilJson(`/api/kelebihan-do?status=${encodeURIComponent(statusKelebihan)}`);
    if (data.error) { tbody.innerHTML = barisKosong(9, data.error); return; }
    dataKelebihan = data;
    const ajukan = tbody.dataset.bolehAjukan === '1', tetapkan = tbody.dataset.bolehTetapkan === '1';
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50 align-top">
            <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(r.created_at)}${r.area ? `<div class="text-slate-400">${escapeHtml(r.area)}</div>` : ''}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.no_tiket)}<div class="text-blue-700">${escapeHtml(r.no_tiket_split)}</div></td>
            <td class="table-cell">${escapeHtml(r.no_plat)}<div class="text-xs text-slate-500">${escapeHtml(r.supir)} · ${escapeHtml(r.customer)}</div></td>
            <td class="table-cell font-mono">${escapeHtml(r.no_do)}</td>
            <td class="table-cell text-right whitespace-nowrap">${kg(r.kuota_kg)}<div class="text-xs text-slate-500">${kg(r.realisasi_kg)}</div></td>
            <td class="table-cell text-right font-semibold text-red-600 whitespace-nowrap">${kg(r.kelebihan_kg)}</td>
            <td class="table-cell">${r.no_do_baru ? `<span class="font-mono">${escapeHtml(r.no_do_baru)}</span>` : '<span class="text-slate-400">-</span>'}
                ${r.catatan ? `<div class="text-xs text-slate-500">${escapeHtml(r.catatan)}</div>` : ''}
                ${r.alasan_kembali && r.status === 'DIKEMBALIKAN' ? `<div class="text-xs text-red-600">Dikembalikan: ${escapeHtml(r.alasan_kembali)}</div>` : ''}</td>
            <td class="table-cell">${badge(labelKode(r.status), WARNA_STATUS_LEBIH[r.status] || WARNA_BADGE.abu)}
                ${r.diajukan_oleh ? `<div class="text-[11px] text-slate-400">diajukan ${escapeHtml(r.diajukan_oleh)}</div>` : ''}
                ${r.ditetapkan_oleh ? `<div class="text-[11px] text-slate-400">${r.status === 'DIKEMBALIKAN' ? 'dikembalikan' : 'ditetapkan'} ${escapeHtml(r.ditetapkan_oleh)}</div>` : ''}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                ${ajukan && ['MENUNGGU', 'DIKEMBALIKAN'].includes(r.status) ? `<button type="button" class="link-aksi text-blue-600" data-on-click="bukaAjukanDO" data-arg="${r.id_kelebihan}">Isi DO Baru</button>` : ''}
                ${tetapkan && r.status === 'DIAJUKAN' ? `<button type="button" class="link-aksi text-emerald-600" data-on-click="tetapkanKelebihan" data-arg="${r.id_kelebihan}">Tetapkan</button>
                    <button type="button" class="link-aksi text-red-600" data-on-click="kembalikanKelebihan" data-arg="${r.id_kelebihan}">Kembalikan</button>` : ''}
            </td>
        </tr>`).join('') || barisKosong(9, 'Belum ada DO yang melebihi kuota');
}

function bukaAjukanDO(id) {
    const r = dataKelebihan.find(x => x.id_kelebihan === id);
    if (!r) return;
    idKelebihanAktif = id;
    document.getElementById('ajukanInfo').textContent =
        `Tiket ${r.no_tiket_split} (${r.no_plat}) kelebihan ${kg(r.kelebihan_kg)} dari DO ${r.no_do}.`;
    document.getElementById('ajukanNoDo').value = r.no_do_baru || '';
    document.getElementById('ajukanCatatan').value = r.catatan || '';
    openModal('modalAjukanDO');
    document.getElementById('ajukanNoDo').focus();
}

async function simpanAjukanDO(btn) {
    const data = await denganTombol(btn, () => kirimForm(`/api/kelebihan-do/${idKelebihanAktif}/ajukan`, {
        no_do_baru: document.getElementById('ajukanNoDo').value.trim(),
        catatan: document.getElementById('ajukanCatatan').value.trim() }));
    if (!tampilkanHasil(data)) return;
    closeModal('modalAjukanDO');
    muatKelebihan();
}

async function tetapkanKelebihan(id) {
    const r = dataKelebihan.find(x => x.id_kelebihan === id);
    if (!await Dialog.konfirmasi({ judul: 'Tetapkan kelebihan DO?', teksYa: 'Tetapkan',
        pesan: `Tiket ${r.no_tiket_split}: ${kg(r.kelebihan_kg)} masuk DO ${r.no_do_baru}.` })) return;
    if (tampilkanHasil(await kirimForm(`/api/kelebihan-do/${id}/tetapkan`, {}))) muatKelebihan();
}

async function kembalikanKelebihan(id) {
    const alasan = (window.prompt('Alasan dikembalikan ke krani:') || '').trim();
    if (!alasan) return;
    if (tampilkanHasil(await kirimForm(`/api/kelebihan-do/${id}/kembalikan`, { alasan }))) muatKelebihan();
}
