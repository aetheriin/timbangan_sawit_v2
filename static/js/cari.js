// ===== PENCARIAN GLOBAL (header › Cari, Ctrl+K) =====
// Kosong: aksi cepat + menu. Diketik (min 2 huruf): menu yang cocok + hasil server (tiket, personel, kendaraan / akun).
const CARI_ADMIN = !!document.querySelector('.sidebar-link[href^="/admin"]');
let cariTimer = null, cariUrutan = 0, cariPilih = 0;

function bukaCari() {
    const ov = document.getElementById('cariOverlay');
    if (!ov) return;
    ov.classList.remove('hidden');
    const input = document.getElementById('cariInput');
    input.value = '';
    tampilkanCari('', null);
    input.focus();
}

function tutupCari() { document.getElementById('cariOverlay')?.classList.add('hidden'); }
function tutupCariLuar(e) { if (e.target.id === 'cariOverlay') tutupCari(); }

// Menu dari sidebar & tombol aksi di header (hanya yang memang tampil untuk user ini)
function menuCari() {
    return Array.from(document.querySelectorAll('.sidebar-link')).map(a => ({
        judul: a.textContent.replace(/\bLive\b/, '').trim(), url: a.getAttribute('href'),
        ikon: (a.querySelector('i')?.className || 'fa-solid fa-circle').replace('sidebar-link-ikon', '').trim(),
    }));
}
function aksiCepat() {
    const aksi = Array.from(document.querySelectorAll('.topbar a.btn-primary, .topbar a.btn-light'))
        .map(a => ({ judul: a.textContent.trim(), url: a.getAttribute('href'), ikon: a.querySelector('i')?.className || '' }));
    if (!CARI_ADMIN) aksi.unshift({ judul: 'Stasiun Timbang', url: '/weighbridge?view=form&tab=timbangan', ikon: 'fa-solid fa-scale-balanced' });
    return aksi.slice(0, 3);
}

const grupCari = (judul, isi, ket = '') => isi ? `<div>
    <div class="cari-grup-judul"><span>${judul}</span><span class="normal-case font-normal">${ket}</span></div>
    <div class="space-y-0.5">${isi}</div></div>` : '';

function itemCari({ url, baru = false, ikon, kiri, kanan = '' }) {
    return `<a href="${escapeHtml(url)}"${baru ? ' target="_blank"' : ''} class="cari-item" data-cari-item>
        <span class="cari-ikon">${ikon}</span>
        <span class="flex-1 min-w-0">${kiri}</span>
        ${kanan ? `<span class="text-right flex-shrink-0">${kanan}</span>` : ''}</a>`;
}

const TIKET_SELESAI = ['SELESAI', 'REJECTED', 'VOID'];
const kg = v => v == null ? '–' : `${Number(v).toLocaleString('id-ID')} kg`;

