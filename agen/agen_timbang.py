"""Agen timbangan: dijalankan di PC jembatan yang tercolok kabel indikator timbangan.

Membaca COM port di PC ini lalu mengirim data mentahnya ke server lewat jaringan (beberapa kali per detik).
Port, baudrate, data bit, parity, stop bit diambil dari Admin › Perangkat / Kiosk › Jembatan Timbang
(sumber data "Agen di PC jembatan"); format berat & aturan stabil diproses di server.

Salin folder agen\ ke PC jembatan, isi .env (contoh: .env.contoh), lalu jalankan.bat.
.env di PC jembatan:
    WEIGHBRIDGE_URL=http://192.168.1.10:5000     alamat server
    JEMBATAN_ID=2                                angka "ID agen" di Admin › Jembatan Timbang
    KIOSK_ID=POS-JT2                             ID pos di Admin › Perangkat / Kiosk
    KIOSK_TOKEN=...                              token pos tersebut

Jalankan:
    python agen_timbang.py                 kirim terus ke server (biarkan jendela terbuka)
    python agen_timbang.py --deteksi COM3  coba kombinasi baudrate / parity, tampilkan yang terbaca jelas
    python agen_timbang.py --lihat COM3 9600 7E1   tampilkan data mentah tanpa server
Butuh Python + pip install pyserial requests python-dotenv (pasang.bat), atau pakai agen_timbang.exe (buat_exe.bat)."""
import functools
import os
import sys
import time

import requests
import serial
from dotenv import load_dotenv

# .env di folder yang sama dengan agen (juga saat dijalankan sebagai agen_timbang.exe)
FOLDER = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
load_dotenv(os.path.join(FOLDER, ".env"))
print = functools.partial(print, flush=True)       # noqa: A001 - tampil langsung walau output dialihkan ke file
URL = os.getenv("WEIGHBRIDGE_URL", "http://127.0.0.1:5000").rstrip("/")
ID = os.getenv("JEMBATAN_ID", "").strip()
HEADER = {"X-Kiosk-Id": os.getenv("KIOSK_ID", "UTAMA"), "X-Kiosk-Token": os.getenv("KIOSK_TOKEN", "")}
JEDA_KIRIM = 0.3            # detik
PARITY = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD, "M": serial.PARITY_MARK,
          "S": serial.PARITY_SPACE}
STOP = {1.0: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE, 2.0: serial.STOPBITS_TWO}


def buka(port, baud, data_bits, parity, stop_bits):
    return serial.serial_for_url(port, baudrate=int(baud), bytesize=int(data_bits), parity=PARITY[parity],
                                 stopbits=STOP[float(stop_bits)], timeout=0.2)


def ambil_konfigurasi():
    while True:
        try:
            r = requests.get(f"{URL}/api/agen/jembatan/{ID}/konfigurasi", headers=HEADER, timeout=5)
            data = r.json()
            if r.ok:
                return data
            print(f"[server] {data.get('error')}  (coba lagi 10 detik)")
        except (requests.RequestException, ValueError) as e:
            print(f"[server] tidak bisa dihubungi {URL}: {type(e).__name__}  (coba lagi 10 detik)")
        time.sleep(10)


def kirim(teks, terhubung=True, error=None):
    """Kembalikan versi pengaturan dari server (None bila gagal)."""
    try:
        r = requests.post(f"{URL}/api/agen/jembatan/{ID}/data", headers=HEADER, timeout=3,
                          json={"teks": teks, "terhubung": terhubung, "error": error})
        return r.json().get("versi") if r.ok else None
    except (requests.RequestException, ValueError):
        return None


