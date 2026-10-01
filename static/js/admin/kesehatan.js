// ===== ADMIN > KESEHATAN SISTEM =====
document.addEventListener('DOMContentLoaded', muatKesehatan);

// status: 'ok' | 'peringatan' | 'gagal' -> warna & ikon kartu
const GAYA_STATUS = {
    ok: ['text-emerald-600', 'fa-circle-check'],
    peringatan: ['text-amber-600', 'fa-triangle-exclamation'],
    gagal: ['text-red-600', 'fa-circle-xmark'],
    info: ['text-slate-800', 'fa-circle-info'],
};

function kartu(judul, ikon, nilai, info, status = 'info') {
    const [warna, ikonStatus] = GAYA_STATUS[status];
    return `<div class="stat-card">
        <div class="flex items-center justify-between">
            <p class="stat-label"><i class="fa-solid ${ikon} mr-1"></i> ${escapeHtml(judul)}</p>
            <i class="fa-solid ${ikonStatus} ${warna}"></i>
        </div>
        <p class="stat-value ${warna}">${escapeHtml(nilai)}</p>
        <p class="text-xs text-slate-500 mt-1">${escapeHtml(info)}</p>
    </div>`;
}

function statusBackup(db) {
    if (db.backup_terakhir === 'tidak bisa dibaca') return ['Tidak terbaca', 'Akun aplikasi tidak punya akses msdb. Cek di SSMS.', 'peringatan'];
    if (!db.backup_terakhir) return ['Belum pernah', 'Jadwalkan backup harian sekarang.', 'gagal'];
    const umur = db.backup_umur_jam;
    return [db.backup_terakhir, `${db.backup_tipe} · ${umur} jam lalu`, umur > 26 ? 'peringatan' : 'ok'];
}

async function muatKesehatan() {
    const d = await ambilJson('/api/admin/kesehatan');
    const wadah = document.getElementById('kartuKesehatan');
    if (d.error) { wadah.innerHTML = `<p class="text-sm text-red-600">${escapeHtml(d.error)}</p>`; return; }
    const db = d.database;
    const [nilaiBackup, infoBackup, stBackup] = db.ok ? statusBackup(db) : ['-', 'Database tidak terhubung', 'gagal'];
    const disk = d.disk;
    wadah.innerHTML = [
        kartu('Database', 'fa-database', db.ok ? 'Terhubung' : 'Gagal',
              db.ok ? `${db.nama || ''} · respons ${db.latensi_ms} ms` : (db.error || 'Cek SQL Server / .env'),
              db.ok ? (db.latensi_ms > 500 ? 'peringatan' : 'ok') : 'gagal'),
        kartu('Ukuran Database', 'fa-hard-drive', db.ukuran_mb != null ? `${db.ukuran_mb} MB` : '-', 'Data + log SQL Server'),
        kartu('Backup Terakhir', 'fa-clock-rotate-left', nilaiBackup, infoBackup, stBackup),
        kartu('Disk Server', 'fa-server', `${disk.sisa_gb} GB sisa`, `dari ${disk.total_gb} GB · terpakai ${disk.terpakai_persen}%`,
              disk.terpakai_persen > 90 ? 'gagal' : disk.terpakai_persen > 80 ? 'peringatan' : 'ok'),
        kartu('Folder Upload', 'fa-folder-open', `${d.upload.ukuran_mb} MB${d.upload.lebih ? '+' : ''}`, 'Foto wajah, surat blacklist, foto absensi'),
        kartu('Timbangan', 'fa-weight-scale', d.timbangan.terhubung ? 'Terhubung' : 'Tidak terhubung', 'Koneksi serial ke indikator timbangan',
              d.timbangan.terhubung ? 'ok' : 'peringatan'),
        kartu('Versi Aplikasi', 'fa-code-branch', d.aplikasi.versi, `Python ${d.aplikasi.python}`),
        kartu('Server Berjalan', 'fa-power-off', `${d.aplikasi.uptime_jam} jam`, `sejak ${d.aplikasi.berjalan_sejak}`),
        kartu('Sesi Aktif', 'fa-users', String(d.aplikasi.sesi_aktif), 'User yang sedang login'),
    ].join('');
    document.getElementById('waktuCekKesehatan').textContent = `Dicek ${new Date().toLocaleTimeString('id-ID')}`;
}