function tampilkanCari(kata, data) {
    const k = kata.toLowerCase();
    const menu = menuCari().filter(m => !k || m.judul.toLowerCase().includes(k));
    let html = '';
    if (!k) {
        html += `<div><div class="cari-grup-judul"><span>Aksi cepat</span></div><div class="grid grid-cols-3 gap-2">${aksiCepat().map(a =>
            `<a href="${escapeHtml(a.url)}" class="cari-aksi" data-cari-item><span class="cari-ikon"><i class="${escapeHtml(a.ikon)}"></i></span>${escapeHtml(a.judul)}</a>`).join('')}</div></div>`;
    }
    html += grupCari('Menu', menu.map(m => itemCari({ url: m.url, ikon: `<i class="${escapeHtml(m.ikon)}"></i>`,
        kiri: `<span class="font-semibold text-slate-800">${escapeHtml(m.judul)}</span>` })).join(''));
    if (data && !CARI_ADMIN) {
        html += grupCari(`Tiket timbangan (${data.tiket.length})`, data.tiket.map(t => {
            const selesai = TIKET_SELESAI.includes(t.status_alur);
            return itemCari({
                url: selesai ? `/cetak/tiket/${encodeURIComponent(t.no_tiket)}` : `/weighbridge?view=form&plat=${encodeURIComponent(t.no_plat)}`,
                baru: selesai, ikon: '<i class="fa-regular fa-file-lines text-blue-600"></i>',
                kiri: `<span class="block font-mono font-semibold text-slate-900 truncate">${escapeHtml(t.no_tiket)} · ${escapeHtml(t.no_plat)}</span>
                       <span class="block text-xs text-slate-500 truncate">${escapeHtml(t.supir)} · ${escapeHtml(t.customer)} · ${escapeHtml(t.produk)}</span>`,
                kanan: `<span class="block font-mono font-bold text-slate-900">${kg(t.netto)}</span>
                        <span class="block text-[11px] text-slate-500">${selesai ? escapeHtml(t.created_at) : badgeStatusTiket(t.status_alur)}</span>`,
            });
        }).join(''), 'klik untuk buka');
        html += grupCari(`Personel (${data.personel.length})`, data.personel.map(p => itemCari({
            url: p.kategori === 'DRIVER' ? '/master?tab=personel' : '/face-recognition?tab=personel',
            ikon: `<span class="font-mono text-[10px] font-bold">${escapeHtml((p.nama_personel || '?').slice(0, 2).toUpperCase())}</span>`,
            kiri: `<span class="block font-semibold text-slate-900 truncate">${escapeHtml(p.nama_personel)}
                   ${p.is_blacklisted ? '<span class="ml-1 text-[10px] font-bold text-red-600 bg-red-50 px-1.5 rounded">BLACKLIST</span>' : ''}</span>
                   <span class="block text-xs text-slate-500">${escapeHtml(p.kode_personel || '-')} · NIK ${escapeHtml(p.nik)}</span>`,
            kanan: `<span class="text-[11px] font-semibold text-slate-500">${escapeHtml(labelKode(p.kategori))}</span>`,
        })).join(''));
        html += grupCari(`Kendaraan (${data.kendaraan.length})`, data.kendaraan.map(v => itemCari({
            url: '/master?tab=kendaraan', ikon: '<i class="fa-solid fa-truck text-slate-600"></i>',
            kiri: `<span class="block font-mono font-semibold text-slate-900">${escapeHtml(v.no_plat)}
                   ${v.is_blacklisted ? '<span class="ml-1 text-[10px] font-bold text-red-600 bg-red-50 px-1.5 rounded">BLACKLIST</span>' : ''}</span>
                   <span class="block text-xs text-slate-500">STNK ${escapeHtml(v.no_stnk)}</span>`,
        })).join(''));
    }
    if (data && CARI_ADMIN) {
        html += grupCari(`Pengguna (${data.akun.length})`, data.akun.map(u => itemCari({
            url: '/admin/users', ikon: `<span class="font-mono text-[10px] font-bold">${escapeHtml(u.nama.slice(0, 2).toUpperCase())}</span>`,
            kiri: `<span class="block font-semibold text-slate-900">${escapeHtml(u.nama)} <span class="font-mono text-xs text-slate-400">@${escapeHtml(u.username)}</span></span>
                   <span class="block text-xs text-slate-500">${escapeHtml(u.nama_level)} · ${escapeHtml(u.area)}</span>`,
            kanan: u.is_active ? '' : '<span class="text-[11px] text-red-600 font-semibold">Nonaktif</span>',
        })).join(''), 'klik untuk buka Kelola User');
    }
    if (k.length >= 2 && !data) html += '<p class="py-6 text-center text-sm text-slate-400">Mencari...</p>';
    const hasil = document.getElementById('cariHasil');
    hasil.innerHTML = html || `<p class="py-8 text-center text-sm text-slate-500">Tidak ada hasil untuk "${escapeHtml(kata)}"</p>`;
    cariPilih = 0;
    tandaiCari();
}

function tandaiCari() {
    const item = document.querySelectorAll('#cariHasil [data-cari-item]');
    item.forEach((el, i) => el.classList.toggle('cari-item-aktif', i === cariPilih));
    item[cariPilih]?.scrollIntoView({ block: 'nearest' });
}

document.getElementById('cariInput')?.addEventListener('input', e => {
    const kata = e.target.value.trim();
    clearTimeout(cariTimer);
    tampilkanCari(kata, null);
    if (kata.length < 2) return;
    const nomor = ++cariUrutan;
    cariTimer = setTimeout(async () => {
        const data = await ambilJson(`${CARI_ADMIN ? '/api/admin/cari' : '/api/cari'}?q=${encodeURIComponent(kata)}`);
        if (nomor !== cariUrutan) return;                 // ketikan sudah berubah, hasil lama dibuang
        tampilkanCari(kata, data.error ? null : data);
    }, 250);
});

document.getElementById('cariInput')?.addEventListener('keydown', e => {
    const item = document.querySelectorAll('#cariHasil [data-cari-item]');
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (item.length) cariPilih = (cariPilih + (e.key === 'ArrowDown' ? 1 : -1) + item.length) % item.length;
        tandaiCari();
    } else if (e.key === 'Enter' && item[cariPilih]) {
        e.preventDefault();
        item[cariPilih].click();
    }
});

document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); bukaCari(); }
    else if (e.key === 'Escape' && !document.getElementById('cariOverlay')?.classList.contains('hidden')) tutupCari();
});
