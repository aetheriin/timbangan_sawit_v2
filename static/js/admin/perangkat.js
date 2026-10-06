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
            : st.terhubung ? `${escapeHtml(st.berat)} Kg${st.siap_kunci ? ' <span class="text-emerald-600">(stabil)</span>' : ''}`
            : `<span class="text-red-600" title="${escapeHtml(st.error || '')}">Tidak terhubung</span>`;
        const sambung = j.mode === 'AGEN'
            ? `Agen di PC jembatan · ID agen <b>${j.id_jembatan}</b><br>${escapeHtml(j.port)}`
            : escapeHtml(j.port);
        return `<tr class="hover:bg-slate-50${j.is_active ? '' : ' text-slate-400'}">
            <td class="table-cell font-mono">${escapeHtml(j.kode)}</td>
            <td class="table-cell">${escapeHtml(j.nama)}</td>
            <td class="table-cell">${escapeHtml(j.area)}</td>
            <td class="table-cell text-xs">${sambung} · ${Number(j.baudrate)} ${j.data_bits}${escapeHtml(j.parity)}${Number(j.stop_bits)}
                · ${escapeHtml(j.format_data)}</td>
            <td class="table-cell">${live}</td>
            <td class="table-cell">${badgeAktif(j.is_active)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                ${j.is_active ? `<button type="button" class="link-aksi text-slate-700" data-on-click="bukaMentah" data-arg="${j.id_jembatan}">Data mentah</button>` : ''}
                <button type="button" class="link-aksi text-blue-600" data-on-click="bukaJembatan" data-arg="${j.id_jembatan}">Ubah</button>
                <button type="button" class="link-aksi ${j.is_active ? 'text-red-600' : 'text-emerald-600'}" data-on-click="ubahAktifJembatan"
                    data-arg="${j.id_jembatan}">${j.is_active ? 'Nonaktifkan' : 'Aktifkan'}</button>
            </td></tr>`;
    }).join('') || barisKosong(7, 'Belum ada jembatan timbang');
}

function bukaJembatan(id) {
    const form = document.getElementById('formJembatan');
    const j = daftarJembatan.find(x => x.id_jembatan === id);
    form.reset();
    isiForm(form, j ? { ...j, stop_bits: String(Number(j.stop_bits)), pola: j.pola || '' }
                    : { id_jembatan: '', mode: 'AGEN', baudrate: 9600, data_bits: 7, parity: 'E', stop_bits: '1', format_data: 'ST_GS',
                        faktor: 1, toleransi_kg: 5, durasi_stabil: 3, berat_min_kg: 100, wajib_st: false });
    aturModeJembatan();
    document.getElementById('judulModalJembatan').textContent = j ? `Ubah Jembatan ${j.kode}` : 'Tambah Jembatan Timbang';
    openModal('modalJembatan');
    document.getElementById('jtKode').focus();
}

function aturModeJembatan() {
    const agen = document.getElementById('jtMode').value === 'AGEN';
    document.getElementById('jtPortHint').textContent = agen
        ? 'COM di PC jembatan (lihat Device Manager › Ports di PC itu)'
        : 'COM di PC server ini, atau socket://IP:PORT untuk alat serial-to-LAN';
    document.getElementById('jtPolaBox').classList.toggle('hidden', document.getElementById('jtFormat').value !== 'POLA');
}

// ===== DATA MENTAH: menyetel baudrate / parity / format di lokasi =====
let timerMentah = null;

function bukaMentah(id) {
    const j = daftarJembatan.find(x => x.id_jembatan === id);
    document.getElementById('judulMentah').textContent = `Data mentah ${j.kode} (${j.port} ${j.baudrate} ${j.data_bits}${j.parity}${Number(j.stop_bits)} · ${j.format_data})`;
    document.getElementById('tabelMentah').innerHTML = '';
    openModal('modalMentah');
    muatMentah(id);
    clearInterval(timerMentah);
    timerMentah = setInterval(() => muatMentah(id), 1000);
}

function tutupMentah() {
    clearInterval(timerMentah);
    closeModal('modalMentah');
    muatPerangkat();
}

async function muatMentah(id) {
    const data = await ambilJson(`/api/admin/jembatan/${id}/mentah`);
    const status = document.getElementById('statusMentah');
    if (data.error) { status.innerHTML = `<span class="text-red-600">${escapeHtml(data.error)}</span>`; return; }
    const st = data.status;
    status.innerHTML = st.terhubung
        ? `<span class="text-emerald-600 font-semibold">Terhubung</span> · berat <b>${escapeHtml(st.berat)} kg</b>
           ${st.siap_kunci ? '· <span class="text-emerald-600">stabil, boleh disimpan</span>' : '· belum stabil'}
           ${st.detik_sejak_data != null ? `· data terakhir ${st.detik_sejak_data} detik lalu` : ''}`
        : `<span class="text-red-600 font-semibold">Tidak terhubung</span> · ${escapeHtml(st.error || '-')}`;
    document.getElementById('tabelMentah').innerHTML = data.baris.map(b => `
        <tr><td class="table-cell">${escapeHtml(b.waktu)}</td><td class="table-cell whitespace-pre">${escapeHtml(JSON.stringify(b.teks))}</td>
            <td class="table-cell text-right">${b.berat == null ? '<span class="text-red-600">tidak terbaca</span>' : escapeHtml(b.berat)}</td>
            <td class="table-cell">${b.stabil ? 'ST' : ''}</td></tr>`).join('')
        || barisKosong(4, data.sisa_buffer ? `Belum ada bingkai utuh. Sisa diterima: ${JSON.stringify(data.sisa_buffer)}` : 'Belum ada data diterima');
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
