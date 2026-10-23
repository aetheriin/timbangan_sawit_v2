// ===== ADMIN > ORGANISASI: perusahaan, area perusahaan, Mill (tipe area), departemen (+ area), jabatan =====
// Perusahaan (CompID) & departemen (DeptID) memakai kode sebagai ID: saat kode diganti, server ikut memindah semua data terkait.
const ORG = {
    company: { id: 'id_company', nama: 'Perusahaan', kolom: c => [mono(c.kode), escapeHtml(c.nama), escapeHtml(c.alamat || '-'),
               escapeHtml(c.label_area || '-')] },
    area: { id: 'id_comp_area', nama: 'Area', kolom: a => [escapeHtml(a.kode_company), mono(a.kode), escapeHtml(a.nama),
            escapeHtml(a.mill || '-') + (a.is_pusat ? ' <span class="badge-status bg-amber-100 text-amber-800">Kantor pusat</span>' : ''),
            escapeHtml(a.keterangan || '-'), Number(a.jumlah_user)] },
    lokasi: { id: 'id_lokasi', nama: 'Mill', kolom: l => [mono(l.kode),
              escapeHtml(l.nama) + (l.is_pusat ? ' <span class="badge-status bg-amber-100 text-amber-800">Kantor pusat</span>' : ''),
              escapeHtml(l.keterangan || '-'), `${Number(l.jumlah_area)} area`] },
    department: { id: 'id_department', nama: 'Departemen', kolom: d => [mono(d.kode), escapeHtml(d.nama), escapeHtml(d.keterangan || '-'),
                  escapeHtml(labelAreaDept(d.area)), Number(d.jumlah_user)] },
    jabatan: { id: 'id_jabatan', nama: 'Jabatan', kolom: j => [mono(String(j.urutan)),
               escapeHtml(j.nama) + (j.is_admin ? ' <span class="badge-status bg-slate-800 text-white">Admin sistem</span>' : ''),
               escapeHtml(j.keterangan || '-'), `${Number(j.jumlah_peran)} departemen`, Number(j.jumlah_user)] },
};
let dataOrg = { company: [], area: [], lokasi: [], department: [], jabatan: [] };

const mono = teks => `<span class="font-mono">${escapeHtml(teks)}</span>`;
const labelAreaDept = ids => (ids || []).map(id => (dataOrg.area.find(a => a.id_comp_area === id) || {}).label)
    .filter(Boolean).join(', ') || 'Belum ada area';
const samaId = (a, b) => String(a) === String(b);

document.addEventListener('DOMContentLoaded', muatOrganisasi);

async function muatOrganisasi() {
    const data = await ambilJson('/api/admin/organisasi');
    if (!data.error) { dataOrg.company = data.company; dataOrg.area = data.area; }   // label departemen sebelum tabel digambar
    Object.keys(ORG).forEach(jenis => {
        const tbody = document.getElementById(`tabelOrg-${jenis}`);
        const n = Number(tbody.dataset.kolom);
        if (data.error) { tbody.innerHTML = barisKosong(n, data.error); return; }
        dataOrg[jenis] = data[jenis];
        const cfg = ORG[jenis];
        tbody.innerHTML = data[jenis].map(r => `
            <tr class="hover:bg-slate-50${r.is_active ? '' : ' text-slate-400'}">
                ${cfg.kolom(r).map(v => `<td class="table-cell">${v}</td>`).join('')}
                <td class="table-cell">${badgeAktif(r.is_active)}</td>
                <td class="table-cell text-right whitespace-nowrap space-x-3">
                    <button type="button" class="link-aksi text-blue-600" data-on-click="bukaOrganisasi" data-arg="${jenis}|${r[cfg.id]}">Ubah</button>
                    <button type="button" class="link-aksi ${r.is_active ? 'text-red-600' : 'text-emerald-600'}"
                        data-on-click="ubahAktifOrganisasi" data-arg="${jenis}|${r[cfg.id]}">${r.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
                </td>
            </tr>`).join('') || barisKosong(n, `Belum ada ${cfg.nama.toLowerCase()}`);
    });
    if (!data.error) tampilStatus(data.status || []);
}

// ===== STATUS TIKET: nama & warna badge di semua halaman =====
const NAMA_WARNA = { abu: 'Abu-abu', biru: 'Biru', hijau: 'Hijau', oranye: 'Oranye', merah: 'Merah', ungu: 'Ungu', kuning: 'Kuning', toska: 'Toska' };
let dataStatus = [];

