// ===== KELOLA USER (admin) =====
let userIdReset = null;

function bukaResetPassword(id) {
    userIdReset = id;
    document.getElementById('formResetPassword').reset();
    openModal('modalResetPassword');
}

document.getElementById('formTambahUser').addEventListener('submit', async function (e) {
    e.preventDefault();
    const btn = this.querySelector('[type=submit]');
    const data = await denganTombol(btn, () => kirimForm('/admin/users/tambah', new FormData(this)));
    if (tampilkanHasil(data)) setTimeout(() => location.reload(), 800);
});

document.getElementById('formResetPassword').addEventListener('submit', async function (e) {
    e.preventDefault();
    const btn = this.querySelector('[type=submit]');
    const data = await denganTombol(btn, () => kirimForm(`/admin/users/reset-password/${userIdReset}`, new FormData(this)));
    if (tampilkanHasil(data)) closeModal('modalResetPassword');
});

async function toggleStatus(id, statusBaru) {
    const aktifkan = statusBaru === 1;
    const ok = await Dialog.konfirmasi({
        judul: aktifkan ? 'Aktifkan user?' : 'Nonaktifkan user?',
        pesan: aktifkan ? 'User bisa login kembali.' : 'User tidak bisa login dan sesinya yang sedang aktif akan berakhir.',
        teksYa: aktifkan ? 'Aktifkan' : 'Nonaktifkan', bahaya: !aktifkan,
    });
    if (!ok) return;
    const data = await kirimForm(`/admin/users/toggle/${id}`, { status: statusBaru });
    if (tampilkanHasil(data)) setTimeout(() => location.reload(), 800);
}
