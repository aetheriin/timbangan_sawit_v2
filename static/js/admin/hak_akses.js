// ===== ADMIN > HAK AKSES (aturan per menu) =====
// Tiap menu punya daftar aturan "Diberikan ke": Semua user / Peran (departemen + jabatan) / Jabatan / Departemen / User,
// Izinkan atau Larang per aksi (Larang menang). Aturan menu induk menjadi gerbang bagi anaknya.
// Menu Dashboard: tiap aturan Izinkan boleh membawa isi dashboard (widget); dipakai yang paling spesifik.
const AKSI = ['lihat', 'tambah', 'ubah', 'hapus', 'setujui', 'tolak', 'selesai'];
const JENIS = [['ALL', 'Semua user'], ['ROLE', 'Peran'], ['LEVEL', 'Jabatan'], ['DEPT', 'Departemen'], ['USER', 'User']];
let DATA = { menu: [], widget: [], jabatan: [], departemen: [], peran: [], halaman_awal: [] };
let menuAktif = null;
let aturan = [];
let berubah = false;
let salinan = null;              // aturan yang di-Copy (dari menu lain)
let barisPilihUser = null;       // indeks baris yang sedang memilih user
let barisWidget = null;          // indeks baris yang sedang diatur widget-nya

document.addEventListener('DOMContentLoaded', async () => {
    await muatAkses();
    const cek = new URLSearchParams(location.search).get('cek');
    if (cek) { pilihTabAkses('cek'); bukaCek(Number(cek)); }
});

async function muatAkses() {
    const data = await ambilJson('/api/admin/akses');
    if (data.error) { document.getElementById('pohonMenu').innerHTML = `<p class="p-4 text-sm text-red-600">${escapeHtml(data.error)}</p>`; return; }
    DATA = data;
    tampilPohonMenu();
    tampilHalamanAwal();
}

function pilihTabAkses(tab) {
    document.querySelectorAll('[data-tab-akses]').forEach(b => b.classList.toggle('chip-active', b.dataset.tabAkses === tab));
    ['aturan', 'cek', 'awal'].forEach(t => document.getElementById(`tabAkses-${t}`).classList.toggle('hidden', t !== tab));
}

// ===== Pohon menu =====
const menuKode = kode => DATA.menu.find(m => m.kode === kode);

function tampilPohonMenu() {
    const q = (document.getElementById('cariMenuAkses').value || '').trim().toLowerCase();
    let tampil = DATA.menu;
    if (q) {
        const cocok = new Set();
        DATA.menu.filter(m => m.nama.toLowerCase().includes(q) || m.kode.toLowerCase().includes(q)).forEach(m => {
            for (let x = m; x; x = x.induk ? menuKode(x.induk) : null) cocok.add(x.kode);
        });
        tampil = DATA.menu.filter(m => cocok.has(m.kode));
    }
    document.getElementById('pohonMenu').innerHTML = tampil.map(m => `
        <button type="button" class="w-full flex items-center gap-2 pr-3 py-1.5 text-left text-sm
            ${menuAktif && menuAktif.id_menu === m.id_menu ? 'bg-slate-900 text-white' : 'hover:bg-slate-50 text-slate-700'}"
            style="padding-left:${0.75 + (m.level - 1) * 1.1}rem" data-on-click="pilihMenuAkses" data-arg="${m.id_menu}">
            <i class="fa-solid ${m.level === 1 ? 'fa-folder' : m.level === 2 ? 'fa-file' : 'fa-angle-right'} w-3 text-[11px] opacity-60"></i>
            <span class="flex-1 truncate ${m.level === 1 ? 'font-semibold' : ''}">${escapeHtml(m.nama)}</span>
            ${m.url || m.level === 1 ? '' : '<span class="text-[10px] opacity-60" title="Halamannya belum dibuat">belum ada</span>'}
            <span class="w-2 h-2 rounded-full flex-shrink-0 ${m.jumlah_aturan ? 'bg-emerald-500' : 'bg-transparent'}"></span>
        </button>`).join('') || '<p class="p-4 text-sm text-slate-400">Menu tidak ditemukan</p>';
}