function tampilStatus(daftar) {
    dataStatus = daftar;
    document.getElementById('tabelOrg-status').innerHTML = daftar.map(st => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell font-mono">${escapeHtml(st.kode)}</td>
            <td class="table-cell">${escapeHtml(st.nama)}</td>
            <td class="table-cell">${badge(st.nama, KELAS_WARNA_STATUS[st.warna] || KELAS_WARNA_STATUS.abu)}</td>
            <td class="table-cell text-right"><button type="button" class="link-aksi text-blue-600" data-on-click="bukaStatus" data-arg="${escapeHtml(st.kode)}">Ubah</button></td>
        </tr>`).join('') || barisKosong(4, 'Status tiket belum tersedia. Jalankan migrasi 033.');
}

function bukaStatus(kode) {
    const st = dataStatus.find(x => x.kode === kode);
    const form = document.getElementById('formOrg-status');
    form.reset();
    isiForm(form, { kode: st.kode, nama: st.nama });
    document.getElementById('kodeStatusOrg').textContent = st.kode;
    document.getElementById('orgStatusWarna').innerHTML = Object.entries(NAMA_WARNA).map(([k, nama]) => `
        <label class="flex items-center gap-2"><input type="radio" name="warna" value="${k}"${k === st.warna ? ' checked' : ''}>
            ${badge(nama, KELAS_WARNA_STATUS[k])}</label>`).join('');
    openModal('modalOrg-status');
    document.getElementById('orgStatusNama').focus();
}

document.getElementById('formOrg-status').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/organisasi/status/simpan', { modal: 'modalOrg-status', setelahnya: muatOrganisasi });
});

// Pilihan di form diisi dari data terbaru setiap kali form dibuka, jadi perubahan nama langsung tampil tanpa
// memuat ulang halaman. Yang nonaktif tidak ditawarkan, kecuali sedang dipakai baris yang diubah.
function isiPilihan(idSelect, daftar, id, label, dipakai) {
    const sel = document.getElementById(idSelect);
    [...sel.options].filter(o => o.value !== '').forEach(o => o.remove());
    daftar.filter(r => r.is_active || r[id] === dipakai).forEach(r => sel.add(new Option(label(r), r[id])));
    sel.value = dipakai ?? '';
}

function bukaOrganisasi(jenis, id) {
    const cfg = ORG[jenis];
    const form = document.getElementById(`formOrg-${jenis}`);
    const r = id != null && id !== '' ? dataOrg[jenis].find(x => samaId(x[cfg.id], id)) : null;
    form.reset();
    if (jenis === 'area') {
        isiPilihan('orgAreaCompany', dataOrg.company, 'id_company', c => `${c.kode} · ${c.nama}`, r ? r.id_company : null);
        isiPilihan('orgAreaMill', dataOrg.lokasi, 'id_lokasi', l => `${l.kode} · ${l.nama}`, r ? r.id_lokasi : null);
    }
    const { area, company, ...isi } = r || {};
    isiForm(form, r ? { ...isi, alamat: r.alamat || '', keterangan: r.keterangan || '' } : { [cfg.id]: '' });
    if (jenis === 'department') isiAreaDepartemen(r ? r.area : []);
    form.querySelector('[data-judul]').textContent = `${r ? 'Ubah' : 'Tambah'} ${cfg.nama}`;
    openModal(`modalOrg-${jenis}`);
    form.querySelector('input:not([type=hidden]):not([readonly]), select').focus();
}

Object.keys(ORG).forEach(jenis => {
    document.getElementById(`formOrg-${jenis}`).addEventListener('submit', e => {
        e.preventDefault();
        kirimFormAdmin(e.target, e.target.dataset.url, { modal: `modalOrg-${jenis}`, setelahnya: muatOrganisasi });
    });
});

function ubahAktifOrganisasi(jenis, id) {
    const cfg = ORG[jenis];
    const r = dataOrg[jenis].find(x => samaId(x[cfg.id], id));
    konfirmasiAktif({
        url: `/api/admin/organisasi/${jenis}/${id}/aktif`,
        aktif: !r.is_active, nama: r.label || r.nama, jenis: cfg.nama.toLowerCase(),
        pesanNonaktif: 'Tidak muncul lagi di pilihan saat membuat / mengubah user.',
        setelahnya: muatOrganisasi,
    });
}

// Centang area tempat departemen ini ada (DepartmentDetails), dikelompokkan per perusahaan
function isiAreaDepartemen(dipilih) {
    document.getElementById('orgDeptArea').innerHTML = dataOrg.area.filter(a => a.is_active || dipilih.includes(a.id_comp_area))
        .map(a => `<label class="flex items-center gap-2"><input type="checkbox" name="area" value="${a.id_comp_area}"${dipilih.includes(a.id_comp_area) ? ' checked' : ''}>
            ${escapeHtml(a.label)}</label>`).join('')
        || '<p class="text-slate-400">Belum ada area. Tambahkan di tabel Area Perusahaan.</p>';
}
