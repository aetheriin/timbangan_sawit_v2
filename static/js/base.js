let statusValidasi = 'none'; // none | draft | done
const TAB_VALID = ['security', 'timbangan', 'sortasi', 'lab'];
const ICON_USER = '<i class="fa-solid fa-user text-slate-300 text-3xl"></i>';

function getTabAktif() {
    return document.querySelector('.tab-btn-active').dataset.tab;
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('sidebar-collapsed');
}

// Sidebar "Form" / "Update Truk" dari tab manapun selalu membawa ke tab Security
function setSidebarView(view) {
    if (view !== 'list' && getTabAktif() !== 'security') {
        switchTab('security', false);
    }
    document.querySelectorAll('.sidebar-link').forEach(el => el.classList.remove('sidebar-link-active'));
    document.querySelector(`.sidebar-link[data-view="${view}"]`).classList.add('sidebar-link-active');
    document.querySelectorAll(`[data-tab-content="${getTabAktif()}"] [data-view-panel]`).forEach(el => {
        el.classList.toggle('hidden', el.dataset.viewPanel !== view);
    });
}

function switchTab(tabName, resetView = true) {
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('tab-btn-active'));
    document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add('tab-btn-active');
    document.querySelectorAll('[data-tab-content]').forEach(el => {
        el.classList.toggle('hidden', el.dataset.tabContent !== tabName);
    });
    perbaruiTombolValidasi();

    const url = new URL(window.location);
    url.searchParams.set('tab', tabName);
    window.history.replaceState({}, '', url);

    if (resetView) setSidebarView('list');
}

// Semua role bebas pindah tab; role hanya menentukan tab pertama saat login (?tab=...)
document.addEventListener('DOMContentLoaded', () => {
    const tab = new URLSearchParams(window.location.search).get('tab');
    switchTab(TAB_VALID.includes(tab) ? tab : 'security');
});

function toggleSection(id) {
    document.getElementById(`body-${id}`).classList.toggle('section-body-hidden');
    document.getElementById(`chevron-${id}`).classList.toggle('section-chevron-collapsed');
}

// Tombol Validasi: hanya di tab Security, hilang setelah tervalidasi
function perbaruiTombolValidasi() {
    const btn = document.getElementById('btnValidasi');
    if (!btn) return;
    btn.classList.toggle('hidden', !(getTabAktif() === 'security' && statusValidasi !== 'done'));
}

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

async function lookupPlat(noPlatRaw) {
    const noPlat = (noPlatRaw || '').trim().toUpperCase();
    if (!noPlat) return;

    const formData = new FormData();
    formData.append('no_plat', noPlat);

    let data;
    try {
        const res = await fetch('/api/plat/lookup', { method: 'POST', body: formData });
        data = await res.json();
    } catch (err) {
        alert('Gagal menghubungi server');
        return;
    }
    if (data.error) { alert(data.error); return; }

    data.no_plat = data.no_plat || noPlat;   // server mengembalikan format baku, mis. 'BM 1455 JJ'
    terapkanHasilLookup(data);
}

function terapkanHasilLookup(data) {
    const tab = getTabAktif();

    // Tiket hanya boleh dibuat di Security
    if (data.status === 'DRAFT' && tab !== 'security') {
        kosongkanInfoBar();
        document.getElementById('infoPlat').value = data.no_plat;
        alert('Plat ini belum punya tiket aktif. Daftarkan dulu di tab Security.');
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
    document.getElementById('infoSupir').value = data.driver ? data.driver.nama : '';
    tampilkanFotoDriver(data.driver ? data.driver.foto_path : null);
    perbaruiTombolValidasi();

    window.dispatchEvent(new CustomEvent('platLookup', { detail: data }));
}

function kosongkanInfoBar() {
    ['infoNoTiket', 'infoNoDO', 'infoSupplier', 'infoSupir'].forEach(id => document.getElementById(id).value = '');
    tampilkanFotoDriver(null);
    statusValidasi = 'none';
    perbaruiTombolValidasi();
}

function tampilkanFotoDriver(path) {
    const box = document.getElementById('infoFotoBox');
    box.innerHTML = path
        ? `<img src="/static/${path}" class="w-full h-full object-cover">`
        : ICON_USER;
}

// ===== 3 JALUR MENUJU CREATE FORM =====
// Jalur 1: tombol Validasi di bawah foto
async function klikValidasi() {
    const plat = document.getElementById('infoPlat').value.trim();
    if (!plat) {
        alert('Ketik nomor plat dulu');
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