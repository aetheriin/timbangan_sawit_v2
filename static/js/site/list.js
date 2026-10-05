// ===== HALAMAN LIST: tiket aktif per tahap + history per produk 7 hari =====
// Tahap tiket = siapa yang harus memproses berikutnya. Security melihat tiket yang baru dibuat (sudah scan wajah),
// lalu tiket berlanjut ke Timbangan, Sortasi / Lab (sesuai alur mill), kembali ke Timbangan, lalu selesai.
let daftarTiket = [];
let tahapAktif = '';

function tahapTiket(t) {
    if (t.status_alur === 'SECURITY_REGISTER') return ['security', 'timbangan'];
    if (t.status_alur === 'TIMBANG_1') {                     // menunggu inspeksi sesuai alur mill tiket
        const tahap = ['SORTASI', 'LAB'].filter(k => tiketPunyaTahap(t, k)).map(k => k.toLowerCase());
        return tahap.length ? tahap : ['timbangan'];
    }
    return ['timbangan'];                                    // TIMBANG_2: menunggu timbang kedua
}

const LABEL_TAHAP = { security: 'Security', timbangan: 'Timbangan', sortasi: 'Sortasi', lab: 'Laboratorium' };

document.addEventListener('DOMContentLoaded', () => {
    tahapAktif = document.getElementById('chipTahap').dataset.awal || '';
    muatTiketAktif();
    muatHistoryProduk();
});

async function muatTiketAktif() {
    const data = await ambilJson('/api/security/list-tiket-aktif');
    const tbody = document.getElementById('tabelTicketAktif');
    if (data.error) { tbody.innerHTML = barisKosong(9, data.error); return; }
    daftarTiket = data;
    tampilkanTiket();
}

function tampilkanTiket() {
    const baris = daftarTiket.filter(t => !tahapAktif || tahapTiket(t).includes(tahapAktif));
    document.getElementById('tabelTicketAktif').innerHTML = baris.map(t => {
        // Tab tujuan saat "Buka": tahap yang dipilih, atau tahap berikutnya tiket ini
        const tab = tahapAktif || tahapTiket(t).slice(-1)[0];
        const menunggu = { SECURITY_REGISTER: 'Timbang 1', TIMBANG_2: 'Timbang 2' }[t.status_alur] || LABEL_TAHAP[tahapTiket(t)[0]];
        return `<tr class="hover:bg-slate-50">
            <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(t.created_at)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(t.no_tiket)}</td>
            <td class="table-cell">${escapeHtml(t.no_plat)}</td>
            <td class="table-cell">${escapeHtml(t.supplier)}</td>
            <td class="table-cell">${escapeHtml(t.produk)}</td>
            <td class="table-cell">${escapeHtml(labelKode(t.jenis_transaksi))}</td>
            <td class="table-cell">${badgeStatusTiket(t.status_alur)}</td>
            <td class="table-cell text-xs text-slate-600">${escapeHtml(menunggu)}</td>
            <td class="table-cell text-right whitespace-nowrap space-x-3">
                <a class="link-aksi text-blue-600" href="/weighbridge?view=form&tab=${encodeURIComponent(tab)}&plat=${encodeURIComponent(t.no_plat)}">Buka</a>
                <a class="link-aksi text-emerald-600" href="/cetak/tiket/${encodeURIComponent(t.no_tiket)}" target="_blank">Cetak QR</a>
            </td>
        </tr>`;
    }).join('') || barisKosong(9, tahapAktif ? `Tidak ada tiket yang menunggu ${LABEL_TAHAP[tahapAktif]}` : 'Belum ada tiket aktif');
    saringTabel(document.getElementById('searchTiket').value);
}

function filterTahap(el) {
    aktifkanChip(el);
    tahapAktif = el.dataset.tahap;
    tampilkanTiket();
}

async function muatHistoryProduk() {
    const idProduk = document.getElementById('filterProdukHistory').value;
    const data = await ambilJson(`/api/list/history-produk?id_produk=${encodeURIComponent(idProduk)}`);
    const tbody = document.getElementById('tabelHistoryProduk');
    if (data.error) { tbody.innerHTML = barisKosong(8, data.error); return; }
    tbody.innerHTML = data.map(r => `
        <tr class="hover:bg-slate-50">
            <td class="table-cell whitespace-nowrap text-xs">${escapeHtml(r.created_at)}</td>
            <td class="table-cell font-mono text-xs">${escapeHtml(r.no_tiket)}</td>
            <td class="table-cell">${escapeHtml(r.no_plat)}</td>
            <td class="table-cell">${escapeHtml(r.supplier)}</td>
            <td class="table-cell">${escapeHtml(r.produk)}</td>
            <td class="table-cell">${escapeHtml(labelKode(r.jenis_transaksi))}</td>
            <td class="table-cell text-right">${r.berat_netto != null ? Number(r.berat_netto).toLocaleString('id-ID') : '-'}</td>
            <td class="table-cell">${badgeStatusTiket(r.status_alur)}</td>
        </tr>`).join('') || barisKosong(8, 'Belum ada transaksi 7 hari terakhir');
    catatanBatas(tbody, data.length, 500, 8);
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
