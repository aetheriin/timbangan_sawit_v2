// ===== ADMIN > LEVEL & HAK AKSES =====
// Pilih departemen -> jabatan (tabel level) -> centang halaman yang boleh dibuka (Lihat) dan aksinya.
let daftarLevel = [];
let daftarDept = [];
let deptDipilih = null;          // id_department, atau 'admin' untuk jabatan admin
let levelDipilih = null;

document.addEventListener('DOMContentLoaded', muatSemua);

async function muatSemua() {
    const [level, org] = await Promise.all([ambilJson('/api/admin/level'), ambilJson('/api/admin/organisasi')]);
    if (level.error || org.error) {
        document.getElementById('tabelLevel').innerHTML = `<p class="p-4 text-sm text-red-600">${escapeHtml(level.error || org.error)}</p>`;
        return;
    }
    daftarLevel = level;
    daftarDept = org.department.filter(d => d.is_active || level.some(lv => lv.id_department === d.id_department));
    if (deptDipilih === null) {
        const lv = daftarLevel.find(x => !x.is_admin);
        deptDipilih = lv ? lv.id_department : (daftarDept[0] || {}).id_department;
    }
    tampilDepartemen();
    tampilLevel();
}

const levelDiDept = id => daftarLevel.filter(lv => (id === 'admin' ? lv.is_admin : !lv.is_admin && lv.id_department === id));

function tampilDepartemen() {
    const item = (id, nama, jumlah) => `
        <button type="button" class="w-full flex items-center justify-between gap-2 px-4 py-2.5 text-left text-sm
            ${id === deptDipilih ? 'bg-slate-900 text-white' : 'hover:bg-slate-50 text-slate-700'}" data-on-click="pilihDepartemen" data-arg="${id}">
            <span class="truncate">${escapeHtml(nama)}</span>
            <span class="text-[11px] ${id === deptDipilih ? 'text-slate-300' : 'text-slate-400'}">${jumlah} jabatan</span>
        </button>`;
    document.getElementById('daftarDepartemen').innerHTML =
        daftarDept.map(d => item(d.id_department, d.nama, levelDiDept(d.id_department).length)).join('') +
        item('admin', 'Admin sistem', levelDiDept('admin').length);
}

function pilihDepartemen(id) {
    deptDipilih = id === 'admin' ? 'admin' : Number(id);
    tampilDepartemen();
    tampilLevel();
}

