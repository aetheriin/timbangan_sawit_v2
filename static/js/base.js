// ===== LAYOUT BASE: sidebar, tab, section =====
// Dipakai semua halaman yang extends base.html. Logika info bar ada di info_bar.js.

function getTabAktif() {
    const btn = document.querySelector('.tab-btn-active');
    return btn ? btn.dataset.tab : null;
}

function daftarTab() {
    return [...document.querySelectorAll('.tab-btn')].map(btn => btn.dataset.tab);
}


function setUrlParam(key, value) {
    const url = new URL(window.location);
    url.searchParams.set(key, value);
    window.history.replaceState({}, '', url);
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('sidebar-collapsed');
}

// List & Form adalah dua halaman terpisah (List tanpa info bar & tab, Form dengan info bar + tab)
function setSidebarView(view) {
    window.location.href = `/weighbridge?view=${view}`;
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.toggle('tab-btn-active', el.dataset.tab === tabName);
    });
    document.querySelectorAll('[data-tab-content]').forEach(el => {
        el.classList.toggle('hidden', el.dataset.tabContent !== tabName);
    });
    setUrlParam('tab', tabName);
    window.dispatchEvent(new CustomEvent('tabChange', { detail: tabName }));
}

function toggleSection(id) {
    document.getElementById(`body-${id}`).classList.toggle('section-body-hidden');
    document.getElementById(`chevron-${id}`).classList.toggle('section-chevron-collapsed');
}

// Tab awal: ?tab=... atau <meta name="tab-awal"> (sesuai role), selain itu tab pertama
document.addEventListener('DOMContentLoaded', () => {
    const tabs = daftarTab();
    if (!tabs.length) return;
    const minta = new URLSearchParams(window.location.search).get('tab')
        || document.querySelector('meta[name="tab-awal"]')?.content;
    switchTab(tabs.includes(minta) ? minta : tabs[0]);
});
