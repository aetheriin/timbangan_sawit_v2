// ===== DASHBOARD =====
// Empat ukuran harga (satuan berbeda) -> satu kartu & satu grafik area per ukuran, warna per ukuran.
// Di bawahnya arus penimbangan hari ini, status jembatan timbang, distribusi muatan; tabel riwayat harga paling bawah.
const UKURAN = [
    { kunci: 'harga_cpo', judul: 'Harga CPO', satuan: 'Rp/kg', desimal: 0, warna: '#2563eb', ket: 'vs penetapan sebelumnya' },
    { kunci: 'harga_kernel', judul: 'Harga Kernel', satuan: 'Rp/kg', desimal: 0, warna: '#4f46e5', ket: 'vs penetapan sebelumnya' },
    { kunci: 'oer_cpo', judul: 'OER CPO', satuan: 'Rendemen %', desimal: 2, warna: '#059669', ket: 'target ekstraksi pabrik' },
    { kunci: 'biaya_olah', judul: 'Biaya Olah', satuan: 'Rp/kg TBS', desimal: 0, warna: '#0284c7', ket: 'standar biaya proses mill' },
];
let hariDashboard = 30;
let dataHarga = [];

const pollingArus = new Poller(muatArus, 30000);
document.addEventListener('DOMContentLoaded', () => {
    const hariTersimpan = document.querySelector(`[data-hari="${Number(Pilihan.ambil('hari'))}"]`);
    if (hariTersimpan) { aktifkanChip(hariTersimpan); hariDashboard = Number(hariTersimpan.dataset.hari); }
    muatDashboard();
    pollingArus.start();
    if (location.hash === '#isi-harga' && document.getElementById('formHarga')) bukaIsiHarga();   // tombol Isi Harga di header
});

const angka = (v, d) => v == null ? '-' : Number(v).toLocaleString('id-ID', { minimumFractionDigits: d, maximumFractionDigits: d });
const tglPendek = s => new Date(`${s}T00:00:00`).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });

function filterHariDashboard(el) {
    aktifkanChip(el);
    hariDashboard = Number(el.dataset.hari);
    Pilihan.simpan('hari', hariDashboard);
    muatDashboard();
}

