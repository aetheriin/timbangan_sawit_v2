// ===== ADMIN > LEVEL & HAK AKSES =====
let daftarLevel = [];
let levelDipilih = null;

document.addEventListener('DOMContentLoaded', muatLevel);

async function muatLevel() {
    const data = await ambilJson('/api/admin/level');
    const tbody = document.getElementById('tabelLevel');
    if (data.error) { tbody.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(data.error)}</p>`; return; }
    daftarLevel = data;
    tbody.innerHTML = data.map(lv => `
        <div class="card p-4 cursor-pointer hover:shadow-md transition${lv.id_level === levelDipilih ? ' border-blue-400 ring-1 ring-blue-200' : ''}${lv.is_active ? '' : ' opacity-60'}"
            data-on-click="pilihLevel" data-arg="${lv.id_level}">
            <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                    <p class="font-bold text-slate-900">${escapeHtml(lv.nama)} <span class="ml-1 text-[11px] font-mono text-slate-400">${escapeHtml(lv.kode)}</span></p>
                    <p class="text-xs text-slate-500 mt-0.5">Halaman awal: ${escapeHtml(labelHalamanAwal(lv.halaman_awal))}</p>
                    ${lv.keterangan ? `<p class="text-xs text-slate-500 mt-1">${escapeHtml(lv.keterangan)}</p>` : ''}
                </div>
                <span class="text-[11px] font-mono font-semibold text-slate-600 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded flex-shrink-0">${Number(lv.jumlah_user)} Pengguna</span>
            </div>
            <div class="flex items-center justify-between gap-2 mt-3 pt-3 border-t border-slate-100">
                ${badgeAktif(lv.is_active)}
                <span class="space-x-3" data-henti-klik>
                    <button type="button" class="link-aksi text-blue-600" data-on-click="bukaLevel" data-arg="${lv.id_level}">Ubah</button>
                    ${lv.is_admin ? '' : `<button type="button" class="link-aksi ${lv.is_active ? 'text-red-600' : 'text-emerald-600'}"
                        data-on-click="ubahAktifLevel" data-arg="${lv.id_level}">${lv.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>`}
                </span>
            </div>
        </div>`).join('') || '<p class="text-sm text-slate-400">Belum ada level</p>';
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
        // Aksi yang tidak ada di menu ini (mis. hapus di Dashboard) tidak ditampilkan; menu tanpa aksi = hanya lihat
        const kotak = aksi => m.aksi.includes(aksi)
            ? `<td class="table-cell text-center"><input type="checkbox" name="${m.id_menu}_${aksi}" value="1"
                class="w-4 h-4"${m[aksi] ? ' checked' : ''}${admin ? ' disabled' : ''}></td>`
            : '<td class="table-cell text-center text-slate-300">–</td>';
        return `${judul}<tr class="hover:bg-slate-50"><td class="table-cell">${escapeHtml(m.nama.split(' › ').pop())}
                <span class="text-xs text-slate-400 font-mono">${escapeHtml(m.kode)}</span>
                ${m.aksi.length ? '' : '<span class="text-xs text-slate-400">· hanya lihat</span>'}</td>
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
        pesanNonaktif: 'Pengguna dengan level ini tidak bisa login dan sesinya langsung berakhir.', setelahnya: muatLevel,
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
