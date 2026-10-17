// ===== ADMIN > LEVEL & HAK AKSES =====
// Pilih departemen -> jabatan (umum: Manager, Staff, ...) -> halaman awal & centang halaman / aksi.
// Hak menempel di gabungan departemen + jabatan (peran); peran dibuat otomatis saat pertama disimpan.
let daftarLevel = [];          // peran yang sudah ada
let daftarJabatan = [];
let daftarDept = [];
let deptDipilih = null;        // id_department, atau 'admin' untuk jabatan admin sistem
let jabatanDipilih = null;

document.addEventListener('DOMContentLoaded', muatSemua);

async function muatSemua() {
    const [level, org] = await Promise.all([ambilJson('/api/admin/level'), ambilJson('/api/admin/organisasi')]);
    if (level.error || org.error) {
        document.getElementById('tabelLevel').innerHTML = `<p class="p-4 text-sm text-red-600">${escapeHtml(level.error || org.error)}</p>`;
        return;
    }
    daftarLevel = level;
    daftarJabatan = org.jabatan.filter(j => j.is_active);
    daftarDept = org.department.filter(d => d.is_active);
    if (deptDipilih === null) deptDipilih = (daftarDept[0] || {}).id_department ?? 'admin';
    tampilDepartemen();
    tampilLevel();
}

const peranDari = (dept, idJabatan) => daftarLevel.find(lv => lv.id_jabatan === idJabatan
    && (dept === 'admin' ? lv.is_admin : !lv.is_admin && lv.id_department === dept));
const jabatanDiDept = dept => daftarJabatan.filter(j => (dept === 'admin') === !!j.is_admin);

function tampilDepartemen() {
    const item = (id, nama) => {
        const diatur = jabatanDiDept(id).filter(j => peranDari(id, j.id_jabatan)).length;
        return `
        <button type="button" class="w-full flex items-center justify-between gap-2 px-4 py-2.5 text-left text-sm
            ${id === deptDipilih ? 'bg-slate-900 text-white' : 'hover:bg-slate-50 text-slate-700'}" data-on-click="pilihDepartemen" data-arg="${id}">
            <span class="truncate">${escapeHtml(nama)}</span>
            <span class="text-[11px] ${id === deptDipilih ? 'text-slate-300' : 'text-slate-400'}">${diatur} diatur</span>
        </button>`;
    };
    document.getElementById('daftarDepartemen').innerHTML =
        daftarDept.map(d => item(d.id_department, d.nama)).join('') + item('admin', 'Admin sistem');
}

function pilihDepartemen(id) {
    deptDipilih = id === 'admin' ? 'admin' : Number(id);
    jabatanDipilih = null;
    tampilDepartemen();
    tampilLevel();
    kosongkanMatriks();
}

function tampilLevel() {
    document.getElementById('tabelLevel').innerHTML = jabatanDiDept(deptDipilih).map(j => {
        const lv = peranDari(deptDipilih, j.id_jabatan);
        return `
        <div class="px-4 py-3 cursor-pointer ${j.id_jabatan === jabatanDipilih ? 'bg-blue-50 ring-1 ring-inset ring-blue-200' : 'hover:bg-slate-50'}"
            data-on-click="pilihJabatan" data-arg="${j.id_jabatan}">
            <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                    <p class="font-semibold text-slate-900 text-sm">${escapeHtml(j.nama)}</p>
                    <p class="text-[11px] mt-0.5 ${lv ? 'text-slate-500' : 'text-amber-700'}">${lv ? `Halaman awal: ${escapeHtml(labelHalamanAwal(lv.halaman_awal))}` : 'Belum diatur'}</p>
                </div>
                <span class="text-[11px] text-slate-500 whitespace-nowrap">${lv ? Number(lv.jumlah_user) : 0} pengguna</span>
            </div>
        </div>`;
    }).join('') || '<p class="p-4 text-sm text-slate-400">Belum ada jabatan. Tambahkan di Admin › Organisasi.</p>';
}

function kosongkanMatriks() {
    document.getElementById('judulMatriks').textContent = '';
    document.getElementById('btnSimpanAkses').disabled = true;
    document.getElementById('levelAwal').disabled = true;
    ['infoAdmin', 'infoBaru'].forEach(id => document.getElementById(id).classList.add('hidden'));
    document.getElementById('tabelAkses').innerHTML = '<tr><td colspan="6" class="table-cell text-center text-slate-400 py-6">Pilih jabatan</td></tr>';
    document.getElementById('ringkasAkses').textContent = '-';
}

