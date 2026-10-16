// ===== POS SECURITY (tahap 1) — PRATINJAU TAMPILAN =====
// Isi di halaman ini masih contoh untuk menilai tampilan. Fungsi nyata (cek plat ke server, scan wajah, simpan jam
// masuk / keluar) dipasang setelah tampilan disetujui; pola peringatan & kartu di sini tetap dipakai.
const POS = document.getElementById('posSecurity');

const CONTOH = {
    normal: {
        plat: 'BK 8492 XA', stnk: '12345678', jenis: 'Truk',
        terakhir: { nama: 'Wawan Setiawan', kode: 'DRV-006', waktu: 'Kemarin 14:20' },
        supir: { nama: 'Wawan Setiawan', kode: 'DRV-006', id: 'P-000006', nik: '1271••••••••0006', sim: 'B1 UMUM · 3207-1234-5678', sim_berlaku: '12-08-2028' },
        customer: 'PT Sawit Sumber Mas', produk: 'TBS', angkut: 'CV Angkut Lancar',
        peringatan: [],
    },
    blacklist: {
        plat: 'BH 8820 LK', stnk: '87654321', jenis: 'Dump Truk',
        terakhir: { nama: 'Hendra Gunawan', kode: 'DRV-002', waktu: '3 hari lalu 09:05' },
        supir: { nama: 'Hendra Gunawan', kode: 'DRV-002', id: 'P-000002', nik: '1271••••••••0002', sim: 'B1 · 3207-9876-5432', sim_berlaku: '02-10-2026', sim_habis: true, blacklist: true },
        customer: 'KUD Harapan Jaya', produk: 'TBS', angkut: '',
        peringatan: [
            { tingkat: 'kritis', ikon: 'fa-user-slash', judul: 'Supir masuk blacklist: Hendra Gunawan (DRV-002)',
              isi: 'Alasan: membawa TBS curian · sejak 12-10-2026 · disetujui Head Office', aksi: 'Lihat detail' },
            { tingkat: 'kritis', ikon: 'fa-truck', judul: 'Kendaraan masuk blacklist: BH 8820 LK',
              isi: 'Alasan: plat palsu · sejak 08-10-2026', aksi: 'Lihat detail' },
            { tingkat: 'perhatian', ikon: 'fa-id-card', judul: 'SIM supir sudah kedaluwarsa',
              isi: 'SIM B1 Hendra Gunawan berlaku sampai 02-10-2026 (14 hari lalu).' },
        ],
    },
    didalam: {
        plat: 'BA 7312 QB', stnk: '55667788', jenis: 'Truk Tangki',
        terakhir: { nama: 'Rahmat Hidayat', kode: 'DRV-004', waktu: 'Hari ini 07:42' },
        supir: { nama: 'Rahmat Hidayat', kode: 'DRV-004', id: 'P-000004', nik: '1271••••••••0004', sim: 'B2 UMUM · 3207-1111-2222', sim_berlaku: '30-10-2026', sim_segera: true },
        customer: 'PT Citra Palma Abadi', produk: 'CPO', angkut: 'PT Trans Sawit',
        peringatan: [
            { tingkat: 'perhatian', ikon: 'fa-door-open', judul: 'Truk ini tercatat masih di dalam sejak 07:42 (3 jam 5 menit)',
              isi: 'Catat keluar dulu sebelum mencatat masuk lagi, atau periksa apakah petugas lupa mencatat keluar.', aksi: 'Catat Keluar' },
            { tingkat: 'perhatian', ikon: 'fa-id-card', judul: 'SIM supir habis dalam 14 hari',
              isi: 'SIM B2 Umum Rahmat Hidayat berlaku sampai 30-10-2026.' },
        ],
    },
};