async function pilihMenuAkses(id) {
    if (berubah && menuAktif && menuAktif.id_menu !== id) {
        const ok = await Dialog.konfirmasi({ judul: 'Perubahan belum disimpan', pesan: `Aturan ${menuAktif.nama} belum disimpan. Tinggalkan tanpa menyimpan?`,
                                             teksYa: 'Tinggalkan', bahaya: true });
        if (!ok) return;
    }
    menuAktif = DATA.menu.find(m => m.id_menu === id);
    const data = await ambilJson(`/api/admin/akses/menu/${id}`);
    if (data.error) { Notif.gagal(data.error); return; }
    aturan = data;
    tandai(false);
    const remah = [];
    for (let x = menuKode(menuAktif.induk); x; x = x.induk ? menuKode(x.induk) : null) remah.unshift(x.nama);
    document.getElementById('remahMenuAkses').textContent = remah.length ? remah.join(' › ') : `Menu Level ${menuAktif.level}`;
    document.getElementById('judulMenuAkses').textContent = menuAktif.nama;
    document.querySelectorAll('[data-perlu-menu]').forEach(b => { b.disabled = false; });
    perbaruiTempel();
    tampilPohonMenu();
    tampilAturan();
}

// ===== Tabel aturan =====
const adaWidget = () => menuAktif && menuAktif.kode === 'DASHBOARD';
const aksiBerlaku = () => ['lihat', ...(menuAktif ? menuAktif.aksi : [])];

function tandai(ya) {
    berubah = ya;
    document.getElementById('tandaBerubah').classList.toggle('hidden', !ya);
    document.getElementById('btnSimpanAturan').disabled = !ya;
}

const opsi = (daftar, nilai) => daftar.map(([v, l]) => `<option value="${escapeHtml(v)}"${String(v) === String(nilai) ? ' selected' : ''}>${escapeHtml(l)}</option>`).join('');

function sasaran(a, i) {
    const dept = DATA.departemen.map(d => [d.id, d.nama]), jab = DATA.jabatan.map(j => [j.id, j.nama]);
    if (a.jenis === 'ALL') return '<span class="text-slate-500">Semua user yang login</span>';
    if (a.jenis === 'ROLE') {
        const [d, j] = String(a.id_target || '').split('|');
        return `<div class="flex gap-1">
            <select class="input-field py-1 text-xs w-36" data-i="${i}" data-f="role_dept" title="Departemen">${opsi(dept, d)}</select>
            <select class="input-field py-1 text-xs w-32" data-i="${i}" data-f="role_jab" title="Jabatan">${opsi(jab, j)}</select></div>`;
    }
    if (a.jenis === 'LEVEL') return `<select class="input-field py-1 text-xs w-36" data-i="${i}" data-f="id_target">${opsi(jab, a.id_target)}</select>`;
    if (a.jenis === 'DEPT') return `<select class="input-field py-1 text-xs w-36" data-i="${i}" data-f="id_target">${opsi(dept, a.id_target)}</select>`;
    return `<button type="button" class="btn-secondary btn-sm max-w-full truncate" data-on-click="bukaPilihUser" data-arg="${i}">
        <i class="fa-solid fa-user mr-1"></i>${escapeHtml(a.id_target ? a.nama_target : 'Pilih user...')}</button>`;
}

const LABEL_AKSI = { lihat: 'Lihat', tambah: 'Tambah', ubah: 'Ubah', hapus: 'Hapus', setujui: 'Setujui', tolak: 'Tolak', selesai: 'Selesai' };