async function muatDashboard() {
    const data = await ambilJson(`/api/dashboard/harga?hari=${hariDashboard}`);
    const wadah = document.getElementById('kartuDashboard');
    if (data.error) { wadah.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(data.error)}</p>`; return false; }
    dataHarga = data;
    wadah.innerHTML = UKURAN.map(kartuUkuran).join('');
    UKURAN.forEach(u => pasangHover(u));
    tampilkanTabelHarga();
}

function kartuUkuran(u) {
    const titik = dataHarga.filter(r => r[u.kunci] != null);
    const akhir = titik[titik.length - 1], sebelum = titik[titik.length - 2];
    let ubah = '<span class="text-slate-400 font-mono">Belum ada pembanding</span>';
    if (akhir && sebelum) {
        const d = akhir[u.kunci] - sebelum[u.kunci];
        ubah = d > 0 ? `<span class="text-emerald-700 font-semibold font-mono"><i class="fa-solid fa-arrow-trend-up mr-1"></i>+${angka(d, u.desimal)}</span>`
             : d < 0 ? `<span class="text-red-600 font-semibold font-mono"><i class="fa-solid fa-arrow-trend-down mr-1"></i>${angka(d, u.desimal)}</span>`
             : '<span class="text-slate-400 font-mono">Stabil</span>';
    }
    const nilai = akhir ? angka(akhir[u.kunci], u.desimal) + (u.kunci === 'oer_cpo' ? '%' : '') : '-';
    return `<div class="stat-card hover:shadow-md transition-shadow">
        <div class="flex items-start justify-between gap-2">
            <div>
                <p class="text-sm font-medium text-slate-500">${u.judul} <span class="text-slate-400 font-normal">(${u.satuan})</span></p>
                <p class="text-3xl font-bold font-mono tracking-tight text-slate-900 mt-1 tabular-nums">${nilai}</p>
            </div>
            ${akhir ? `<span class="kpi-tanggal">${escapeHtml(tglPendek(akhir.tanggal))}</span>` : ''}
        </div>
        <p class="mt-3 flex items-center gap-2 text-xs">${ubah}<span class="text-slate-400">${u.ket}</span></p>
        <div class="relative mt-4 pt-3 border-t border-slate-100" id="grafik-${u.kunci}">${grafikGaris(titik, u)}
            <div data-tooltip class="hidden absolute pointer-events-none bg-slate-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap"></div>
        </div>
    </div>`;
}

// Grafik area SVG: garis 2px + isian gradasi, label tanggal awal / akhir, titik akhir diberi penanda
const G = { w: 280, h: 120, kiri: 4, kanan: 6, atas: 8, bawah: 18 };

function skala(titik, u) {
    const nilai = titik.map(r => r[u.kunci]);
    let min = Math.min(...nilai), max = Math.max(...nilai);
    if (min === max) { min -= 1; max += 1; }
    const pad = (max - min) * 0.1;
    min -= pad; max += pad;
    const lebar = G.w - G.kiri - G.kanan, tinggi = G.h - G.atas - G.bawah;
    return {
        x: i => G.kiri + (titik.length === 1 ? lebar / 2 : (i / (titik.length - 1)) * lebar),
        y: v => G.atas + (1 - (v - min) / (max - min)) * tinggi,
    };
}

function grafikGaris(titik, u) {
    if (!titik.length) return `<p class="text-xs text-slate-400 py-6 text-center">Belum ada data ${hariDashboard} hari terakhir</p>`;
    const s = skala(titik, u);
    const jalur = titik.map((r, i) => `${i ? 'L' : 'M'}${s.x(i).toFixed(1)},${s.y(r[u.kunci]).toFixed(1)}`).join(' ');
    const dasar = G.h - G.bawah;
    const area = `${jalur} L${s.x(titik.length - 1).toFixed(1)},${dasar} L${s.x(0).toFixed(1)},${dasar} Z`;
    const akhir = titik.length - 1;
    return `<svg viewBox="0 0 ${G.w} ${G.h}" class="w-full h-auto overflow-visible" role="img" aria-label="${u.judul} ${hariDashboard} hari">
        <defs><linearGradient id="gradasi-${u.kunci}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${u.warna}" stop-opacity="0.25"/><stop offset="100%" stop-color="${u.warna}" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="${area}" fill="url(#gradasi-${u.kunci})"/>
        <path d="${jalur}" fill="none" stroke="${u.warna}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${s.x(akhir)}" cy="${s.y(titik[akhir][u.kunci])}" r="4" fill="${u.warna}" stroke="#fff" stroke-width="2"/>
        <text x="${G.kiri}" y="${G.h - 3}" font-size="9" font-family="JetBrains Mono, monospace" fill="#94a3b8">${escapeHtml(tglPendek(titik[0].tanggal))}</text>
        <text x="${G.w - G.kanan}" y="${G.h - 3}" font-size="9" font-family="JetBrains Mono, monospace" fill="#94a3b8" text-anchor="end">${escapeHtml(tglPendek(titik[akhir].tanggal))}</text>
        <line data-silang x1="0" x2="0" y1="${G.atas}" y2="${dasar}" stroke="#94a3b8" stroke-width="1" visibility="hidden"/>
        <circle data-titik r="4" fill="${u.warna}" stroke="#fff" stroke-width="2" visibility="hidden"/>
        <rect data-area x="0" y="0" width="${G.w}" height="${G.h}" fill="transparent"/>
    </svg>`;
}

// Hover: garis silang + tooltip pada titik terdekat (target selebar grafik, bukan hanya garisnya)
function pasangHover(u) {
    const wadah = document.getElementById(`grafik-${u.kunci}`);
    const svg = wadah.querySelector('svg');
    if (!svg) return;
    const titik = dataHarga.filter(r => r[u.kunci] != null);
    const s = skala(titik, u);
    const silang = svg.querySelector('[data-silang]'), bulat = svg.querySelector('[data-titik]'), tip = wadah.querySelector('[data-tooltip]');
    svg.querySelector('[data-area]').addEventListener('mousemove', e => {
        const kotak = svg.getBoundingClientRect();
        const xSvg = (e.clientX - kotak.left) * G.w / kotak.width;
        let i = 0;
        titik.forEach((_, j) => { if (Math.abs(s.x(j) - xSvg) < Math.abs(s.x(i) - xSvg)) i = j; });
        const r = titik[i], x = s.x(i), y = s.y(r[u.kunci]);
        silang.setAttribute('x1', x); silang.setAttribute('x2', x); silang.setAttribute('visibility', 'visible');
        bulat.setAttribute('cx', x); bulat.setAttribute('cy', y); bulat.setAttribute('visibility', 'visible');
        tip.textContent = `${tglPendek(r.tanggal)} · ${angka(r[u.kunci], u.desimal)} ${u.satuan}`;
        tip.classList.remove('hidden');
        const px = x * kotak.width / G.w;
        tip.style.left = `${Math.min(Math.max(px - tip.offsetWidth / 2, 0), kotak.width - tip.offsetWidth)}px`;
        tip.style.top = `${y * kotak.height / G.h - 34}px`;
    });
    svg.querySelector('[data-area]').addEventListener('mouseleave', () => {
        silang.setAttribute('visibility', 'hidden'); bulat.setAttribute('visibility', 'hidden'); tip.classList.add('hidden');
    });
}

function tampilkanTabelHarga() {
    const tbody = document.getElementById('tabelHarga');
    const bolehUbah = tbody.dataset.bolehUbah === '1';
    tbody.innerHTML = [...dataHarga].reverse().map(r => `<tr class="hover:bg-slate-50">
        <td class="table-cell whitespace-nowrap">${escapeHtml(r.tanggal)}</td>
        ${UKURAN.map(u => `<td class="table-cell text-right">${angka(r[u.kunci], u.desimal)}</td>`).join('')}
        <td class="table-cell">${escapeHtml(r.oleh || '-')}</td>
        ${bolehUbah ? `<td class="table-cell text-right"><button type="button" class="link-aksi text-blue-600" data-on-click="bukaIsiHarga" data-arg="${escapeHtml(r.tanggal)}">Ubah</button></td>` : ''}
    </tr>`).join('') || barisKosong(bolehUbah ? 7 : 6, 'Belum ada data harga');
}

function bukaIsiHarga(tanggal) {
    const form = document.getElementById('formHarga');
    form.reset();
    const r = dataHarga.find(x => x.tanggal === tanggal);
    isiForm(form, r || { tanggal: new Date().toISOString().slice(0, 10) });
    openModal('modalHarga');
}

document.getElementById('formHarga')?.addEventListener('submit', e => {
    e.preventDefault();
    kirimFormAdmin(e.target, '/api/dashboard/harga/simpan', { modal: 'modalHarga', setelahnya: muatDashboard });
});

// ===== ARUS PENIMBANGAN HARI INI =====
const WARNA_DISTRIBUSI = ['bg-blue-600', 'bg-emerald-600', 'bg-indigo-600', 'bg-amber-500', 'bg-sky-500', 'bg-rose-500'];
const TIKET_FINAL = ['SELESAI', 'REJECTED', 'VOID'];

async function muatArus() {
    const r = await Api.get('/api/dashboard/arus', { polling: true });
    const d = r.data;
    if (!d || d.error) return;
    const s = d.ringkas;
    const stat = (label, nilai, satuan) => `<div class="mini-stat"><p class="mini-stat-label">${label}</p>
        <p class="mini-stat-nilai">${nilai} <span class="text-xs font-sans font-normal text-slate-500">${satuan}</span></p></div>`;
    document.getElementById('arusRingkas').innerHTML =
        stat('TBS diterima hari ini', angka((s.tbs_kg || 0) / 1000, 1), 'ton') +
        stat('Truk masuk / selesai', `${angka(s.masuk || 0, 0)} / ${angka(s.selesai || 0, 0)}`, 'truk') +
        stat('Truk di dalam', angka(s.di_dalam || 0, 0), 'truk') +
        stat('Rata-rata siklus', s.siklus_menit != null ? angka(s.siklus_menit, 0) : '-', 'menit');

    document.getElementById('tabelTerkini').innerHTML = d.terkini.map(t => {
        const selesai = TIKET_FINAL.includes(t.status_alur);
        return `<tr class="hover:bg-slate-50" data-jejak="${escapeHtml(`${t.no_tiket}|${t.status_alur}`)}">
            <td class="table-cell font-mono font-semibold text-slate-900 whitespace-nowrap">${escapeHtml(t.no_tiket)}</td>
            <td class="table-cell font-mono whitespace-nowrap">${escapeHtml(t.no_plat)}</td>
            <td class="table-cell font-semibold text-slate-700">${escapeHtml(t.produk)}</td>
            <td class="table-cell text-slate-600 max-w-[12rem] truncate">${escapeHtml(t.customer)}</td>
            <td class="table-cell text-right font-mono font-bold whitespace-nowrap">${t.netto != null ? `${angka(t.netto, 0)} kg` : '–'}</td>
            <td class="table-cell">${badgeStatusTiket(t.status_alur)}</td>
            <td class="table-cell text-right whitespace-nowrap">${selesai
                ? `<a class="link-aksi text-blue-600" href="/cetak/tiket/${encodeURIComponent(t.no_tiket)}" target="_blank">Lihat Slip</a>`
                : `<a class="link-aksi text-blue-600" href="/weighbridge?view=form&plat=${encodeURIComponent(t.no_plat)}">Buka</a>`}</td>
        </tr>`;
    }).join('') || barisKosong(7, 'Belum ada tiket');

    const jembatan = [...d.jembatan].sort((a, b) => a.terhubung - b.terhubung || a.area.localeCompare(b.area) || a.kode.localeCompare(b.kode));
    const online = jembatan.filter(j => j.terhubung).length;
    document.getElementById('ringkasJembatan').innerHTML = jembatan.length
        ? `<span class="${online === jembatan.length ? 'text-emerald-600' : 'text-red-600'}">${online}/${jembatan.length}</span> terhubung` : '';
    document.getElementById('statusJembatan').innerHTML = jembatan.map(j => `
        <div class="flex items-center gap-3 py-2.5">
            <span class="w-2 h-2 rounded-full flex-shrink-0 ${j.terhubung ? (j.stabil ? 'bg-emerald-500' : 'bg-amber-400') : 'bg-red-500'}"></span>
            <div class="min-w-0 flex-1">
                <p class="text-sm font-semibold text-slate-800 truncate">${escapeHtml(j.kode)} · ${escapeHtml(j.nama)}</p>
                <p class="text-[11px] text-slate-400 truncate">${escapeHtml(j.area)}${j.terhubung ? '' : ` · ${escapeHtml(j.error || 'tidak mengirim data')}`}</p>
            </div>
            <span class="font-mono text-xs font-semibold whitespace-nowrap ${j.terhubung ? 'text-slate-800' : 'text-red-600'}">${j.terhubung ? `${angka(j.berat || 0, 0)} kg` : 'TERPUTUS'}</span>
        </div>`).join('') || '<p class="text-sm text-slate-400 py-2">Belum ada jembatan timbang aktif</p>';

    const total = d.distribusi.reduce((a, x) => a + (x.netto || 0), 0);
    document.getElementById('distribusiMuatan').innerHTML = d.distribusi.map((x, i) => {
        const persen = total ? (x.netto / total) * 100 : 0;
        return `<div>
            <div class="flex items-center justify-between text-sm text-slate-600 mb-1">
                <span class="font-medium">${escapeHtml(x.produk)} <span class="text-xs text-slate-400 font-mono">${angka(x.netto / 1000, 1)} ton</span></span>
                <span class="font-mono font-bold text-slate-900">${angka(persen, 1)}%</span>
            </div>
            <div class="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                <div class="h-full ${WARNA_DISTRIBUSI[i % WARNA_DISTRIBUSI.length]} rounded-full" style="width:${persen.toFixed(1)}%"></div>
            </div></div>`;
    }).join('') || '<p class="text-sm text-slate-400">Belum ada muatan selesai hari ini</p>';
}
