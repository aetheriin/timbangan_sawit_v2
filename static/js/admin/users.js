// ===== ADMIN > KELOLA USER =====
let daftarUser = [];
let filterRole = '';
let idUserReset = null;

document.addEventListener('DOMContentLoaded', muatUser);

async function muatUser() {
    const data = await ambilJson('/api/admin/users');
    const tbody = document.getElementById('tabelUser');
    if (data.error) { tbody.innerHTML = barisKosong(9, data.error); return; }
    daftarUser = data;
    tampilkanUser();
}

function tampilkanUser() {
    const tbody = document.getElementById('tabelUser');
    const baris = daftarUser.filter(u => !filterRole || u.role === filterRole);
    tbody.innerHTML = baris.map(u => `
        <tr class="hover:bg-slate-50${u.is_active ? '' : ' text-slate-400'}" data-cari="${escapeHtml(`${u.username} ${u.nama}`.toLowerCase())}">
            <td class="table-cell font-mono">${escapeHtml(u.username)}${u.is_saya ? ' <span class="text-xs text-blue-600">(Anda)</span>' : ''}</td>
            <td class="table-cell">${escapeHtml(u.nama)}</td>
            <td class="table-cell">${badgeRole(u.role, u.nama_level)}</td>
            <td class="table-cell">${escapeHtml(u.department)}</td>
            <td class="table-cell">${escapeHtml(u.area)}${u.di_pusat ? `<span class="block text-[11px] text-slate-500">${u.pt_kelola.length ? `Mengelola ${u.pt_kelola.length} PT` : 'Mengelola semua PT'}</span>` : ''}</td>
            <td class="table-cell">${badgeAktif(u.is_active)}</td>
            <td class="table-cell">${escapeHtml(u.last_login || 'Belum pernah')}</td>
            <td class="table-cell">${escapeHtml(u.created_at || '-')}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaUbahUser" data-arg="${u.id_user}">Ubah</button>
                <button type="button" class="link-aksi text-amber-700" data-on-click="bukaResetPassword" data-arg="${u.id_user}">Atur Ulang Password</button>
                ${u.is_saya ? '' : `<button type="button" class="link-aksi ${u.is_active ? 'text-red-600' : 'text-emerald-600'}"
                    data-on-click="ubahAktifUser" data-arg="${u.id_user}">${u.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>`}
            </td>
        </tr>`).join('') || barisKosong(9, 'Belum ada pengguna', aksiKosong('bukaTambahUser', 'Tambah Pengguna'));
    saringBaris('tabelUser', document.getElementById('cariUser').value);
}

function filterRoleUser(el) {
    aktifkanChip(el);
    filterRole = el.dataset.filter;
    tampilkanUser();
}

function cariUser(teks) {
    saringBaris('tabelUser', teks);
}

function cariDataUser(id) {
    return daftarUser.find(u => u.id_user === id);
}

function siapkanModalUser(ubah) {
    const form = document.getElementById('formUser');
    form.reset();
    document.getElementById('judulModalUser').textContent = ubah ? 'Ubah Pengguna' : 'Tambah Pengguna';
    document.getElementById('blokPasswordUser').classList.toggle('hidden', ubah);
    document.getElementById('noteRoleUser').classList.toggle('hidden', !ubah);
    form.elements.username.readOnly = ubah;
    form.elements.username.classList.toggle('bg-slate-50', ubah);
    form.elements.password.required = form.elements.password_ulang.required = !ubah;
    return form;
}

// Area mengikuti perusahaan, departemen mengikuti area, jabatan mengikuti departemen
// (sumber: <template> di users_modals.html)
function isiDariSumber(idSelect, idSumber, cocok, pilih) {
    const sel = document.getElementById(idSelect);
    [...sel.options].filter(o => o.value !== '').forEach(o => o.remove());
    [...document.getElementById(idSumber).content.querySelectorAll('option')].filter(cocok).forEach(o => sel.add(o.cloneNode(true)));
    sel.value = pilih != null && [...sel.options].some(o => o.value === String(pilih)) ? String(pilih) : '';
}

function aturAreaUser(pilih) {
    const company = document.getElementById('userCompany').value;
    isiDariSumber('userArea', 'sumberArea', o => o.dataset.company === company, typeof pilih === 'number' ? pilih : null);
    aturDeptUser();
}

function aturDeptUser(pilih) {
    const area = document.getElementById('userArea').value;
    const dept = typeof pilih === 'number' ? pilih : Number(document.getElementById('userDept').value) || null;
    isiDariSumber('userDept', 'sumberDept', o => !o.dataset.area || (area && o.dataset.area.split(',').includes(area)), dept);
    aturJabatanUser();
    aturPtKelola();
}

function aturJabatanUser(pilih) {
    const dept = document.getElementById('userDept').value;
    const jabatan = typeof pilih === 'number' ? pilih : Number(document.getElementById('userLevel').value) || null;
    isiDariSumber('userLevel', 'sumberJabatan', o => o.dataset.dept === dept, jabatan);
}

// PT yang dikelola hanya untuk area kantor pusat
function aturPtKelola() {
    const sel = document.getElementById('userArea');
    const opsi = sel.options[sel.selectedIndex];
    document.getElementById('blokPtKelola').classList.toggle('hidden', !(opsi && opsi.dataset.pusat === '1'));
}

function bukaTambahUser() {
    siapkanModalUser(false).elements.id_user.value = '';
    aturAreaUser();
    openModal('modalUser');
    document.getElementById('userNama').focus();
}

function bukaUbahUser(id) {
    const u = cariDataUser(id);
    const form = siapkanModalUser(true);
    isiForm(form, { id_user: u.id_user, nama: u.nama, username: u.username });
    const lv = document.querySelector('#sumberJabatan').content.querySelector(`option[value="${u.id_level}"]`);
    const ar = document.querySelector('#sumberArea').content.querySelector(`option[value="${u.id_comp_area}"]`);
    document.getElementById('userCompany').value = ar ? ar.dataset.company : '';
    aturAreaUser(u.id_comp_area);
    aturDeptUser(lv ? Number(lv.dataset.dept) : null);
    aturJabatanUser(u.id_level);
    form.querySelectorAll('[name=pt_kelola]').forEach(c => { c.checked = u.pt_kelola.includes(Number(c.value)); });
    aturPtKelola();
    openModal('modalUser');
}

document.getElementById('formUser').addEventListener('submit', e => {
    e.preventDefault();
    const form = e.target;
    const id = form.elements.id_user.value;
    kirimFormAdmin(form, id ? `/api/admin/users/${id}/ubah` : '/api/admin/users/tambah',
                   { modal: 'modalUser', setelahnya: muatUser });
});

function bukaResetPassword(id) {
    idUserReset = id;
    document.getElementById('formResetPassword').reset();
    document.getElementById('resetUsername').textContent = cariDataUser(id).username;
    openModal('modalResetPassword');
    document.getElementById('resetPassword').focus();
}

document.getElementById('formResetPassword').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, `/api/admin/users/${idUserReset}/reset-password`, { modal: 'modalResetPassword' });
});

function ubahAktifUser(id) {
    const u = cariDataUser(id);
    konfirmasiAktif({
        url: `/api/admin/users/${id}/aktif`, aktif: !u.is_active, nama: u.username, jenis: 'user',
        pesanNonaktif: 'Pengguna tidak bisa login dan sesinya yang sedang aktif langsung berakhir.', setelahnya: muatUser,
    });
}
