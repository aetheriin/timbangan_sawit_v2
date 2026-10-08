"""Pembacaan berat dari indikator timbangan, satu pembaca per jembatan timbang.

Pengaturan per jembatan dari Admin › Perangkat / Kiosk › Jembatan Timbang (tabel jembatan_timbang, migrasi 017):
  mode LOKAL : server membuka port sendiri. Port COMx / /dev/ttyUSB0 (indikator dicolok ke PC server) atau
               socket://192.168.1.50:4001 (alat serial-to-LAN).
  mode AGEN  : indikator dicolok ke PC jembatan; agen_timbang.py di PC itu mengirim data mentah ke server
               (terima_dari_agen). Server tidak membuka port.
Data mentah dipotong per bingkai lalu dibaca sesuai format_data (lihat FORMAT), dikali faktor (ton -> kg).
Stabil (siap disimpan) = pembacaan tidak berubah lebih dari toleransi_kg selama durasi_stabil detik;
bila wajib_st, indikator juga harus mengirim tanda stabil (ST)."""
import collections
import logging
import os
import re
import threading
import time

import serial

log = logging.getLogger("weighbridge")

PORT = os.getenv("PORT_TIMBANGAN", "COM3")      # port bawaan bila tabel jembatan_timbang belum ada
BAUDRATE = 9600
AGEN_PUTUS_DETIK = 5        # agen dianggap putus bila tidak mengirim data selama ini

# Profil bawaan = perilaku lama (indikator 7E1, "ST,GS,+00012345kg")
BAWAAN = {"mode": "LOKAL", "port": PORT, "baudrate": BAUDRATE, "data_bits": 7, "parity": "E", "stop_bits": 1.0,
          "format_data": "ST_GS", "pola": None, "faktor": 1.0, "toleransi_kg": 5.0, "durasi_stabil": 3.0,
          "berat_min_kg": 0.0, "wajib_st": False}
KUNCI_PORT = ("mode", "port", "baudrate", "data_bits", "parity", "stop_bits")      # berubah -> port dibuka ulang

FORMAT = {
    "ST_GS": "ST,GS,+00012345kg (field ke-3 = berat, ST/US = stabil/tidak)",
    "ANGKA": "Angka pertama di setiap baris, mis. ' 12340 kg' / 'WN0012340kg'; stabil bila ada 'ST'",
    "TERBALIK": "Digit terbalik setelah '=' (XK3190 / A9 dan sejenis), mis. '=0.43210' = 1234.0",
    "POLA": "Regex sendiri dengan grup (?P<berat>...) dan opsional (?P<stabil>...)",
}
_ANGKA = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_ST = re.compile(r"(?<![A-Z])ST(?![A-Z])")

_lock = threading.Lock()
_pembaca = {}               # id_jembatan -> data pembaca (lihat _data_baru)


# ===== Parser =====
def _angka(teks):
    m = _ANGKA.search(teks)
    return float(m.group().replace(",", ".")) if m else None


def bingkai(buffer, format_data):
    """Potong teks mentah menjadi bingkai utuh. Kembalikan (daftar_bingkai, sisa_buffer)."""
    if format_data == "TERBALIK":               # indikator mengirim terus tanpa baris baru: '=xxxxxxx=xxxxxxx'
        bagian = buffer.split("=")
        return [b for b in bagian[1:-1] if b.strip()], "=" + bagian[-1] if len(bagian) > 1 else buffer
    bagian = re.split(r"[\r\n\x02\x03]+", buffer)
    return [b for b in bagian[:-1] if b.strip()], bagian[-1]


