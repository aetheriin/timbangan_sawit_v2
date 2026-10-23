// ===== DATA MASTER > TABEL REFERENSI (Mata Uang, Bank, Rekening, Jenis & Grup Supplier, Jenis & Harga Produk) =====
// Kolom, isian form, hak, dan pilihan datang dari /api/master/ref/<jenis> (utils/db_referensi.py).
// Tombol: data-arg="jenis|id" -> fungsi(jenis, id)
const dataRef = {};

document.addEventListener('DOMContentLoaded', muatSemuaRef);

function muatSemuaRef() {
    document.querySelectorAll('[data-ref]').forEach(el => muatRef(el.dataset.ref));
}

function kotakRef(jenis) {
    return document.querySelector(`[data-ref="${CSS.escape(jenis)}"]`);
}

function labelPilihan(meta, kunci, id) {
    const o = (meta.pilihan[kunci] || []).find(x => x.id === id);
    return o ? o.label : `#${id}`;
}

function nilaiRef(meta, f, r) {
    const v = r[f.kunci];
    if (v === null || v === undefined || v === '') return '<span class="text-slate-300">-</span>';
    if (f.tipe === 'pilih') return escapeHtml(labelPilihan(meta, f.kunci, v));
    if (f.tipe === 'angka') return `<span class="tabular-nums">${Number(v).toLocaleString('id-ID', { maximumFractionDigits: 4 })}</span>`;
    if (f.tipe === 'kode' || f.tipe === 'tanggal') return `<span class="font-mono text-xs">${escapeHtml(v)}</span>`;
    return escapeHtml(v);
}

async function muatRef(jenis) {
    const box = kotakRef(jenis);
    const tbody = box.querySelector('tbody');
    const meta = await ambilJson(`/api/master/ref/${encodeURIComponent(jenis)}`);
    if (meta.error) { box.classList.add('hidden'); return; }      // tidak berhak melihat
    dataRef[jenis] = meta;
    box.querySelector('[data-ref-tambah]').classList.toggle('hidden', !(meta.tambah && meta.boleh_tambah));
    const status = meta.aktif || meta.void;
    const ekstra = meta.void ? ['Dibuat Oleh'] : [];
    box.querySelector('thead tr').innerHTML = [...meta.kolom.map(f => f.label), ...ekstra, ...(status ? ['Status'] : []), '']
        .map((l, i, arr) => `<th class="table-cell${i === arr.length - 1 ? ' text-right' : ''}">${escapeHtml(l || 'Aksi')}</th>`).join('');
    const nKolom = meta.kolom.length + ekstra.length + (status ? 1 : 0) + 1;
    const ubah = meta.boleh_ubah;
    tbody.innerHTML = meta.data.map(r => {
        const mati = (meta.aktif && !r.is_active) || (meta.void && r.is_void);
        const aksi = [
            meta.ubah && ubah ? `<button type="button" class="link-aksi text-blue-600" data-on-click="bukaRef" data-arg="${jenis}|${r.id}">Ubah</button>` : '',
            meta.aktif && ubah ? `<button type="button" class="link-aksi ${r.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifRef"
                data-arg="${jenis}|${r.id}">${r.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>` : '',
            meta.void && ubah && !r.is_void ? `<button type="button" class="link-aksi text-red-600" data-on-click="batalkanRef" data-arg="${jenis}|${r.id}">Batalkan</button>` : '',
        ].filter(Boolean).join(' ');
        return `<tr class="hover:bg-slate-50${mati ? ' text-slate-400' : ''}">
            ${meta.kolom.map(f => `<td class="table-cell${f.tipe === 'angka' ? ' text-right' : ''}">${nilaiRef(meta, f, r)}</td>`).join('')}
            ${meta.void ? `<td class="table-cell">${escapeHtml(r.dibuat_oleh || '-')}</td>` : ''}
            ${meta.aktif ? `<td class="table-cell">${badgeAktif(r.is_active)}</td>` : ''}
            ${meta.void ? `<td class="table-cell">${r.is_void ? badge(`Dibatalkan${r.void_oleh ? ' · ' + r.void_oleh : ''}`, WARNA_BADGE.abu)
                                                             : badge('Berlaku', WARNA_BADGE.hijau)}</td>` : ''}
            <td class="table-cell text-right whitespace-nowrap space-x-3">${aksi}</td>
        </tr>`;
    }).join('') || barisKosong(nKolom, `Belum ada data ${meta.judul.toLowerCase()}`,
        meta.tambah && meta.boleh_tambah ? { fungsi: 'bukaRef', label: `Tambah ${meta.judul}`, arg: jenis } : null);
}

