// ===== AKSES API: fetch dengan timeout, pesan error yang ramah, deteksi sesi habis =====
// Semua pemanggilan server memakai Api / ambilJson / kirimForm, tidak memanggil fetch langsung.

const TIMEOUT_DEFAULT_MS = 15000;
const TIMEOUT_WAJAH_MS = 60000;           // proses face recognition lebih lama

const PESAN_STATUS = {
    400: 'Data yang dikirim belum lengkap / tidak valid.',
    401: 'Sesi Anda berakhir. Silakan login ulang.',
    403: 'Anda tidak punya akses untuk tindakan ini.',
    404: 'Data tidak ditemukan.',
    409: 'Data bentrok dengan data lain.',
    413: 'Ukuran file terlalu besar.',
    500: 'Terjadi kesalahan di server. Coba lagi atau hubungi admin.',
    503: 'Server sedang sibuk. Coba beberapa saat lagi.',
};

const Api = {
    // Hasil selalu { ok, status, data, error }; tidak pernah melempar exception
    async request(url, { method = 'GET', body = null, timeout = TIMEOUT_DEFAULT_MS } = {}) {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), timeout);
        try {
            const res = await fetch(url, {
                method, body, signal: ctrl.signal, credentials: 'same-origin',
                headers: { 'Accept': 'application/json', 'X-Requested-With': 'fetch' },
            });
            if (res.redirected && new URL(res.url).pathname === '/login') {
                return { ok: false, status: 401, data: null, error: PESAN_STATUS[401] };
            }
            const jenis = res.headers.get('content-type') || '';
            const data = jenis.includes('application/json') ? await res.json() : null;
            if (!res.ok || (data && data.error)) {
                return { ok: false, status: res.status, data,
                         error: (data && data.error) || PESAN_STATUS[res.status] || `Permintaan gagal (${res.status}).` };
            }
            return { ok: true, status: res.status, data, error: null };
        } catch (err) {
            return { ok: false, status: 0, data: null,
                     error: err.name === 'AbortError' ? 'Server tidak merespons (timeout). Coba lagi.'
                                                      : 'Tidak dapat terhubung ke server. Periksa jaringan.' };
        } finally {
            clearTimeout(timer);
        }
    },

    get(url, opsi = {}) {
        return this.request(url, opsi);
    },

    post(url, data = {}, opsi = {}) {
        return this.request(url, { ...opsi, method: 'POST', body: keFormData(data) });
    },
};

function keFormData(data) {
    if (data instanceof FormData) return data;
    const formData = new FormData();
    Object.entries(data || {}).forEach(([k, v]) => formData.append(k, v ?? ''));
    return formData;
}

// Bentuk lama yang dipakai kode tab: data JSON, atau { ..., error } bila gagal
async function ambilJson(url, opsi) {
    const r = await Api.get(url, opsi);
    return r.ok ? r.data : { ...(r.data || {}), error: r.error };
}

async function kirimForm(url, data, opsi) {
    const r = await Api.post(url, data, opsi);
    return r.ok ? r.data : { ...(r.data || {}), error: r.error };
}

// ===== POLLING BERURUTAN =====
// Request berikutnya baru dikirim setelah yang sebelumnya selesai (tidak menumpuk saat server lambat),
// dan berhenti sementara saat tab browser tidak terlihat / kondisi aktif() salah.
class Poller {
    constructor(fn, intervalMs, { aktif = () => true, maksDurasiMs = 0, onHabis = null } = {}) {
        this.fn = fn;
        this.interval = intervalMs;
        this.aktif = aktif;
        this.maksDurasi = maksDurasiMs;
        this.onHabis = onHabis;
        this.jalan = false;
        this.timer = null;
    }

    start() {
        if (this.jalan) return;
        this.jalan = true;
        this.mulai = Date.now();
        this._putar();
    }

    stop() {
        this.jalan = false;
        clearTimeout(this.timer);
        this.timer = null;
    }

    async _putar() {
        if (!this.jalan) return;
        if (this.maksDurasi && Date.now() - this.mulai > this.maksDurasi) {
            this.stop();
            if (this.onHabis) this.onHabis();
            return;
        }
        if (!document.hidden && this.aktif()) {
            try { await this.fn(); } catch (err) { /* satu kegagalan tidak menghentikan polling */ }
        }
        if (this.jalan) this.timer = setTimeout(() => this._putar(), this.interval);
    }
}