// Kolom aksi hanya yang berlaku di menu ini (mis. Dashboard: Lihat & Ubah)
function tampilKepala() {
    const sel = document.querySelector('#kepalaAturan .kolom-aksi');
    sel.parentElement.querySelectorAll('[data-kolom-aksi]').forEach(el => el.remove());
    aksiBerlaku().forEach(k => sel.insertAdjacentHTML('beforebegin',
        `<th class="table-cell !px-1 text-center text-[11px]" data-kolom-aksi>${LABEL_AKSI[k]}</th>`));
    sel.classList.add('hidden');
}

function tampilAturan() {
    const berlaku = aksiBerlaku();
    tampilKepala();
    document.querySelectorAll('.kolom-widget').forEach(el => el.classList.toggle('hidden', !adaWidget()));
    const namaWidget = Object.fromEntries(DATA.widget.map(w => [w.kode, w.nama]));
    document.getElementById('tabelAturan').innerHTML = aturan.map((a, i) => `
        <tr class="${a.tolak ? 'bg-red-50/60' : 'hover:bg-slate-50'}">
            <td class="table-cell !px-2"><select class="input-field py-1 text-xs font-semibold w-24 ${a.tolak ? 'text-red-700' : 'text-emerald-700'}" data-i="${i}" data-f="tolak">
                ${opsi([['0', 'Izinkan'], ['1', 'Larang']], a.tolak ? '1' : '0')}</select></td>
            <td class="table-cell !px-2"><select class="input-field py-1 text-xs w-28" data-i="${i}" data-f="jenis">${opsi(JENIS, a.jenis)}</select></td>
            <td class="table-cell !px-2">${sasaran(a, i)}</td>
            ${berlaku.map(k => `<td class="table-cell !px-1 text-center"><input type="checkbox" class="w-4 h-4" data-i="${i}" data-f="aksi"
                data-aksi="${k}" title="${LABEL_AKSI[k]}"${a.aksi[k] ? ' checked' : ''}></td>`).join('')}
            ${adaWidget() ? `<td class="table-cell !px-2 min-w-[9rem]">${a.tolak ? '<span class="text-slate-300">–</span>'
                : `<button type="button" class="link-aksi text-blue-600 text-left" data-on-click="bukaWidgetAturan" data-arg="${i}">
                    ${a.widget.length ? a.widget.map(w => escapeHtml(namaWidget[w] || w)).join(', ') : '<span class="text-slate-400">Atur isi</span>'}</button>`}</td>` : ''}
            <td class="table-cell !px-2 text-right whitespace-nowrap">
                <button type="button" class="px-1.5 text-emerald-600 hover:text-emerald-800" title="Allow all baris ini" data-on-click="aksiBaris" data-arg="${i}|$true"><i class="fa-solid fa-check-double"></i></button>
                <button type="button" class="px-1.5 text-slate-400 hover:text-red-600" title="Deny all baris ini" data-on-click="aksiBaris" data-arg="${i}|$false"><i class="fa-solid fa-ban"></i></button>
                <button type="button" class="px-1.5 text-slate-400 hover:text-red-600" title="Hapus aturan" data-on-click="hapusAturan" data-arg="${i}"><i class="fa-solid fa-trash-can"></i></button>
            </td>
        </tr>`).join('') || `<tr><td colspan="12" class="table-cell text-center text-slate-400 py-10">Belum ada aturan: menu ini tidak terlihat oleh siapa pun.
            <button type="button" class="link-aksi text-blue-600 ml-1" data-on-click="tambahAturan">Tambah aturan</button></td></tr>`;
}

function targetAwal(jenis) {
    if (jenis === 'ROLE') return `${(DATA.departemen[0] || {}).id || ''}|${(DATA.jabatan[0] || {}).id || ''}`;
    if (jenis === 'LEVEL') return String((DATA.jabatan[0] || {}).id || '');
    if (jenis === 'DEPT') return (DATA.departemen[0] || {}).id || '';
    return null;
}

