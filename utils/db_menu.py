"""Admin › Kelola Menu: susunan menu 3 level (Lv1 grup, Lv2 halaman, Lv3 bagian) di tabel Menu + aksi yang berlaku (MenuAction).

Kode menu tidak bisa diubah (dipakai kode program, mis. izin('LIST', 'ubah')). Pindah induk = level ikut menyesuaikan, beserta
anak-anaknya; maksimal 3 level. Hak akses menempel di menu (AccessMenu.MenuID), jadi ikut pindah bersama menunya."""
from utils.db_utils import get_connection, _rows_to_dicts

APLIKASI = ("CPOS", "ANALYTICS", "REKAPIN")


def _query(sql, *params):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, *params)
        return _rows_to_dicts(cursor)
    finally:
        conn.close()


def daftar_menu():
    """Semua menu (termasuk nonaktif) urut seperti sidebar: [{id_menu, kode, nama, url, ikon, level, aplikasi, id_induk,
    urutan, is_active, aksi: [ActionID], jumlah_aturan}]"""
    rows = _query("""SELECT m.MenuID AS id_menu, m.MenuCode AS kode, m.MenuName AS nama, m.Url AS url, m.Icon AS ikon,
                            m.MenuLevel AS level, m.AppCode AS aplikasi, m.ParentMenuID AS id_induk, m.SortOrder AS urutan,
                            m.Active AS is_active,
                            (SELECT STRING_AGG(CAST(ma.ActionID AS VARCHAR(3)), ',') FROM MenuAction ma WHERE ma.MenuID = m.MenuID) AS aksi,
                            (SELECT COUNT(*) FROM (SELECT DISTINCT a.TargetType, a.LevelDetID, a.LevelID, a.DeptID, a.UserID, a.IsDeny
                                                   FROM AccessMenu a WHERE a.MenuID = m.MenuID) x) AS jumlah_aturan
                     FROM Menu m ORDER BY m.SortOrder, m.MenuName""")
    anak = {}
    for r in rows:
        r["aksi"] = [int(x) for x in (r["aksi"] or "").split(",") if x]
        anak.setdefault(r["id_induk"], []).append(r)
    hasil = []

    def tambah(id_induk):
        for r in anak.get(id_induk, []):
            hasil.append(r)
            tambah(r["id_menu"])
    tambah(None)
    return hasil


def _turunan(menu, id_menu):
    """id semua turunan menu (anak, cucu)."""
    hasil, antre = [], [id_menu]
    while antre:
        i = antre.pop()
        for m in menu:
            if m["id_induk"] == i:
                hasil.append(m["id_menu"])
                antre.append(m["id_menu"])
    return hasil


def _kedalaman(menu, id_menu):
    """Berapa level di bawah menu ini (0 = tanpa anak)."""
    anak = [m["id_menu"] for m in menu if m["id_induk"] == id_menu]
    return 1 + max(_kedalaman(menu, a) for a in anak) if anak else 0


