// ===== ADMIN › ALUR PERSETUJUAN: tahap berjenjang per jenis pengajuan + kategori target =====
// Tiap tahap dipilih sebagai departemen + jabatan (peran dibuat otomatis bila belum ada).
const DATA_ALUR = JSON.parse(document.getElementById('dataAlurSetuju').dataset.isi);
const PILIH_DEPT = DATA_ALUR.departemen.map((id, i) => [id, DATA_ALUR.nama_departemen[i]]);
const PILIH_JABATAN = DATA_ALUR.jabatan.map((id, i) => [id, DATA_ALUR.nama_jabatan[i]]);
let dataAlurSetuju = [];

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('alurJenis').innerHTML = Object.entries(DATA_ALUR.jenis)
        .map(([k, v]) => `<option value="${escapeHtml(k)}">${escapeHtml(v)}</option>`).join('');
    document.getElementById('alurKategori').innerHTML = '<option value="">Semua kategori</option>' +
        DATA_ALUR.kategori.map(k => `<option value="${escapeHtml(k.kode)}">${escapeHtml(k.nama)}</option>`).join('');
    muatAlurSetuju();
});

async function muatAlurSetuju() {
    const data = await ambilJson('/api/admin/alur-persetujuan');
    const tbody = document.getElementById('tabelAlurSetuju');
    if (data.error) { tbody.innerHTML = barisKosong(5, data.error); return; }
    dataAlurSetuju = data;
    tbody.innerHTML = data.map(a => `<tr class="hover:bg-slate-50 align-top">
        <td class="table-cell font-semibold text-slate-800 whitespace-nowrap">${escapeHtml(a.nama_jenis)}</td>
        <td class="table-cell whitespace-nowrap">${a.kategori ? escapeHtml(a.nama_kategori || a.kategori) : '<span class="text-slate-400">Semua kategori</span>'}</td>
        <td class="table-cell">${rantaiTahap(a.tahap)}${a.keterangan ? `<p class="text-xs text-slate-500 mt-1">${escapeHtml(a.keterangan)}</p>` : ''}</td>
        <td class="table-cell">${badgeAktif(a.is_active)}</td>
        <td class="table-cell text-right whitespace-nowrap">
            <button type="button" class="link-aksi text-blue-600" data-on-click="bukaAlurSetuju" data-arg="${a.id_alur_persetujuan}">Ubah</button>
            <button type="button" class="link-aksi text-slate-600 ml-3" data-on-click="aktifAlurSetuju" data-arg="${a.id_alur_persetujuan}">${a.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            <button type="button" class="link-aksi text-red-600 ml-3" data-on-click="hapusAlurSetuju" data-arg="${a.id_alur_persetujuan}">Hapus</button></td>
    </tr>`).join('') || barisKosong(5, 'Belum ada alur persetujuan. Pengajuan memakai cara lama (satu tahap, hak Setujui).',
        { fungsi: 'bukaAlurSetuju', label: 'Tambah Alur' });
}

// Tahap 1 → Tahap 2 → ... dengan peringatan bila peran belum punya pengguna / belum bisa membuka menunya
function rantaiTahap(tahap) {
    return `<div class="flex flex-wrap items-center gap-1.5">${tahap.map((t, i) => {
        const masalah = !t.jumlah_user ? 'Belum ada pengguna aktif dengan peran ini'
            : (!t.bisa_lihat ? 'Peran ini belum boleh membuka menunya (atur di Hak Akses)' : '');
        return `${i ? '<i class="fa-solid fa-arrow-right text-[10px] text-slate-400"></i>' : ''}
            <span class="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${masalah ? 'border-amber-300 bg-amber-50 text-amber-800' : 'border-slate-200 bg-white text-slate-700'}"
                  ${masalah ? `title="${escapeHtml(masalah)}"` : ''}>
                <b class="text-slate-400">${i + 1}</b> ${escapeHtml(t.nama)}${masalah ? ' <i class="fa-solid fa-triangle-exclamation"></i>' : ''}</span>`;
    }).join('')}</div>`;
}

// ===== MODAL =====
function opsi(daftar, dipilih) {
    return '<option value="">Pilih...</option>' + daftar.map(([id, nama]) =>
        `<option value="${id}"${id === dipilih ? ' selected' : ''}>${escapeHtml(nama)}</option>`).join('');
}

function bukaAlurSetuju(id) {
    const a = dataAlurSetuju.find(x => x.id_alur_persetujuan === id);
    const form = document.getElementById('formAlurSetuju');
    form.reset();
    form.elements.id_alur_persetujuan.value = a ? a.id_alur_persetujuan : '';
    form.elements.jenis.value = a ? a.jenis : 'BLACKLIST_TAMBAH';
    form.elements.kategori.value = a ? (a.kategori || '') : '';
    form.elements.keterangan.value = a ? (a.keterangan || '') : '';
    document.getElementById('judulAlurSetuju').textContent = a ? 'Ubah Alur Persetujuan' : 'Tambah Alur Persetujuan';
    document.getElementById('daftarTahapAlur').innerHTML = '';
    (a ? a.tahap : [{}]).forEach(t => tambahTahapAlur(t.id_department, t.id_jabatan));
    openModal('modalAlurSetuju');
}

