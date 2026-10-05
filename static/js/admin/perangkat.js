// ===== ADMIN > PERANGKAT / KIOSK =====
let daftarPos = [];
let modeUbahPos = false;

document.addEventListener('DOMContentLoaded', muatPerangkat);

async function muatPerangkat() {
    const data = await ambilJson('/api/admin/perangkat');
    const tbody = document.getElementById('tabelPos');
    if (data.error) { tbody.innerHTML = barisKosong(8, data.error); return false; }
    daftarPos = data.perangkat;

    const t = data.timbangan;
    const elT = document.getElementById('statTimbangan');
    elT.textContent = `${t.terhubung} / ${t.jumlah}`;
    elT.className = `stat-value ${t.jumlah && t.terhubung === t.jumlah ? 'text-emerald-600' : 'text-red-600'}`;
    document.getElementById('statTimbanganInfo').textContent = 'Port serial yang sedang dibaca server';
    tampilkanJembatan(data.jembatan || []);
    document.getElementById('statJumlahPos').textContent = daftarPos.length;
    document.getElementById('statPosAktif').textContent = `${daftarPos.filter(p => p.is_active).length} aktif`;
    const elEnv = document.getElementById('statTokenEnv');
    elEnv.textContent = data.token_env ? 'Dipakai' : 'Kosong';
    elEnv.className = `stat-value ${data.token_env ? 'text-amber-600' : 'text-slate-800'}`;

    tbody.innerHTML = daftarPos.map(p => `
        <tr class="hover:bg-slate-50${p.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono">${escapeHtml(p.id_pos)}</td>
            <td class="table-cell">${escapeHtml(p.nama)}</td>
            <td class="table-cell">${escapeHtml(p.lokasi || '-')}</td>
            <td class="table-cell">${badgeAktif(p.is_active)}</td>
            <td class="table-cell">${p.terakhir_detik == null ? '<span class="text-slate-400">Belum terhubung</span>'
                : `${durasiSingkat(p.terakhir_detik)} lalu`}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(p.ip || '-')}</td>
            <td class="table-cell">${p.kamera_aktif ? badge('Sedang scan', WARNA_BADGE.biru) : badge('Siaga', WARNA_BADGE.abu)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaPos" data-arg="${escapeHtml(p.id_pos)}">Ubah</button>
                <button type="button" class="link-aksi text-amber-700" data-on-click="gantiTokenPos" data-arg="${escapeHtml(p.id_pos)}">Ganti Token</button>
                <button type="button" class="link-aksi ${p.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifPos"
                    data-arg="${escapeHtml(p.id_pos)}">${p.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td>
        </tr>`).join('') || barisKosong(8, 'Belum ada pos kiosk. Tambah pos agar setiap kiosk punya token sendiri.');
}

function bukaPos(idPos) {
    const form = document.getElementById('formPos');
    const p = daftarPos.find(x => x.id_pos === idPos);
    modeUbahPos = !!p;
    form.reset();
    if (p) isiForm(form, p);
    form.elements.id_pos.readOnly = modeUbahPos;
    form.elements.id_pos.classList.toggle('bg-slate-50', modeUbahPos);
    document.getElementById('judulModalPos').textContent = p ? 'Ubah Pos Kiosk' : 'Tambah Pos Kiosk';
    openModal('modalPos');
    (p ? form.elements.nama : form.elements.id_pos).focus();
}

document.getElementById('formPos').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, modeUbahPos ? '/api/admin/perangkat/ubah' : '/api/admin/perangkat/tambah', {
        modal: 'modalPos',
        setelahnya: data => { muatPerangkat(); if (data.token) tampilkanToken(data.id_pos, data.token); },
    });
});

function tampilkanToken(idPos, token) {
    document.getElementById('isiEnvKiosk').textContent =
        `KIOSK_ID=${idPos}\nKIOSK_TOKEN=${token}\nWEIGHBRIDGE_URL=${location.origin}`;
    openModal('modalToken');
}

