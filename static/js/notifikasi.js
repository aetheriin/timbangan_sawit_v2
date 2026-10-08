// ===== NOTIFIKASI (lonceng top bar) =====
// Diperbarui tiap 60 detik selama tab terlihat; tidak dihitung sebagai aktivitas sesi.
let notifData = [];

async function muatNotifikasi() {
    if (!document.getElementById('btnNotif')) return;
    const data = await ambilJson('/api/notifikasi', { polling: true });
    if (data.error) return;
    notifData = data.notifikasi;
    const jumlah = document.getElementById('notifJumlah');
    jumlah.textContent = data.belum_dibaca > 99 ? '99+' : data.belum_dibaca;
    jumlah.classList.toggle('hidden', !data.belum_dibaca);
    document.getElementById('notifDaftar').innerHTML = notifData.map(n => `
        <a href="${escapeHtml(n.tautan || '#')}" data-on-click="klikNotifikasi" data-arg="${n.id_notifikasi}"
           class="block px-4 py-2 hover:bg-slate-50${n.dibaca ? ' text-slate-400' : ''}">
            <p class="font-medium${n.dibaca ? '' : ' text-slate-800'}">${n.dibaca ? '' : '<span class="inline-block w-2 h-2 rounded-full bg-red-500 mr-1"></span>'}${escapeHtml(n.judul)}</p>
            ${n.isi ? `<p class="text-xs">${escapeHtml(n.isi)}</p>` : ''}
            <p class="text-[11px] text-slate-400">${escapeHtml(n.waktu)}${n.area ? ` · ${escapeHtml(n.area)}` : ''}</p>
        </a>`).join('') || '<p class="px-4 py-6 text-center text-slate-400">Belum ada notifikasi</p>';
}

function bukaNotifikasi() {
    document.getElementById('notifPanel').classList.toggle('hidden');
}

function klikNotifikasi(id) {
    kirimForm('/api/notifikasi/baca', { id_notifikasi: id });     // tautan tetap dibuka
}

async function bacaSemuaNotifikasi() {
    await kirimForm('/api/notifikasi/baca', {});
    muatNotifikasi();
}

document.addEventListener('click', e => {
    const panel = document.getElementById('notifPanel');
    if (panel && !panel.classList.contains('hidden') && !e.target.closest('#notifPanel, #btnNotif')) panel.classList.add('hidden');
});

if (document.getElementById('btnNotif')) {
    muatNotifikasi();
    setInterval(() => { if (!document.hidden) muatNotifikasi(); }, 60000);
}