function tambahTahapAlur(idDept = null, idJabatan = null) {
    const wadah = document.getElementById('daftarTahapAlur');
    const baris = document.createElement('div');
    baris.className = 'tahap-alur flex items-center gap-2';
    baris.innerHTML = `<span class="nomor-tahap w-7 h-7 rounded-full bg-slate-900 text-white text-xs font-bold flex items-center justify-center flex-shrink-0"></span>
        <select class="input-field flex-1" data-peran="dept" aria-label="Departemen" data-on-change="pratinjauAlur">${opsi(PILIH_DEPT, idDept)}</select>
        <select class="input-field flex-1" data-peran="jabatan" aria-label="Jabatan" data-on-change="pratinjauAlur">${opsi(PILIH_JABATAN, idJabatan)}</select>
        <button type="button" class="btn-secondary btn-sm" title="Naik" data-on-click="geserTahapAlur" data-arg="$el|-1"><i class="fa-solid fa-arrow-up"></i></button>
        <button type="button" class="btn-secondary btn-sm" title="Turun" data-on-click="geserTahapAlur" data-arg="$el|1"><i class="fa-solid fa-arrow-down"></i></button>
        <button type="button" class="btn-secondary btn-sm text-red-600" title="Hapus tahap" data-on-click="hapusTahapAlur" data-arg="$el"><i class="fa-solid fa-trash"></i></button>`;
    wadah.appendChild(baris);
    pratinjauAlur();
}

function geserTahapAlur(el, arah) {
    const baris = el.closest('.tahap-alur');
    const sasaran = arah < 0 ? baris.previousElementSibling : baris.nextElementSibling;
    if (!sasaran) return;
    if (arah < 0) sasaran.before(baris); else sasaran.after(baris);
    pratinjauAlur();
}

function hapusTahapAlur(el) {
    el.closest('.tahap-alur').remove();
    pratinjauAlur();
}

function pratinjauAlur() {
    const baris = [...document.querySelectorAll('#daftarTahapAlur .tahap-alur')];
    baris.forEach((b, i) => b.querySelector('.nomor-tahap').textContent = i + 1);
    const nama = baris.map(b => {
        const [d, j] = b.querySelectorAll('select');
        return d.value && j.value ? `${d.selectedOptions[0].text} · ${j.selectedOptions[0].text}` : '?';
    });
    document.getElementById('pratinjauAlur').textContent = nama.length ? `Alur: Pengaju → ${nama.join(' → ')} → selesai` : 'Belum ada tahap.';
}

document.getElementById('formAlurSetuju').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target;
    const tahap = [...document.querySelectorAll('#daftarTahapAlur .tahap-alur')].map(b => {
        const [d, j] = b.querySelectorAll('select');
        return `${d.value}:${j.value}`;
    });
    if (!tahap.length) { Notif.peringatan('Tambahkan minimal satu tahap'); return; }
    const fd = new FormData(form);
    fd.append('tahap', tahap.join(','));
    const data = await denganTombol(form.querySelector('[type=submit]'), () => kirimForm('/api/admin/alur-persetujuan/simpan', fd));
    if (!tampilkanHasil(data)) return;
    closeModal('modalAlurSetuju');
    muatAlurSetuju();
});

function aktifAlurSetuju(id) {
    const a = dataAlurSetuju.find(x => x.id_alur_persetujuan === id);
    if (!a) return;
    konfirmasiAktif({ url: `/api/admin/alur-persetujuan/${id}/aktif`, aktif: !a.is_active, jenis: 'alur persetujuan',
        nama: `${a.nama_jenis} · ${a.nama_kategori || 'Semua kategori'}`,
        pesanNonaktif: 'Pengajuan baru memakai alur Semua kategori atau cara lama.', setelahnya: muatAlurSetuju });
}

async function hapusAlurSetuju(id) {
    const a = dataAlurSetuju.find(x => x.id_alur_persetujuan === id);
    if (!a) return;
    const ok = await Dialog.konfirmasi({ judul: 'Hapus alur persetujuan?', teksYa: 'Hapus', bahaya: true,
        pesan: `${a.nama_jenis} · ${a.nama_kategori || 'Semua kategori'} dihapus. Pengajuan yang sedang berjalan tetap memakai tahap lamanya.` });
    if (!ok) return;
    const data = await kirimForm(`/api/admin/alur-persetujuan/${id}/hapus`, {});
    if (tampilkanHasil(data)) muatAlurSetuju();
}
