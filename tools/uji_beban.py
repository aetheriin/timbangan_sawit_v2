"""Uji beban sederhana: mensimulasikan beberapa PC membuka aplikasi bersamaan.

Contoh (aplikasi harus sudah jalan, sebaiknya lewat serve.py):
    python tools/uji_beban.py --url http://127.0.0.1:5000 --user ho --password ho12345 --pc 10 --detik 30

Setiap "PC" login sendiri lalu mengulang: status timbangan (seperti tab Timbangan, 2x/detik),
list tiket aktif, dan history driver. Hasil: jumlah request, error, dan waktu respons p50/p95/maks."""
import argparse
import statistics
import threading
import time
import requests

ENDPOINT = [
    ("/api/timbang/status", 0.5),
    ("/api/security/list-tiket-aktif", 5),
    ("/api/security/history-driver", 10),
    ("/health", 10),
]


def pc(args, hasil, kunci):
    s = requests.Session()
    s.post(f"{args.url}/login", data={"username": args.user, "password": args.password}, timeout=10)
    selesai, berikut = time.time() + args.detik, {e: 0.0 for e, _ in ENDPOINT}
    while time.time() < selesai:
        sekarang = time.time()
        for ep, jeda in ENDPOINT:
            if sekarang < berikut[ep]:
                continue
            berikut[ep] = sekarang + jeda
            mulai = time.perf_counter()
            try:
                ok = s.get(f"{args.url}{ep}", timeout=10).status_code < 500
            except requests.RequestException:
                ok = False
            ms = (time.perf_counter() - mulai) * 1000
            with kunci:
                hasil.setdefault(ep, []).append((ms, ok))
        time.sleep(0.05)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:5000")
    p.add_argument("--user", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--pc", type=int, default=5)
    p.add_argument("--detik", type=int, default=30)
    args = p.parse_args()

    hasil, kunci = {}, threading.Lock()
    threads = [threading.Thread(target=pc, args=(args, hasil, kunci)) for _ in range(args.pc)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"\n{args.pc} PC x {args.detik} detik")
    print(f"{'Endpoint':38} {'req':>6} {'error':>6} {'p50 ms':>8} {'p95 ms':>8} {'maks ms':>8}")
    for ep, data in hasil.items():
        waktu = sorted(ms for ms, _ in data)
        p95 = waktu[int(len(waktu) * 0.95) - 1] if len(waktu) > 1 else waktu[0]
        print(f"{ep:38} {len(data):>6} {sum(1 for _, ok in data if not ok):>6} "
              f"{statistics.median(waktu):>8.0f} {p95:>8.0f} {max(waktu):>8.0f}")


if __name__ == "__main__":
    main()
