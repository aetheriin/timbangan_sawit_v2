// ===== ADMIN > ORGANISASI: company, area (site), department, mill =====
const ORG = {
    company: { id: 'id_company', nama: 'Company', kolom: c => [mono(c.kode), escapeHtml(c.nama), Number(c.jumlah_area)] },
    area: { id: 'id_comp_area', nama: 'Area', kolom: a => [mono(a.kode), escapeHtml(a.nama), escapeHtml(a.company),
                                                          escapeHtml(a.alamat || '-'), Number(a.jumlah_user)] },
    department: { id: 'id_department', nama: 'Department', kolom: d => [escapeHtml(d.nama), escapeHtml(d.keterangan || '-'),
                                                                        Number(d.jumlah_user)] },
    mill: { id: 'id_mill', nama: 'Mill', kolom: m => [mono(m.kode), escapeHtml(m.nama), escapeHtml(m.area), escapeHtml(m.nama_alur)] },
    kategori: { id: 'kode', nama: 'Kategori Personel', kolom: k => [mono(k.kode), escapeHtml(k.nama),
                k.prefix_kode ? mono(`${k.prefix_kode}-001`) : '<span class="text-slate-400">PRGBS-001</span>',
                k.wajib_sim ? 'Ya' : '-', k.boleh_akun ? 'Ya' : '-'] },
};
let dataOrg = { company: [], area: [], department: [], mill: [], kategori: [] };

const mono = teks => `<span class="font-mono">${escapeHtml(teks)}</span>`;

document.addEventListener('DOMContentLoaded', muatOrganisasi);

async function muatOrganisasi() {
    const data = await ambilJson('/api/admin/organisasi');
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
}

function bukaOrganisasi(jenis, id) {
    const cfg = ORG[jenis];
    const form = document.getElementById(`formOrg-${jenis}`);
    const r = id ? dataOrg[jenis].find(x => x[cfg.id] === id) : null;
    form.reset();
    isiForm(form, r ? { ...r, alamat: r.alamat || '', keterangan: r.keterangan || '', prefix_kode: r.prefix_kode || '', kode_lama: r.kode }
                    : { [cfg.id]: '', kode_lama: '' });
    if (form.elements.kode_lama) form.elements.kode.readOnly = !!r;      // kode kategori tetap setelah dibuat
    form.querySelector('[data-judul]').textContent = `${r ? 'Ubah' : 'Tambah'} ${cfg.nama}`;
    openModal(`modalOrg-${jenis}`);
    form.querySelector('input:not([type=hidden]), select').focus();
}

Object.keys(ORG).forEach(jenis => {
    document.getElementById(`formOrg-${jenis}`).addEventListener('submit', e => {
        e.preventDefault();
        kirimFormAdmin(e.target, e.target.dataset.url, { modal: `modalOrg-${jenis}`, setelahnya: muatOrganisasi });
    });
});

function ubahAktifOrganisasi(jenis, id) {
    const cfg = ORG[jenis];
    const r = dataOrg[jenis].find(x => x[cfg.id] === id);
    konfirmasiAktif({
        url: `/api/admin/organisasi/${jenis}/${id}/aktif`, aktif: !r.is_active, nama: r.nama, jenis: cfg.nama.toLowerCase(),
        pesanNonaktif: jenis === 'mill' ? 'Tiket baru tidak lagi memakai mill ini.' : 'Tidak muncul lagi di pilihan saat membuat / mengubah user.', setelahnya: muatOrganisasi,
    });
}
