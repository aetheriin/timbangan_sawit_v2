import io
import os
import random
import time
import cv2
import face_recognition
import mediapipe as mp
import numpy as np
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("WEIGHBRIDGE_URL", "http://127.0.0.1:5000")
SERVER_URL = f"{BASE_URL}/api/verifikasi-wajah"
URL_TRIGGER = f"{BASE_URL}/api/kamera/status"
URL_BATAL = f"{BASE_URL}/api/kamera/batal"
# Token perangkat (sama dengan KIOSK_TOKEN di .env server). Kosong = kiosk di PC yang sama dengan server.
HEADER_KIOSK = {"X-Kiosk-Token": os.getenv("KIOSK_TOKEN", ""), "X-Kiosk-Id": os.getenv("KIOSK_ID", "UTAMA")}
KAMERA_INDEX = 0
# ===== Waktu scan wajah (detik) =====
HITUNG_MUNDUR = 3            # "Bersiap... 3 2 1" sebelum perintah kedip / menoleh muncul
BATAS_TANTANGAN = 10         # waktu supir untuk mengikuti perintah, lewat dari ini diulang
JEDA_REKAM = 0.12            # selama perintah berjalan, 1 foto direkam tiap 0,12 detik
REKAM_SETELAH = 0.6          # setelah gerakan terdeteksi, tetap merekam sebentar (mata terbuka / wajah kembali)
MAKS_KIRIM = 16              # foto yang dikirim ke server (server menerima maks. 20)
MAKS_PERCOBAAN = 3           # liveness gagal -> diulang otomatis sampai sekian kali
JEDA_ULANG = 2               # lama pesan "diulang" tampil
DURASI_TAMPIL_HASIL = 5
EAR_KEDIP = 0.21             # mata dianggap tertutup bila EAR di bawah ini (MediaPipe)
TEKS_TANTANGAN = {
    "KEDIP": ("Silakan KEDIPKAN MATA", "Kedip sekali seperti biasa"),
    "MENOLEH_KANAN": ("Silakan MENOLEH ke KANAN", "Tahan sebentar lalu kembali lurus"),
    "MENOLEH_KIRI": ("Silakan MENOLEH ke KIRI", "Tahan sebentar lalu kembali lurus"),
}
NAMA_JENDELA = "Verifikasi Supir - Timbangan"

# Inisialisasi MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# Indeks landmark mata
EYE_LEFT = [362, 385, 387, 263, 373, 380]
EYE_RIGHT = [33, 160, 158, 133, 153, 144]

def frame_ke_bytes(frame):
  """Convert frame OpenCV (numpy array) jadi bytes JPEG untuk dikirim via HTTP."""
  ret, buffer = cv2.imencode('.jpg', frame)
  return io.BytesIO(buffer.tobytes())

def kirim_ke_server(frames, tantangan):
  """Kembalikan (kode_http, json). Kode 0 = server tidak bisa dihubungi."""
  files = []
  for i, frame in enumerate(frames):
    buf = frame_ke_bytes(frame)
    files.append(('frames', (f'frame{i}.jpg', buf, 'image/jpeg')))

  try:
    response = requests.post(
        SERVER_URL, files=files, data={'tantangan': tantangan}, headers=HEADER_KIOSK, timeout=60
    )
    return response.status_code, response.json()
  except Exception as e:
    return 0, {'error': f'Gagal menghubungi server: {e}'}

def pilih_frame(rekaman, idx_kunci, maks=MAKS_KIRIM):
  """Foto yang dikirim: awal perintah (pembanding wajah lurus / mata terbuka), sekitar gerakan, dan sesudahnya."""
  n = len(rekaman)
  if n <= maks:
    return list(rekaman)
  indeks = {0, n - 1} | {i for i in range(idx_kunci - 2, idx_kunci + 3) if 0 <= i < n}
  for i in (round(k * (n - 1) / (maks - 1)) for k in range(maks)):
    if len(indeks) >= maks:
      break
    indeks.add(i)
  return [rekaman[i] for i in sorted(indeks)]

def gambar_kotak_wajah(frame, lokasi_wajah):
  for top, right, bottom, left in lokasi_wajah:
    cv2.rectangle(frame, (left, top), (right, bottom), (0, 200, 0), 2)

def hitung_ear(landmarks, indeks_mata, w, h):
  """Menghitung Eye Aspect Ratio (EAR) untuk deteksi kedipan."""
  p = []
  for idx in indeks_mata:
    pt = landmarks[idx]
    p.append(np.array([pt.x * w, pt.y * h]))

  d_v1 = np.linalg.norm(p[1] - p[5])
  d_v2 = np.linalg.norm(p[2] - p[4])
  d_h = np.linalg.norm(p[0] - p[3])

  return (d_v1 + d_v2) / (2.0 * d_h)

