// ===== ADMIN > KELOLA MENU =====
// Susunan menu 3 level (tabel Menu). Siapa yang mendapat menu diatur di Hak Akses; di sini hanya bentuk menunya.
const LABEL_AKSI_MENU = { tambah: 'Tambah', ubah: 'Ubah', hapus: 'Hapus', setujui: 'Setujui', tolak: 'Tolak', selesai: 'Selesai' };
let DATA_MENU = { menu: [], aplikasi: [], aksi: [] };

document.addEventListener('DOMContentLoaded', muatMenuKelola);

async function muatMenuKelola() {
    const data = await ambilJson('/api/admin/menu');
    const tbody = document.getElementById('tabelMenuKelola');
    if (data.error) { tbody.innerHTML = barisKosong(7, data.error); return false; }
    DATA_MENU = data;
    tampilMenuKelola();
}

const namaAksi = id => LABEL_AKSI_MENU[(DATA_MENU.aksi.find(a => a.id === id) || {}).nama] || id;

function tampilMenuKelola() {
    const q = (document.getElementById('cariMenuKelola').value || '').trim().toLowerCase();
    const menu = DATA_MENU.menu;
    let tampil = menu;
    if (q) {
        const per = Object.fromEntries(menu.map(m => [m.id_menu, m]));
        const cocok = new Set();
        menu.filter(m => m.nama.toLowerCase().includes(q) || m.kode.toLowerCase().includes(q))
            .forEach(m => { for (let x = m; x; x = per[x.id_induk]) cocok.add(x.id_menu); });
        tampil = menu.filter(m => cocok.has(m.id_menu));
    }
    const saudara = m => menu.filter(x => x.id_induk === m.id_induk);
    document.getElementById('tabelMenuKelola').innerHTML = tampil.map(m => {
        const s = saudara(m), i = s.indexOf(m);
        return `<tr class="hover:bg-slate-50${m.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell" style="padding-left:${0.75 + (m.level - 1) * 1.5}rem">
                <div class="flex items-center gap-2"><i class="fa-solid ${escapeHtml(m.ikon || (m.level === 1 ? 'fa-folder' : m.level === 2 ? 'fa-file' : 'fa-angle-right'))} w-4 text-center text-slate-400"></i>
                <div class="min-w-0"><p class="${m.level === 1 ? 'font-bold uppercase text-xs tracking-wider' : 'font-semibold'}">${escapeHtml(m.nama)}</p>
                <p class="text-[11px] font-mono text-slate-400">${escapeHtml(m.kode)} · Lv${m.level}</p></div></div></td>
            <td class="table-cell font-mono text-xs">${m.url ? escapeHtml(m.url) : '<span class="text-slate-400">belum ada</span>'}</td>
            <td class="table-cell text-xs">${escapeHtml(m.aplikasi)}</td>
            <td class="table-cell text-xs">${m.aksi.map(namaAksi).join(', ') || '<span class="text-slate-400">Lihat saja</span>'}</td>
            <td class="table-cell text-right font-mono">${m.jumlah_aturan}</td>
            <td class="table-cell">${badgeAktif(m.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap">
                <button type="button" class="px-1.5 text-slate-500 hover:text-blue-600 disabled:opacity-30" title="Naik" data-on-click="geserMenuKelola" data-arg="${m.id_menu}|-1"${i <= 0 ? ' disabled' : ''}><i class="fa-solid fa-arrow-up"></i></button>
                <button type="button" class="px-1.5 text-slate-500 hover:text-blue-600 disabled:opacity-30" title="Turun" data-on-click="geserMenuKelola" data-arg="${m.id_menu}|1"${i >= s.length - 1 ? ' disabled' : ''}><i class="fa-solid fa-arrow-down"></i></button>
                <button type="button" class="link-aksi text-blue-600 ml-2" data-on-click="bukaMenuKelola" data-arg="${m.id_menu}">Ubah</button>
                <button type="button" class="link-aksi ${m.is_active ? 'text-red-600' : 'text-emerald-600'} ml-2" data-on-click="aktifMenuKelola" data-arg="${m.id_menu}">${m.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td></tr>`;
    }).join('') || barisKosong(7, 'Menu tidak ditemukan');
}

