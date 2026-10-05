"""Cek komputer siap menjalankan aplikasi: Python, library, ODBC driver, .env, koneksi & versi database, folder upload,
port serial timbangan. Jalankan dari folder proyek:  venv\\Scripts\\python tools\\cek_lingkungan.py"""
import importlib
import os
import platform
import struct
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AKAR)
os.chdir(AKAR)
hasil = {"gagal": 0}


def baris(ok, teks, saran=""):
    print(f"  [{'OK' if ok else 'X '}] {teks}" + (f"\n        -> {saran}" if not ok and saran else ""))
    if not ok:
        hasil["gagal"] += 1


print("\n== Python")
versi = sys.version_info
baris(versi[:2] in ((3, 10), (3, 11)) and struct.calcsize("P") == 8, f"Python {platform.python_version()} {struct.calcsize('P') * 8}-bit",
      "Butuh Python 3.10 / 3.11 64-bit (mediapipe 0.10.9 belum ada untuk 3.12+)")

print("\n== Library")
for modul, paket in [("flask", "Flask"), ("flask_login", "Flask-Login"), ("flask_wtf", "Flask-WTF"),
                     ("flask_compress", "Flask-Compress"), ("waitress", "waitress"), ("dotenv", "python-dotenv"),
                     ("pyodbc", "pyodbc"), ("serial", "pyserial"), ("numpy", "numpy"), ("cv2", "opencv-python"),
                     ("mediapipe", "mediapipe"), ("dlib", "dlib-bin"), ("face_recognition", "face-recognition"),
                     ("qrcode", "qrcode"), ("PIL", "pillow")]:
    try:
        m = importlib.import_module(modul)
        baris(True, f"{paket} {getattr(m, '__version__', '')}".strip())
    except Exception as e:      # noqa: BLE001
        baris(False, f"{paket}: {e}", "Jalankan tools\\pasang_windows.bat")

print("\n== .env")
from dotenv import load_dotenv  # noqa: E402
ada_env = os.path.exists(".env")
baris(ada_env, ".env ada di folder proyek", "Salin .env dari PC lama (SECRET_KEY & HASH_SECRET_KEY harus SAMA)")
load_dotenv()
for kunci in ("SECRET_KEY", "HASH_SECRET_KEY"):
    baris(len(os.getenv(kunci) or "") >= 32, f"{kunci} terisi (>= 32 karakter)",
          "Pakai nilai dari .env PC lama; HASH_SECRET_KEY beda = hash timbang lama dianggap rusak")
for kunci in ("DB_SERVER", "DB_NAME"):
    baris(bool(os.getenv(kunci)), f"{kunci} = {os.getenv(kunci)}", "Isi di .env, mis. DB_SERVER=localhost\\SQLEXPRESS")

print("\n== ODBC & database")
try:
    import pyodbc
    from config import DB_CONFIG, get_connection_string
    driver = DB_CONFIG["driver"].strip("{}")
    baris(driver in pyodbc.drivers(), f"ODBC driver '{driver}' terpasang (ada: {', '.join(pyodbc.drivers()) or '-'})",
          "Pasang 'ODBC Driver 18 for SQL Server' (msodbcsql.msi), atau isi DB_DRIVER di .env sesuai yang ada")
    conn = pyodbc.connect(get_connection_string(), timeout=5)
    cur = conn.cursor()
    baris(True, "Terhubung ke " + cur.execute("SELECT @@SERVERNAME + ' / ' + DB_NAME()").fetchone()[0])
    ver = cur.execute("SELECT CAST(SERVERPROPERTY('ProductMajorVersion') AS INT)").fetchone()[0]
    baris(ver >= 13, f"SQL Server versi {ver} (2016 = 13, 2019 = 15, 2022 = 16)", "Butuh SQL Server 2016 SP1 atau lebih baru")
    for objek, tipe, ket in [("akun", "U", "migrasi 016"), ("mitra", "U", "migrasi 016"), ("log_aktivitas", "U", "migrasi 015"),
                             ("sp_catat_log", "P", "migrasi 015"), ("kontrak", "U", "migrasi 013"),
                             ("jenis_kendaraan", "U", "migrasi 014")]:
        ada = cur.execute("SELECT OBJECT_ID(?, ?)", f"dbo.{objek}", tipe).fetchone()[0] is not None
        baris(ada, f"{objek} ada", f"Database belum versi terbaru: jalankan {ket} (atau database/schema.sql untuk DB baru)")
    n_akun = cur.execute("SELECT COUNT(*) FROM akun WHERE is_active = 1").fetchone()[0]
    baris(n_akun > 0, f"{n_akun} akun aktif")
    rusak = cur.execute("SELECT COUNT(*) FROM v_log_rusak").fetchone()[0]
    baris(rusak == 0, "Rantai log utuh" if rusak == 0 else f"{rusak} baris log rusak")
    conn.close()
except Exception as e:      # noqa: BLE001
    baris(False, f"Koneksi database gagal: {str(e)[:200]}",
          "Cek SQL Server berjalan, DB_SERVER / DB_NAME di .env, dan database sudah di-restore / dibuat")

print("\n== Folder & perangkat")
from extensions import UPLOAD_FOLDER  # noqa: E402
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
jumlah = sum(len(f) for _, _, f in os.walk(UPLOAD_FOLDER))
baris(os.access(UPLOAD_FOLDER, os.W_OK), f"Folder upload {UPLOAD_FOLDER} ({jumlah} file)",
      "Salin folder data\\uploads dari PC lama (foto wajah, surat, dokumen)")
try:
    from serial.tools import list_ports
    port = [p.device for p in list_ports.comports()]
    print(f"  [i ] Port serial terlihat: {', '.join(port) or 'tidak ada'} (atur di Admin > Perangkat / Kiosk > Jembatan)")
except Exception:       # noqa: BLE001
    pass

print("\n" + ("SIAP: jalankan  venv\\Scripts\\python serve.py" if hasil["gagal"] == 0
              else f"{hasil['gagal']} hal perlu dibereskan (lihat tanda X di atas)."))
sys.exit(1 if hasil["gagal"] else 0)
