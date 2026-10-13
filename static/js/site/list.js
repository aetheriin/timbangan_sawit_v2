// ===== HALAMAN LIST: tiket aktif per tahap + history per produk 7 hari =====
// Tahap tiket = siapa yang harus memproses berikutnya: Timbangan, Sortasi / Lab (sesuai alur mill), Timbangan lagi.
// Tab Security = semua tiket aktif (truk yang masih di dalam) + posisinya. Lama di dalam ada di History.
// Tiket aktif dimuat ulang tiap 15 detik; tiket baru / yang pindah tahap disorot sebentar (Halaman.sorot).
// Pilihan tahap & produk history diingat per user (Pilihan di common.js).
let daftarTiket = [];
let tahapAktif = '';
let tiketSudahDimuat = false;
const jejakTiket = t => `${t.no_tiket}|${t.status_alur}`;

function tahapTiket(t) {
    if (t.status_alur === 'SECURITY_REGISTER') return ['timbangan'];
    if (t.status_alur === 'TIMBANG_1') {                     // menunggu inspeksi sesuai alur mill tiket
        const tahap = ['SORTASI', 'LAB'].filter(k => tiketPunyaTahap(t, k)).map(k => k.toLowerCase());
        return tahap.length ? tahap : ['timbangan'];
    }
    return ['timbangan'];                                    // TIMBANG_2: menunggu timbang kedua
}

const LABEL_TAHAP = { security: 'Security', timbangan: 'Timbangan', sortasi: 'Sortasi', lab: 'Laboratorium' };

document.addEventListener('DOMContentLoaded', () => {
    const chip = document.getElementById('chipTahap');
    const tersimpan = Pilihan.ambil('tahap');
    tahapAktif = tersimpan != null && chip.querySelector(`[data-tahap="${CSS.escape(tersimpan)}"]`) ? tersimpan : chip.dataset.awal || '';
    aktifkanChip(chip.querySelector(`[data-tahap="${CSS.escape(tahapAktif)}"]`));
    new Poller(muatTiketAktif, 15000).start();
    muatHistoryProduk();
});

async function muatTiketAktif() {
    const data = await ambilJson('/api/security/list-tiket-aktif', { polling: tiketSudahDimuat });
    const tbody = document.getElementById('tabelTicketAktif');
    if (data.error) { if (!tiketSudahDimuat) tbody.innerHTML = barisKosong(7, data.error); return; }
    // Muatan pertama: semua tiket dianggap sudah dikenal (tidak disorot walau tab tahap diganti)
    if (!tiketSudahDimuat) Halaman.kenali(tbody, data.map(jejakTiket));
    tiketSudahDimuat = true;
    daftarTiket = data;
    tampilkanTiket();
}

const angkaKg = v => v == null ? '–' : Number(v).toLocaleString('id-ID');
// Sel dua baris: teks utama + keterangan kecil di bawahnya
const duaBaris = (atas, bawah, mono = false) => `<span class="block ${mono ? 'font-mono font-semibold text-slate-900' : 'text-slate-800'} whitespace-nowrap">${atas}</span>
    <span class="block text-xs text-slate-500 truncate max-w-[14rem]">${bawah || '-'}</span>`;

function tampilkanTiket() {
    const baris = daftarTiket.filter(t => !tahapAktif || tahapAktif === 'security' || tahapTiket(t).includes(tahapAktif));
    document.getElementById('tabelTicketAktif').innerHTML = baris.map(t => {
        // Tab tujuan saat "Buka": tahap yang dipilih, atau tahap berikutnya tiket ini
        const tab = tahapAktif && tahapAktif !== 'security' ? tahapAktif : tahapTiket(t).slice(-1)[0];
        const menunggu = { SECURITY_REGISTER: 'Timbang 1', TIMBANG_2: 'Timbang 2' }[t.status_alur] || LABEL_TAHAP[tahapTiket(t)[0]];
        return `<tr class="hover:bg-slate-50" data-jejak="${escapeHtml(jejakTiket(t))}">
            <td class="table-cell">${duaBaris(escapeHtml(t.no_tiket), escapeHtml(t.created_at), true)}</td>
            <td class="table-cell">${duaBaris(escapeHtml(t.no_plat), escapeHtml(t.supir), true)}</td>
            <td class="table-cell">${duaBaris(`<span class="font-semibold">${escapeHtml(t.produk)}</span>`, escapeHtml(labelKode(t.jenis_transaksi)))}</td>
            <td class="table-cell">${duaBaris(escapeHtml(t.supplier), `<span class="font-mono">${escapeHtml(t.no_do || 'Tanpa DO')}</span>`)}</td>
            <td class="table-cell">${badgeStatusTiket(t.status_alur)}</td>
            <td class="table-cell text-xs font-semibold text-slate-600">${escapeHtml(menunggu)}</td>
            <td class="table-cell text-right whitespace-nowrap">
                <a class="aksi-ikon" title="Buka di form" href="/weighbridge?view=form&tab=${encodeURIComponent(tab)}&plat=${encodeURIComponent(t.no_plat)}"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>
                <a class="aksi-ikon" title="Cetak QR" href="/cetak/tiket/${encodeURIComponent(t.no_tiket)}" target="_blank"><i class="fa-solid fa-print"></i></a>
            </td>
        </tr>`;
    }).join('') || barisKosong(7, tahapAktif === 'security' ? 'Tidak ada truk di dalam'
        : tahapAktif ? `Tidak ada tiket yang menunggu ${LABEL_TAHAP[tahapAktif]}` : 'Belum ada tiket aktif');
    document.getElementById('infoJumlahTiket').innerHTML = `Menampilkan <b class="text-slate-900">${baris.length}</b> dari ${daftarTiket.length} tiket aktif`;
    saringTabel(document.getElementById('searchTiket').value);
}

