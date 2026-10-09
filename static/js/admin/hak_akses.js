// ===== ADMIN > LEVEL & HAK AKSES =====
let daftarLevel = [];
let levelDipilih = null;

document.addEventListener('DOMContentLoaded', muatLevel);

async function muatLevel() {
    const data = await ambilJson('/api/admin/level');
    const tbody = document.getElementById('tabelLevel');
    if (data.error) { tbody.innerHTML = barisKosong(5, data.error); return; }
    daftarLevel = data;
    tbody.innerHTML = data.map(lv => `
        <tr class="hover:bg-slate-50 cursor-pointer${lv.is_active ? '' : ' text-slate-400'}${lv.id_level === levelDipilih ? ' bg-blue-50' : ''}"
            data-on-click="pilihLevel" data-arg="${lv.id_level}">
            <td class="table-cell">${badgeRole(lv.kode, lv.nama)}<div class="text-xs text-slate-400 font-mono">${escapeHtml(lv.kode)}</div></td>
            <td class="table-cell text-xs">${escapeHtml(labelHalamanAwal(lv.halaman_awal))}</td>
            <td class="table-cell">${Number(lv.jumlah_user)}</td>
            <td class="table-cell">${badgeAktif(lv.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3" data-henti-klik>
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaLevel" data-arg="${lv.id_level}">Ubah</button>
                ${lv.is_admin ? '' : `<button type="button" class="link-aksi ${lv.is_active ? 'text-red-600' : 'text-emerald-600'}"
                    data-on-click="ubahAktifLevel" data-arg="${lv.id_level}">${lv.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>`}
            </td>
        </tr>`).join('') || barisKosong(5, 'Belum ada level');
}

async function pilihLevel(id) {
    levelDipilih = id;
    muatLevel();
    const data = await ambilJson(`/api/admin/level/${id}/akses`);
    const tbody = document.getElementById('tabelAkses');
    if (data.error) { tbody.innerHTML = barisKosong(4, data.error); return; }
    const admin = !!data.level.is_admin;
    document.getElementById('judulMatriks').textContent = data.level.nama;
    document.getElementById('infoAdmin').classList.toggle('hidden', !admin);
    document.getElementById('btnSimpanAkses').disabled = admin;
    let induk = null;
    tbody.innerHTML = data.menu.map(m => {
        const judul = m.induk && m.induk !== induk
            ? `<tr class="bg-slate-50"><td colspan="4" class="table-cell text-xs font-semibold text-slate-500 uppercase">${escapeHtml(m.induk)}</td></tr>` : '';
        induk = m.induk;
        const kotak = aksi => `<td class="table-cell text-center"><input type="checkbox" name="${m.id_menu}_${aksi}" value="1"
            class="w-4 h-4"${m[aksi] ? ' checked' : ''}${admin ? ' disabled' : ''}></td>`;
        return `${judul}<tr class="hover:bg-slate-50"><td class="table-cell">${escapeHtml(m.nama.split(' › ').pop())}
                <span class="text-xs text-slate-400 font-mono">${escapeHtml(m.kode)}</span></td>
                ${kotak('tambah')}${kotak('ubah')}${kotak('hapus')}</tr>`;
    }).join('');
}

document.getElementById('formAkses').addEventListener('submit', e => {
    e.preventDefault();
    if (levelDipilih) kirimFormAdmin(e.target, `/api/admin/level/${levelDipilih}/akses`);
});

function bukaLevel(id) {
    const form = document.getElementById('formLevel');
    const lv = daftarLevel.find(x => x.id_level === id);
    form.reset();
    pastikanPilihanAwal(lv ? lv.halaman_awal : '');
    isiForm(form, lv ? { id_level: lv.id_level, kode: lv.kode, nama: lv.nama, halaman_awal: lv.halaman_awal, keterangan: lv.keterangan || '' }
                     : { id_level: '', halaman_awal: '/weighbridge?view=list' });
    form.elements.kode.readOnly = !!lv;
    form.elements.kode.required = !lv;
    form.elements.kode.classList.toggle('bg-slate-50', !!lv);
    document.getElementById('judulModalLevel').textContent = lv ? `Ubah Level ${lv.kode}` : 'Tambah Level';
    openModal('modalLevel');
    (lv ? form.elements.nama : form.elements.kode).focus();
}

document.getElementById('formLevel').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/level/simpan', { modal: 'modalLevel', setelahnya: muatLevel });
});

function ubahAktifLevel(id) {
    const lv = daftarLevel.find(x => x.id_level === id);
    konfirmasiAktif({
        url: `/api/admin/level/${id}/aktif`, aktif: !lv.is_active, nama: `Level ${lv.nama}`, jenis: 'level',
        pesanNonaktif: 'User dengan level ini tidak bisa login dan sesinya langsung berakhir.', setelahnya: muatLevel,
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
