// ===== LOGBOOK KENDARAAN: masih di dalam (semua) & sudah keluar (per tanggal), dari /api/pos/logbook =====
// Kunjungan Pos Security & tiket timbang biasa sama-sama tercatat di transaksi (jam masuk = dibuat, jam keluar = waktu_keluar).
const LB = document.getElementById('logbook');
const BATAS_MENIT = Number(LB.dataset.batasJam || 4) * 60;
const bolehKeluar = LB.dataset.bolehKeluar === '1';

let dataDalam = [], dataKeluar = [], masukHariIni = 0, tanggalLb = '';

const keDate = s => new Date(s.replace(' ', 'T'));
const hariIni = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
const jamMenit = d => d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
const jamMasuk = d => d.toDateString() === new Date().toDateString() ? jamMenit(d)
    : `${d.toLocaleDateString('id-ID', { day: '2-digit', month: '2-digit' })} ${jamMenit(d)}`;
const durasi = menit => { const j = Math.floor(menit / 60); return j ? `${j} jam ${menit % 60} mnt` : `${menit} mnt`; };
const lamaMenit = (dari, sampai = new Date()) => Math.max(0, Math.round((sampai - dari) / 60000));

document.addEventListener('DOMContentLoaded', () => {
    const tgl = document.getElementById('lbTanggal');
    tgl.value = hariIni();
    tgl.addEventListener('change', muatLogbook);
    muatLogbook();
    setInterval(muatLogbook, 60000);              // lama di dalam ikut bertambah, data petugas lain ikut masuk
});

async function muatLogbook() {
    const d = await ambilJson(`/api/pos/logbook?tanggal=${encodeURIComponent(document.getElementById('lbTanggal').value || hariIni())}`);
    if (d.error) { Notif.gagal(d.error); return; }
    const ubah = r => ({ ...r, plat: r.no_plat, kode: r.kode_personel || formatIdPersonel(r.id_driver), angkut: r.pengangkutan || 'Kendaraan pengirim',
                         masuk: keDate(r.waktu_masuk), keluar: r.waktu_keluar ? keDate(r.waktu_keluar) : null,
                         petugas: r.petugas_masuk || '-', petugas_keluar: r.petugas_keluar || '-' });
    dataDalam = d.dalam.map(ubah);
    dataKeluar = d.keluar.map(ubah);
    masukHariIni = d.masuk_hari_ini;
    tanggalLb = d.tanggal;
    tampilLogbook();
}

