// ===== ADMIN > PENGATURAN SITE =====
let daftarPengaturan = [];

document.addEventListener('DOMContentLoaded', muatPengaturan);

function inputPengaturan(p) {
    if (p.tipe === 'bool') {
        return `<label class="inline-flex items-center gap-2 text-sm"><input type="checkbox" name="${p.kunci}" class="w-4 h-4"
            ${p.nilai ? 'checked' : ''}> Aktif</label>`;
    }
    if (p.tipe === 'area') {          // pilihan area dari dropdown "Berlaku untuk" di atas
        const opsi = Array.from(document.getElementById('pengaturanArea').options).filter(o => o.value)
            .map(o => `<option value="${escapeHtml(o.value)}"${String(p.nilai) === o.value ? ' selected' : ''}>${escapeHtml(o.text.replace(/^Area /, ''))}</option>`);
        return `<select name="${p.kunci}" class="input-field" data-tanpa-cari><option value="0">(tidak ada)</option>${opsi.join('')}</select>`;
    }
    const step = p.tipe === 'float' ? '0.01' : '1';
    return `<input type="number" name="${p.kunci}" class="input-field w-32" step="${step}" min="${p.min}" max="${p.max}"
        value="${escapeHtml(p.nilai)}" required>
        <span class="text-xs text-slate-400 ml-1">${p.min} - ${p.max}</span>`;
}

const areaPengaturan = () => document.getElementById('pengaturanArea').value;

async function muatPengaturan() {
    document.getElementById('infoPengaturanArea').classList.toggle('hidden', !areaPengaturan());
    document.getElementById('btnSalinCompany').classList.toggle('hidden', !areaPengaturan());
    const data = await ambilJson(`/api/admin/pengaturan?area=${encodeURIComponent(areaPengaturan())}`);
    const wadah = document.getElementById('grupPengaturan');
    if (data.error) { wadah.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(data.error)}</p>`; return; }
    daftarPengaturan = data;
    const grup = [...new Set(data.map(p => p.grup))];
    wadah.innerHTML = grup.map(g => `
        <div class="card">
            <h3 class="card-title">${escapeHtml(g)}</h3>
            <div class="space-y-4">${data.filter(p => p.grup === g).map(p => `
                <div>
                    <div class="flex items-center justify-between gap-2 mb-1.5">
                        <span class="text-sm font-medium text-slate-700">${escapeHtml(p.label)}</span>
                        ${badge(p.sumber, p.sumber === 'Admin' || p.sumber === 'Area' ? WARNA_BADGE.biru : WARNA_BADGE.abu)}
                    </div>
                    <div class="flex items-center">${inputPengaturan(p)}</div>
                    <p class="field-hint">${escapeHtml(p.keterangan)}. ${areaPengaturan() ? 'Global' : 'Bawaan'}: ${escapeHtml(String(p.tipe === 'bool' ? (p.bawaan ? 'Aktif' : 'Tidak') : p.bawaan))}
                        ${p.sumber === 'Admin' || p.sumber === 'Area' ? `· <button type="button" class="text-blue-600 hover:underline"
                            data-on-click="kembalikanBawaan" data-arg="${p.kunci}">${areaPengaturan() ? 'Ikuti global' : 'Kembalikan bawaan'}</button>` : ''}
                        ${!areaPengaturan() && p.per_area ? ' · bisa diatur per area' : ''}</p>
                </div>`).join('')}
            </div>
        </div>`).join('');
}

document.getElementById('formPengaturan').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.target;
    const data = { id_comp_area: areaPengaturan() };
    daftarPengaturan.forEach(p => {
        const el = form.elements[p.kunci];
        data[p.kunci] = p.tipe === 'bool' ? (el.checked ? 'true' : 'false') : el.value;
    });
    const btn = form.querySelector('[type=submit]');
    if (tampilkanHasil(await denganTombol(btn, () => kirimForm('/api/admin/pengaturan/simpan', data)))) muatPengaturan();
});

async function kembalikanBawaan(kunci) {
    if (tampilkanHasil(await kirimForm('/api/admin/pengaturan/bawaan', { kunci, id_comp_area: areaPengaturan() }))) muatPengaturan();
}

async function salinPengaturanCompany(btn) {
    const ok = await Dialog.konfirmasi({ judul: 'Terapkan ke semua area company?', teksYa: 'Terapkan',
        pesan: 'Pengaturan area ini (yang sudah disimpan) akan dipakai juga oleh semua area lain di company yang sama.' });
    if (!ok) return;
    tampilkanHasil(await denganTombol(btn, () => kirimForm('/api/admin/pengaturan/salin-company', { id_comp_area: areaPengaturan() })));
}
