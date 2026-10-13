// ===== PINTASAN KEYBOARD =====
// Ctrl+K atau /  : pencarian (cari.js)          ?   : daftar pintasan
// G lalu huruf   : pindah menu (G D = Dashboard, G L = List, G F = Form, ...), G lalu 1-9 = menu sidebar ke-n
// G N            : Tiket Baru (bila boleh)
// Pintasan dua tombol (G lalu huruf) supaya ketikan biasa / scanner barcode tidak memindahkan halaman.
// Tidak aktif saat kursor di kotak isian atau ada modal terbuka. Menu hanya yang memang tampil di sidebar user ini.
const PINTASAN_MENU = [
    ['d', '/dashboard', 'Dashboard'],
    ['l', 'view=list', 'List'],
    ['f', 'view=form', 'Form / Stasiun Timbang'],
    ['r', '/face-recognition', 'Face Recognition'],
    ['b', '/blacklist', 'Blacklist'],
    ['t', '/tamu', 'Tamu'],
    ['k', '/kontrak', 'Kontrak & DO'],
    ['e', '/kelebihan-do', 'Kelebihan DO'],
    ['m', '/master', 'Data Master'],
];
let pintasanG = 0;                       // waktu tombol G ditekan (menunggu huruf berikutnya, 1,5 detik)

const linkSidebar = () => [...document.querySelectorAll('.sidebar-link')];
const linkMenu = pola => linkSidebar().find(a => (a.getAttribute('href') || '').includes(pola));

function sedangMengetik(e) {
    const el = e.target;
    return el.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
}
const adaModalTerbuka = () => !!document.querySelector('.modal-overlay.flex, #cariOverlay:not(.hidden), #pintasanOverlay');

document.addEventListener('keydown', e => {
    if (e.ctrlKey || e.altKey || e.metaKey || sedangMengetik(e)) return;
    if (e.key === 'Escape') { tutupPintasan(); return; }
    if (adaModalTerbuka()) return;
    const k = e.key.toLowerCase();
    if (Date.now() - pintasanG < 1500) {
        pintasanG = 0;
        let tujuan = null;
        if (/^[1-9]$/.test(k)) tujuan = linkSidebar()[Number(k) - 1];
        else if (k === 'n') tujuan = document.querySelector('.topbar a.btn-primary');
        else tujuan = linkMenu((PINTASAN_MENU.find(p => p[0] === k) || [])[1] || '\0');
        if (tujuan) { e.preventDefault(); tujuan.click(); }
        return;
    }
    if (k === 'g') { pintasanG = Date.now(); return; }
    if (e.key === '/' && typeof bukaCari === 'function') { e.preventDefault(); bukaCari(); return; }
    if (e.key === '?') { e.preventDefault(); bukaPintasan(); }
});

function bukaPintasan() {
    const baris = (tombol, ket) => `<div class="flex items-center justify-between gap-4 py-1.5">
        <span class="text-slate-600">${ket}</span><span class="flex gap-1">${tombol.map(t => `<kbd class="topbar-kbd">${t}</kbd>`).join('')}</span></div>`;
    const menu = PINTASAN_MENU.filter(p => linkMenu(p[1])).map(p => baris(['G', p[0].toUpperCase()], p[2]));
    const umum = [baris(['Ctrl', 'K'], 'Cari (plat, tiket, DO, supir, menu)'), baris(['/'], 'Cari'),
        baris(['G', '1–9'], 'Menu sidebar ke-1 s/d 9')];
    if (document.querySelector('.topbar a.btn-primary')) umum.push(baris(['G', 'N'], 'Tiket Baru'));
    umum.push(baris(['?'], 'Daftar pintasan ini'), baris(['Esc'], 'Tutup'));
    const ov = document.createElement('div');
    ov.id = 'pintasanOverlay';
    ov.className = 'cari-overlay';
    ov.innerHTML = `<div class="cari-box max-w-lg" role="dialog" aria-label="Pintasan keyboard">
        <div class="flex items-center justify-between px-5 py-3.5 border-b border-slate-100">
            <span class="font-bold text-slate-900"><i class="fa-regular fa-keyboard mr-2 text-slate-400"></i>Pintasan Keyboard</span>
            <button type="button" class="sidebar-ikon-btn" data-on-click="tutupPintasan" title="Tutup"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <div class="overflow-y-auto px-5 py-3 text-sm divide-y divide-slate-100">${umum.join('')}${menu.join('')}</div>
        <p class="px-5 py-2.5 text-[11px] text-slate-500 bg-slate-50 border-t border-slate-100">Tekan G, lepas, lalu huruf dalam 1,5 detik. Tidak berlaku saat mengetik di kotak isian.</p>
    </div>`;
    ov.addEventListener('click', e => { if (e.target === ov) tutupPintasan(); });
    document.body.appendChild(ov);
}

function tutupPintasan() { document.getElementById('pintasanOverlay')?.remove(); }
