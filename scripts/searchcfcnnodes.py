import csv
import subprocess
from concurrent.futures import ThreadPoolExecutor

INPUT_FILE = "data.csv"
THREADS = 50

def check(row):
    ip = row["ip"]
    port = row["port"]
    proto = row["protocol"]

    url = f"{proto}://www.visa.cn:{port}/cdn-cgi/trace"

    cmd = [
        "curl",
        "-s",
        "--max-time", "5",
        "--resolve", f"www.visa.cn:{port}:{ip}",
        url
    ]

    try:
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()

        if "fl=" in result and "ip=" in result:
            print(f"[✔] 反代: {ip}:{port}")
            return ip, port
        else:
            print(f"[✘] 无效: {ip}:{port}")

    except:
        print(f"[!] 错误: {ip}:{port}")

def main():
    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        pool.map(check, rows)

if __name__ == "__main__":
    main()