document.getElementById('tabelAturan').addEventListener('change', e => {
    const el = e.target, a = aturan[Number(el.dataset.i)];
    if (!a) return;
    const f = el.dataset.f;
    if (f === 'tolak') a.tolak = el.value === '1';
    else if (f === 'jenis') { a.jenis = el.value; a.id_target = targetAwal(a.jenis); a.nama_target = ''; }
    else if (f === 'id_target') a.id_target = el.value;
    else if (f === 'role_dept' || f === 'role_jab') {
        const [d, j] = String(a.id_target || '|').split('|');
        a.id_target = f === 'role_dept' ? `${el.value}|${j}` : `${d}|${el.value}`;
    } else if (f === 'aksi') {
        a.aksi[el.dataset.aksi] = el.checked;
        // Izinkan: aksi apa pun berarti boleh melihat menunya. Larang Lihat = menu (dan anaknya) tidak terlihat.
        if (!a.tolak && el.checked && el.dataset.aksi !== 'lihat') a.aksi.lihat = true;
        if (!a.tolak && !el.checked && el.dataset.aksi === 'lihat') AKSI.forEach(k => { a.aksi[k] = false; });
    }
    tandai(true);
    tampilAturan();
});

function tambahAturan() {
    aturan.push({ jenis: 'ROLE', id_target: targetAwal('ROLE'), nama_target: '', tolak: false, aksi: { lihat: true }, widget: [] });
    tandai(true);
    tampilAturan();
}

function hapusAturan(i) {
    aturan.splice(i, 1);
    tandai(true);
    tampilAturan();
}

function aksiBaris(i, nilai) {
    aksiBerlaku().forEach(k => { aturan[i].aksi[k] = nilai; });
    tandai(true);
    tampilAturan();
}

function semuaAksi(nilai) {
    aturan.forEach((_, i) => aksiBerlaku().forEach(k => { aturan[i].aksi[k] = nilai; }));
    tandai(true);
    tampilAturan();
}

// ===== Copy / Paste =====
function salinAturan() {
    salinan = { dari: menuAktif.nama, aturan: JSON.parse(JSON.stringify(aturan)) };
    Notif.info(`${aturan.length} aturan dari ${menuAktif.nama} disalin. Buka menu lain lalu klik Paste.`);
    perbaruiTempel();
}

function perbaruiTempel() {
    document.getElementById('btnTempel').disabled = !salinan || !menuAktif;
    document.getElementById('infoSalinan').textContent = salinan ? `Salinan: ${salinan.dari} (${salinan.aturan.length})` : '';
}

function tempelAturan() {
    if (!salinan) return;
    const berlaku = aksiBerlaku();
    const kunci = a => `${a.jenis}|${a.id_target}|${a.tolak}`;
    const ada = new Set(aturan.map(kunci));
    let n = 0;
    salinan.aturan.forEach(s => {
        if (ada.has(kunci(s))) return;        // sasaran yang sama sudah ada: tidak digandakan
        aturan.push({ ...s, aksi: Object.fromEntries(Object.entries(s.aksi).filter(([k]) => berlaku.includes(k))),
                      widget: adaWidget() ? s.widget : [] });
        n++;
    });
    Notif.info(n ? `${n} aturan ditempel. Periksa lalu Simpan.` : 'Semua sasaran dari salinan sudah ada di menu ini.');
    if (n) tandai(true);
    tampilAturan();
}

// ===== Simpan =====
document.getElementById('formAturan').addEventListener('submit', async e => {
    e.preventDefault();
    if (aturan.some(a => a.jenis === 'USER' && !a.id_target)) { Notif.peringatan('Ada aturan User yang belum dipilih usernya.'); return; }
    const kirim = aturan.map(a => ({ jenis: a.jenis, id_target: a.id_target, tolak: a.tolak,
                                     aksi: AKSI.filter(k => a.aksi[k]), widget: a.widget }));
    const btn = document.getElementById('btnSimpanAturan');
    const data = await denganTombol(btn, () => kirimForm(`/api/admin/akses/menu/${menuAktif.id_menu}`, { aturan: JSON.stringify(kirim) }));
    if (!tampilkanHasil(data)) return;
    const id = menuAktif.id_menu;
    tandai(false);
    await muatAkses();
    pilihMenuAkses(id);
});