function filterTahap(el) {
    aktifkanChip(el);
    tahapAktif = el.dataset.tahap;
    Pilihan.simpan('tahap', tahapAktif);
    tampilkanTiket();
}

async function muatHistoryProduk() {
    const idProduk = document.getElementById('filterProdukHistory').value;
    const data = await ambilJson(`/api/list/history-produk?id_produk=${encodeURIComponent(idProduk)}`);
    const tbody = document.getElementById('tabelHistoryProduk');
    if (data.error) { tbody.innerHTML = barisKosong(10, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell">${duaBaris(escapeHtml(r.no_tiket), escapeHtml(r.created_at), true)}</td>
            <td class="table-cell">${duaBaris(escapeHtml(r.no_plat), escapeHtml(r.supir), true)}</td>
            <td class="table-cell">${duaBaris(`<span class="font-semibold">${escapeHtml(r.produk)}</span>`, escapeHtml(labelKode(r.jenis_transaksi)))}</td>
            <td class="table-cell">${duaBaris(escapeHtml(r.supplier), `<span class="font-mono">${escapeHtml(r.no_do || 'Tanpa DO')}</span>`)}</td>
            <td class="table-cell text-right font-mono text-slate-600">${angkaKg(r.berat_bruto)}</td>
            <td class="table-cell text-right font-mono text-slate-600">${angkaKg(r.berat_tara)}</td>
            <td class="table-cell text-right font-mono font-bold text-blue-700">${angkaKg(r.berat_netto)}</td>
            <td class="table-cell whitespace-nowrap text-xs">${labelLama(r.lama_menit)}</td>
            <td class="table-cell">${badgeStatusTiket(r.status_alur)}</td>
            <td class="table-cell text-right whitespace-nowrap">
                <a class="aksi-ikon" title="Cetak tiket" href="/cetak/tiket/${encodeURIComponent(r.no_tiket)}" target="_blank"><i class="fa-solid fa-print"></i></a>
            </td>
        </tr>`).join('') || barisKosong(10, 'Belum ada transaksi 7 hari terakhir');
    const total = data.reduce((a, r) => a + (Number(r.berat_netto) || 0), 0);
    document.getElementById('infoTotalNetto').innerHTML = `Total netto 7 hari: <b class="text-slate-900">${angkaKg(total)} kg</b>`;
    catatanBatas(tbody, data.length, 500, 10);
    saringTabel(document.getElementById('searchTiket').value);
}

// Cari: "bm1455" cocok dengan "BM 1455 JJ"
function saringTabel(kata) {
    const cari = kata.toUpperCase().replace(/\s+/g, '');
    ['tabelTicketAktif', 'tabelHistoryProduk'].forEach(id => {
        document.querySelectorAll(`#${id} tr`).forEach(tr => {
            if (tr.children.length < 2) return;
            tr.classList.toggle('hidden', !!cari && !tr.textContent.toUpperCase().replace(/\s+/g, '').includes(cari));
        });
        Halaman.segarkan(document.getElementById(id));
    });
}

// Lama truk di dalam (tiket dibuat s/d timbang terakhir); merah bila lebih dari 4 jam
function labelLama(menit) {
    if (menit == null) return '-';
    const jam = Math.floor(menit / 60);
    const teks = jam ? `${jam} jam ${menit % 60} mnt` : `${menit} mnt`;
    return jam >= 4 ? `<span class="text-red-600 font-semibold">${teks}</span>` : teks;
}