function tampilLogbook() {
    const lama = r => lamaMenit(r.masuk);
    const warnaLama = m => m > BATAS_MENIT ? 'bg-red-100 text-red-700' : m >= BATAS_MENIT * 0.75 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-50 text-emerald-700';
    const kolomSupir = r => `${escapeHtml(r.supir)}<span class="block text-[11px] text-slate-400 font-mono">${escapeHtml(r.kode)}</span>`;
    const urutDalam = [...dataDalam].sort((a, b) => a.masuk - b.masuk);
    document.getElementById('tabelDalam').innerHTML = urutDalam.map(r => {
        const m = lama(r);
        return `<tr class="hover:bg-slate-50${m > BATAS_MENIT ? ' bg-red-50/40' : ''}" data-cari="${escapeHtml(`${r.plat} ${r.supir} ${r.customer}`.toUpperCase())}">
            <td class="table-cell font-mono font-semibold whitespace-nowrap">${escapeHtml(r.plat)}</td>
            <td class="table-cell">${kolomSupir(r)}</td>
            <td class="table-cell">${escapeHtml(r.customer)}</td>
            <td class="table-cell">${escapeHtml(r.produk)}${r.pos ? '' : ' <span class="badge-status bg-blue-50 text-blue-700">Tiket</span>'}</td>
            <td class="table-cell text-slate-600">${escapeHtml(r.angkut)}</td>
            <td class="table-cell font-mono whitespace-nowrap">${jamMasuk(r.masuk)}</td>
            <td class="table-cell"><span class="badge-status ${warnaLama(m)}">${m > BATAS_MENIT ? '<i class="fa-solid fa-triangle-exclamation mr-1"></i>' : ''}${durasi(m)}</span></td>
            <td class="table-cell text-slate-600">${escapeHtml(r.petugas)}</td>
            <td class="table-cell text-right">${bolehKeluar
                ? `<button type="button" class="btn-secondary btn-sm text-amber-700" data-on-click="catatKeluar" data-arg="${escapeHtml(r.no_tiket)}"><i class="fa-solid fa-right-from-bracket"></i> Catat Keluar</button>` : ''}</td>
        </tr>`;
    }).join('') || barisKosong(9, 'Tidak ada truk di dalam');
    const urutKeluar = [...dataKeluar].sort((a, b) => b.keluar - a.keluar);
    document.getElementById('tabelKeluar').innerHTML = urutKeluar.map(r => `
        <tr class="hover:bg-slate-50" data-cari="${escapeHtml(`${r.plat} ${r.supir} ${r.customer}`.toUpperCase())}">
            <td class="table-cell font-mono font-semibold whitespace-nowrap">${escapeHtml(r.plat)}</td>
            <td class="table-cell">${kolomSupir(r)}</td>
            <td class="table-cell">${escapeHtml(r.customer)}</td>
            <td class="table-cell">${escapeHtml(r.produk)}${r.pos ? '' : ' <span class="badge-status bg-blue-50 text-blue-700">Tiket</span>'}</td>
            <td class="table-cell text-slate-600">${escapeHtml(r.angkut)}</td>
            <td class="table-cell font-mono whitespace-nowrap">${jamMasuk(r.masuk)}</td>
            <td class="table-cell font-mono whitespace-nowrap">${jamMenit(r.keluar)}</td>
            <td class="table-cell">${durasi(lamaMenit(r.masuk, r.keluar))}</td>
            <td class="table-cell text-slate-600 text-xs">${escapeHtml(r.petugas)}<span class="text-slate-400"> / </span>${escapeHtml(r.petugas_keluar)}</td>
        </tr>`).join('') || barisKosong(9, tanggalLb === hariIni() ? 'Belum ada truk keluar hari ini' : 'Tidak ada truk keluar pada tanggal ini');

    document.getElementById('jmlDalam').textContent = `${dataDalam.length} truk`;
    document.getElementById('jmlKeluar').textContent = `${dataKeluar.length} truk`;
    const rata = dataKeluar.length ? Math.round(dataKeluar.reduce((a, r) => a + lamaMenit(r.masuk, r.keluar), 0) / dataKeluar.length) : null;
    const lewat = dataDalam.filter(r => lama(r) > BATAS_MENIT).length;
    const stat = (label, nilai, satuan, catatan = '') => `<div class="mini-stat"><p class="mini-stat-label">${label}</p>
        <p class="mini-stat-nilai">${nilai} <span class="text-xs font-sans font-normal text-slate-500">${satuan}</span></p>${catatan}</div>`;
    document.getElementById('ringkasLogbook').innerHTML =
        stat('Masih di dalam', dataDalam.length, 'truk', lewat ? `<p class="text-[11px] text-red-600 mt-1"><i class="fa-solid fa-triangle-exclamation mr-1"></i>${lewat} lewat batas</p>` : '') +
        stat(tanggalLb === hariIni() ? 'Masuk hari ini' : 'Masuk tanggal ini', masukHariIni, 'truk') +
        stat(tanggalLb === hariIni() ? 'Keluar hari ini' : 'Keluar tanggal ini', dataKeluar.length, 'truk') +
        stat('Rata-rata di dalam', rata == null ? '-' : durasi(rata), '');
    cariLogbook(document.getElementById('lbCari').value);
}

function cariLogbook(teks) {
    const cari = (teks || '').toUpperCase().replace(/\s+/g, '');
    ['tabelDalam', 'tabelKeluar'].forEach(id => {
        document.querySelectorAll(`#${id} tr[data-cari]`).forEach(tr => {
            tr.classList.toggle('hidden', !!cari && !tr.dataset.cari.replace(/\s+/g, '').includes(cari));
        });
        if (typeof Halaman !== 'undefined') Halaman.segarkan(document.getElementById(id));
    });
}

