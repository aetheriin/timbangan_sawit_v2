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

// POST form sederhana (data = objek), hasil JSON
function kirimForm(url, data) {
    const formData = new FormData();
    Object.entries(data).forEach(([k, v]) => formData.append(k, v ?? ''));
    return fetch(url, { method: 'POST', body: formData }).then(r => r.json());
}

// GET JSON; kembalikan { error } bila server / jaringan gagal
async function ambilJson(url) {
    try {
        const res = await fetch(url);
        return await res.json();
    } catch (err) {
        return { error: 'Gagal menghubungi server' };
    }
}

// ===== FORMAT PERSONEL =====
// ID tidak pernah berubah (006), Kode diisi HO (PRGBS-001). Tampilan: "Kode · Nama" atau "ID 014 · Nama".
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
    return kode ? escapeHtml(kode) : '<span class="text-amber-700 font-medium">— belum ada kode</span>';
}

function barisKosong(kolom, teks) {
    return `<tr><td colspan="${kolom}" class="table-cell text-slate-400 text-center py-8">${escapeHtml(teks)}</td></tr>`;
}

// Filter chip: aktifkan chip yang diklik di dalam grupnya
function aktifkanChip(el) {
    el.parentElement.querySelectorAll('.chip').forEach(c => c.classList.toggle('chip-active', c === el));
}
