// ===== HELPER BERSAMA HALAMAN ADMIN =====
// Setiap halaman admin punya file sendiri (users.js, sesi.js, ...); fungsi di sini dipakai bersama.

const LABEL_ROLE = {
    ADMIN: ['Admin', 'bg-slate-900 text-white'],
    HO: ['HO', 'bg-blue-100 text-blue-700'],
    SECURITY: ['Security', 'bg-amber-100 text-amber-700'],
    OPERATOR_TIMBANG: ['Operator Timbang', 'bg-emerald-100 text-emerald-700'],
    SORTASI: ['Sortasi', 'bg-lime-100 text-lime-700'],
    LAB: ['Lab', 'bg-violet-100 text-violet-700'],
};

function badgeRole(role) {
    const [label, warna] = LABEL_ROLE[role] || [labelKode(role), WARNA_BADGE.abu];
    return badge(label, warna);
}

function badgeAktif(aktif, teksAktif = 'Aktif', teksNonaktif = 'Nonaktif') {
    return aktif ? badge(teksAktif, WARNA_BADGE.hijau) : badge(teksNonaktif, WARNA_BADGE.abu);
}

// Isi form dari objek: <input name="x"> <- data.x
function isiForm(form, data) {
    Object.entries(data).forEach(([k, v]) => {
        const el = form.elements[k];
        if (!el) return;
        if (el.type === 'checkbox') el.checked = !!v;
        else el.value = v ?? '';
    });
}

// Kirim <form> ke url. Sukses -> notifikasi, tutup modal (bila ada), jalankan setelahnya().
async function kirimFormAdmin(form, url, { modal = null, setelahnya = null } = {}) {
    const btn = form.querySelector('[type=submit]');
    const data = await denganTombol(btn, () => kirimForm(url, new FormData(form)));
    if (!tampilkanHasil(data)) return null;
    if (modal) closeModal(modal);
    if (setelahnya) setelahnya(data);
    return data;
}

// Aktif / nonaktif dengan konfirmasi. jenis = 'user', 'supplier', dst. (untuk teks dialog)
async function konfirmasiAktif({ url, aktif, nama, jenis, pesanNonaktif = '', data = {}, setelahnya }) {
    const ok = await Dialog.konfirmasi({
        judul: `${aktif ? 'Aktifkan' : 'Nonaktifkan'} ${jenis}?`,
        pesan: aktif ? `${nama} akan aktif kembali.` : `${nama} dinonaktifkan. ${pesanNonaktif}`,
        teksYa: aktif ? 'Aktifkan' : 'Nonaktifkan', bahaya: !aktif,
    });
    if (!ok) return;
    const hasil = await kirimForm(url, { ...data, aktif: aktif ? 1 : 0 });
    if (tampilkanHasil(hasil) && setelahnya) setelahnya();
}

function durasiSingkat(detik) {
    if (detik == null) return '-';
    if (detik < 60) return `${detik} detik`;
    if (detik < 3600) return `${Math.floor(detik / 60)} menit`;
    if (detik < 86400) return `${Math.floor(detik / 3600)} jam`;
    return `${Math.floor(detik / 86400)} hari`;
}

// Cari di tabel yang sudah dimuat (tanpa request ulang ke server)
function saringBaris(tbodyId, teks) {
    const q = teks.trim().toLowerCase();
    document.querySelectorAll(`#${tbodyId} tr[data-cari]`).forEach(tr => {
        tr.classList.toggle('hidden', q && !tr.dataset.cari.includes(q));
    });
    Halaman.segarkan(document.getElementById(tbodyId));
}

// Tombol Muat Ulang / Cek Ulang: ikon berputar selama memuat, lalu konfirmasi.
// <button data-on-click="muatUlang" data-arg="$el|muatSesi">
async function muatUlang(btn, namaFungsi) {
    const ikon = btn.querySelector('i');
    btn.disabled = true;
    if (ikon) ikon.classList.add('fa-spin');
    const mulai = Date.now();
    try {
        const ok = await window[namaFungsi]();          // fungsi muat mengembalikan false bila gagal
        await new Promise(r => setTimeout(r, Math.max(0, 400 - (Date.now() - mulai))));   // putaran sempat terlihat
        if (ok !== false) Notif.sukses(`Data sudah diperbarui (${new Date().toLocaleTimeString('id-ID')})`);
    } finally {
        btn.disabled = false;
        if (ikon) ikon.classList.remove('fa-spin');
    }
}