// ===== Pilih user (aturan User) =====
function bukaPilihUser(i) {
    barisPilihUser = i;
    document.getElementById('cariPilihUser').value = '';
    document.getElementById('hasilPilihUser').innerHTML = '';
    openModal('modalPilihUser');
    document.getElementById('cariPilihUser').focus();
    cariPilihUser();
}

let timerCariUser = null;
function cariUser(q, wadahId, fungsi) {
    clearTimeout(timerCariUser);
    timerCariUser = setTimeout(async () => {
        const data = await ambilJson(`/api/admin/akses/user?q=${encodeURIComponent(q || '')}`);
        const wadah = document.getElementById(wadahId);
        if (data.error) { wadah.innerHTML = `<p class="p-3 text-sm text-red-600">${escapeHtml(data.error)}</p>`; return; }
        wadah.innerHTML = data.map(u => `
            <button type="button" class="w-full text-left px-3 py-2 hover:bg-slate-50" data-on-click="${fungsi}" data-arg="${u.id_user}"
                data-nama="${escapeHtml(u.nama)} · ${escapeHtml(u.username)}">
                <p class="text-sm font-semibold text-slate-800">${escapeHtml(u.nama)} <span class="font-normal text-slate-400">· ${escapeHtml(u.username)}</span></p>
                <p class="text-xs text-slate-500">${escapeHtml(u.nik || '-')} · ${escapeHtml(u.peran || '-')}</p>
            </button>`).join('') || '<p class="p-3 text-sm text-slate-400">Tidak ada user yang cocok</p>';
    }, 250);
}

function cariPilihUser() { cariUser(document.getElementById('cariPilihUser').value, 'hasilPilihUser', 'pakaiUser'); }

function pakaiUser(id) {
    const tombol = document.querySelector(`#hasilPilihUser [data-arg="${id}"]`);
    Object.assign(aturan[barisPilihUser], { id_target: String(id), nama_target: tombol ? tombol.dataset.nama : String(id) });
    closeModal('modalPilihUser');
    tandai(true);
    tampilAturan();
}

// ===== Isi dashboard (widget) per aturan =====
function bukaWidgetAturan(i) {
    barisWidget = i;
    const a = aturan[i];
    document.getElementById('judulWidgetAturan').textContent = `· ${JENIS.find(j => j[0] === a.jenis)[1]}${a.nama_target ? ` ${a.nama_target}` : ''}`;
    const urut = [...a.widget, ...DATA.widget.map(w => w.kode).filter(k => !a.widget.includes(k))];
    const per = Object.fromEntries(DATA.widget.map(w => [w.kode, w]));
    document.getElementById('daftarWidgetAturan').innerHTML = urut.filter(k => per[k]).map(k => `
        <div class="flex items-center gap-3 px-3 py-2" data-widget-baris>
            <input type="checkbox" value="${escapeHtml(k)}" id="wa_${escapeHtml(k)}"${a.widget.includes(k) ? ' checked' : ''}>
            <label for="wa_${escapeHtml(k)}" class="flex-1 min-w-0">
                <span class="text-sm font-semibold text-slate-800">${escapeHtml(per[k].nama)}</span>
                <span class="block text-xs text-slate-500">${escapeHtml(per[k].keterangan || '')}</span>
            </label>
            <button type="button" class="btn-secondary px-2 py-1" title="Naik" data-on-click="geserWidget" data-arg="$el|-1"><i class="fa-solid fa-arrow-up"></i></button>
            <button type="button" class="btn-secondary px-2 py-1" title="Turun" data-on-click="geserWidget" data-arg="$el|1"><i class="fa-solid fa-arrow-down"></i></button>
        </div>`).join('');
    openModal('modalWidgetAturan');
}

