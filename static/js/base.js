// ===== LAYOUT BASE: sidebar, tab, section =====
// Dipakai semua halaman yang extends base.html. Logika info bar ada di info_bar.js.

function getTabAktif() {
    const btn = document.querySelector('.tab-btn-active');
    return btn ? btn.dataset.tab : null;
}

function daftarTab() {
    return [...document.querySelectorAll('.tab-btn')].map(btn => btn.dataset.tab);
}

// Halaman site punya panel List / Form (data-view-panel); halaman lain tidak
function adaPanelView() {
    return !!document.querySelector('[data-view-panel]');
}

function setUrlParam(key, value) {
    const url = new URL(window.location);
    url.searchParams.set(key, value);
    window.history.replaceState({}, '', url);
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('sidebar-collapsed');
}

// List / Form di halaman site. Form = Create Ticket (tab Security) dan tampil tanpa header tab.
function setSidebarView(view) {
    if (!adaPanelView()) {                       // dipanggil dari halaman lain -> buka halaman site
        window.location.href = `/weighbridge?view=${view}`;
        return;
    }
    if (view === 'form' && getTabAktif() !== 'security') switchTab('security', false);

    document.querySelectorAll('.sidebar-link[data-view]').forEach(el => {
        el.classList.toggle('sidebar-link-active', el.dataset.view === view);
    });
    document.getElementById('tabHeader').classList.toggle('hidden', view === 'form');
    document.querySelectorAll(`[data-tab-content="${getTabAktif()}"] [data-view-panel]`).forEach(el => {
        el.classList.toggle('hidden', el.dataset.viewPanel !== view);
    });
    setUrlParam('view', view);
}

function switchTab(tabName, resetView = true) {
    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.toggle('tab-btn-active', el.dataset.tab === tabName);
    });
    document.querySelectorAll('[data-tab-content]').forEach(el => {
        el.classList.toggle('hidden', el.dataset.tabContent !== tabName);
    });
    setUrlParam('tab', tabName);
    window.dispatchEvent(new CustomEvent('tabChange', { detail: tabName }));

    if (resetView && adaPanelView()) setSidebarView('list');
}

function toggleSection(id) {
    document.getElementById(`body-${id}`).classList.toggle('section-body-hidden');
    document.getElementById(`chevron-${id}`).classList.toggle('section-chevron-collapsed');
}

// Semua role bebas pindah tab; role hanya menentukan tab pertama saat login (?tab=...)
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.sidebar-link[data-view]').forEach(link => {
        link.addEventListener('click', e => {
            if (!adaPanelView()) return;          // halaman lain: ikuti href
            e.preventDefault();
            setSidebarView(link.dataset.view);
        });
    });

    const tabs = daftarTab();
    if (!tabs.length) return;
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    switchTab(tabs.includes(tab) ? tab : tabs[0]);
    if (params.get('view') === 'form') setSidebarView('form');
});
