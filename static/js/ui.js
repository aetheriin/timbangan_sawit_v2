// ===== NOTIFIKASI (toast) & DIALOG KONFIRMASI =====
// Pengganti alert() / confirm() bawaan browser. Markup ada di templates/partials/layout/notifikasi.html.

const Notif = {
    MAKS: 4,                                   // toast lama dibuang supaya tidak menumpuk di memori

    tampil(pesan, jenis = 'info', durasiMs) {
        const wadah = document.getElementById('notifWadah');
        if (!wadah || !pesan) return;
        const gaya = {
            sukses: ['notif-sukses', 'fa-circle-check'],
            gagal: ['notif-gagal', 'fa-circle-xmark'],
            peringatan: ['notif-peringatan', 'fa-triangle-exclamation'],
            info: ['notif-info', 'fa-circle-info'],
        }[jenis] || ['notif-info', 'fa-circle-info'];

        const el = document.createElement('div');
        el.className = `notif ${gaya[0]}`;
        el.setAttribute('role', jenis === 'gagal' ? 'alert' : 'status');
        el.innerHTML = `<i class="fa-solid ${gaya[1]} mt-0.5"></i>
            <p class="flex-1">${escapeHtml(pesan)}</p>
            <button type="button" class="notif-tutup" aria-label="Tutup"><i class="fa-solid fa-xmark"></i></button>`;
        const hapus = () => { clearTimeout(el._timer); el.remove(); };
        el.querySelector('.notif-tutup').addEventListener('click', hapus, { once: true });
        el._timer = setTimeout(hapus, durasiMs || (jenis === 'gagal' ? 7000 : 4000));

        wadah.appendChild(el);
        while (wadah.children.length > this.MAKS) {
            clearTimeout(wadah.firstElementChild._timer);
            wadah.firstElementChild.remove();
        }
    },

    sukses(pesan) { this.tampil(pesan, 'sukses'); },
    gagal(pesan) { this.tampil(pesan, 'gagal'); },
    peringatan(pesan) { this.tampil(pesan, 'peringatan'); },
    info(pesan) { this.tampil(pesan, 'info'); },
};

// Tampilkan hasil API: { message } -> sukses, { error } -> gagal. Kembalikan true bila sukses.
function tampilkanHasil(data, pesanSukses) {
    if (!data || data.error) {
        Notif.gagal((data && data.error) || 'Terjadi kesalahan');
        return false;
    }
    Notif.sukses(data.message || pesanSukses || 'Berhasil');
    return true;
}

const Dialog = {
    _selesai: null,

    // await Dialog.konfirmasi({ judul, pesan, teksYa, bahaya }) -> true / false
    konfirmasi({ judul = 'Konfirmasi', pesan = '', teksYa = 'Ya, lanjutkan', teksBatal = 'Batal', bahaya = false } = {}) {
        if (this._selesai) this._selesai(false);          // dialog lama dianggap batal
        document.getElementById('dialogJudul').textContent = judul;
        document.getElementById('dialogPesan').textContent = pesan;
        const ya = document.getElementById('dialogYa');
        ya.textContent = teksYa;
        ya.className = bahaya ? 'btn-danger flex-1' : 'btn-primary flex-1';
        document.getElementById('dialogBatal').textContent = teksBatal;
        openModal('dialogKonfirmasi');
        ya.focus();
        return new Promise(resolve => { this._selesai = resolve; });
    },

    jawab(nilai) {
        closeModal('dialogKonfirmasi');
        const selesai = this._selesai;
        this._selesai = null;
        if (selesai) selesai(nilai);
    },
};

document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && Dialog._selesai) Dialog.jawab(false);
});

// Tombol sibuk: nonaktif + teks proses, mencegah klik ganda selama request berjalan
function setBusy(btn, sibuk, teksProses = 'Memproses...') {
    if (!btn) return;
    if (sibuk) {
        if (btn.dataset.teksAsli === undefined) btn.dataset.teksAsli = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i>${escapeHtml(teksProses)}`;
    } else {
        if (btn.dataset.teksAsli !== undefined) btn.innerHTML = btn.dataset.teksAsli;
        delete btn.dataset.teksAsli;
        btn.disabled = false;
    }
}

// Jalankan aksi async dengan tombol sibuk
async function denganTombol(btn, aksi, teksProses) {
    setBusy(btn, true, teksProses);
    try {
        return await aksi();
    } finally {
        setBusy(btn, false);
    }
}