function isianRef(f, terkunci) {
    const id = `ref_${f.kunci}`;
    const wajib = f.wajib ? ' required' : '';
    const label = `<label class="field-label" for="${id}">${escapeHtml(f.label)}${f.wajib ? '' : ' <span class="text-slate-400 font-normal">(opsional)</span>'}</label>`;
    let input;
    if (f.tipe === 'pilih') {
        const meta = dataRef[jenisRefAktif];
        input = `<select id="${id}" name="${f.kunci}" class="input-field"${wajib}><option value="">-</option>${
            (meta.pilihan[f.kunci] || []).map(o => `<option value="${o.id}">${escapeHtml(o.label)}</option>`).join('')}</select>`;
    } else {
        const tipe = { angka: 'number', tanggal: 'date' }[f.tipe] || 'text';
        input = `<input type="${tipe}" id="${id}" name="${f.kunci}" class="input-field${f.tipe === 'kode' ? ' uppercase font-mono' : ''}"${wajib}
            ${f.maks ? `maxlength="${f.maks}"` : ''}${f.tipe === 'angka' ? ' step="any" min="0"' : ''}${terkunci ? ' readonly' : ''}>`;
    }
    return `<div>${label}${input}${terkunci ? '<p class="field-hint">Kode dipakai aturan aplikasi, tidak bisa diubah.</p>' : ''}</div>`;
}

let jenisRefAktif = null;

function bukaRef(jenis, id = null) {
    const meta = dataRef[jenis];
    if (!meta) return;
    jenisRefAktif = jenis;
    const r = id ? meta.data.find(x => x.id === id) : null;
    const form = document.getElementById('formRef');
    form.reset();
    document.getElementById('isiFormRef').innerHTML = meta.kolom.map(f => isianRef(f, !!r && f.kunci_tetap)).join('');
    const isi = { id: r ? r.id : '' };
    meta.kolom.forEach(f => { isi[f.kunci] = r ? (r[f.kunci] ?? '') : (f.tipe === 'tanggal' ? new Date().toISOString().slice(0, 10) : ''); });
    isiForm(form, isi);
    document.getElementById('judulModalRef').textContent = `${r ? 'Ubah' : 'Tambah'} ${meta.judul}`;
    openModal('modalRef');
    form.querySelector('input:not([type=hidden]):not([readonly]), select')?.focus();
}

document.getElementById('formRef')?.addEventListener('submit', e => {
    e.preventDefault();
    // pilihan tabel lain ikut berubah (mis. bank baru muncul di rekening) -> muat ulang semua kotak
    kirimFormAdmin(e.target, `/api/master/ref/${encodeURIComponent(jenisRefAktif)}/simpan`, { modal: 'modalRef', setelahnya: muatSemuaRef });
});

function ubahAktifRef(jenis, id = null) {
    const meta = dataRef[jenis];
    const r = meta.data.find(x => x.id === id);
    konfirmasiAktif({
        url: `/api/master/ref/${encodeURIComponent(jenis)}/${id}/aktif`, aktif: !r.is_active, jenis: meta.judul.toLowerCase(),
        nama: r.nama || r.kode || r.no_rekening || meta.judul, pesanNonaktif: 'Tidak muncul lagi di pilihan formulir.',
        setelahnya: muatSemuaRef,
    });
}

async function batalkanRef(jenis, id = null) {
    const meta = dataRef[jenis];
    const ok = await Dialog.konfirmasi({ judul: `Batalkan ${meta.judul.toLowerCase()}?`, teksYa: 'Batalkan', bahaya: true,
        pesan: 'Data tetap tersimpan sebagai riwayat dengan status Dibatalkan. Input ulang bila perlu.' });
    if (!ok) return;
    if (tampilkanHasil(await kirimForm(`/api/master/ref/${encodeURIComponent(jenis)}/${id}/void`, {}))) muatRef(jenis);
}