def jalankan():
    if not ID.isdigit():
        sys.exit("Isi JEMBATAN_ID di .env (angka 'ID agen' di Admin › Perangkat / Kiosk › Jembatan Timbang)")
    while True:
        cfg = ambil_konfigurasi()
        label = f"{cfg['kode']} {cfg['port']} {cfg['baudrate']} {cfg['data_bits']}{cfg['parity']}{float(cfg['stop_bits']):g}"
        try:
            ser = buka(cfg["port"], cfg["baudrate"], cfg["data_bits"], cfg["parity"], cfg["stop_bits"])
        except Exception as e:      # noqa: BLE001 - port salah / dipakai program lain / setting tidak didukung
            print(f"[{label}] port gagal dibuka: {e}  (coba lagi 5 detik)")
            kirim("", False, f"Agen: port {cfg['port']} gagal dibuka: {e}")
            time.sleep(5)
            continue
        print(f"[{label}] terhubung, mengirim ke {URL} ... (Ctrl+C untuk berhenti)")
        buffer, terakhir, gagal = "", 0.0, 0
        try:
            while True:
                potong = ser.read(ser.in_waiting or 1)
                if potong:
                    buffer += potong.decode("latin-1")
                if time.time() - terakhir >= JEDA_KIRIM:
                    versi = kirim(buffer[-8000:])
                    terakhir, buffer = time.time(), ""
                    if versi is None:
                        gagal += 1
                        if gagal in (1, 20):
                            print("[server] pengiriman gagal, terus mencoba...")
                        continue
                    gagal = 0
                    if versi != cfg["versi"]:
                        print("[server] pengaturan port berubah, menyambung ulang...")
                        break
        except Exception as e:      # noqa: BLE001 - kabel dicabut / driver USB-serial lepas
            print(f"[{label}] koneksi port putus: {e}")
            kirim("", False, f"Agen: port {cfg['port']} putus: {e}")
            time.sleep(3)
        finally:
            ser.close()


def _skor(teks):
    """Seberapa 'masuk akal' data mentah: banyak karakter cetak & angka, ada pemisah baris / '='."""
    if not teks:
        return 0
    cetak = sum(1 for c in teks if c.isprintable() or c in "\r\n")
    angka = sum(1 for c in teks if c.isdigit())
    return cetak / len(teks) + min(angka / len(teks), 0.5) + (0.3 if any(c in teks for c in "\r\n=") else 0)


def deteksi(port):
    """Coba kombinasi umum, urutkan dari yang paling terbaca."""
    hasil = []
    for baud in (9600, 2400, 4800, 1200, 19200):
        for bits, parity, stop in ((7, "E", 1), (8, "N", 1), (7, "O", 1), (8, "E", 1), (7, "N", 2)):
            try:
                with buka(port, baud, bits, parity, stop) as ser:
                    ser.reset_input_buffer()
                    akhir, data = time.time() + 1.5, b""
                    while time.time() < akhir:
                        data += ser.read(ser.in_waiting or 1)
                teks = data.decode("latin-1")
                hasil.append((_skor(teks), f"{baud} {bits}{parity}{stop}", teks))
                print(f"  {baud:>6} {bits}{parity}{stop}: {len(data):4d} byte  {teks[:50]!r}")
            except (serial.SerialException, OSError) as e:
                sys.exit(f"Port {port} tidak bisa dibuka: {e}")
    hasil.sort(reverse=True)
    print("\nPaling mungkin (isi di Admin › Jembatan Timbang):")
    for skor, label, teks in hasil[:3]:
        print(f"  {label}  skor {skor:.2f}  contoh: {teks.strip()[:60]!r}")


def lihat(port, baud=9600, mode="7E1"):
    print(f"Data mentah {port} {baud} {mode} (Ctrl+C untuk berhenti):")
    with buka(port, baud, int(mode[0]), mode[1].upper(), float(mode[2:])) as ser:
        while True:
            data = ser.read(ser.in_waiting or 1)
            if data:
                print(repr(data.decode("latin-1")))


if __name__ == "__main__":
    try:
        if len(sys.argv) >= 3 and sys.argv[1] == "--deteksi":
            deteksi(sys.argv[2])
        elif len(sys.argv) >= 3 and sys.argv[1] == "--lihat":
            lihat(sys.argv[2], *(sys.argv[3:5]))
        else:
            jalankan()
    except KeyboardInterrupt:
        print("\nAgen berhenti.")