async function salinTokenKiosk() {
    try {
        await navigator.clipboard.writeText(document.getElementById('isiEnvKiosk').textContent);
        Notif.sukses('Disalin');
    } catch (e) {
        Notif.peringatan('Browser menolak menyalin otomatis. Blok teksnya lalu tekan Ctrl+C.');
    }
}

async function gantiTokenPos(idPos) {
    const ok = await Dialog.konfirmasi({
        judul: 'Ganti token?', pesan: `Token lama pos ${idPos} langsung tidak berlaku. Kiosk itu berhenti sampai .env-nya diisi token baru.`,
        teksYa: 'Ganti Token', bahaya: true,
    });
    if (!ok) return;
    const data = await kirimForm('/api/admin/perangkat/ganti-token', { id_pos: idPos });
    if (tampilkanHasil(data)) tampilkanToken(data.id_pos, data.token);
}

function ubahAktifPos(idPos) {
    const p = daftarPos.find(x => x.id_pos === idPos);
    konfirmasiAktif({
        url: '/api/admin/perangkat/aktif', data: { id_pos: idPos }, aktif: !p.is_active, nama: `Pos ${idPos}`, jenis: 'pos kiosk',
        pesanNonaktif: 'Kiosk di pos ini ditolak server sampai diaktifkan lagi.', setelahnya: muatPerangkat,
    });
}

// ===== JEMBATAN TIMBANG =====
let daftarJembatan = [];

function tampilkanJembatan(data) {
    daftarJembatan = data;
    document.getElementById('tabelJembatan').innerHTML = data.map(j => {
        const st = j.status;
        const live = !st ? '<span class="text-slate-400">Tidak dibaca</span>'
            : st.terhubung ? `${escapeHtml(st.berat)} Kg${st.stabil ? ' <span class="text-emerald-600">(stabil)</span>' : ''}`
            : '<span class="text-red-600">Tidak terhubung</span>';
        return `<tr class="hover:bg-slate-50${j.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono">${escapeHtml(j.kode)}</td>
            <td class="table-cell">${escapeHtml(j.nama)}</td>
            <td class="table-cell">${escapeHtml(j.area)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(j.port)} · ${Number(j.baudrate)}</td>
            <td class="table-cell">${live}</td>
            <td class="table-cell">${badgeAktif(j.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaJembatan" data-arg="${j.id_jembatan}">Ubah</button>
                <button type="button" class="link-aksi ${j.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifJembatan"
                    data-arg="${j.id_jembatan}">${j.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td></tr>`;
    }).join('') || barisKosong(7, 'Belum ada jembatan timbang (jalankan migrasi 011)');
}

function bukaJembatan(id) {
    const form = document.getElementById('formJembatan');
    const j = daftarJembatan.find(x => x.id_jembatan === id);
    form.reset();
    isiForm(form, j ? { id_jembatan: j.id_jembatan, kode: j.kode, nama: j.nama, id_comp_area: j.id_comp_area, port: j.port, baudrate: j.baudrate }
                    : { id_jembatan: '', baudrate: 9600 });
    document.getElementById('judulModalJembatan').textContent = j ? `Ubah Jembatan ${j.kode}` : 'Tambah Jembatan Timbang';
    openModal('modalJembatan');
    document.getElementById('jtKode').focus();
}

document.getElementById('formJembatan').addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/admin/jembatan/simpan', { modal: 'modalJembatan', setelahnya: muatPerangkat });
});

function ubahAktifJembatan(id) {
    const j = daftarJembatan.find(x => x.id_jembatan === id);
    konfirmasiAktif({
        url: `/api/admin/jembatan/${id}/aktif`, aktif: !j.is_active, nama: `Jembatan ${j.kode}`, jenis: 'jembatan timbang',
        pesanNonaktif: 'Tidak bisa dipilih lagi di PC operator timbang.', setelahnya: muatPerangkat,
    });
}
