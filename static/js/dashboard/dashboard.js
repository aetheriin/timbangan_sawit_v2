// ===== DASHBOARD HARGA =====
// Empat ukuran dengan satuan berbeda -> satu kartu & satu grafik garis per ukuran (tidak digabung dua sumbu).
// Satu seri per grafik: warna tunggal, judul kartu menjadi namanya. Tabel di bawah = tampilan data lengkap.
const UKURAN = [
    { kunci: 'harga_cpo', judul: 'Harga CPO', satuan: 'Rp/kg', desimal: 0 },
    { kunci: 'harga_kernel', judul: 'Harga Kernel', satuan: 'Rp/kg', desimal: 0 },
    { kunci: 'oer_cpo', judul: 'OER CPO', satuan: '%', desimal: 2 },
    { kunci: 'biaya_olah', judul: 'Biaya Olah', satuan: 'Rp/kg TBS', desimal: 0 },
];
const WARNA_GARIS = '#2563eb';
let hariDashboard = 30;
let dataHarga = [];

document.addEventListener('DOMContentLoaded', muatDashboard);

const angka = (v, d) => v == null ? '-' : Number(v).toLocaleString('id-ID', { minimumFractionDigits: d, maximumFractionDigits: d });
const tglPendek = s => new Date(`${s}T00:00:00`).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });

function filterHariDashboard(el) {
    aktifkanChip(el);
    hariDashboard = Number(el.dataset.hari);
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
    let ubah = '<span class="text-slate-400">Belum ada pembanding</span>';
    if (akhir && sebelum) {
        const d = akhir[u.kunci] - sebelum[u.kunci];
        const arah = d > 0 ? '▲ naik' : d < 0 ? '▼ turun' : '● tetap';
        ubah = `<span class="text-slate-600">${arah} ${angka(Math.abs(d), u.desimal)} dari ${tglPendek(sebelum.tanggal)}</span>`;
    }
    return `<div class="stat-card">
        <div class="flex items-baseline justify-between gap-2">
            <p class="stat-label">${u.judul} <span class="text-slate-400">(${u.satuan})</span></p>
            <p class="text-xs text-slate-400">${akhir ? escapeHtml(tglPendek(akhir.tanggal)) : ''}</p>
        </div>
        <p class="text-3xl font-semibold text-slate-800 mt-1">${akhir ? angka(akhir[u.kunci], u.desimal) : '-'}</p>
        <p class="text-xs mt-1">${ubah}</p>
        <div class="relative mt-3" id="grafik-${u.kunci}">${grafikGaris(titik, u)}
            <div data-tooltip class="hidden absolute pointer-events-none bg-slate-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap"></div>
        </div>
    </div>`;
}

// Grafik garis SVG: garis 2px, grid & sumbu samar, label min / maks, titik akhir diberi penanda
const G = { w: 560, h: 150, kiri: 8, kanan: 8, atas: 10, bawah: 22 };

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
    if (!titik.length) return `<p class="text-xs text-slate-400 py-8 text-center">Belum ada data ${hariDashboard} hari terakhir</p>`;
    const s = skala(titik, u);
    const jalur = titik.map((r, i) => `${i ? 'L' : 'M'}${s.x(i).toFixed(1)},${s.y(r[u.kunci]).toFixed(1)}`).join(' ');
    const akhir = titik.length - 1;
    const grid = [0, 0.5, 1].map(f => { const y = G.atas + f * (G.h - G.atas - G.bawah);
        return `<line x1="${G.kiri}" x2="${G.w - G.kanan}" y1="${y}" y2="${y}" stroke="#e2e8f0" stroke-width="1"/>`; }).join('');
    return `<svg viewBox="0 0 ${G.w} ${G.h}" class="w-full h-auto" role="img" aria-label="${u.judul} ${hariDashboard} hari">
        ${grid}
        <path d="${jalur}" fill="none" stroke="${WARNA_GARIS}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <circle cx="${s.x(akhir)}" cy="${s.y(titik[akhir][u.kunci])}" r="4" fill="${WARNA_GARIS}" stroke="#fff" stroke-width="2"/>
        <text x="${G.kiri}" y="${G.h - 6}" font-size="11" fill="#64748b">${escapeHtml(tglPendek(titik[0].tanggal))}</text>
        <text x="${G.w - G.kanan}" y="${G.h - 6}" font-size="11" fill="#64748b" text-anchor="end">${escapeHtml(tglPendek(titik[akhir].tanggal))}</text>
        <line data-silang x1="0" x2="0" y1="${G.atas}" y2="${G.h - G.bawah}" stroke="#94a3b8" stroke-width="1" visibility="hidden"/>
        <circle data-titik r="5" fill="${WARNA_GARIS}" stroke="#fff" stroke-width="2" visibility="hidden"/>
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