def cek_liveness_lokal(frame):
  """Memeriksa apakah wajah menghadap depan dan sedang berkedip."""
  h, w, _ = frame.shape
  rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
  results = face_mesh.process(rgb_frame)

  menghadap_depan = False
  kedip = False

  if results.multi_face_landmarks:
    landmarks = results.multi_face_landmarks[0].landmark

    # Cek wajah lurus ke depan
    hidung = landmarks[1].x * w
    mata_kiri = landmarks[263].x * w
    mata_kanan = landmarks[33].x * w
    jarak_kiri = abs(hidung - mata_kiri)
    jarak_kanan = abs(hidung - mata_kanan)
    rasio = jarak_kiri / (jarak_kanan + 1e-6)

    if 0.65 <= rasio <= 1.35:
      menghadap_depan = True

    # Cek kedipan mata
    ear_kiri = hitung_ear(landmarks, EYE_LEFT, w, h)
    ear_kanan = hitung_ear(landmarks, EYE_RIGHT, w, h)
    avg_ear = (ear_kiri + ear_kanan) / 2.0

    if avg_ear < 0.21:  # Batas kelopak mata berkedip
      kedip = True

  return menghadap_depan, kedip

def cek_arah_wajah(landmarks, w):
  """Return rasio untuk deteksi arah hadap: <1 menoleh kanan, >1 menoleh kiri, ~1 lurus."""
  hidung = landmarks[1].x * w
  mata_kiri = landmarks[263].x * w
  mata_kanan = landmarks[33].x * w
  jarak_kiri = abs(hidung - mata_kiri)
  jarak_kanan = abs(hidung - mata_kanan)
  return jarak_kiri / (jarak_kanan + 1e-6)

def gambar_banner_status(frame, teks_utama, teks_sub='', warna_bg=(0, 0, 0)):
  """Menggambar banner transparan di bagian atas agar teks rapi & proporsional."""
  h, w = frame.shape[:2]

  skala_utama = max(0.45, w / 1100.0)
  skala_sub = max(0.35, w / 1400.0)
  tebal = 1 if w < 640 else 2

  overlay = frame.copy()
  tinggi_banner = int(h * 0.15) if teks_sub else int(h * 0.10)
  cv2.rectangle(overlay, (0, 0), (w, tinggi_banner), warna_bg, -1)
  cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

  cv2.putText(
      frame,
      teks_utama,
      (20, int(tinggi_banner * 0.5)),
      cv2.FONT_HERSHEY_SIMPLEX,
      skala_utama,
      (255, 255, 255),
      tebal,
      cv2.LINE_AA,
  )

  if teks_sub:
    cv2.putText(
        frame,
        teks_sub,
        (20, int(tinggi_banner * 0.85)),
        cv2.FONT_HERSHEY_SIMPLEX,
        skala_sub,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )

