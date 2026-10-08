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
            <td class="table-cell">${escapeHtml(u.area)}</td>
            <td class="table-cell">${badgeAktif(u.is_active)}</td>
            <td class="table-cell">${escapeHtml(u.last_login || 'Belum pernah')}</td>
            <td class="table-cell">${escapeHtml(u.created_at || '-')}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaUbahUser" data-arg="${u.id_user}">Ubah</button>
                <button type="button" class="link-aksi text-amber-700" data-on-click="bukaResetPassword" data-arg="${u.id_user}">Reset Password</button>
                ${u.is_saya ? '' : `<button type="button" class="link-aksi ${u.is_active ? 'text-red-600' : 'text-emerald-600'}"
                    data-on-click="ubahAktifUser" data-arg="${u.id_user}">${u.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>`}
            </td>
        </tr>`).join('') || barisKosong(9, 'Belum ada user');
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
    document.getElementById('judulModalUser').textContent = ubah ? 'Ubah User' : 'Tambah User';
    document.getElementById('blokPasswordUser').classList.toggle('hidden', ubah);
    document.getElementById('noteRoleUser').classList.toggle('hidden', !ubah);
    form.elements.username.readOnly = ubah;
    form.elements.username.classList.toggle('bg-slate-50', ubah);
    form.elements.password.required = form.elements.password_ulang.required = !ubah;
    return form;
}

function bukaTambahUser() {
    siapkanModalUser(false).elements.id_user.value = '';
    openModal('modalUser');
    document.getElementById('userNama').focus();
}

function bukaUbahUser(id) {
    const u = cariDataUser(id);
    isiForm(siapkanModalUser(true), { id_user: u.id_user, nama: u.nama, username: u.username, id_level: u.id_level,
                                      id_department: u.id_department, id_comp_area: u.id_comp_area });
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
        pesanNonaktif: 'User tidak bisa login dan sesinya yang sedang aktif langsung berakhir.', setelahnya: muatUser,
    });
}
