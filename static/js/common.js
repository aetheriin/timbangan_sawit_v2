// ===== HELPER BERSAMA (semua halaman) =====

function openModal(id) {
    document.getElementById(id).classList.remove('hidden');
    document.getElementById(id).classList.add('flex');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('flex');
    document.getElementById(id).classList.add('hidden');
}

function escapeHtml(teks) {
    return String(teks ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// File upload (foto wajah, surat) disimpan privat: dibuka lewat /berkas/... yang wajib login
function urlBerkas(path) {
    return path ? `/berkas/${String(path).split('/').map(encodeURIComponent).join('/')}` : '';
}

// ===== FORMAT PERSONEL =====
function formatIdPersonel(id) {
    return String(id ?? '').padStart(3, '0');
}

function formatNamaPersonel(kode, id, nama) {
    return kode ? `${kode} · ${nama}` : `ID ${formatIdPersonel(id)} · ${nama}`;
}

const LABEL_KATEGORI = {
    DRIVER: ['DRIVER', 'bg-blue-100 text-blue-700'],
    SECURITY: ['SECURITY', 'bg-slate-900 text-white'],
    EMPLOYEE: ['EMPLOYEE HO', 'bg-slate-200 text-slate-600'],
};

const WARNA_BADGE = {
    hijau: 'bg-emerald-100 text-emerald-700',
    oranye: 'bg-amber-100 text-amber-700',
    abu: 'bg-slate-200 text-slate-600',
    biru: 'bg-blue-100 text-blue-700',
    merah: 'bg-red-100 text-red-700',
};

function badge(label, warna) {
    return `<span class="badge-status ${warna}">${escapeHtml(label)}</span>`;
}

function badgeKategori(kategori) {
    const [label, warna] = LABEL_KATEGORI[kategori] || [kategori, 'bg-slate-200 text-slate-600'];
    return badge(label, warna);
}

function kodeAtauKosong(kode) {
    return kode ? escapeHtml(kode) : '<span class="text-amber-700 font-medium">Belum ada kode</span>';
}

// Kode sistem -> teks tampilan: 'SECURITY_REGISTER' -> 'Security Register' (untuk kode yang belum punya label)
function labelKode(kode) {
    if (!kode) return '';
    return String(kode).toLowerCase().split(/[_\-]+/).filter(Boolean)
        .map(k => k[0].toUpperCase() + k.slice(1)).join(' ');
}

// Status alur tiket: [label, warna badge]
const LABEL_STATUS_TIKET = {
    SECURITY_REGISTER: ['Registrasi Security', 'bg-amber-100 text-amber-700'],
    TIMBANG_1: ['Timbang 1', 'bg-blue-100 text-blue-700'],
    TIMBANG_2: ['Timbang 2', 'bg-indigo-100 text-indigo-700'],
    SELESAI: ['Selesai', 'bg-emerald-100 text-emerald-700'],
    REJECTED: ['Ditolak', 'bg-red-100 text-red-700'],
    VOID: ['Void', 'bg-slate-200 text-slate-500'],
};

function labelStatusTiket(status) {
    return (LABEL_STATUS_TIKET[status] || [labelKode(status)])[0];
}

function badgeStatusTiket(status) {
    const [label, warna] = LABEL_STATUS_TIKET[status] || [labelKode(status), 'bg-slate-200 text-slate-600'];
    return badge(label, warna);
}

// Tombol pilih file yang memicu <input type="file"> tersembunyi
function klikElemen(id) {
    document.getElementById(id).click();
}

function tampilkanNamaFile(input, idTarget) {
    document.getElementById(idTarget).textContent = input.files[0] ? input.files[0].name : '';
}

// Daftar dibatasi server (mis. 200 baris terbaru) supaya ringan; beri tahu user bila batas tercapai
function catatanBatas(tbody, jumlah, batas, kolom) {
    if (jumlah < batas) return;
    tbody.insertAdjacentHTML('beforeend', `<tr><td colspan="${kolom}" class="table-cell text-center text-xs text-slate-500 py-3">
        Menampilkan ${batas} data terbaru. Gunakan pencarian / filter untuk data lain.</td></tr>`);
}

function barisKosong(kolom, teks) {
    return `<tr><td colspan="${kolom}" class="table-cell text-slate-400 text-center py-8">${escapeHtml(teks)}</td></tr>`;
}

// Filter chip: aktifkan chip yang diklik di dalam grupnya
function aktifkanChip(el) {
    el.parentElement.querySelectorAll('.chip').forEach(c => c.classList.toggle('chip-active', c === el));
}
