// ===== SIDEBAR TOGGLE (show/hide) =====
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('sidebar-collapsed');
}

// ===== SIDEBAR: LIST vs FORM VIEW (per tab aktif) =====
function setSidebarView(view) {
    document.querySelectorAll('.sidebar-link').forEach(el => el.classList.remove('sidebar-link-active'));
    document.querySelector(`.sidebar-link[data-view="${view}"]`).classList.add('sidebar-link-active');

    const tabAktif = document.querySelector('.tab-btn-active').dataset.tab;
    document.querySelectorAll(`[data-tab-content="${tabAktif}"] [data-view-panel]`).forEach(el => {
        el.classList.toggle('hidden', el.dataset.viewPanel !== view);
    });
}

// ===== TAB SWITCH (Security/Timbangan/Sortasi/Lab) =====
function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('tab-btn-active'));
    document.querySelector(`.tab-btn[data-tab="${tabName}"]`).classList.add('tab-btn-active');

    document.querySelectorAll('[data-tab-content]').forEach(el => {
        el.classList.toggle('hidden', el.dataset.tabContent !== tabName);
    });

    // Validasi button cuma tampil di tab Security
    const btnValidasi = document.getElementById('btnValidasi');
    if (btnValidasi) btnValidasi.classList.toggle('hidden', tabName !== 'security');

    // sinkronkan URL supaya bisa reload di tab yang sama
    const url = new URL(window.location);
    url.searchParams.set('tab', tabName);
    window.history.replaceState({}, '', url);

    setSidebarView('list'); // default balik ke List tiap ganti tab
}

// ===== COLLAPSIBLE SECTION (chevron) =====
function toggleSection(id) {
    const body = document.getElementById(`body-${id}`);
    const chevron = document.getElementById(`chevron-${id}`);
    body.classList.toggle('section-body-hidden');
    chevron.classList.toggle('section-chevron-collapsed');
}

// ===== INFO BAR: LOOKUP PLAT (tekan Tab) =====
async function lookupPlat(inputEl) {
    const noPlat = inputEl.value.trim().toUpperCase();
    if (!noPlat) return;

    const formData = new FormData();
    formData.append('no_plat', noPlat);

    const res = await fetch('/api/plat/lookup', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.status === 'ADA_TIKET') {
        isiInfoBar(data);
    } else if (data.status === 'DRAFT') {
        isiInfoBarDraft(data, noPlat);
    }

    window.dispatchEvent(new CustomEvent('platLookup', { detail: data }));
}

function isiInfoBar(data) {
    document.getElementById('infoNoTiket').value = data.no_tiket || '';
    document.getElementById('infoNoDO').value = data.no_do || '';
    document.getElementById('infoSupplier').value = data.supplier || '';
    document.getElementById('infoSupir').value = data.driver ? data.driver.nama : '';
    document.getElementById('btnValidasi').classList.add('hidden'); // sudah ada tiket, tidak perlu validasi lagi
}

function isiInfoBarDraft(data, noPlat) {
    document.getElementById('infoNoTiket').value = data.no_tiket_reserved || '';
    document.getElementById('infoNoDO').value = '';
    document.getElementById('infoSupplier').value = '';
    document.getElementById('infoSupir').value = data.driver ? data.driver.nama : '';

    const tabAktif = document.querySelector('.tab-btn-active').dataset.tab;
    if (tabAktif === 'security') {
        document.getElementById('btnValidasi').classList.remove('hidden');
    }
}

function kosongkanInfoBar(noPlat) {
    document.getElementById('infoNoTiket').value = '';
    document.getElementById('infoNoDO').value = '';
    document.getElementById('infoSupplier').value = '';
    document.getElementById('infoSupir').value = '';
}

// ===== TOMBOL VALIDASI DI INFO BAR =====
function klikValidasi() {
    const noTiket = document.getElementById('infoNoTiket').value;
    if (!noTiket) {
        // Belum ada tiket untuk plat ini -> arahkan ke Create Ticket (jalur 1)
        setSidebarView('form');
        return;
    }
    // Sudah ada tiket -> trigger scan wajah (dipakai lagi di fase berikutnya)
    alert('Memulai verifikasi wajah untuk tiket: ' + noTiket);
}

// ===== JALUR 2: TOMBOL AKSI DI TABEL LIST TIKET AKTIF =====
function bukaFormDariTabel(noPlat) {
    document.getElementById('infoPlat').value = noPlat;
    lookupPlat(document.getElementById('infoPlat'));
    setSidebarView('form');
}