async function catatKeluar(noTiket) {
    const r = dataDalam.find(x => x.no_tiket === noTiket);
    if (!r) return;
    const ok = await Dialog.konfirmasi({ judul: `Catat ${r.plat} keluar?`, teksYa: 'Catat Keluar',
        pesan: `${r.supir} · ${r.customer}\nMasuk ${jamMasuk(r.masuk)}, sudah ${durasi(lamaMenit(r.masuk))} di dalam.` });
    if (!ok) return;
    const d = await kirimForm('/api/pos/keluar', { no_tiket: noTiket });
    if (d.error) { Notif.gagal(d.error); return; }
    Notif.sukses(d.message);
    muatLogbook();
}

// ===== Cetak serah terima shift: halaman A4 berisi truk masih di dalam + ringkasan + tanda tangan =====
function cetakSerahTerima() {
    const sekarang = new Date();
    const baris = [...dataDalam].sort((a, b) => a.masuk - b.masuk).map((r, i) => `<tr><td>${i + 1}</td><td><b>${escapeHtml(r.plat)}</b></td>
        <td>${escapeHtml(r.supir)}</td><td>${escapeHtml(r.customer)}</td><td>${escapeHtml(r.produk)}</td>
        <td>${jamMasuk(r.masuk)}</td><td>${durasi(lamaMenit(r.masuk))}</td><td></td></tr>`).join('')
        || '<tr><td colspan="8" style="text-align:center;color:#64748b">Tidak ada truk di dalam</td></tr>';
    const w = window.open('', '_blank');
    if (!w) { Notif.peringatan('Izinkan pop-up untuk mencetak serah terima.'); return; }
    w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Serah Terima Shift Security</title><style>
        body{font-family:Arial,sans-serif;font-size:12px;color:#0f172a;margin:24px} h1{font-size:18px;margin:0}
        .sub{color:#475569;margin:4px 0 16px} table{width:100%;border-collapse:collapse;margin-top:8px}
        th,td{border:1px solid #cbd5e1;padding:6px 8px;text-align:left} th{background:#f1f5f9}
        .ringkas{display:flex;gap:12px;margin:12px 0} .ringkas div{border:1px solid #cbd5e1;border-radius:6px;padding:8px 12px;flex:1}
        .ringkas b{display:block;font-size:16px} .ttd{display:flex;justify-content:space-between;margin-top:48px}
        .ttd div{width:40%;text-align:center} .garis{margin-top:64px;border-top:1px solid #0f172a;padding-top:4px}
        @page{size:A4;margin:14mm}</style></head><body>
        <h1>Serah Terima Shift Security</h1>
        <p class="sub">${escapeHtml(document.title.replace(' · CPOS', ''))} · Dicetak ${sekarang.toLocaleString('id-ID')}</p>
        <div class="ringkas"><div>Masih di dalam<b>${dataDalam.length} truk</b></div><div>Masuk ${escapeHtml(tanggalLb)}<b>${masukHariIni} truk</b></div>
            <div>Keluar ${escapeHtml(tanggalLb)}<b>${dataKeluar.length} truk</b></div></div>
        <p><b>Truk masih di dalam saat serah terima</b></p>
        <table><thead><tr><th>No</th><th>Plat</th><th>Supir</th><th>Customer / Supplier</th><th>Produk</th><th>Jam Masuk</th><th>Lama</th><th>Keterangan</th></tr></thead>
        <tbody>${baris}</tbody></table>
        <div class="ttd"><div>Petugas yang menyerahkan<div class="garis">Nama &amp; tanda tangan</div></div>
            <div>Petugas yang menerima<div class="garis">Nama &amp; tanda tangan</div></div></div>
        </body></html>`);
    w.document.close();
    w.focus();
    w.print();
}