document.addEventListener('DOMContentLoaded', () => {
    const jam = () => { document.getElementById('jamSekarang').textContent = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' }); };
    jam(); setInterval(jam, 15000);
    contohPos('normal');
});

function contohPos(keadaan) {
    document.querySelectorAll('[data-on-click="contohPos"]').forEach(b => b.classList.toggle('chip-active', b.dataset.arg === keadaan));
    const c = CONTOH[keadaan];
    const isi = (id, v) => { const el = document.getElementById(id); el.value = v || ''; el.dispatchEvent(new Event('change')); };
    isi('posPlat', c && c.plat); isi('posStnk', c && c.stnk); isi('posJenis', c && c.jenis); isi('posAngkut', c && c.angkut);
    pilihTeks('posCustomer', c && c.customer);
    pilihTeks('posProduk', c && c.produk);
    tampilPeringatan(c ? c.peringatan : []);
    tampilTerakhir(c && c.terakhir);
    tampilSupir(c && c.supir);
    document.getElementById('badgePlat').innerHTML = c && c.peringatan.some(p => p.ikon === 'fa-truck')
        ? '<span class="badge-status bg-red-600 text-white"><i class="fa-solid fa-ban mr-1"></i>BLACKLIST</span>'
        : keadaan === 'didalam' ? '<span class="badge-status bg-amber-100 text-amber-800">Masih di dalam</span>' : '';
    document.getElementById('btnKeluarPos')?.classList.toggle('hidden', keadaan !== 'didalam');
    document.getElementById('btnSimpanPos')?.toggleAttribute('disabled', keadaan === 'didalam' || !c);
    document.getElementById('posStatusScan').textContent = c ? 'Wajah cocok 96% dengan data personel.' : '';
    document.getElementById('ringkasPos').textContent = c
        ? `${c.plat} · ${c.supir.nama} · ${c.customer} · ${c.produk}${c.angkut ? ` · ${c.angkut}` : ''}` : 'Belum ada data';
}

function pilihTeks(id, teks) {
    const sel = document.getElementById(id);
    const opsi = [...sel.options].find(o => teks && o.textContent.trim() === teks) || [...sel.options].find(o => teks && o.value);
    sel.value = teks && opsi ? opsi.value : '';
    sel.dispatchEvent(new Event('change'));
}

// Panel peringatan: kritis (merah) selalu di atas, perhatian (kuning) di bawahnya; tiap baris ikon + judul + keterangan
function tampilPeringatan(daftar) {
    const panel = document.getElementById('panelPeringatan');
    if (!daftar.length) { panel.classList.add('hidden'); panel.innerHTML = ''; return; }
    const kritis = daftar.filter(p => p.tingkat === 'kritis');
    const perhatian = daftar.filter(p => p.tingkat !== 'kritis');
    const baris = (p, merah) => `
        <div class="flex items-start gap-3 px-5 py-3">
            <span class="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${merah ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-700'}">
                <i class="fa-solid ${p.ikon}"></i></span>
            <div class="flex-1 min-w-0">
                <p class="font-semibold ${merah ? 'text-red-800' : 'text-amber-900'}">${escapeHtml(p.judul)}</p>
                <p class="text-xs ${merah ? 'text-red-700' : 'text-amber-800'} mt-0.5">${escapeHtml(p.isi)}</p>
            </div>
            ${p.aksi ? `<button type="button" class="btn-secondary btn-sm flex-shrink-0" data-on-click="contohInfo" data-arg="${escapeHtml(p.aksi)}">${escapeHtml(p.aksi)}</button>` : ''}
        </div>`;
    panel.className = `rounded-xl border overflow-hidden shadow-sm ${kritis.length ? 'border-red-300' : 'border-amber-300'}`;
    panel.innerHTML =
        (kritis.length ? `<div class="bg-red-600 text-white px-5 py-2.5 flex items-center gap-2">
                <i class="fa-solid fa-triangle-exclamation"></i><span class="font-bold tracking-wide">PERINGATAN BLACKLIST</span>
                <span class="text-xs text-red-100 ml-1">Truk tetap bisa dicatat masuk; setiap deteksi tercatat di Log Validasi Blacklist.</span></div>
            <div class="bg-red-50 divide-y divide-red-100">${kritis.map(p => baris(p, true)).join('')}</div>` : '') +
        (perhatian.length ? `<div class="${kritis.length ? 'border-t border-amber-200' : ''} bg-amber-50">
                ${kritis.length ? '' : `<div class="px-5 pt-3 text-xs font-bold text-amber-800 tracking-wide uppercase"><i class="fa-solid fa-circle-exclamation mr-1"></i>Perlu perhatian</div>`}
                <div class="divide-y divide-amber-100">${perhatian.map(p => baris(p, false)).join('')}</div></div>` : '');
}

function tampilTerakhir(t) {
    document.getElementById('supirTerakhir').innerHTML = t ? `
        <div class="info-photo-box w-20 h-20"><i class="fa-solid fa-user text-slate-300 text-2xl"></i></div>
        <div class="min-w-0">
            <p class="font-semibold text-slate-900">${escapeHtml(t.nama)}</p>
            <p class="text-xs text-slate-500 font-mono">${escapeHtml(t.kode)}</p>
            <p class="text-xs text-slate-500 mt-1"><i class="fa-regular fa-clock mr-1"></i>Terakhir masuk ${escapeHtml(t.waktu)}</p>
            <p class="mt-2 text-xs font-semibold px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 inline-block"><i class="fa-solid fa-check mr-1"></i>Sama dengan supir yang discan</p>
        </div>` : '<p class="text-sm text-slate-400">Belum ada riwayat. Ketik plat terlebih dahulu.</p>';
}

function tampilSupir(s) {
    document.getElementById('badgeSupir').innerHTML = s && s.blacklist
        ? '<span class="badge-status bg-red-600 text-white"><i class="fa-solid fa-ban mr-1"></i>BLACKLIST</span>' : '';
    const sim = s ? (s.sim_habis ? '<span class="badge-status bg-red-100 text-red-700 ml-1">SIM habis</span>'
                   : s.sim_segera ? '<span class="badge-status bg-amber-100 text-amber-800 ml-1">SIM segera habis</span>'
                   : '<span class="badge-status bg-emerald-100 text-emerald-700 ml-1">SIM berlaku</span>') : '';
    const baris = (label, nilai) => `<div class="flex justify-between gap-3 text-sm"><span class="text-slate-500">${label}</span><span class="text-slate-900 text-right">${nilai}</span></div>`;
    document.getElementById('kartuSupir').innerHTML = s ? `
        <p class="font-bold text-slate-900">${escapeHtml(s.nama)} <span class="text-xs font-mono font-normal text-slate-500">${escapeHtml(s.kode)}</span></p>
        <div class="mt-2 space-y-1.5">
            ${baris('ID Personel', `<span class="font-mono">${escapeHtml(s.id)}</span>`)}
            ${baris('NIK', `<span class="font-mono">${escapeHtml(s.nik)}</span>`)}
            ${baris('SIM', escapeHtml(s.sim))}
            ${baris('Berlaku sampai', `${escapeHtml(s.sim_berlaku)}${sim}`)}
        </div>` : '<p class="text-sm text-slate-400">Belum ada supir. Nyalakan kamera lalu Scan Wajah.</p>';
}

function contohKamera() { Notif.info('Pratinjau: kamera menyala di sini, wajah supir diarahkan ke bingkai oval.'); }
function contohScanWajah() { contohPos('normal'); Notif.sukses('Pratinjau: wajah dikenali sebagai Wawan Setiawan (96%).'); }
function contohInfo(teks) { Notif.info(`Pratinjau: tombol "${teks}" akan berfungsi setelah tampilan disetujui.`); }

function contohSimpanPos() {
    const jam = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    Notif.sukses(`Pratinjau: ${document.getElementById('posPlat').value} tercatat MASUK pukul ${jam}. Data muncul di Logbook › Masih di Dalam.`);
}

function contohKeluarPos() {
    const jam = new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    Notif.sukses(`Pratinjau: ${document.getElementById('posPlat').value} tercatat KELUAR pukul ${jam} (3 jam 5 menit di dalam).`);
    contohPos('kosong');
}