async function geserMenuKelola(id, arah) {
    const r = await kirimForm(`/api/admin/menu/${id}/geser`, { arah });
    if (r.error) { Notif.gagal(r.error); return; }
    muatMenuKelola();
}

// Pilihan induk: Lv1 & Lv2 (Lv3 tidak bisa punya anak). Menu itu sendiri & turunannya tidak ditawarkan.
function isiPilihanInduk(m) {
    const turunan = new Set();
    if (m) { const antre = [m.id_menu]; while (antre.length) { const i = antre.pop(); DATA_MENU.menu.filter(x => x.id_induk === i).forEach(x => { turunan.add(x.id_menu); antre.push(x.id_menu); }); } }
    const opsi = DATA_MENU.menu.filter(x => x.level < 3 && (!m || (x.id_menu !== m.id_menu && !turunan.has(x.id_menu))))
        .map(x => `<option value="${x.id_menu}">${x.level === 2 ? '   › ' : ''}${escapeHtml(x.nama)} (${escapeHtml(x.kode)})</option>`);
    document.getElementById('menuInduk').innerHTML = '<option value="">— Tanpa induk (grup Level 1) —</option>' + opsi.join('');
}

function infoLevel() {
    const id = Number(document.getElementById('menuInduk').value) || null;
    const induk = DATA_MENU.menu.find(x => x.id_menu === id);
    const lv = induk ? induk.level + 1 : 1;
    document.getElementById('infoLevelMenu').textContent = lv === 1 ? 'Tanpa induk = grup Level 1.'
        : `Menjadi Level ${lv} di bawah ${induk.nama}.${lv === 2 ? ' Level 2 = halaman di sidebar.' : ' Level 3 = bagian / sub-halaman.'}`;
}
document.getElementById('menuInduk').addEventListener('change', infoLevel);

function pratinjauIkon() {
    const v = document.getElementById('menuIkon').value.trim();
    document.getElementById('contohIkon').innerHTML = /^fa-[a-z0-9-]+$/.test(v) ? `<i class="fa-solid ${escapeHtml(v)}"></i>` : '';
}

function bukaMenuKelola(id) {
    const m = DATA_MENU.menu.find(x => x.id_menu === Number(id));
    const form = document.getElementById('formMenuKelola');
    form.reset();
    isiPilihanInduk(m);
    document.getElementById('menuApp').innerHTML = DATA_MENU.aplikasi.map(a => `<option value="${a}">${a}</option>`).join('');
    document.getElementById('aksiMenuKelola').innerHTML = DATA_MENU.aksi.map(a => `<label class="inline-flex items-center gap-2">
        <input type="checkbox" name="aksi" value="${a.id}"${m && m.aksi.includes(a.id) ? ' checked' : ''}> ${LABEL_AKSI_MENU[a.nama] || a.nama}</label>`).join('');
    form.elements.id_menu.value = m ? m.id_menu : '';
    form.elements.kode.value = m ? m.kode : '';
    form.elements.kode.readOnly = !!m;
    form.elements.kode.required = !m;
    form.elements.kode.classList.toggle('bg-slate-50', !!m);
    form.elements.nama.value = m ? m.nama : '';
    form.elements.id_induk.value = m && m.id_induk ? m.id_induk : '';
    form.elements.url.value = m ? m.url || '' : '';
    form.elements.ikon.value = m ? m.ikon || '' : '';
    form.elements.aplikasi.value = m ? m.aplikasi : 'CPOS';
    document.getElementById('judulModalMenu').textContent = m ? `Ubah Menu · ${m.kode}` : 'Tambah Menu';
    infoLevel();
    pratinjauIkon();
    openModal('modalMenuKelola');
    (m ? form.elements.nama : form.elements.kode).focus();
}

document.getElementById('formMenuKelola').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/menu/simpan', { modal: 'modalMenuKelola', setelahnya: muatMenuKelola });
});

function aktifMenuKelola(id) {
    const m = DATA_MENU.menu.find(x => x.id_menu === Number(id));
    konfirmasiAktif({ url: `/api/admin/menu/${m.id_menu}/aktif`, aktif: !m.is_active, nama: m.nama, jenis: 'menu',
                      pesanNonaktif: 'Menu ini beserta turunannya hilang dari sidebar semua pengguna.', setelahnya: muatMenuKelola });
}