def gambar_overlay_hasil(frame, teks_utama, teks_sub, warna):
  """Tampilan penuh saat hasil respons dari server muncul."""
  h, w = frame.shape[:2]
  overlay = frame.copy()
  cv2.rectangle(overlay, (0, 0), (w, h), warna, -1)
  cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

  skala_utama = max(0.6, w / 800.0)
  skala_sub = max(0.45, w / 1100.0)

  cv2.putText(
      frame,
      teks_utama,
      (30, h // 2 - 10),
      cv2.FONT_HERSHEY_SIMPLEX,
      skala_utama,
      (255, 255, 255),
      2,
      cv2.LINE_AA,
  )
  cv2.putText(
      frame,
      teks_sub,
      (30, h // 2 + 35),
      cv2.FONT_HERSHEY_SIMPLEX,
      skala_sub,
      (255, 255, 255),
      1,
      cv2.LINE_AA,
  )

def jendela_masih_terbuka():
  try:
    return cv2.getWindowProperty(NAMA_JENDELA, cv2.WND_PROP_VISIBLE) >= 1
  except cv2.error:
    return False

def notify_batal_to_server():
    """Memberitahu server Flask bahwa scan dibatalkan agar status camera_trigger_state di-reset."""
    try:
        requests.post(URL_BATAL, headers=HEADER_KIOSK, timeout=2)
        print("[!] Scan dibatalkan oleh pengguna. Mengirim sinyal reset ke server...")
    except Exception:
        pass

def jalankan_verifikasi_wajah():
    """Cari wajah -> wajah lurus -> hitung mundur -> perintah (kedip / menoleh) SAMBIL merekam -> kirim ke server.

    Foto yang dikirim diambil selama supir mengikuti perintah, jadi gerakannya ikut terekam dan bisa diperiksa
    server. Bila server menolak (liveness / wajah tidak jelas), perintah baru diberikan otomatis."""
    video = cv2.VideoCapture(KAMERA_INDEX)
    if not video.isOpened():
        print("Gagal membuka kamera. Cek KAMERA_INDEX atau koneksi webcam.")
        notify_batal_to_server()
        return

    cv2.namedWindow(NAMA_JENDELA, cv2.WINDOW_NORMAL)

    status, waktu_status = "CARI_WAJAH", time.time()
    percobaan = 1
    tantangan = None
    rekaman, idx_kunci, idx_tutup, waktu_kunci, waktu_rekam = [], None, None, 0.0, 0.0
    mata_tertutup, ear_terkecil = False, 1.0
    pesan_ulang = ""
    hasil_terakhir = None
    gagal_baca_beruntun = 0
    dibatalkan_manual = False

    while True:
        # Cek jika pengguna menutup jendela via tombol [X]
        if not jendela_masih_terbuka():
            print("Jendela ditutup oleh pengguna (Tombol X).")
            dibatalkan_manual = True
            break

        ret, frame = video.read()
        if not ret or frame is None:
            gagal_baca_beruntun += 1
            if gagal_baca_beruntun >= 10:
                print("Kamera tidak mengirim gambar valid.")
                dibatalkan_manual = True
                break
            if cv2.waitKey(1) & 0xFF == ord('q'):
                dibatalkan_manual = True
                break
            continue

        gagal_baca_beruntun = 0
        frame = cv2.flip(frame, 1)
        bersih = frame.copy()                      # foto tanpa tulisan, ini yang dikirim ke server
        sekarang = time.time()
        lama = sekarang - waktu_status

        # 1. Tunggu wajah terlihat
        if status == "CARI_WAJAH":
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            lokasi_wajah = face_recognition.face_locations(small_frame)
            gambar_kotak_wajah(frame, [(t*2, r*2, b*2, l*2) for (t, r, b, l) in lokasi_wajah])
            gambar_banner_status(frame, "Arahkan wajah ke kamera...", "Pastikan wajah terlihat jelas (Tekan 'Q' / X untuk batal)", (0, 0, 0))
            if lokasi_wajah:
                status, waktu_status = "WAJAH_LURUS", sekarang

        # 2. Wajah harus lurus ke depan
        elif status == "WAJAH_LURUS":
            lurus, _ = cek_liveness_lokal(bersih)
            if lurus:
                status, waktu_status = "HITUNG_MUNDUR", sekarang
            else:
                gambar_banner_status(frame, "Silakan menghadap lurus ke kamera", "Posisikan wajah lurus ke depan", (0, 50, 150))

        # 3. Hitung mundur supaya supir siap
        elif status == "HITUNG_MUNDUR":
            sisa = HITUNG_MUNDUR - int(lama)
            if sisa > 0:
                gambar_banner_status(frame, f"Bersiap... {sisa}",
                                     f"Percobaan {percobaan} dari {MAKS_PERCOBAAN} - ikuti perintah yang muncul", (0, 100, 0))
            else:
                tantangan = random.choice(list(TEKS_TANTANGAN))
                rekaman, idx_kunci, idx_tutup, waktu_rekam = [], None, None, 0.0
                mata_tertutup, ear_terkecil = False, 1.0
                status, waktu_status = "TANTANGAN", sekarang

        # 4. Perintah liveness: foto direkam selama supir bergerak
        elif status == "TANTANGAN":
            judul, sub = TEKS_TANTANGAN[tantangan]
            simpan = sekarang - waktu_rekam >= JEDA_REKAM
            jadi_kunci = False

            if idx_kunci is None:
                results = face_mesh.process(cv2.cvtColor(bersih, cv2.COLOR_BGR2RGB))
                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0].landmark
                    h, w, _ = bersih.shape
                    if tantangan == "KEDIP":
                        ear = (hitung_ear(landmarks, EYE_LEFT, w, h) + hitung_ear(landmarks, EYE_RIGHT, w, h)) / 2.0
                        if ear < EAR_KEDIP:
                            mata_tertutup = True
                            if ear < ear_terkecil:          # foto mata paling tertutup selalu disimpan
                                ear_terkecil, simpan, jadi_kunci = ear, True, True
                        elif mata_tertutup and idx_tutup is not None:    # terbuka lagi -> kedip lengkap
                            idx_kunci, waktu_kunci = idx_tutup, sekarang
                    else:
                        rasio = cek_arah_wajah(landmarks, w)
                        if (tantangan == "MENOLEH_KANAN" and rasio < 0.6) or (tantangan == "MENOLEH_KIRI" and rasio > 1.8):
                            simpan, jadi_kunci = True, True
                            waktu_kunci = sekarang

            if simpan:
                rekaman.append(bersih)
                waktu_rekam = sekarang
                if jadi_kunci:
                    if tantangan == "KEDIP":
                        idx_tutup = len(rekaman) - 1
                    else:
                        idx_kunci = len(rekaman) - 1

            gambar_banner_status(frame, judul, sub, (0, 120, 180))

            if idx_kunci is not None and sekarang - waktu_kunci >= REKAM_SETELAH:
                gambar_banner_status(frame, "Memverifikasi... Mohon tunggu", "Mengirim data ke server...", (0, 100, 200))
                cv2.imshow(NAMA_JENDELA, frame)
                cv2.waitKey(1)
                kode, hasil_terakhir = kirim_ke_server(pilih_frame(rekaman, idx_kunci), tantangan)
                rekaman = []
                if kode == 400 and percobaan < MAKS_PERCOBAAN:      # liveness / wajah tidak jelas -> ulang
                    percobaan += 1
                    pesan_ulang = hasil_terakhir.get("error", "Belum berhasil")
                    status, waktu_status = "ULANG", time.time()
                else:
                    status, waktu_status = "HASIL", time.time()
                continue
            if idx_kunci is None and lama > BATAS_TANTANGAN:
                rekaman = []
                if percobaan < MAKS_PERCOBAAN:
                    percobaan += 1
                    pesan_ulang = "Gerakan tidak terdeteksi"
                    status, waktu_status = "ULANG", sekarang
                else:
                    hasil_terakhir = {"error": "Gerakan tidak terdeteksi"}
                    status, waktu_status = "HASIL", sekarang

        # 5. Gagal tapi masih ada kesempatan
        elif status == "ULANG":
            gambar_banner_status(frame, f"Belum berhasil: {pesan_ulang}",
                                 f"Diulang... percobaan {percobaan} dari {MAKS_PERCOBAAN}", (30, 30, 130))
            if lama > JEDA_ULANG:
                status, waktu_status = "WAJAH_LURUS", sekarang

        # 6. Hasil dari server
        elif status == "HASIL":
            if hasil_terakhir and hasil_terakhir.get("message"):
                gambar_overlay_hasil(frame, hasil_terakhir["message"], "Terima kasih! Menutup kamera...", (30, 100, 30))
            else:
                err_msg = hasil_terakhir.get("error", "Gagal Verifikasi") if hasil_terakhir else "Error"
                gambar_overlay_hasil(frame, err_msg, "Minta Security menekan Scan lagi", (30, 30, 130))

            if lama > DURASI_TAMPIL_HASIL:
                print("[+] Verifikasi selesai. Menutup jendela kamera...")
                break

        cv2.imshow(NAMA_JENDELA, frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            dibatalkan_manual = True
            break

    video.release()
    cv2.destroyAllWindows()
    cv2.waitKey(1)

    # Dibatalkan (tombol X / Q) atau gagal: permintaan scan di server diakhiri supaya kamera tidak terbuka lagi
    if dibatalkan_manual or not (hasil_terakhir and hasil_terakhir.get("message")):
        notify_batal_to_server()


def main():
  """Main Loop Background Service untuk menunggu trigger dari Pos Security."""
  print("===========================================================")
  print("  KIOSK CAMERA SERVICE STANDBY - MENUNGGU TRIGGER SECURITY ")
  print("===========================================================")

  try:
    while True:
      try:
        # Pengecekan status trigger ke server Flask
        res = requests.get(URL_TRIGGER, headers=HEADER_KIOSK, timeout=2).json()

        if res.get("is_active") is True:
          print("\n[!] Sinyal diterima dari Security! Membuka kamera...")
          jalankan_verifikasi_wajah()
          print("[+] Kamera ditutup. Kembali ke mode siaga...\n")

      except requests.exceptions.RequestException:
        # Abaikan error jika server app.py belum dinyalakan/berjalan
        pass

      # Jeda 1 detik agar penggunaan CPU tetap ringan
      time.sleep(1)

  except KeyboardInterrupt:
    print("\nProgram dihentikan oleh pengguna. Keluar...")


if __name__ == "__main__":
  main()