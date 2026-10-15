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
    DRIVER: ['SUPIR', 'bg-blue-100 text-blue-700'],
    SECURITY: ['SECURITY', 'bg-slate-900 text-white'],
    EMPLOYEE: ['KARYAWAN HO', 'bg-slate-200 text-slate-600'],
    TAMU: ['TAMU', 'bg-amber-100 text-amber-700'],
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
    TIMBANG_2: ['Timbang 2', 'bg-blue-100 text-blue-700'],
    SELESAI: ['Selesai', 'bg-emerald-100 text-emerald-700'],
    REJECTED: ['Ditolak', 'bg-red-100 text-red-700'],
    VOID: ['Dibatalkan', 'bg-slate-200 text-slate-500'],
};

// Nama & warna status dari Admin › Organisasi › Status Tiket menimpa label bawaan di atas
const KELAS_WARNA_STATUS = {
    abu: 'bg-slate-200 text-slate-600', biru: 'bg-blue-100 text-blue-700', hijau: 'bg-emerald-100 text-emerald-700',
    oranye: 'bg-amber-100 text-amber-700', merah: 'bg-red-100 text-red-700', ungu: 'bg-violet-100 text-violet-700',
    kuning: 'bg-yellow-100 text-yellow-800', toska: 'bg-teal-100 text-teal-700',
};
try {
    (JSON.parse(document.getElementById('dataStatusTiket')?.dataset.status || '[]') || []).forEach(s => {
        LABEL_STATUS_TIKET[s.kode] = [s.nama, KELAS_WARNA_STATUS[s.warna] || KELAS_WARNA_STATUS.abu];
    });
} catch (e) { /* data status rusak: pakai label bawaan */ }

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

// Baris tabel kosong: ikon + teks, opsional tombol aksi { label, fungsi, arg } (mis. "Tambah Blacklist")
function barisKosong(kolom, teks, aksi = null) {
    const tombol = aksi ? `<button type="button" class="btn-primary btn-sm mt-3" data-on-click="${escapeHtml(aksi.fungsi)}"
        ${aksi.arg != null ? `data-arg="${escapeHtml(aksi.arg)}"` : ''}><i class="fa-solid fa-plus"></i> ${escapeHtml(aksi.label)}</button>` : '';
    return `<tr><td colspan="${kolom}" class="table-cell text-center py-10">
        <i class="fa-regular fa-folder-open text-2xl text-slate-300"></i>
        <p class="text-sm text-slate-500 mt-2">${escapeHtml(teks)}</p>${tombol}</td></tr>`;
}

// Tombol aksi untuk tabel kosong, hanya bila tombol tambahnya memang tampil di halaman (sesuai hak akses)
function aksiKosong(fungsi, label) {
    return document.querySelector(`button[data-on-click="${fungsi}"]`) ? { fungsi, label } : null;
}

// Filter chip: aktifkan chip yang diklik di dalam grupnya
function aktifkanChip(el) {
    el.parentElement.querySelectorAll('.chip').forEach(c => c.classList.toggle('chip-active', c === el));
}

// Tiket melewati tahap ini? (alur_tahap dari mill tiket; tiket lama tanpa mill memakai kategori produk)
function tiketPunyaTahap(t, kode) {
    if (t.alur_tahap && t.alur_tahap.length) return t.alur_tahap.includes(kode);
    return t.kategori_produk === (kode === 'SORTASI' ? 'TBS' : 'PRODUK_PKS');
}

// ===== AKSI TABEL = IKON =====
// Tombol / link teks "Ubah", "Hapus", dst. (kelas link-aksi) otomatis diganti ikon + tooltip; warna teks lama tetap.
// Berlaku juga untuk baris yang dirender belakangan (MutationObserver). Label yang tidak dikenal tetap berupa teks.
const IKON_AKSI = {
    'Ubah': 'fa-pen', 'Edit': 'fa-pen', 'Hapus': 'fa-trash-can', 'Nonaktifkan': 'fa-toggle-off', 'Aktifkan': 'fa-toggle-on',
    'Atur Ulang Password': 'fa-key', 'Hak Akses': 'fa-user-shield', 'Periksa': 'fa-clipboard-check', 'Paksa Keluar': 'fa-right-from-bracket', 'Keluar': 'fa-right-from-bracket',
    'Lihat Slip': 'fa-print', 'Cetak QR': 'fa-print', 'Buka': 'fa-arrow-up-right-from-square', 'Void': 'fa-ban', 'Batalkan': 'fa-ban',
    'Lampirkan Surat': 'fa-paperclip', 'Lampirkan BA': 'fa-paperclip', 'Lampirkan': 'fa-paperclip', 'Lihat Surat': 'fa-file-lines',
    'Tetapkan': 'fa-circle-check', 'Kembalikan': 'fa-rotate-left', 'Isi DO Baru': 'fa-file-pen', 'Ganti Token': 'fa-key',
    'Data mentah': 'fa-wave-square', 'Buka Kunci': 'fa-lock-open',
};

