// ===== ADMIN > DASHBOARD PERAN =====
// Tiap dashboard = menu Lv2 /dashboard/<nama> berisi daftar widget (Menu.Widgets). Widget sendiri dibuat di kode
// (katalog utils/db_dashboard.py WIDGET); di sini admin hanya memilih widget & urutannya.
const KATALOG_WIDGET = JSON.parse(document.getElementById('katalogWidget').dataset.katalog || '{}');
let daftarDashboard = [];

document.addEventListener('DOMContentLoaded', muatDashboardAdmin);

async function muatDashboardAdmin() {
    const data = await ambilJson('/api/admin/dashboard');
    const tbody = document.getElementById('tabelDashboardAdmin');
    if (data.error) { tbody.innerHTML = barisKosong(7, data.error); return false; }
    daftarDashboard = data;
    tbody.innerHTML = data.map(d => `
        <tr class="hover:bg-slate-50${d.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-semibold">${escapeHtml(d.nama)}<span class="block text-[11px] font-mono font-normal text-slate-400">${escapeHtml(d.kode)}</span></td>
            <td class="table-cell font-mono text-xs"><a href="${escapeHtml(d.url)}" class="text-blue-600 hover:underline">${escapeHtml(d.url)}</a></td>
            <td class="table-cell">${d.widget.map((w, i) => `<span class="badge-status bg-slate-100 text-slate-700 mr-1 mb-1">${i + 1}. ${escapeHtml(w)}</span>`).join('')
                || '<span class="text-slate-400">-</span>'}</td>
            <td class="table-cell">${d.isi_harga ? '<i class="fa-solid fa-check text-emerald-600"></i>' : '<span class="text-slate-400">-</span>'}</td>
            <td class="table-cell text-right font-mono">${d.jumlah_peran}</td>
            <td class="table-cell">${badgeAktif(d.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaDashboardAdmin" data-arg="${d.id_menu}">Ubah</button>
                <button type="button" class="link-aksi ${d.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifDashboard"
                    data-arg="${d.id_menu}">${d.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td>
        </tr>`).join('') || barisKosong(7, 'Belum ada dashboard');
}

// Daftar widget di modal: yang dipilih di atas (sesuai urutan), sisanya di bawah tidak dicentang
function isiDaftarWidget(dipilih) {
    const urut = [...dipilih.filter(w => w in KATALOG_WIDGET), ...Object.keys(KATALOG_WIDGET).filter(w => !dipilih.includes(w))];
    document.getElementById('daftarWidget').innerHTML = urut.map(w => `
        <div class="flex items-center gap-3 px-3 py-2" data-widget-baris>
            <input type="checkbox" name="widget" value="${escapeHtml(w)}" id="wg_${escapeHtml(w)}"${dipilih.includes(w) ? ' checked' : ''}>
            <label for="wg_${escapeHtml(w)}" class="flex-1 min-w-0">
                <span class="text-sm font-semibold text-slate-800 font-mono">${escapeHtml(w)}</span>
                <span class="block text-xs text-slate-500">${escapeHtml(KATALOG_WIDGET[w])}</span>
            </label>
            <button type="button" class="btn-secondary px-2 py-1" title="Naik" data-on-click="geserWidget" data-arg="$el|-1"><i class="fa-solid fa-arrow-up"></i></button>
            <button type="button" class="btn-secondary px-2 py-1" title="Turun" data-on-click="geserWidget" data-arg="$el|1"><i class="fa-solid fa-arrow-down"></i></button>
        </div>`).join('');
}

function geserWidget(el, arah) {
    const baris = el.closest('[data-widget-baris]');
    const tujuan = Number(arah) < 0 ? baris.previousElementSibling : baris.nextElementSibling;
    if (!tujuan) return;
    if (Number(arah) < 0) tujuan.before(baris); else tujuan.after(baris);
}

function bukaDashboardAdmin(id) {
    const form = document.getElementById('formDashboardAdmin');
    const d = daftarDashboard.find(x => x.id_menu === Number(id));
    form.reset();
    form.elements.id_menu.value = d ? d.id_menu : '';
    form.elements.nama.value = d ? d.nama : '';
    form.elements.slug.value = d ? d.url.replace(/^\/dashboard\/?/, '') : '';
    form.elements.slug.readOnly = !!d;
    form.elements.slug.required = !d;
    form.elements.slug.classList.toggle('bg-slate-50', !!d);
    form.elements.isi_harga.checked = !!(d && d.isi_harga);
    isiDaftarWidget(d ? d.widget : []);
    document.getElementById('judulModalDashboard').textContent = d ? `Ubah ${d.nama}` : 'Tambah Dashboard';
    openModal('modalDashboardAdmin');
    form.elements.nama.focus();
}

document.getElementById('formDashboardAdmin').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/dashboard/simpan', { modal: 'modalDashboardAdmin', setelahnya: muatDashboardAdmin });
});

function ubahAktifDashboard(id) {
    const d = daftarDashboard.find(x => x.id_menu === Number(id));
    konfirmasiAktif({ url: `/api/admin/dashboard/${d.id_menu}/aktif`, aktif: !d.is_active, nama: d.nama, jenis: 'dashboard',
                      pesanNonaktif: 'Menu ini hilang dari sidebar semua peran.', setelahnya: muatDashboardAdmin });
}
