from flask_login import UserMixin

class User(UserMixin):
    def __init__(self, id, username, nama_lengkap, role, id_level=None, is_admin=False, halaman_awal="/weighbridge"):
        self.id = id
        self.username = username
        self.nama_lengkap = nama_lengkap
        self.role = role
        self.id_level = id_level
        self.is_admin = bool(is_admin)
        self.halaman_awal = halaman_awal

    @staticmethod
    def dari_row(row):
        return User(row.id_user, row.username, row.nama, row.role, row.id_level, row.is_admin, row.halaman_awal)
