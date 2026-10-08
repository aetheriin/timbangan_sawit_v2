import os
from waitress import serve
from app import app, jalankan_layanan_latar

if __name__ == "__main__":
    jalankan_layanan_latar()
    host, port = os.getenv("HOST", "0.0.0.0"), int(os.getenv("PORT", "5000"))
    print(f"Weighbridge berjalan di http://{host}:{port} (waitress, {os.getenv('THREADS', '8')} thread)")
    serve(app, host=host, port=port, threads=int(os.getenv("THREADS", "8")),
          channel_timeout=120, connection_limit=200)