def simpan_menu(id_menu, kode, nama, id_induk, url, ikon, aplikasi, aksi):
    """Tambah (id_menu None) atau ubah menu. aksi = ActionID selain View yang berlaku. Kembalikan kode menu."""
    menu = daftar_menu()
    per_id = {m["id_menu"]: m for m in menu}
    if id_induk is not None and id_induk not in per_id:
        raise ValueError("Menu induk tidak ditemukan")
    if id_menu is not None:
        if id_menu not in per_id:
            raise ValueError("Menu tidak ditemukan")
        if id_induk == id_menu or id_induk in _turunan(menu, id_menu):
            raise ValueError("Menu tidak bisa dipindah ke bawah dirinya sendiri")
        kode = per_id[id_menu]["kode"]
    elif any(m["kode"] == kode for m in menu):
        raise ValueError(f"Kode menu {kode} sudah dipakai")
    level = per_id[id_induk]["level"] + 1 if id_induk is not None else 1
    if level + (_kedalaman(menu, id_menu) if id_menu is not None else 0) > 3:
        raise ValueError("Menu paling banyak 3 level. Pindahkan ke induk yang lebih atas")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_menu is None:
            cursor.execute("""SET NOCOUNT ON; INSERT INTO Menu (MenuCode, MenuName, ParentMenuID, MenuLevel, Url, Icon, AppCode, SortOrder)
                              VALUES (?, ?, ?, ?, ?, ?, ?, (SELECT ISNULL(MAX(SortOrder), 0) + 10 FROM Menu
                                                            WHERE ISNULL(ParentMenuID, 0) = ISNULL(?, 0)));
                              SELECT CAST(SCOPE_IDENTITY() AS INT)""",
                           kode, nama, id_induk, level, url, ikon, aplikasi, id_induk)
            id_menu = cursor.fetchone()[0]
        else:
            lama = per_id[id_menu]
            cursor.execute("""UPDATE Menu SET MenuName = ?, ParentMenuID = ?, MenuLevel = ?, Url = ?, Icon = ?, AppCode = ?
                              WHERE MenuID = ?""", nama, id_induk, level, url, ikon, aplikasi, id_menu)
            if lama["id_induk"] != id_induk:      # pindah induk: taruh paling bawah, turunannya ikut naik / turun level
                cursor.execute("""UPDATE Menu SET SortOrder = (SELECT ISNULL(MAX(SortOrder), 0) + 10 FROM Menu
                                                               WHERE ISNULL(ParentMenuID, 0) = ISNULL(?, 0) AND MenuID <> ?)
                                  WHERE MenuID = ?""", id_induk, id_menu, id_menu)
                selisih = level - lama["level"]
                for t in _turunan(menu, id_menu):
                    cursor.execute("UPDATE Menu SET MenuLevel = MenuLevel + ? WHERE MenuID = ?", selisih, t)
        # Aksi yang berlaku; aturan hak untuk aksi yang dicabut ikut dihapus (tidak berlaku lagi)
        cursor.execute("SELECT ActionID FROM MenuAction WHERE MenuID = ?", id_menu)
        ada = {r[0] for r in cursor.fetchall()}
        for a in ada - set(aksi):
            cursor.execute("DELETE FROM MenuAction WHERE MenuID = ? AND ActionID = ?", id_menu, a)
            cursor.execute("DELETE FROM AccessMenu WHERE MenuID = ? AND ActionID = ?", id_menu, a)
        for a in set(aksi) - ada:
            cursor.execute("INSERT INTO MenuAction (MenuID, ActionID) VALUES (?, ?)", id_menu, a)
        conn.commit()
    finally:
        conn.close()
    return kode


def geser_menu(id_menu, arah):
    """Naik (-1) / turun (+1) satu posisi di antara menu seinduk; urutan ditulis ulang 10, 20, 30, ..."""
    menu = daftar_menu()
    m = next((x for x in menu if x["id_menu"] == id_menu), None)
    if m is None:
        raise ValueError("Menu tidak ditemukan")
    saudara = [x["id_menu"] for x in menu if x["id_induk"] == m["id_induk"]]
    i = saudara.index(id_menu)
    j = i + (1 if arah > 0 else -1)
    if not 0 <= j < len(saudara):
        return False
    saudara[i], saudara[j] = saudara[j], saudara[i]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        for n, s in enumerate(saudara, 1):
            cursor.execute("UPDATE Menu SET SortOrder = ? WHERE MenuID = ?", n * 10, s)
        conn.commit()
    finally:
        conn.close()
    return True


def set_aktif_menu(id_menu, aktif):
    """Nonaktif = menu (dan turunannya, karena induk jadi gerbang) hilang dari sidebar; aturan hak tetap tersimpan."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Menu SET Active = ? WHERE MenuID = ?", 1 if aktif else 0, id_menu)
        if cursor.rowcount == 0:
            raise ValueError("Menu tidak ditemukan")
        conn.commit()
    finally:
        conn.close()
