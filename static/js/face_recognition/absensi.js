// ===== TAB ABSENSI: scan wajah live + liveness, absensi hari ini, rekap, jadwal =====
const TANTANGAN_ABSEN = [
    ['KEDIP', 'KEDIPKAN MATA'],
    ['MENOLEH_KIRI', 'MENOLEH KE KIRI'],
    ['MENOLEH_KANAN', 'MENOLEH KE KANAN'],
];
const JUMLAH_FRAME_ABSEN = 10;
const JEDA_FRAME_MS = 200;

let absensiDimuat = false;
let kategoriAbsen = '';
let scanAbsenBerjalan = false;

window.addEventListener('tabChange', e => {
    if (e.detail !== 'absensi') {
        batalScanAbsen();
        return;
    }
    if (absensiDimuat) return;
    absensiDimuat = true;
    const hariIni = new Date();
    document.getElementById('absenTanggal').value = tanggalIso(hariIni);
    document.getElementById('rekapBulan').value = tanggalIso(hariIni).slice(0, 7);
    muatAbsensiHarian();
    muatRekapBulanan();
    muatJadwalKerja();
});

function tanggalIso(d) {
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// ===== SCAN =====
async function mulaiScanAbsen() {
    if (scanAbsenBerjalan) return;
    const video = document.getElementById('absenVideo');
    const status = document.getElementById('absenStatus');
    const label = document.getElementById('absenTantangan');
    const btn = document.getElementById('btnMulaiAbsen');

    scanAbsenBerjalan = true;
    btn.disabled = true;
    status.textContent = 'Menyalakan kamera...';
    try {
        await Kamera.mulai(video);
    } catch (err) {
        status.textContent = 'Kamera tidak bisa dibuka. Izinkan akses kamera di browser.';
        selesaiScanAbsen();
        return;
    }

    const [kode, teks] = TANTANGAN_ABSEN[Math.floor(Math.random() * TANTANGAN_ABSEN.length)];
    label.textContent = `Tantangan liveness: ${teks}`;
    status.textContent = 'Hadapkan wajah ke oval, lalu ikuti tantangan...';
    await new Promise(r => setTimeout(r, 1000));
    if (!scanAbsenBerjalan) return;

    const frames = await Kamera.ambilBanyak(video, JUMLAH_FRAME_ABSEN, JEDA_FRAME_MS);
    if (!scanAbsenBerjalan) return;
    status.textContent = 'Memproses...';

    const formData = new FormData();
    frames.forEach((blob, i) => formData.append('frames', blob, `frame${i}.jpg`));
    formData.append('tantangan', kode);
    formData.append('perangkat', 'Web');

    const data = await kirimForm('/api/absensi/scan', formData, { timeout: TIMEOUT_WAJAH_MS });
    frames.length = 0;                               // lepas frame dari memori
    tampilkanHasilAbsen(data);
    status.textContent = data.status === 'BERHASIL' ? 'Absensi tercatat.' : '';
    selesaiScanAbsen();
    if (data.status === 'BERHASIL') muatAbsensiHarian();
}

function selesaiScanAbsen() {
    scanAbsenBerjalan = false;
    Kamera.stop();
    document.getElementById('btnMulaiAbsen').disabled = false;
    document.getElementById('absenTantangan').textContent = 'Tekan "Mulai Scan Absen"';
}

function batalScanAbsen() {
    if (!scanAbsenBerjalan && !Kamera.aktif()) return;
    selesaiScanAbsen();
    document.getElementById('absenStatus').textContent = 'Scan dibatalkan.';
}

function keteranganWaktu(status, selisih, jenis) {
    if (status === 'TERLAMBAT') return badge(`TERLAMBAT ${selisih} menit`, WARNA_BADGE.oranye);
    if (status === 'PULANG_AWAL') return badge(`PULANG AWAL ${selisih} menit`, WARNA_BADGE.oranye);
    if (status === 'HARI_LIBUR') return badge('HARI LIBUR', WARNA_BADGE.abu);
    return badge(jenis === 'PULANG' ? 'Tepat waktu / lembur' : 'Tepat waktu', WARNA_BADGE.hijau);
}

function tampilkanHasilAbsen(d) {
    const box = document.getElementById('absenHasil');
    if (d.status !== 'BERHASIL') {
        const warna = d.status === 'DITOLAK_BLACKLIST' ? 'note-danger' : 'note-warning';
        box.innerHTML = `<div class="${warna}">${escapeHtml(d.error || 'Scan gagal')}</div>`;
        return;
    }
    const foto = d.foto_path || d.foto_scan;
    const jadwal = d.jadwal
        ? `${d.jadwal.jam_masuk} – ${d.jadwal.jam_pulang} (${d.jadwal.nama_hari}, tanpa toleransi)` : 'Hari libur';
    box.innerHTML = `
        <div class="flex items-center gap-4 mb-3">
            <div class="w-24 h-28 rounded-lg bg-slate-200 overflow-hidden flex-shrink-0">
                ${foto ? `<img src="/static/${escapeHtml(foto)}" class="w-full h-full object-cover" alt="">` : ''}
            </div>
            <div class="space-y-1.5">
                <p class="text-lg font-bold text-slate-800">${escapeHtml(d.nama_personel)}</p>
                <p class="text-xs font-medium text-slate-500">${escapeHtml(d.kode_personel || '-')} · ID ${formatIdPersonel(d.id_personel)} · ${escapeHtml((LABEL_KATEGORI[d.kategori] || [d.kategori])[0])}</p>
                <div class="flex gap-2">${badge(d.jenis, WARNA_BADGE.biru)} ${keteranganWaktu(d.status_waktu, d.selisih_menit, d.jenis)}</div>
            </div>
        </div>
        <dl class="divide-y divide-slate-100 text-sm">
            ${[['Waktu scan', d.waktu], [`Jadwal ${d.jenis === 'MASUK' ? 'masuk' : 'pulang'}`, jadwal],
               ['Jarak wajah', `${d.jarak_wajah} (ambang ≤ ${d.ambang})`], ['Liveness', `✓ Lolos (${d.tantangan})`]]
              .map(([k, v]) => `<div class="flex justify-between py-2"><dt class="text-slate-500">${k}</dt><dd class="font-semibold text-slate-800">${escapeHtml(v)}</dd></div>`).join('')}
        </dl>`;
}

// ===== ABSENSI HARI INI =====
function filterAbsensi(el) {
    aktifkanChip(el);
    kategoriAbsen = el.dataset.kategori;
    muatAbsensiHarian();
}

async function muatAbsensiHarian() {
    const tanggal = document.getElementById('absenTanggal').value;
    const data = await ambilJson(`/api/absensi/harian?tanggal=${tanggal}&kategori=${kategoriAbsen}`);
    const tbody = document.getElementById('tabelAbsensiHarian');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    tbody.innerHTML = data.map(r => {
        let ket = r.jam_masuk ? keteranganWaktu(r.status_masuk, r.selisih_masuk, 'MASUK') : badge('Belum absen', WARNA_BADGE.abu);
        if (r.status_pulang === 'PULANG_AWAL') ket += ' ' + keteranganWaktu(r.status_pulang, r.selisih_pulang, 'PULANG');
        return `<tr class="hover:bg-slate-50">
            <td class="table-cell">${r.kode_personel ? escapeHtml(r.kode_personel) : `<span class="text-amber-700 font-medium">ID ${formatIdPersonel(r.id_personel)}</span>`}</td>
            <td class="table-cell">${escapeHtml(r.nama_personel)}</td>
            <td class="table-cell">${badgeKategori(r.kategori)}</td>
            <td class="table-cell">${r.jam_masuk || '—'}</td>
            <td class="table-cell">${r.jam_pulang || '—'}</td>
            <td class="table-cell space-x-1">${ket}</td>
        </tr>`;
    }).join('') || barisKosong(6, 'Belum ada personel');
}

// ===== REKAP BULANAN =====
async function muatRekapBulanan() {
    const bulan = document.getElementById('rekapBulan').value;
    const data = await ambilJson(`/api/absensi/rekap?bulan=${bulan}`);
    const tbody = document.getElementById('tabelRekapAbsensi');
    if (data.error) { tbody.innerHTML = barisKosong(6, data.error); return; }
    tbody.innerHTML = data.map(r => `<tr class="hover:bg-slate-50">
            <td class="table-cell">${kodeAtauKosong(r.kode_personel)}</td>
            <td class="table-cell">${escapeHtml(r.nama_personel)}</td>
            <td class="table-cell">${badgeKategori(r.kategori)}</td>
            <td class="table-cell text-right">${r.hari_hadir}</td>
            <td class="table-cell text-right">${r.jml_terlambat}x${r.menit_terlambat ? ` (${r.menit_terlambat} menit)` : ''}</td>
            <td class="table-cell text-right">${r.jml_pulang_awal}x</td>
        </tr>`).join('') || barisKosong(6, 'Belum ada data');
}

// ===== JADWAL KERJA =====
async function muatJadwalKerja() {
    const data = await ambilJson('/api/jadwal-kerja');
    const tbody = document.getElementById('tabelJadwalKerja');
    if (data.error) { tbody.innerHTML = barisKosong(4, data.error); return; }
    tbody.innerHTML = data.map(j => `<tr>
            <td class="table-cell">${escapeHtml(j.nama_hari)}</td>
            <td class="table-cell">${j.is_libur ? '—' : j.jam_masuk}</td>
            <td class="table-cell">${j.is_libur ? '—' : j.jam_pulang}</td>
            <td class="table-cell">${j.is_libur ? badge('Libur', WARNA_BADGE.abu) : `Semua kategori · toleransi ${j.toleransi_menit} menit`}</td>
        </tr>`).join('');
}
