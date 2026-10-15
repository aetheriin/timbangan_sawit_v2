// ===== ADMIN > AUDIT ADMIN =====
let hariAuditAdmin = 7;

document.addEventListener('DOMContentLoaded', () => { muatAuditAdmin(); muatAuditData(); });

function filterAuditAdmin(el) {
    aktifkanChip(el);
    hariAuditAdmin = Number(el.dataset.hari);
    muatAuditAdmin();
    muatAuditData();
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
    saringBaris('tabelAuditData', teks);
}

// ===== Perubahan data (trigger database, migrasi 034) =====
const LABEL_AKSI_DATA = { DATA_TAMBAH: ['Tambah', WARNA_BADGE.hijau], DATA_UBAH: ['Ubah', WARNA_BADGE.biru],
                          DATA_HAPUS: ['Hapus', WARNA_BADGE.merah], KOREKSI_TIKET: ['Koreksi', WARNA_BADGE.oranye] };

function nilaiLog(v) {
    if (v === null || v === undefined || v === '') return '<span class="text-slate-400">kosong</span>';
    if (v === true || v === false) return v ? 'Ya' : 'Tidak';
    return escapeHtml(String(v).replace(/T(\d\d:\d\d:\d\d)(\.\d+)?$/, ' $1'));
}

async function muatAuditData() {
    const sel = document.getElementById('filterTabelData');
    const data = await ambilJson(`/api/admin/audit/data?hari=${hariAuditAdmin}&tabel=${encodeURIComponent(sel.value)}`);
    const tbody = document.getElementById('tabelAuditData');
    if (data.error) { tbody.innerHTML = barisKosong(5, data.error); return; }
    if (sel.options.length === 1) Object.entries(data.tabel).forEach(([k, v]) => sel.add(new Option(v, k)));
    tbody.innerHTML = data.data.map(r => {
        const [label, warna] = LABEL_AKSI_DATA[r.aksi] || [labelKode(r.aksi), WARNA_BADGE.abu];
        const isi = r.aksi === 'DATA_UBAH' || r.aksi === 'KOREKSI_TIKET'
            ? r.perubahan.map(p => `<div><span class="font-mono text-slate-500">${escapeHtml(p.kolom)}</span>: <span class="line-through text-red-600">${nilaiLog(p.lama)}</span> → <span class="text-emerald-700">${nilaiLog(p.baru)}</span></div>`).join('')
            : r.perubahan.slice(0, 6).map(p => `<span class="font-mono text-slate-500">${escapeHtml(p.kolom)}</span>=${nilaiLog(r.aksi === 'DATA_HAPUS' ? p.lama : p.baru)}`).join(' · ');
        return `<tr class="hover:bg-slate-50 align-top" data-cari="${escapeHtml(`${r.nama_tabel} ${r.id_baris} ${r.oleh || ''} ${JSON.stringify(r.perubahan)}`.toLowerCase())}">
            <td class="table-cell whitespace-nowrap">${escapeHtml(r.waktu)}</td>
            <td class="table-cell">${r.oleh ? `${escapeHtml(r.oleh)} <span class="text-xs text-slate-400 font-mono">${escapeHtml(r.username)}</span>`
                                            : '<span class="text-amber-700 text-xs">Langsung di database</span>'}</td>
            <td class="table-cell">${escapeHtml(r.nama_tabel)} <span class="font-mono text-xs text-slate-500">#${escapeHtml(r.id_baris)}</span></td>
            <td class="table-cell">${badge(label, warna)}</td>
            <td class="table-cell text-xs text-slate-700 space-y-0.5">${isi || '-'}</td>
        </tr>`;
    }).join('') || barisKosong(5, 'Belum ada perubahan data pada rentang ini');
    catatanBatas(tbody, data.data.length, 500, 5);
    saringBaris('tabelAuditData', document.getElementById('cariAuditAdmin').value);
}

// Rantai hash log_aktivitas: setiap baris membawa hash baris sebelumnya, jadi ubah / hapus langsung di DB ketahuan
async function verifikasiLog(btn) {
    const data = await denganTombol(btn, () => ambilJson('/api/admin/audit/verifikasi'), 'Memeriksa...');
    const el = document.getElementById('hasilVerifikasiLog');
    if (data.error) { el.className = 'text-xs text-red-600'; el.textContent = data.error; return; }
    if (data.utuh) {
        el.className = 'text-xs text-emerald-600';
        el.textContent = `✓ ${Number(data.jumlah).toLocaleString('id-ID')} log utuh`;
        return;
    }
    el.className = 'text-xs text-red-600 font-semibold';
    const r = data.rusak[0];
    el.textContent = `✗ Rantai rusak mulai log #${r.id_log} (${r.waktu}, ${r.kategori} ${r.aksi}: ${labelKode(r.masalah)})`;
}
