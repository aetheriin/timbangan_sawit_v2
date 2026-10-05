"""Pembacaan berat dari indikator timbangan lewat port serial, satu thread per jembatan timbang.

Daftar jembatan & port dari tabel jembatan_timbang (Admin › Perangkat / Kiosk); bila tabel belum ada / DB mati,
memakai satu port bawaan (env PORT_TIMBANGAN, default COM3). Setiap port punya status & deteksi stabil sendiri."""
import logging
import os
import re
import threading
import time

import serial

log = logging.getLogger("weighbridge")

PORT = os.getenv("PORT_TIMBANGAN", "COM3")      # port bawaan (tanpa tabel jembatan_timbang)
BAUDRATE = 9600

AMBANG_TOLERANSI_KG = 5       # anggap "sama" kalau selisih di bawah ini
DURASI_STABIL_DIBUTUHKAN = 3  # detik

_lock = threading.Lock()
_pembaca = {}                 # port -> {"state": {...}, "riwayat": {...}, "baudrate": int}


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


def _state_baru():
    return {"berat": 0, "stabil": False, "terhubung": False, "siap_kunci": False}


def _update_stabilitas_software(riwayat, berat):
    now = time.time()
    if riwayat["berat_terakhir"] is None or abs(berat - riwayat["berat_terakhir"]) > AMBANG_TOLERANSI_KG:
        riwayat["berat_terakhir"] = berat
        riwayat["waktu_mulai_stabil"] = now
        return False
    return now - riwayat["waktu_mulai_stabil"] >= DURASI_STABIL_DIBUTUHKAN


def _loop_baca_serial(port):
    data = _pembaca[port]
    while True:
        try:
            ser = serial.Serial(
                port, baudrate=data["baudrate"], bytesize=serial.SEVENBITS,
                parity=serial.PARITY_EVEN, stopbits=serial.STOPBITS_ONE, timeout=1
            )
            with _lock:
                data["state"]["terhubung"] = True
            while True:
                raw = ser.readline()
                if raw:
                    berat, stabil_hw = parse_data_timbangan(raw)
                    if berat is not None:
                        siap_kunci = _update_stabilitas_software(data["riwayat"], berat)
                        with _lock:
                            data["state"].update(berat=berat, stabil=stabil_hw or siap_kunci, siap_kunci=siap_kunci)
        except serial.SerialException:
            with _lock:
                data["state"]["terhubung"] = False
            time.sleep(3)


def pastikan_pembaca(port, baudrate=BAUDRATE):
    """Mulai thread baca untuk port ini bila belum ada (dipanggil saat start & saat admin menambah jembatan)."""
    if not port:
        return
    with _lock:
        if port in _pembaca:
            return
        _pembaca[port] = {"state": _state_baru(), "riwayat": {"berat_terakhir": None, "waktu_mulai_stabil": None},
                          "baudrate": int(baudrate or BAUDRATE)}
    threading.Thread(target=_loop_baca_serial, args=(port,), daemon=True, name=f"serial-{port}").start()


def mulai_pembacaan_serial():
    try:
        from utils.db_jembatan import daftar_jembatan
        jembatan = [j for j in daftar_jembatan() if j["is_active"]]
    except Exception:       # noqa: BLE001 - migrasi 011 belum dijalankan / DB mati: satu port bawaan
        log.exception("Daftar jembatan timbang tidak terbaca, memakai port bawaan %s", PORT)
        jembatan = []
    for j in jembatan or [{"port": PORT, "baudrate": BAUDRATE}]:
        pastikan_pembaca(j["port"], j["baudrate"])


def _data(port):
    with _lock:
        if port:
            return _pembaca.get(port)
        return next(iter(_pembaca.values()), None)


def reset_deteksi_stabil(port=None):
    data = _data(port)
    if data:
        data["riwayat"].update(berat_terakhir=None, waktu_mulai_stabil=None)


def baca_status_asli(port=None):
    """Status satu port (default: port pertama). Port belum dibaca -> tidak terhubung."""
    data = _data(port)
    if data is None:
        return _state_baru()
    with _lock:
        return dict(data["state"])


def semua_status():
    with _lock:
        return {port: dict(d["state"]) for port, d in _pembaca.items()}
