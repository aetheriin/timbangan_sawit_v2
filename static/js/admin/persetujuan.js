// ===== ADMIN > PERSETUJUAN: penyetuju 1-3 langkah per jenis pengajuan =====
document.addEventListener('DOMContentLoaded', muatPersetujuan);

async function muatPersetujuan() {
    const data = await ambilJson('/api/admin/persetujuan');
    const wadah = document.getElementById('daftarPersetujuan');
    if (data.error) { wadah.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(data.error)}</p>`; return; }
    const opsi = document.getElementById('opsiJabatan').innerHTML;
    wadah.innerHTML = data.map(j => `
        <form class="section-box" data-jenis="${escapeHtml(j.jenis)}">
            <input type="hidden" name="jenis" value="${escapeHtml(j.jenis)}">
            <div class="flex items-center justify-between gap-2 px-5 py-3 border-b border-slate-100">
                <div><p class="font-bold text-slate-900">${escapeHtml(j.nama)}</p>
                    <p class="text-xs ${j.langkah.length ? 'text-slate-500' : 'text-amber-700'}">${j.langkah.length
                        ? `${j.langkah.length} langkah persetujuan` : 'Belum ada penyetuju: pengajuan langsung berlaku'}</p></div>
                <button type="submit" class="btn-primary btn-sm">Simpan</button>
            </div>
            <div class="p-5 space-y-3">
                ${[1, 2, 3].map(i => `
                <div class="grid grid-cols-[5.5rem_1fr] items-center gap-3">
                    <label class="text-sm font-semibold text-slate-700" for="lk_${j.jenis}_${i}">Langkah ${i}</label>
                    <select id="lk_${j.jenis}_${i}" name="langkah_${i}" class="input-field" data-tanpa-cari>${opsi}</select>
                </div>`).join('')}
                <p class="field-hint">Langkah berikutnya hanya berjalan setelah langkah sebelumnya disetujui. Langkah kosong di tengah dilewati.</p>
            </div>
        </form>`).join('');
    data.forEach(j => j.langkah.forEach((id, i) => {
        document.getElementById(`lk_${j.jenis}_${i + 1}`).value = String(id);
    }));
}

document.getElementById('daftarPersetujuan').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/persetujuan/simpan', { setelahnya: muatPersetujuan });
});
