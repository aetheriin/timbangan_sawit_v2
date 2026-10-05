import os
from dotenv import load_dotenv
load_dotenv()

DB_CONFIG = {
    "driver": os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}"),
    "server": os.getenv("DB_SERVER"),
    "database": os.getenv("DB_NAME", "DbSistemTimbangan"),
    # Akun SQL khusus aplikasi (hak minimal, lihat database/keamanan/01_user_aplikasi.sql).
    # Bila DB_USER kosong, tetap memakai Windows Authentication (Trusted_Connection) seperti sebelumnya.
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "trust_server_certificate": os.getenv("DB_TRUST_CERT", "yes"),
}

def get_connection_string():
    auth = (f"UID={DB_CONFIG['user']};PWD={DB_CONFIG['password']};" if DB_CONFIG["user"]
            else "Trusted_Connection=yes;")
    return (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"{auth}"
        f"TrustServerCertificate={DB_CONFIG['trust_server_certificate']};"
    )