function geserWidget(el, arah) {
    const baris = el.closest('[data-widget-baris]');
    const tujuan = arah < 0 ? baris.previousElementSibling : baris.nextElementSibling;
    if (tujuan) (arah < 0 ? tujuan.before(baris) : tujuan.after(baris));
}

function pakaiWidgetAturan() {
    aturan[barisWidget].widget = [...document.querySelectorAll('#daftarWidgetAturan input:checked')].map(c => c.value);
    if (aturan[barisWidget].widget.length) aturan[barisWidget].aksi.lihat = true;
    closeModal('modalWidgetAturan');
    tandai(true);
    tampilAturan();
}

// ===== Cek Akses User =====
function cariUserCek() { cariUser(document.getElementById('cariUserCek').value, 'hasilUserCek', 'bukaCek'); }

const LABEL_JENIS = Object.fromEntries(JENIS);

async function bukaCek(id) {
    const data = await ambilJson(`/api/admin/akses/cek/${id}`);
    if (data.error) { Notif.gagal(data.error); return; }
    const namaWidget = Object.fromEntries(DATA.widget.map(w => [w.kode, w.nama]));
    document.getElementById('judulCek').textContent = `${data.user.nama} · ${data.user.username}`;
    document.getElementById('infoCek').textContent = `Peran: ${data.user.nama_level} · Isi dashboard: ${data.widget.map(w => namaWidget[w] || w).join(', ') || '-'}`;
    document.getElementById('tabelCek').innerHTML = data.menu.map(m => {
        const kelompok = {};
        m.sumber.forEach(s => {
            const k = `${s.tolak}|${s.jenis}|${s.nama}`;
            (kelompok[k] = kelompok[k] || { ...s, aksi: [] }).aksi.push(LABEL_AKSI[s.aksi] || s.aksi);
        });
        const asal = Object.values(kelompok).map(s => `<span class="badge-status mr-1 mb-1 ${s.tolak ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-700'}">
            ${s.tolak ? 'Larang' : 'Izinkan'} ${escapeHtml(s.aksi.join(', '))} · ${escapeHtml(LABEL_JENIS[s.jenis])}${s.jenis === 'ALL' ? '' : ` ${escapeHtml(s.nama || '')}`}</span>`).join('');
        const hak = m.hak ? AKSI.filter(k => m.hak[k]).map(k => LABEL_AKSI[k]).join(', ') : '';
        return `<tr class="${m.hak ? '' : 'text-slate-400'}">
            <td class="table-cell" style="padding-left:${0.75 + (m.level - 1) * 1.1}rem"><span class="${m.level === 1 ? 'font-semibold' : ''}">${escapeHtml(m.nama)}</span></td>
            <td class="table-cell">${m.hak ? `<span class="text-emerald-700">${escapeHtml(hak)}</span>` : 'Tidak terlihat'}</td>
            <td class="table-cell">${asal || '<span class="text-slate-300">-</span>'}</td></tr>`;
    }).join('');
}

// ===== Halaman awal per peran =====
function tampilHalamanAwal() {
    const pilihan = DATA.halaman_awal.map(h => [h.url, h.nama]);
    document.getElementById('tabelHalamanAwal').innerHTML = DATA.peran.map(p => `
        <tr class="${p.is_active ? '' : 'text-slate-400'}">
            <td class="table-cell">${escapeHtml(p.nama)}</td>
            <td class="table-cell text-right font-mono">${p.jumlah_user}</td>
            <td class="table-cell"><select class="input-field py-1.5 max-w-md" data-on-change="simpanHalamanAwal" data-arg="$el" data-id="${p.id}">
                ${opsi(pilihan.some(([u]) => u === p.halaman_awal) ? pilihan : [[p.halaman_awal, p.halaman_awal], ...pilihan], p.halaman_awal)}</select></td>
        </tr>`).join('') || barisKosong(3, 'Belum ada peran');
}

async function simpanHalamanAwal(el) {
    tampilkanHasil(await kirimForm(`/api/admin/level/${el.dataset.id}/halaman-awal`, { halaman_awal: el.value }));
}