async function pilihJabatan(id) {
    jabatanDipilih = id;
    tampilLevel();
    const dept = deptDipilih === 'admin' ? '' : deptDipilih;
    const form = document.getElementById('formAkses');
    form.elements.id_department.value = dept;
    form.elements.id_jabatan.value = id;
    const data = await ambilJson(`/api/admin/peran?id_department=${dept}&id_jabatan=${id}`);
    const tbody = document.getElementById('tabelAkses');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    const j = daftarJabatan.find(x => x.id_jabatan === id);
    const admin = !!j.is_admin;
    const namaDept = deptDipilih === 'admin' ? '' : `${(daftarDept.find(d => d.id_department === deptDipilih) || {}).nama} · `;
    document.getElementById('judulMatriks').textContent = `· ${namaDept}${j.nama}`;
    document.getElementById('infoAdmin').classList.toggle('hidden', !admin);
    document.getElementById('infoBaru').classList.toggle('hidden', !!data.level || admin);
    document.getElementById('btnSimpanAkses').disabled = false;
    const awal = document.getElementById('levelAwal');
    awal.disabled = false;
    pastikanPilihanAwal(data.halaman_awal);
    awal.value = data.halaman_awal;
    // Dikelompokkan: Halaman Utama (menu tanpa induk) lalu tiap induk (Stasiun Timbang, Pengenalan Wajah, ...).
    // Kelompok yang sudah ada centangnya langsung terbuka; sisanya tertutup dan bisa dibuka lewat panah.
    const grup = [];
    data.menu.forEach(m => {
        const nama = m.induk || 'Halaman Utama';
        let g = grup.find(x => x.nama === nama);
        if (!g) grup.push(g = { nama, menu: [] });
        g.menu.push(m);
    });
    const kotak = (m, aksi, ada) => ada
        ? `<td class="table-cell text-center"><input type="checkbox" name="${m.id_menu}_${aksi}" value="1" data-menu="${m.id_menu}"
            data-aksi="${aksi}" data-nama="${escapeHtml(m.nama)}" class="w-4 h-4"${m[aksi] ? ' checked' : ''}${admin ? ' disabled' : ''}></td>`
        : '<td class="table-cell text-center text-slate-300">–</td>';
    tbody.innerHTML = grup.map((g, i) => {
        const buka = g.menu.some(m => m.lihat);
        return `<tr class="bg-slate-50 cursor-pointer select-none hover:bg-slate-100" data-on-click="bukaGrupAkses" data-arg="${i}" data-grup-kepala="${i}">
                <td colspan="6" class="table-cell">
                    <span class="flex items-center gap-2">
                        <i class="fa-solid fa-chevron-right text-[10px] text-slate-400 transition-transform${buka ? ' rotate-90' : ''}" data-panah></i>
                        <span class="text-xs font-bold text-slate-600 uppercase tracking-wide">${escapeHtml(g.nama)}</span>
                        <span class="ml-auto text-[11px] font-normal text-slate-500" data-jumlah-grup="${i}"></span>
                    </span></td></tr>` +
            g.menu.map(m => `<tr class="hover:bg-slate-50${buka ? '' : ' hidden'}" data-grup="${i}"><td class="table-cell pl-9">${escapeHtml(m.nama.split(' › ').pop())}</td>
                ${kotak(m, 'lihat', true)}${kotak(m, 'tambah', m.aksi.includes('tambah'))}${kotak(m, 'ubah', m.aksi.includes('ubah'))}${kotak(m, 'hapus', m.aksi.includes('hapus'))}${kotak(m, 'setujui', m.aksi.includes('setujui'))}</tr>`).join('');
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

function bukaGrupAkses(i, paksa) {
    const baris = document.querySelectorAll(`#tabelAkses tr[data-grup="${i}"]`);
    const buka = paksa ?? [...baris].some(r => r.classList.contains('hidden'));
    baris.forEach(r => r.classList.toggle('hidden', !buka));
    document.querySelector(`#tabelAkses tr[data-grup-kepala="${i}"] [data-panah]`)?.classList.toggle('rotate-90', buka);
}

function bukaSemuaAkses(buka) {
    document.querySelectorAll('#tabelAkses tr[data-grup-kepala]').forEach(r => bukaGrupAkses(r.dataset.grupKepala, buka));
}

async function kosongkanAkses() {
    if (!await Dialog.konfirmasi({ judul: 'Kosongkan semua centang?', teksYa: 'Kosongkan', bahaya: true,
        pesan: 'Semua halaman & aksi untuk peran ini dilepas. Belum tersimpan sampai Anda menekan Simpan.' })) return;
    document.querySelectorAll('#tabelAkses input[type=checkbox]:not(:disabled)').forEach(c => { c.checked = false; });
    ringkasAkses();
}

function ringkasAkses() {
    // Jumlah halaman tercentang per kelompok (tampil di baris kepala kelompok)
    document.querySelectorAll('#tabelAkses [data-jumlah-grup]').forEach(el => {
        const semua = document.querySelectorAll(`#tabelAkses tr[data-grup="${el.dataset.jumlahGrup}"] input[data-aksi="lihat"]`);
        const n = [...semua].filter(c => c.checked).length;
        el.innerHTML = n ? `<span class="badge-status bg-emerald-100 text-emerald-700">${n} / ${semua.length} halaman</span>` : `${semua.length} halaman`;
    });
    const label = { tambah: 'tambah', ubah: 'ubah', hapus: 'hapus', setujui: 'setujui' };
    const chip = [...document.querySelectorAll('#tabelAkses input[data-aksi="lihat"]:checked')].map(c => {
        const aksi = [...document.querySelectorAll(`#tabelAkses input[data-menu="${c.dataset.menu}"]:checked`)]
            .map(x => label[x.dataset.aksi]).filter(Boolean);
        return `<span class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-slate-700">${escapeHtml(c.dataset.nama)}${aksi.length ? ` <span class="text-slate-400 ml-1">· ${aksi.join(', ')}</span>` : ''}</span>`;
    });
    document.getElementById('ringkasAkses').innerHTML = chip.join('') || 'Belum ada halaman yang dicentang';
}

document.getElementById('formAkses').addEventListener('submit', e => {
    e.preventDefault();
    if (jabatanDipilih) kirimFormAdmin(e.target, '/api/admin/peran/akses', { setelahnya: async () => { await muatSemua(); pilihJabatan(jabatanDipilih); } });
});

// Halaman awal: tampilkan nama menu, bukan alamat. Nilai lama yang diketik manual tetap muncul sebagai pilihan.
function labelHalamanAwal(url) {
    const opsi = Array.from(document.getElementById('levelAwal')?.options || []).find(o => o.value === url);
    return opsi ? opsi.text : url;
}

function pastikanPilihanAwal(url) {
    const sel = document.getElementById('levelAwal');
    if (url && !Array.from(sel.options).some(o => o.value === url)) sel.add(new Option(`${url} (lama)`, url));
}
