import serial
import threading
import time
import re

PORT = "COM3"  # sesuaikan
BAUDRATE = 9600

_state = {"berat": 0, "stabil": False, "terhubung": False, "siap_kunci": False}
_lock = threading.Lock()

AMBANG_TOLERANSI_KG = 5       # anggap "sama" kalau selisih di bawah ini
DURASI_STABIL_DIBUTUHKAN = 3  # detik

_riwayat = {"berat_terakhir": None, "waktu_mulai_stabil": None}

def parse_data_timbangan(raw_line):
    try:
        teks = raw_line.decode('ascii', errors='ignore').strip()
        if not teks:
            return None, False
        bagian = teks.split(',')
        if len(bagian) < 3:
            return None, False
        stabil_hw = bagian[0].strip() == 'ST'
        angka_teks = re.search(r'[-+]?\d+\.?\d*', bagian[2])
        if not angka_teks:
            return None, False
        return float(angka_teks.group()), stabil_hw
    except Exception:
        return None, False

def _update_stabilitas_software(berat):
    now = time.time()
    if _riwayat["berat_terakhir"] is None or abs(berat - _riwayat["berat_terakhir"]) > AMBANG_TOLERANSI_KG:
        _riwayat["berat_terakhir"] = berat
        _riwayat["waktu_mulai_stabil"] = now
        return False

    durasi = now - _riwayat["waktu_mulai_stabil"]
    return durasi >= DURASI_STABIL_DIBUTUHKAN

def _loop_baca_serial():
    global _state
    while True:
        try:
            ser = serial.Serial(
                PORT, baudrate=BAUDRATE, bytesize=serial.SEVENBITS,
                parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_ONE, timeout=1
            )
            with _lock:
                _state["terhubung"] = True
            while True:
                raw = ser.readline()
                if raw:
                    berat, stabil_hw = parse_data_timbangan(raw)
                    if berat is not None:
                        siap_kunci = _update_stabilitas_software(berat)
                        with _lock:
                            _state["berat"] = berat
                            _state["stabil"] = stabil_hw or siap_kunci
                            _state["siap_kunci"] = siap_kunci
        except serial.SerialException:
            with _lock:
                _state["terhubung"] = False
            time.sleep(3)

def mulai_pembacaan_serial():
    thread = threading.Thread(target=_loop_baca_serial, daemon=True)
    thread.start()

def reset_deteksi_stabil():
    _riwayat["berat_terakhir"] = None
    _riwayat["waktu_mulai_stabil"] = None

def baca_status_asli():
    with _lock:
        return dict(_state)