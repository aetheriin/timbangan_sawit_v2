// ===== ADMIN > KELOLA USER =====
let daftarUser = [];
let filterRole = '';
let idUserReset = null;
let idUserAkses = null;

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
    const baris = daftarUser.filter(u => !filterRole || String(u.id_jabatan) === filterRole);
    tbody.innerHTML = baris.map(u => `
        <tr class="hover:bg-slate-50${u.is_active ? '' : ' text-slate-400'}" data-cari="${escapeHtml(`${u.username} ${u.nama} ${u.nik || ''} ${u.email || ''}`.toLowerCase())}">
            <td class="table-cell font-mono">${escapeHtml(u.username)}${u.is_saya ? ' <span class="text-xs text-blue-600">(Anda)</span>' : ''}</td>
            <td class="table-cell">${escapeHtml(u.nama)}<span class="block text-[11px] text-slate-500">${u.nik ? `NIK ${escapeHtml(u.nik)}` : '<span class="text-amber-700">NIK belum diisi</span>'}${u.email ? ` · ${escapeHtml(u.email)}` : ''}</span></td>
            <td class="table-cell">${badgeRole(u.role, u.nama_level)}${u.jumlah_akses_khusus ? ` <span class="badge-status bg-violet-100 text-violet-800" title="${u.jumlah_akses_khusus} menu berbeda dari jabatan">Hak khusus</span>` : ''}</td>
            <td class="table-cell">${escapeHtml(u.department)}</td>
            <td class="table-cell">${escapeHtml(u.area)}${u.di_pusat ? `<span class="block text-[11px] text-slate-500">${u.pt_kelola.length ? `Mengelola ${u.pt_kelola.length} PT` : 'Mengelola semua PT'}</span>` : ''}</td>
            <td class="table-cell">${badgeAktif(u.is_active)}</td>
            <td class="table-cell">${escapeHtml(u.last_login || 'Belum pernah')}</td>
            <td class="table-cell">${escapeHtml(u.created_at || '-')}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaUbahUser" data-arg="${u.id_user}">Ubah</button>
                ${u.is_admin ? '' : `<button type="button" class="link-aksi text-violet-700" data-on-click="bukaAksesUser" data-arg="${u.id_user}">Hak Akses</button>`}
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
    const info = document.getElementById('infoNikUser');
    info.classList.add('hidden');
    info.textContent = '';
    form.reset();
    document.getElementById('judulModalUser').textContent = ubah ? 'Ubah Pengguna' : 'Tambah Pengguna';
    document.getElementById('blokPasswordUser').classList.toggle('hidden', ubah);
    document.getElementById('noteRoleUser').classList.toggle('hidden', !ubah);
    form.elements.username.readOnly = ubah;
    form.elements.username.classList.toggle('bg-slate-50', ubah);
    form.elements.password.required = form.elements.password_ulang.required = !ubah;
    return form;
}

// Area mengikuti perusahaan, departemen mengikuti area (DepartmentDetails). Jabatan admin sistem tanpa departemen.
// (sumber: <template> di users_modals.html)
function isiDariSumber(idSelect, idSumber, cocok, pilih) {
    const sel = document.getElementById(idSelect);
    [...sel.options].filter(o => o.value !== '').forEach(o => o.remove());
    [...document.getElementById(idSumber).content.querySelectorAll('option')].filter(cocok).forEach(o => sel.add(o.cloneNode(true)));
    sel.value = pilih != null && [...sel.options].some(o => o.value === String(pilih)) ? String(pilih) : '';
}

function aturAreaUser(pilih) {
    const company = document.getElementById('userCompany').value;
    isiDariSumber('userArea', 'sumberArea', o => o.dataset.company === company, pilih ?? null);
    aturDeptUser();
}

function aturDeptUser(pilih) {
    const area = document.getElementById('userArea').value;
    const dept = typeof pilih === 'string' ? pilih : document.getElementById('userDept').value || null;
    isiDariSumber('userDept', 'sumberDept', o => area && o.dataset.area.split(',').includes(area), dept);
    aturPtKelola();
}

function aturJabatanUser() {
    const sel = document.getElementById('userLevel');
    const admin = (sel.options[sel.selectedIndex] || {}).dataset?.admin === '1';
    document.getElementById('blokUserDept').classList.toggle('hidden', admin);
    document.getElementById('userDept').required = !admin;
}

// PT yang dikelola hanya untuk area kantor pusat
function aturPtKelola() {
    const sel = document.getElementById('userArea');
    const opsi = sel.options[sel.selectedIndex];
    document.getElementById('blokPtKelola').classList.toggle('hidden', !(opsi && opsi.dataset.pusat === '1'));
}

function bukaTambahUser() {
    const form = siapkanModalUser(false);
    form.elements.id_user.value = '';
    aturAreaUser();
    aturJabatanUser();
    openModal('modalUser');
    document.getElementById('userNik').focus();
}

function bukaUbahUser(id) {
    const u = cariDataUser(id);
    const form = siapkanModalUser(true);
    isiForm(form, { id_user: u.id_user, nama: u.nama, username: u.username, nik: u.nik || '' });
    const ar = document.querySelector('#sumberArea').content.querySelector(`option[value="${u.id_comp_area}"]`);
    document.getElementById('userCompany').value = ar ? ar.dataset.company : '';
    aturAreaUser(u.id_comp_area);
    aturDeptUser(u.id_department);
    document.getElementById('userLevel').value = u.id_jabatan ?? '';
    aturJabatanUser();
    form.querySelectorAll('[name=pt_kelola]').forEach(c => { c.checked = u.pt_kelola.includes(c.value); });
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

// NIK yang sudah terdaftar sebagai personel (mis. security yang sudah didaftarkan wajahnya) langsung dihubungkan
async function cekNikUser(nik) {
    const info = document.getElementById('infoNikUser');
    const form = document.getElementById('formUser');
    info.classList.add('hidden');
    if (form.elements.id_user.value || nik.length !== 16) return;
    const p = await ambilJson(`/api/admin/users/nik/${nik}`);
    if (!p || !p.id_personel) return;
    info.classList.remove('hidden');
    info.classList.toggle('text-red-600', !!p.akun || !p.boleh_akun);
    if (p.akun) { info.textContent = `NIK ini sudah dipakai akun ${p.akun}.`; return; }
    if (!p.boleh_akun) { info.textContent = `NIK ini terdaftar sebagai ${p.nama_kategori || p.kategori} dan tidak bisa dibuatkan akun.`; return; }
    info.textContent = `Terdaftar sebagai personel ${p.nama_personel}. Akun ini akan dihubungkan ke personel tersebut.`;
    form.elements.nama.value = p.nama_personel;
}

// ===== HAK AKSES KHUSUS =====
const AKSI_USER = ['lihat', 'tambah', 'ubah', 'hapus', 'setujui', 'tolak', 'selesai'];

async function bukaAksesUser(id) {
    idUserAkses = id;
    const data = await ambilJson(`/api/admin/users/${id}/akses`);
    if (data.error) { Notif.error(data.error); return; }
    document.getElementById('judulAksesUser').textContent = `· ${data.user.username}`;
    document.getElementById('jabatanAksesUser').textContent = data.user.nama_level;
    let induk = null;
    document.getElementById('tabelAksesUser').innerHTML = data.menu.map(m => {
        const judul = m.induk && m.induk !== induk
            ? `<tr class="bg-slate-50"><td colspan="8" class="table-cell text-xs font-semibold text-slate-500 uppercase">${escapeHtml(m.induk)}</td></tr>` : '';
        induk = m.induk;
        const kotak = a => (a === 'lihat' || m.aksi.includes(a))
            ? `<td class="table-cell text-center"><input type="checkbox" class="w-4 h-4" name="${m.id_menu}_${a}" data-menu="${m.id_menu}" data-aksi="${a}"
                data-jabatan="${m.jabatan[a] ? 1 : 0}"${m[a] ? ' checked' : ''}></td>`
            : '<td class="table-cell text-center text-slate-300">–</td>';
        return `${judul}<tr data-baris="${m.id_menu}"><td class="table-cell">${escapeHtml(m.nama.split(' › ').pop())}
                <span class="badge-status bg-violet-100 text-violet-800 ml-1${m.khusus ? '' : ' hidden'}" data-khusus>Khusus</span></td>
                ${AKSI_USER.map(kotak).join('')}</tr>`;
    }).join('');
    openModal('modalAksesUser');
}

// Lihat dilepas -> aksinya ikut dilepas; aksi dicentang -> Lihat ikut; tanda Khusus bila berbeda dari jabatan
document.getElementById('tabelAksesUser').addEventListener('change', e => {
    const c = e.target;
    if (!c.dataset.menu) return;
    const baris = [...document.querySelectorAll(`#tabelAksesUser input[data-menu="${c.dataset.menu}"]`)];
    if (c.dataset.aksi === 'lihat' && !c.checked) baris.forEach(x => { x.checked = false; });
    if (c.dataset.aksi !== 'lihat' && c.checked) baris.forEach(x => { if (x.dataset.aksi === 'lihat') x.checked = true; });
    const beda = baris.some(x => x.checked !== (x.dataset.jabatan === '1'));
    document.querySelector(`#tabelAksesUser tr[data-baris="${c.dataset.menu}"] [data-khusus]`).classList.toggle('hidden', !beda);
});

document.getElementById('formAksesUser').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, `/api/admin/users/${idUserAkses}/akses`, { modal: 'modalAksesUser', setelahnya: muatUser });
});

async function resetAksesUser() {
    const fd = new FormData();
    fd.append('reset', '1');
    const data = await kirimForm(`/api/admin/users/${idUserAkses}/akses`, fd);
    if (!tampilkanHasil(data)) return;
    closeModal('modalAksesUser');
    muatUser();
}
