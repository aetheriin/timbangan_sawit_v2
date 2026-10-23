"""ERD dari katalog SQL Server: diagram lengkap + per kelompok, ditulis ke docs/erd/*.mmd.

Pakai koneksi .env aplikasi:  python tools/gen_erd.py
Lalu gambar (butuh Node.js):  npx -p @mermaid-js/mermaid-cli mmdc -i docs/erd/04_proses_tiket.mmd -o docs/erd/04_proses_tiket.png
Diagram lengkap butuh -c dengan {"maxTextSize": 500000, "maxEdges": 2000}."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pyodbc
from config import get_connection_string
c = pyodbc.connect(get_connection_string())
q = lambda sql: c.execute(sql).fetchall()

kolom = {}
for t, col, tipe, nullable, pk in q("""
    SELECT t.name, c.name, ty.name, c.is_nullable,
           CASE WHEN EXISTS (SELECT 1 FROM sys.index_columns ic JOIN sys.indexes i ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                             WHERE i.is_primary_key = 1 AND ic.object_id = c.object_id AND ic.column_id = c.column_id) THEN 1 ELSE 0 END
    FROM sys.tables t JOIN sys.columns c ON c.object_id = t.object_id JOIN sys.types ty ON ty.user_type_id = c.user_type_id
    ORDER BY t.name, c.column_id"""):
    kolom.setdefault(t, []).append({"nama": col, "tipe": tipe, "null": bool(nullable), "pk": bool(pk)})
# kolom unik tunggal (constraint / index unik 1 kolom, termasuk terfilter)
unik = {(t, col) for t, col in q("""
    SELECT OBJECT_NAME(i.object_id), c.name FROM sys.indexes i
    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
    JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
    WHERE i.is_unique = 1 AND i.is_primary_key = 0 AND OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
      AND (SELECT COUNT(*) FROM sys.index_columns x WHERE x.object_id = i.object_id AND x.index_id = i.index_id AND x.is_included_column = 0) = 1""")}
fk = [dict(zip(("anak", "kolom", "induk"), r)) for r in q("""
    SELECT OBJECT_NAME(f.parent_object_id), pc.name, OBJECT_NAME(f.referenced_object_id)
    FROM sys.foreign_keys f JOIN sys.foreign_key_columns fc ON fc.constraint_object_id = f.object_id
    JOIN sys.columns pc ON pc.object_id = fc.parent_object_id AND pc.column_id = fc.parent_column_id
    ORDER BY 1, 2""")]
fk_kolom = {(f["anak"], f["kolom"]) for f in fk}
null_of = {(t, k["nama"]): k["null"] for t, ks in kolom.items() for k in ks}

KELOMPOK = [
    ("01_organisasi_akses", "Organisasi, akun & hak akses",
     ["Company", "Mill", "CompanyArea", "Department", "DepartmentDetails", "Level", "LevelDetails", "Menu", "ActionType",
      "AccessMenu", "Users", "PasswordManager", "UserCompany", "UserSession", "Setting", "SettingArea", "RequiredDataField",
      "Device", "WorkSchedule", "UserCategory"]),
    ("02_personel_dokumen", "Orang (Users), SIM, wajah, kunjungan, absensi, blacklist & dokumen",
     ["UserCategory", "Users", "License", "LicenseDetail", "FaceRecog", "VisitPurpose", "Guest", "FaceActivity",
      "Blacklist", "BlacklistDetection", "DocumentType", "Document", "DocumentFile", "DetailVehicle", "CompanyArea"]),
    ("03_mitra_kontrak", "Supplier, bank, produk, harga, kontrak, DO & invoice",
     ["Currency", "Bank", "BankDetails", "SupplierType", "SupplierTypeDetails", "SupplierGroup", "Supplier", "SupplierCompany",
      "Company", "VehicleType", "DetailVehicle", "VehicleDriver", "VehicleContract", "ProductType", "Product", "ProductPrice",
      "DailyPrice", "Contract", "DeliveryOrder", "DOTransport", "Invoice", "WeightBridgeType", "Flow", "Users"]),
    ("04_proses_tiket", "Tiket & timbang: WeightBridge, Weighing, Grading, LabResult, TicketVoid, DOExcess",
     ["WeightBridge", "WeightBridgeType", "Status", "FlowStage", "Flow", "FlowStep", "CompanyArea", "Scale", "Weighing",
      "Grading", "LabResult", "TicketVoid", "DOExcess", "Product", "Supplier", "DetailVehicle", "DeliveryOrder",
      "VehicleContract", "Document", "Users"]),
    ("05_log_persetujuan", "Log aktivitas, persetujuan & notifikasi",
     ["Log", "ApprovalRequest", "ApprovalHistory", "ApprovalRequestStep", "ApprovalFlow", "ApprovalFlowStep",
      "LevelDetails", "Notification", "NotificationRead", "Users", "CompanyArea"]),
]

def entitas(t, ringkas=False):
    baris = []
    for k in kolom[t]:
        if ringkas and not k["pk"]:
            continue
        kunci = [x for x, ya in (("PK", k["pk"]), ("FK", (t, k["nama"]) in fk_kolom), ("UK", (t, k["nama"]) in unik)) if ya]
        tipe = k["tipe"].replace(" ", "_")
        catatan = ' "NULL"' if k["null"] else ""
        kunci_teks = (" " + ",".join(kunci)) if kunci else ""
        baris.append(f"        {tipe} {k['nama']}{kunci_teks}{catatan}")
    return f"    {t} {{\n" + "\n".join(baris) + "\n    }"

def relasi(f):
    pk = [k["nama"] for k in kolom[f["anak"]] if k["pk"]]
    satu = (f["anak"], f["kolom"]) in unik or pk == [f["kolom"]]
    kiri = "|o" if null_of[(f["anak"], f["kolom"])] else "||"
    kanan = "o|" if satu else "o{"
    return f'    {f["induk"]} {kiri}--{kanan} {f["anak"]} : "{f["kolom"]}"'

def diagram(tabel, utama, tanpa_akun=False):
    out = ["erDiagram"]
    for t in tabel:
        out.append(entitas(t, ringkas=t not in utama))
    for f in fk:
        if f["anak"] in tabel and f["induk"] in tabel and (f["anak"] in utama or f["induk"] in utama):
            if tanpa_akun and f["induk"] == "Users" and "Users" not in utama:
                continue
            out.append(relasi(f))
    return "\n".join(out)

hasil = {"lengkap": diagram(sorted(kolom), set(kolom))}
for kode, judul, tabel in KELOMPOK:
    utama = {t for t in tabel}
    # tabel pendukung (milik kelompok lain) cukup ditampilkan PK-nya
    pendukung = {"01_organisasi_akses": {"UserCategory"}, "02_personel_dokumen": {"Users", "DetailVehicle", "CompanyArea"},
                 "03_mitra_kontrak": {"Users", "Flow", "Company", "WeightBridgeType"},
                 "04_proses_tiket": {"CompanyArea", "Product", "Supplier", "DetailVehicle", "DeliveryOrder",
                                     "VehicleContract", "Document", "Users"},
                 "05_log_persetujuan": {"Users", "CompanyArea"}}[kode]
    hasil[kode] = diagram(tabel, utama - pendukung, tanpa_akun=kode in ("03_mitra_kontrak", "04_proses_tiket"))
folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "erd")
os.makedirs(folder, exist_ok=True)
for nama, isi in hasil.items():
    with open(os.path.join(folder, f"{nama}.mmd"), "w", encoding="utf-8") as f:
        f.write(isi)
print(len(kolom), "tabel,", sum(map(len, kolom.values())), "kolom,", len(fk), "FK")
