// ===== ADMIN > ORGANISASI: company, lokasi, site (company + lokasi), department, mill =====
const ORG = {
    company: { id: 'id_company', nama: 'Perusahaan', kolom: c => [mono(c.kode), escapeHtml(c.nama), Number(c.jumlah_area)] },
    lokasi: { id: 'id_lokasi', nama: 'Lokasi', kolom: l => [mono(l.kode), escapeHtml(l.nama),
             l.is_pusat ? '<span class="badge-status bg-amber-100 text-amber-800">Kantor pusat</span>' : escapeHtml(JENIS_LOKASI[l.jenis] || l.jenis),
             Number(l.jumlah_site)] },
    area: { id: 'id_comp_area', nama: 'Site', kolom: a => [escapeHtml(a.company), `${mono(a.kode)} (${escapeHtml(a.lokasi || '-')})`,
                                                          escapeHtml(a.nama), escapeHtml(a.alamat || '-'), Number(a.jumlah_user)] },
    department: { id: 'id_department', nama: 'Departemen', kolom: d => [escapeHtml(d.nama), escapeHtml(d.keterangan || '-'),
                                                                        Number(d.jumlah_user)] },
    mill: { id: 'id_mill', nama: 'Pabrik', kolom: m => [mono(m.kode), escapeHtml(m.nama), escapeHtml(m.area), escapeHtml(m.nama_alur)] },
};
let dataOrg = { company: [], lokasi: [], area: [], department: [], mill: [] };
const JENIS_LOKASI = { KANTOR_PUSAT: 'Kantor pusat', PKS: 'PKS', REFINERY: 'Refinery', TANGKI: 'Tangki timbun',
                       LAB: 'Laboratorium', KEBUN: 'Kebun', GUDANG: 'Gudang', LAINNYA: 'Lainnya' };

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
    if (!data.error) isiPilihanOrganisasi();
}

// Pilihan Perusahaan & Lokasi (form Site) dan Site (form Pabrik) diisi ulang dari data terbaru setiap kali data dimuat,
// jadi nama yang baru diubah langsung tampil di form tanpa memuat ulang halaman. Yang nonaktif tidak ditawarkan.
// Pilihan kosong "-- Pilih ... --" (pilih_cari.js) dipertahankan.
function isiPilihanOrganisasi() {
    const isi = (idSelect, daftar, id, label) => {
        const sel = document.getElementById(idSelect);
        if (!sel) return;
        const pilihan = sel.value;
        [...sel.options].filter(o => o.value !== '').forEach(o => o.remove());
        daftar.filter(r => r.is_active).forEach(r => sel.add(new Option(label(r), r[id])));
        sel.value = pilihan;
    };
    isi('orgAreaCompany', dataOrg.company, 'id_company', c => c.nama);
    isi('orgAreaLokasi', dataOrg.lokasi, 'id_lokasi', l => `${l.kode} (${l.nama})`);
    isi('orgMillArea', dataOrg.area, 'id_comp_area', a => a.label);
}

function bukaOrganisasi(jenis, id) {
    const cfg = ORG[jenis];
    const form = document.getElementById(`formOrg-${jenis}`);
    const r = id ? dataOrg[jenis].find(x => x[cfg.id] === id) : null;
    form.reset();
    isiForm(form, r ? { ...r, alamat: r.alamat || '', keterangan: r.keterangan || '' } : { [cfg.id]: '' });
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