function tampilLevel() {
    const daftar = levelDiDept(deptDipilih);
    document.getElementById('tabelLevel').innerHTML = daftar.map(lv => `
        <div class="px-4 py-3 cursor-pointer ${lv.id_level === levelDipilih ? 'bg-blue-50 ring-1 ring-inset ring-blue-200' : 'hover:bg-slate-50'}${lv.is_active ? '' : ' opacity-60'}"
            data-on-click="pilihLevel" data-arg="${lv.id_level}">
            <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                    <p class="font-semibold text-slate-900 text-sm">${escapeHtml(lv.nama)}</p>
                    <p class="text-[11px] text-slate-500 mt-0.5">Halaman awal: ${escapeHtml(labelHalamanAwal(lv.halaman_awal))}</p>
                </div>
                <span class="text-[11px] text-slate-500 whitespace-nowrap">${Number(lv.jumlah_user)} pengguna</span>
            </div>
            <div class="flex items-center justify-between gap-2 mt-2">
                ${badgeAktif(lv.is_active)}
                <span class="space-x-3" data-henti-klik>
                    <button type="button" class="link-aksi text-blue-600" data-on-click="bukaLevel" data-arg="${lv.id_level}">Ubah</button>
                    ${lv.is_admin ? '' : `<button type="button" class="link-aksi ${lv.is_active ? 'text-red-600' : 'text-emerald-600'}"
                        data-on-click="ubahAktifLevel" data-arg="${lv.id_level}">${lv.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>`}
                </span>
            </div>
        </div>`).join('') || `<p class="p-4 text-sm text-slate-400">Belum ada jabatan di departemen ini</p>`;
}

async function pilihLevel(id) {
    levelDipilih = id;
    tampilLevel();
    const data = await ambilJson(`/api/admin/level/${id}/akses`);
    const tbody = document.getElementById('tabelAkses');
    if (data.error) { tbody.innerHTML = barisKosong(5, data.error); return; }
    const admin = !!data.level.is_admin;
    document.getElementById('judulMatriks').textContent = `· ${data.level.nama}`;
    document.getElementById('infoAdmin').classList.toggle('hidden', !admin);
    document.getElementById('btnSimpanAkses').disabled = admin;
    let induk = null;
    tbody.innerHTML = data.menu.map(m => {
        const judul = m.induk && m.induk !== induk
            ? `<tr class="bg-slate-50"><td colspan="5" class="table-cell text-xs font-semibold text-slate-500 uppercase">${escapeHtml(m.induk)}</td></tr>` : '';
        induk = m.induk;
        const kotak = (aksi, ada) => ada
            ? `<td class="table-cell text-center"><input type="checkbox" name="${m.id_menu}_${aksi}" value="1" data-menu="${m.id_menu}"
                data-aksi="${aksi}" data-nama="${escapeHtml(m.nama)}" class="w-4 h-4"${m[aksi] ? ' checked' : ''}${admin ? ' disabled' : ''}></td>`
            : '<td class="table-cell text-center text-slate-300">–</td>';
        return `${judul}<tr class="hover:bg-slate-50"><td class="table-cell">${escapeHtml(m.nama.split(' › ').pop())}</td>
                ${kotak('lihat', true)}${kotak('tambah', m.aksi.includes('tambah'))}${kotak('ubah', m.aksi.includes('ubah'))}${kotak('hapus', m.aksi.includes('hapus'))}</tr>`;
    }).join('');
    ringkasAkses();
}

// Aksi apa pun berarti halaman itu bisa dibuka; Lihat dilepas -> aksinya ikut dilepas
document.getElementById('tabelAkses').addEventListener('change', e => {
    const c = e.target;
    if (!c.dataset.menu) return;
    const baris = document.querySelectorAll(`#tabelAkses input[data-menu="${c.dataset.menu}"]`);
    if (c.dataset.aksi === 'lihat' && !c.checked) baris.forEach(x => { x.checked = false; });
    if (c.dataset.aksi !== 'lihat' && c.checked) baris.forEach(x => { if (x.dataset.aksi === 'lihat') x.checked = true; });
    ringkasAkses();
});

function ringkasAkses() {
    const label = { tambah: 'tambah', ubah: 'ubah', hapus: 'hapus' };
    const chip = [...document.querySelectorAll('#tabelAkses input[data-aksi="lihat"]:checked')].map(c => {
        const aksi = [...document.querySelectorAll(`#tabelAkses input[data-menu="${c.dataset.menu}"]:checked`)]
            .map(x => label[x.dataset.aksi]).filter(Boolean);
        return `<span class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-slate-700">${escapeHtml(c.dataset.nama)}${aksi.length ? ` <span class="text-slate-400 ml-1">· ${aksi.join(', ')}</span>` : ''}</span>`;
    });
    document.getElementById('ringkasAkses').innerHTML = chip.join('') || 'Belum ada halaman yang dicentang';
}

document.getElementById('formAkses').addEventListener('submit', e => {
    e.preventDefault();
    if (levelDipilih) kirimFormAdmin(e.target, `/api/admin/level/${levelDipilih}/akses`, { setelahnya: muatSemua });
});

function bukaLevel(id) {
    const form = document.getElementById('formLevel');
    const lv = daftarLevel.find(x => x.id_level === id);
    form.reset();
    pastikanPilihanAwal(lv ? lv.halaman_awal : '');
    const dept = lv ? lv.id_department : (deptDipilih === 'admin' ? '' : deptDipilih);
    isiForm(form, lv ? { id_level: lv.id_level, kode: lv.kode, nama: lv.nama, halaman_awal: lv.halaman_awal,
                         keterangan: lv.keterangan || '', id_department: dept || '' }
                     : { id_level: '', halaman_awal: '/weighbridge?view=list', id_department: dept || '' });
    form.elements.kode.readOnly = !!lv;
    form.elements.kode.required = !lv;
    form.elements.kode.classList.toggle('bg-slate-50', !!lv);
    document.getElementById('judulModalLevel').textContent = lv ? `Ubah Jabatan ${lv.nama}` : 'Tambah Jabatan';
    openModal('modalLevel');
    (lv ? form.elements.nama : form.elements.kode).focus();
}

document.getElementById('formLevel').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/level/simpan', { modal: 'modalLevel', setelahnya: muatSemua });
});

function ubahAktifLevel(id) {
    const lv = daftarLevel.find(x => x.id_level === id);
    konfirmasiAktif({
        url: `/api/admin/level/${id}/aktif`, aktif: !lv.is_active, nama: `Jabatan ${lv.nama}`, jenis: 'jabatan',
        pesanNonaktif: 'Pengguna dengan jabatan ini tidak bisa login dan sesinya langsung berakhir.', setelahnya: muatSemua,
    });
}

// Halaman awal: tampilkan nama menu, bukan alamat. Nilai lama yang diketik manual tetap muncul sebagai pilihan.
function labelHalamanAwal(url) {
    const opsi = Array.from(document.getElementById('levelAwal')?.options || []).find(o => o.value === url);
    return opsi ? opsi.text : url;
}

function pastikanPilihanAwal(url) {
    const sel = document.getElementById('levelAwal');
    if (url && !Array.from(sel.options).some(o => o.value === url)) sel.add(new Option(`${url} (lama)`, url));
}