def parse(teks, cfg):
    """Satu bingkai -> (berat_kg | None, stabil_dari_indikator)."""
    try:
        fmt = cfg.get("format_data") or "ST_GS"
        teks = teks.strip()
        if not teks:
            return None, False
        if fmt == "ST_GS":
            bagian = teks.split(",")
            if len(bagian) < 3:
                return None, False
            berat, stabil = _angka(bagian[2]), bagian[0].strip().upper() == "ST"
        elif fmt == "ANGKA":
            berat, stabil = _angka(teks), bool(_ST.search(teks.upper()))
        elif fmt == "TERBALIK":
            digit = teks.strip("= ")[::-1]
            berat, stabil = (float(digit) if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", digit) else None), False
        elif fmt == "POLA":
            m = re.search(cfg.get("pola") or "", teks)
            if not m or "berat" not in m.groupdict():
                return None, False
            berat = _angka(m.group("berat") or "")
            stabil = bool(m.groupdict().get("stabil"))
        else:
            return None, False
        if berat is None:
            return None, False
        return round(berat * float(cfg.get("faktor") or 1), 2), stabil
    except (ValueError, re.error):
        return None, False


# ===== Data per jembatan =====
def _state_baru():
    return {"berat": 0, "stabil": False, "terhubung": False, "siap_kunci": False, "stabil_hw": False, "error": None}


def _data_baru(cfg):
    return {"cfg": dict(cfg), "state": _state_baru(), "riwayat": {"berat_terakhir": None, "waktu_mulai_stabil": None},
            "buffer": "", "mentah": collections.deque(maxlen=30), "terakhir": 0.0, "versi": 0, "stop": False}


def _update_stabilitas(data, berat):
    cfg, riwayat, sekarang = data["cfg"], data["riwayat"], time.time()
    if riwayat["berat_terakhir"] is None or abs(berat - riwayat["berat_terakhir"]) > float(cfg["toleransi_kg"]):
        riwayat["berat_terakhir"] = berat
        riwayat["waktu_mulai_stabil"] = sekarang
        return False
    return sekarang - riwayat["waktu_mulai_stabil"] >= float(cfg["durasi_stabil"])


def _proses_teks(data, teks):
    """Teks mentah (dari port atau agen) -> bingkai -> berat & stabil. Dipanggil dengan _lock dipegang."""
    data["buffer"] = (data["buffer"] + teks)[-4000:]
    bingkai_utuh, data["buffer"] = bingkai(data["buffer"], data["cfg"]["format_data"])
    for b in bingkai_utuh:
        berat, stabil_hw = parse(b, data["cfg"])
        data["mentah"].append({"waktu": time.strftime("%H:%M:%S"), "teks": b[:120], "berat": berat, "stabil": stabil_hw})
        if berat is None:
            continue
        siap = _update_stabilitas(data, berat)
        if data["cfg"]["wajib_st"]:
            siap = siap and stabil_hw
        data["state"].update(berat=berat, stabil_hw=stabil_hw, stabil=siap or stabil_hw, siap_kunci=siap)
    data["terakhir"] = time.time()


# ===== Mode LOKAL: thread membuka port =====
def _buka(cfg):
    parity = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD,
              "M": serial.PARITY_MARK, "S": serial.PARITY_SPACE}[cfg["parity"]]
    stop = {1.0: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE, 2.0: serial.STOPBITS_TWO}[float(cfg["stop_bits"])]
    return serial.serial_for_url(cfg["port"], baudrate=int(cfg["baudrate"]), bytesize=int(cfg["data_bits"]),
                                 parity=parity, stopbits=stop, timeout=0.3)


def _loop_lokal(id_jembatan):
    while True:
        with _lock:
            data = _pembaca.get(id_jembatan)
            if data is None or data["stop"] or data["cfg"]["mode"] != "LOKAL":
                return                              # dinonaktifkan / pindah ke mode AGEN
            cfg, versi = dict(data["cfg"]), data["versi"]
        ser = None
        try:
            ser = _buka(cfg)
            with _lock:
                data["state"].update(terhubung=True, error=None)
            while True:
                with _lock:
                    if data["stop"] or data["versi"] != versi:        # dinonaktifkan / port diganti dari Admin
                        break
                potong = ser.read(ser.in_waiting or 1)
                if potong:
                    with _lock:
                        _proses_teks(data, potong.decode("latin-1"))
        except Exception as e:      # noqa: BLE001 - port salah / dicabut / setting tidak didukung: coba lagi
            with _lock:
                data["state"].update(terhubung=False, error=str(e)[:200])
            time.sleep(3)
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:       # noqa: BLE001
                    pass


# ===== API =====
def _cfg_dari(j):
    return {k: (j.get(k) if j.get(k) is not None else BAWAAN[k]) for k in BAWAAN}


