// ===== ADMIN > JADWAL KERJA =====
document.addEventListener('DOMContentLoaded', muatJadwal);

async function muatJadwal() {
    const data = await ambilJson(`/api/admin/jadwal?area=${encodeURIComponent(document.getElementById('jadwalArea').value)}`);
    const tbody = document.getElementById('tabelJadwal');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    tbody.innerHTML = data.map(j => `
        <tr class="hover:bg-slate-50" id="jadwal-${j.hari}">
            <td class="table-cell font-medium">${escapeHtml(j.nama_hari)}</td>
            <td class="table-cell"><input type="checkbox" name="is_libur" class="w-4 h-4" ${j.is_libur ? 'checked' : ''}
                data-on-change="aturLibur" data-arg="${j.hari}"></td>
            <td class="table-cell"><input type="time" name="jam_masuk" class="input-field py-1.5 w-32" value="${escapeHtml(j.jam_masuk || '')}"></td>
            <td class="table-cell"><input type="time" name="jam_pulang" class="input-field py-1.5 w-32" value="${escapeHtml(j.jam_pulang || '')}"></td>
            <td class="table-cell"><input type="number" name="toleransi_menit" min="0" max="120" class="input-field py-1.5 w-24"
                value="${Number(j.toleransi_menit) || 0}"></td>
            <td class="table-cell text-right"><button type="button" class="btn-primary py-1.5" data-on-click="simpanJadwal"
                data-arg="${j.hari}|$el">Simpan</button></td>
        </tr>`).join('');
    data.forEach(j => aturLibur(j.hari));
}

function inputJadwal(hari, nama) {
    return document.querySelector(`#jadwal-${hari} [name=${nama}]`);
}

function aturLibur(hari) {
    const libur = inputJadwal(hari, 'is_libur').checked;
    ['jam_masuk', 'jam_pulang', 'toleransi_menit'].forEach(n => { inputJadwal(hari, n).disabled = libur; });
}

async function simpanJadwal(hari, btn) {
    const data = {
        id_comp_area: document.getElementById('jadwalArea').value,
        hari,
        is_libur: inputJadwal(hari, 'is_libur').checked ? 1 : 0,
        jam_masuk: inputJadwal(hari, 'jam_masuk').value,
        jam_pulang: inputJadwal(hari, 'jam_pulang').value,
        toleransi_menit: inputJadwal(hari, 'toleransi_menit').value,
    };
    tampilkanHasil(await denganTombol(btn, () => kirimForm('/api/admin/jadwal/simpan', data)));
}
