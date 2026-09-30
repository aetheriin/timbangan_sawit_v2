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

    // Frame asli (tidak dicerminkan) sebagai Blob JPEG
    ambilFrame(video, kualitas = 0.85) {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', kualitas));
    },

    async ambilBanyak(video, jumlah, jedaMs) {
        const frames = [];
        for (let i = 0; i < jumlah; i++) {
            frames.push(await this.ambilFrame(video));
            await new Promise(r => setTimeout(r, jedaMs));
        }
        return frames;
    },
};