def atur(jembatan):
    """Samakan pembaca dengan daftar jembatan (saat start & setiap Admin menyimpan). Perubahan langsung berlaku."""
    aktif = {j["id_jembatan"]: _cfg_dari(j) for j in jembatan if j.get("is_active", True)}
    mulai = []
    with _lock:
        for id_j, data in list(_pembaca.items()):
            if id_j not in aktif:
                data["stop"] = True
                del _pembaca[id_j]
        for id_j, cfg in aktif.items():
            data = _pembaca.get(id_j)
            if data is None:
                _pembaca[id_j] = data = _data_baru(cfg)
                if cfg["mode"] == "LOKAL":
                    mulai.append(id_j)
                continue
            port_berubah = any(str(data["cfg"][k]) != str(cfg[k]) for k in KUNCI_PORT)
            pindah_ke_lokal = data["cfg"]["mode"] != "LOKAL" and cfg["mode"] == "LOKAL"
            data["cfg"] = dict(cfg)
            if port_berubah:
                data["versi"] += 1
                data.update(buffer="", state=_state_baru())
                data["riwayat"].update(berat_terakhir=None, waktu_mulai_stabil=None)
                if pindah_ke_lokal:
                    mulai.append(id_j)
    for id_j in mulai:
        threading.Thread(target=_loop_lokal, args=(id_j,), daemon=True, name=f"timbangan-{id_j}").start()


def mulai_pembacaan_serial():
    try:
        from utils.db_jembatan import daftar_jembatan
        atur(daftar_jembatan())
    except Exception:       # noqa: BLE001 - migrasi belum dijalankan / DB mati: satu port bawaan
        log.exception("Daftar jembatan timbang tidak terbaca, memakai port bawaan %s", PORT)
        atur([{"id_jembatan": 0, **BAWAAN}])


def terima_dari_agen(id_jembatan, teks, terhubung=True, error=None):
    """Data mentah dari agen_timbang.py. Kembalikan versi pengaturan port (agen menyambung ulang bila berubah)."""
    with _lock:
        data = _pembaca.get(id_jembatan)
        if data is None or data["cfg"]["mode"] != "AGEN":
            return None
        data["state"].update(terhubung=bool(terhubung), error=(error or None) and str(error)[:200])
        if teks:
            _proses_teks(data, teks)
        data["terakhir"] = time.time()
        return data["versi"]


def _status(data):
    s = dict(data["state"])
    if data["cfg"]["mode"] == "AGEN" and time.time() - data["terakhir"] > AGEN_PUTUS_DETIK:
        s.update(terhubung=False, stabil=False, siap_kunci=False,
                 error=s.get("error") or "Agen di PC jembatan tidak mengirim data")
    s.update(mode=data["cfg"]["mode"], berat_min_kg=float(data["cfg"]["berat_min_kg"]),
             detik_sejak_data=round(time.time() - data["terakhir"], 1) if data["terakhir"] else None)
    return s


def baca_status(id_jembatan):
    with _lock:
        data = _pembaca.get(id_jembatan)
        return _status(data) if data else {**_state_baru(), "error": "Jembatan belum dibaca / tidak aktif"}


def reset_deteksi_stabil(id_jembatan):
    with _lock:
        data = _pembaca.get(id_jembatan)
        if data:
            data["riwayat"].update(berat_terakhir=None, waktu_mulai_stabil=None)
            data["state"].update(siap_kunci=False)


def semua_status():
    with _lock:
        return {id_j: _status(d) for id_j, d in _pembaca.items()}


def data_mentah(id_jembatan):
    """Bingkai terakhir yang diterima (Admin › Jembatan › Data mentah) untuk menyetel format di lokasi."""
    with _lock:
        data = _pembaca.get(id_jembatan)
        if not data:
            return None
        return {"status": _status(data), "baris": list(data["mentah"])[::-1], "sisa_buffer": data["buffer"][-120:]}


def konfigurasi(id_jembatan):
    with _lock:
        data = _pembaca.get(id_jembatan)
        return ({**{k: data["cfg"][k] for k in KUNCI_PORT}, "versi": data["versi"]}) if data else None
