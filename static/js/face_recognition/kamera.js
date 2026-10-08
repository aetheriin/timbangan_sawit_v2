// ===== KAMERA BROWSER (dipakai Absensi & foto Personel) =====
const Kamera = {
    stream: null,

    async mulai(video) {
        this.stop();
        this.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        video.srcObject = this.stream;
        await new Promise(resolve => {
            if (video.readyState >= 2) resolve();
            else video.onloadeddata = () => resolve();
        });
    },

    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
    },

    aktif() {
        return !!this.stream;
    },

    // Frame asli (tidak dicerminkan) sebagai Blob JPEG, diperkecil ke lebar maks supaya upload & proses ringan
    ambilFrame(video, kualitas = 0.85, maksLebar = 640) {
        const skala = Math.min(1, maksLebar / video.videoWidth);
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(video.videoWidth * skala);
        canvas.height = Math.round(video.videoHeight * skala);
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
        return new Promise(resolve => canvas.toBlob(blob => { canvas.width = canvas.height = 0; resolve(blob); },
                                                    'image/jpeg', kualitas));
    },

    async ambilBanyak(video, jumlah, jedaMs, maksLebar = 480) {
        const frames = [];
        for (let i = 0; i < jumlah; i++) {
            frames.push(await this.ambilFrame(video, 0.8, maksLebar));
            await new Promise(r => setTimeout(r, jedaMs));
        }
        return frames;
    },
};

// ===== REKAM WAJAH + TANTANGAN (Security, Absensi, Tamu) =====
// Tantangan wajib / tidak diatur per area di Admin › Pengaturan Site (TANTANGAN_SECURITY / _ABSENSI / _TAMU).
const TANTANGAN_WAJAH = [['KEDIP', 'KEDIPKAN MATA'], ['MENOLEH_KIRI', 'MENOLEH KE KIRI'], ['MENOLEH_KANAN', 'MENOLEH KE KANAN']];
let _cacheTantangan = null;

async function aturanTantangan() {
    if (!_cacheTantangan || Date.now() - _cacheTantangan.waktu > 30000) {
        const d = await ambilJson('/api/tantangan-wajah');
        _cacheTantangan = { waktu: Date.now(), data: d.error ? { security: true, absensi: true, tamu: false } : d };
    }
    return _cacheTantangan.data;
}

// tampil(teks, angkaHitung | null) dipanggil untuk memberi instruksi; batal() -> true untuk berhenti.
// Kembalikan { frames, tantangan } atau null bila dibatalkan. Tanpa tantangan: cukup hadap kamera (5 frame).
async function rekamWajah(video, { wajib, tampil = () => {}, batal = () => false, hitungMundur = 3 } = {}) {
    const [kode, teks] = wajib ? TANTANGAN_WAJAH[Math.floor(Math.random() * TANTANGAN_WAJAH.length)] : ['TANPA', 'TETAP MENGHADAP KAMERA'];
    for (let i = hitungMundur; i > 0; i--) {
        tampil(wajib ? `Bersiap... setelah ini: ${teks}` : 'Hadapkan wajah lurus ke kamera...', i);
        await new Promise(r => setTimeout(r, 1000));
        if (batal()) return null;
    }
    tampil(wajib ? `Sekarang: ${teks}` : 'Tahan, foto sedang diambil...', null);
    const frames = await Kamera.ambilBanyak(video, wajib ? 15 : 5, wajib ? 200 : 150);
    return batal() ? null : { frames, tantangan: kode };
}

// Kecilkan foto upload (sisi terpanjang maks 1024 px, JPEG) sebelum dikirim ke server
async function kecilkanFoto(file, maksSisi = 1024, kualitas = 0.85) {
    if (!file || !file.type.startsWith('image/')) return file;
    let bitmap;
    try {
        bitmap = await createImageBitmap(file);
    } catch (err) {
        return file;                               // format tidak didukung browser: kirim apa adanya
    }
    const skala = Math.min(1, maksSisi / Math.max(bitmap.width, bitmap.height));
    if (skala === 1 && file.size < 500 * 1024) { bitmap.close(); return file; }
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * skala);
    canvas.height = Math.round(bitmap.height * skala);
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', kualitas));
    canvas.width = canvas.height = 0;              // lepas memori canvas
    return blob ? new File([blob], (file.name || 'foto').replace(/\.\w+$/, '') + '.jpg', { type: 'image/jpeg' }) : file;
}

// Kamera wajib mati saat halaman ditinggal / disembunyikan
window.addEventListener('pagehide', () => Kamera.stop());