function ikonkanAksi(akar) {
    (akar.querySelectorAll ? akar.querySelectorAll('.link-aksi') : []).forEach(el => {
        const teks = el.textContent.trim();
        const ikon = IKON_AKSI[teks];
        if (!ikon) return;
        el.title = el.title || teks;
        el.setAttribute('aria-label', teks);
        el.innerHTML = `<i class="fa-solid ${ikon}"></i>`;
        el.classList.replace('link-aksi', 'aksi-tombol');
    });
}
// ===== AMAN DARI TERJEMAHAN BROWSER (Chrome Translate) =====
// Kode (No. Tiket, plat, NIK, angka: huruf .font-mono), panel kamera, dan panel indikator timbangan tidak ikut
// diterjemahkan: teksnya data / diperbarui terus oleh kode, dan terjemahan otomatis bisa membuatnya kacau.
const PILIH_JANGAN_TERJEMAH = '.font-mono, .indikator-panel, .kode-plat';
function janganTerjemah(akar) {
    if (akar.matches && akar.matches(PILIH_JANGAN_TERJEMAH)) akar.setAttribute('translate', 'no');
    akar.querySelectorAll(PILIH_JANGAN_TERJEMAH).forEach(el => el.setAttribute('translate', 'no'));
    akar.querySelectorAll('video').forEach(v => v.parentElement.setAttribute('translate', 'no'));
}

document.addEventListener('DOMContentLoaded', () => {
    ikonkanAksi(document);
    janganTerjemah(document);
    new MutationObserver(daftar => daftar.forEach(m => m.addedNodes.forEach(n => {
        if (n.nodeType === 1) { ikonkanAksi(n); janganTerjemah(n); }
    }))).observe(document.body, { childList: true, subtree: true });
});

// ===== PILIHAN TERSIMPAN PER USER (filter, tab, jumlah baris) =====
// Disimpan di browser ini (localStorage), dipisah per user & per halaman. Gagal simpan (mode privat) diabaikan.
// <select data-simpan="nama"> / <input data-simpan="nama">: nilai dipulihkan saat halaman dibuka & disimpan saat berubah.
const Pilihan = {
    kunci(nama) { return `pilihan:${document.body.dataset.user || '-'}:${location.pathname}:${nama}`; },
    ambil(nama) { try { return localStorage.getItem(this.kunci(nama)); } catch (e) { return null; } },
    simpan(nama, nilai) { try { localStorage.setItem(this.kunci(nama), nilai); } catch (e) { /* abaikan */ } },
};

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-simpan]').forEach(el => {
        const nilai = Pilihan.ambil(el.dataset.simpan);
        // Pilihan lama yang sudah tidak ada di daftar (mis. produk dihapus) tidak dipulihkan
        if (nilai != null && (el.tagName !== 'SELECT' || [...el.options].some(o => o.value === nilai))) el.value = nilai;
        el.addEventListener('change', () => Pilihan.simpan(el.dataset.simpan, el.value));
    });
});

// ===== NOMOR PLAT (semua kotak <input data-plat>) =====
// Diketik -> langsung huruf besar. Tab / pindah kotak / mouse keluar dari kotak yang sedang diketik ->
// dirapikan ke format baku "BK 1234 AB" (pola sama dengan utils/plat_utils.py; server tetap memvalidasi).
// Teks yang bukan plat (mis. No. Tiket hasil scanner "TKT-...") hanya dijadikan huruf besar.
const POLA_PLAT_BAKU = /^([A-Z]{1,2})[\s.\-]*([1-9][0-9]{0,3})[\s.\-]*([A-Z]{0,3})$/;

function rapikanPlat(teks) {
    const t = String(teks ?? '').trim().toUpperCase().replace(/\s+/g, ' ');
    const m = t.startsWith('TKT-') ? null : t.match(POLA_PLAT_BAKU);
    return m ? m.slice(1).filter(Boolean).join(' ') : t;
}

function rapikanKotakPlat(input) {
    const rapi = rapikanPlat(input.value);
    if (rapi !== input.value) input.value = rapi;
}

document.addEventListener('input', e => {
    const el = e.target;
    if (!el.matches || !el.matches('input[data-plat]')) return;
    const besar = el.value.toUpperCase();
    if (besar === el.value) return;
    const posisi = el.selectionStart;
    el.value = besar;
    el.setSelectionRange(posisi, posisi);
});
document.addEventListener('focusout', e => { if (e.target.matches && e.target.matches('input[data-plat]')) rapikanKotakPlat(e.target); });

// ===== NIK (semua kotak <input data-nik>) =====
// Hanya angka, maksimal 16 (NIK KTP). Teks tempelan dengan spasi / titik ikut dibersihkan. Server tetap memvalidasi.
document.addEventListener('input', e => {
    const el = e.target;
    if (!el.matches || !el.matches('input[data-nik]')) return;
    const bersih = el.value.replace(/\D/g, '').slice(0, 16);
    if (bersih !== el.value) el.value = bersih;
});
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[data-plat]').forEach(el => el.addEventListener('mouseleave', () => {
        if (document.activeElement === el) rapikanKotakPlat(el);
    }));
});
