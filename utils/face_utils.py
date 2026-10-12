import logging
import math
from functools import lru_cache

import face_recognition
import numpy as np

log = logging.getLogger(__name__)


@lru_cache(maxsize=40)
def _analisa(path):
    """(image, lokasi_wajah, landmarks) satu frame scan, dihitung SEKALI lalu dipakai ulang oleh cek kedip / menoleh
    dan pemilihan frame frontal (dulu tiap tahap membaca & mendeteksi ulang semua frame = lambat).
    Frame kamera sudah kecil (lebar 480) dan wajah besar di bingkai: deteksi tanpa upsample (~4x lebih cepat),
    upsample 1x hanya bila tidak ketemu. Path frame unik (uuid) dan dihapus setelah request."""
    image = face_recognition.load_image_file(path)
    lokasi = face_recognition.face_locations(image, number_of_times_to_upsample=0) \
        or face_recognition.face_locations(image, number_of_times_to_upsample=1)
    landmarks = face_recognition.face_landmarks(image, lokasi) if lokasi else []
    return image, lokasi, landmarks

def extract_embedding(image_path):
    # Baca gambar dan deteksi wajah
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)
    if len(encodings) == 0:
        return None
    return encodings[0]

def extract_embedding_tunggal(image_path):
    """Untuk pendaftaran personel: foto wajib berisi tepat 1 wajah. Kembalikan (embedding | None, jumlah_wajah)."""
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)
    return (encodings[0] if len(encodings) == 1 else None), len(encodings)

def embedding_to_binary(embedding):
    # Convert embedding (numpy array) jadi bytes
    return embedding.astype(np.float64).tobytes()

def binary_to_embedding(binary_data):
    # Convert bytes dari database balik jadi numpy array embedding
    return np.frombuffer(binary_data, dtype=np.float64)

def compare_faces(known_embedding, unknown_embedding, threshold=0.55):
    # Bandingkan dua embedding
    distance = np.linalg.norm(known_embedding - unknown_embedding)
    return distance <= threshold, distance

def hitung_ear(mata_points):
    mata_points = np.array(mata_points)
    A = np.linalg.norm(mata_points[1] - mata_points[5])
    B = np.linalg.norm(mata_points[2] - mata_points[4])
    C = np.linalg.norm(mata_points[0] - mata_points[3])
    ear = (A + B) / (2.0 * C)
    return ear

def deteksi_kedipan(list_filepath, threshold_ear=0.25):
    riwayat_ear = []

    for filepath in list_filepath:
        landmarks_list = _analisa(filepath)[2]

        if len(landmarks_list) == 0:
            continue

        landmarks = landmarks_list[0]
        if 'left_eye' not in landmarks or 'right_eye' not in landmarks:
            continue

        ear_kiri = hitung_ear(landmarks['left_eye'])
        ear_kanan = hitung_ear(landmarks['right_eye'])
        ear_rata = (ear_kiri + ear_kanan) / 2.0
        riwayat_ear.append(ear_rata)

    log.debug("Riwayat EAR: %s", riwayat_ear)

    if len(riwayat_ear) < 3:
        log.debug("Frame tidak cukup untuk analisis EAR")
        return False

    ear_minimum = min(riwayat_ear)
    ear_maksimum = max(riwayat_ear)
    log.debug("EAR min: %s, max: %s", ear_minimum, ear_maksimum)

    return ear_minimum < threshold_ear and ear_maksimum > threshold_ear

def hitung_rasio_yaw(landmarks):
    """Rasio jarak hidung ke mata kiri vs kanan, untuk deteksi arah hadap wajah."""
    nose_x = sum(p[0] for p in landmarks['nose_tip']) / len(landmarks['nose_tip'])
    left_eye_x = min(p[0] for p in landmarks['left_eye'])
    right_eye_x = max(p[0] for p in landmarks['right_eye'])

    jarak_ke_kiri = abs(nose_x - left_eye_x)
    jarak_ke_kanan = abs(nose_x - right_eye_x)

    return jarak_ke_kiri / (jarak_ke_kanan + 1e-6)

def deteksi_menoleh(list_filepath, arah, ambang_perubahan=0.3):
    riwayat_rasio = []

    for filepath in list_filepath:
        landmarks_list = _analisa(filepath)[2]

        if len(landmarks_list) == 0:
            continue

        landmarks = landmarks_list[0]
        if 'nose_tip' not in landmarks or 'left_eye' not in landmarks or 'right_eye' not in landmarks:
            continue

        riwayat_rasio.append(hitung_rasio_yaw(landmarks))

    log.debug("Arah: %s, riwayat rasio: %s", arah, riwayat_rasio)

    if len(riwayat_rasio) < 3:
        return False

    baseline = riwayat_rasio[0] 
    perubahan_max = max(abs(r - baseline) / baseline for r in riwayat_rasio)

    log.debug("Baseline: %s, perubahan maksimum: %s", baseline, perubahan_max)

    return perubahan_max > ambang_perubahan

EAR_MEREM = 0.2


def embedding_frontal(list_filepath, jumlah=2):
    """Embedding dari frame scan yang paling MENGHADAP KAMERA dengan mata terbuka.

    Frame tengah rekaman tantangan biasanya wajah menoleh / mata terpejam; embedding dari frame seperti itu
    tidak khas dan bisa tertukar dengan wajah orang lain. Yang dinilai: frame awal & akhir rekaman
    (sebelum / sesudah tantangan). Kembalikan (embeddings dari `jumlah` frame terbaik, jumlah wajah terbanyak
    dalam satu frame, path frame terbaik untuk foto bukti). embeddings kosong = wajah tidak terdeteksi."""
    urutan = list(dict.fromkeys(list_filepath[:3] + list_filepath[-2:]))
    kandidat, wajah_maks = [], 0
    for path in urutan:
        image, lokasi, lm = _analisa(path)
        wajah_maks = max(wajah_maks, len(lokasi))
        if len(lokasi) != 1:
            continue
        if not lm or not all(k in lm[0] for k in ("nose_tip", "left_eye", "right_eye")):
            continue
        skor = abs(math.log(max(hitung_rasio_yaw(lm[0]), 1e-3)))          # 0 = lurus menghadap kamera
        if (hitung_ear(lm[0]["left_eye"]) + hitung_ear(lm[0]["right_eye"])) / 2 < EAR_MEREM:
            skor += 1                                                     # mata terpejam: pilihan terakhir
        kandidat.append((skor, path, image, lokasi))
    kandidat.sort(key=lambda k: k[0])
    embeddings = [face_recognition.face_encodings(image, lokasi)[0] for _, _, image, lokasi in kandidat[:jumlah]]
    return embeddings, wajah_maks, (kandidat[0][1] if kandidat else None)


TANTANGAN_VALID = ("KEDIP", "MENOLEH_KIRI", "MENOLEH_KANAN")
TANPA_TANTANGAN = "TANPA"


def cek_liveness(list_filepath, tantangan, wajib):
    """Pengaturan per area (TANTANGAN_*). Wajib: tantangan acak harus valid & lolos. Tidak wajib: cukup menghadap
    kamera (adanya tepat satu wajah dicek pemanggil saat mengambil embedding)."""
    if not wajib:
        return True
    return tantangan in TANTANGAN_VALID and verifikasi_liveness(list_filepath, tantangan)


def verifikasi_liveness(list_filepath, tantangan):
    if tantangan == "KEDIP":
        return deteksi_kedipan(list_filepath)
    elif tantangan in ("MENOLEH_KANAN", "MENOLEH_KIRI"):
        return deteksi_menoleh(list_filepath, tantangan)
    else:
        return False