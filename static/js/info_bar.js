// ===== INFO BAR (kontainer atas halaman site) =====
// Input plat / No. Tiket, foto supir, dan tombol Validasi.
// Tombol Validasi hanya tampil di tab Security dan hilang setelah plat tervalidasi (sudah punya tiket).
let statusValidasi = 'none'; // none | draft | done
const ICON_USER = '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';

function perbaruiTombolValidasi() {
    const btn = document.getElementById('btnValidasi');
    if (!btn) return;
    btn.classList.toggle('hidden', !(getTabAktif() === 'security' && statusValidasi !== 'done'));
}

window.addEventListener('tabChange', perbaruiTombolValidasi);

// ===== INPUT PLAT: Tab / Enter =====
function handlePlatKey(e) {
    if (e.key === 'Tab' && e.shiftKey) return;
    if (e.key === 'Tab' || e.key === 'Enter') {
        const val = e.target.value.trim();
        if (!val) return;
        e.preventDefault();          // cegah fokus loncat ke kotak lain
        lookupPlat(val);
    }
}

// No. Tiket (hasil scanner barcode / QR) -> cari tiket aktif
async function lookupTiket(noTiket) {
    const data = await kirimForm('/api/timbang/scan-qr', { no_tiket: noTiket });
    if (data.status === 'ADA_TIKET') terapkanHasilLookup(data);
    else Notif.gagal(data.error || 'Tiket tidak ditemukan');
}

async function lookupPlat(noPlatRaw) {
    const noPlat = (noPlatRaw || '').trim().toUpperCase();
    if (!noPlat) return;
    // Scanner barcode yang diarahkan ke kolom plat akan mengetik No. Tiket
    if (noPlat.startsWith('TKT-')) { await lookupTiket(noPlat); return; }

    const data = await kirimForm('/api/plat/lookup', { no_plat: noPlat });
    if (data.error) { Notif.gagal(data.error); return; }

    data.no_plat = data.no_plat || noPlat;   // server mengembalikan format baku, mis. 'BM 1455 JJ'
    terapkanHasilLookup(data);
}

function terapkanHasilLookup(data) {
    const tab = getTabAktif();

    // Tiket hanya boleh dibuat di Security
    if (data.status === 'DRAFT' && tab !== 'security') {
        kosongkanInfoBar();
        document.getElementById('infoPlat').value = data.no_plat;
        Notif.peringatan('Plat ini belum punya tiket aktif. Daftarkan dulu di tab Security.');
        window.dispatchEvent(new CustomEvent('platLookup', { detail: data }));
        return;
    }

    document.getElementById('infoPlat').value = data.no_plat;

    if (data.status === 'ADA_TIKET') {
        document.getElementById('infoNoTiket').value = data.no_tiket || '';
        document.getElementById('infoNoDO').value = data.no_do || '';
        document.getElementById('infoSupplier').value = data.supplier || '';
        statusValidasi = 'done';
    } else {
        document.getElementById('infoNoTiket').value = data.no_tiket_reserved || '';
        document.getElementById('infoNoDO').value = '';
        document.getElementById('infoSupplier').value = '';
        statusValidasi = 'draft';
    }
    document.getElementById('infoSupir').value = data.driver
        ? formatNamaPersonel(data.driver.kode_personel, data.driver.id_driver, data.driver.nama) : '';
    // Plat blacklist ditandai merah; detail & banner ditampilkan di Form (security.js)
    document.getElementById('infoPlat').classList.toggle('border-red-500', !!data.kendaraan_blacklist);
    tampilkanFotoDriver(data.driver ? data.driver.foto_path : null);
    perbaruiTombolValidasi();

    window.dispatchEvent(new CustomEvent('platLookup', { detail: data }));
}

function kosongkanInfoBar() {
    ['infoNoTiket', 'infoNoDO', 'infoSupplier', 'infoSupir'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('infoPlat').classList.remove('border-red-500');
    tampilkanFotoDriver(null);
    statusValidasi = 'none';
    perbaruiTombolValidasi();
}

function tampilkanFotoDriver(path) {
    const box = document.getElementById('infoFotoBox');
    box.innerHTML = path
        ? `<img src="${escapeHtml(urlBerkas(path))}" class="w-full h-full object-cover" alt="">`
        : ICON_USER;
}

// ===== 3 JALUR MENUJU CREATE FORM =====
// Jalur 1: tombol Validasi di bawah foto
async function klikValidasi() {
    const plat = document.getElementById('infoPlat').value.trim();
    if (!plat) {
        Notif.peringatan('Ketik nomor plat dulu');
        document.getElementById('infoPlat').focus();
        return;
    }
    if (!document.getElementById('infoNoTiket').value) await lookupPlat(plat);
    setSidebarView('form');
}

// Jalur 2: tombol Aksi di tabel List Ticket Aktif
async function bukaFormDariTabel(noPlat) {
    await lookupPlat(noPlat);
    setSidebarView('form');
}
// Jalur 3: menu "Form" di sidebar (langsung setSidebarView('form'))