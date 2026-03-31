import csv
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor

# ===== 配置区 =====
CSV_URL = "https://example.com/data.csv"   # 👈 在这里填你的CSV链接
THREADS = 50
TIMEOUT = 5

seen = set()

def fetch_csv(url):
    print(f"[+] 下载CSV: {url}")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    lines = resp.text.splitlines()
    return list(csv.DictReader(lines))

def check(row):
    ip = row.get("ip", "").strip()
    port = row.get("port", "").strip()
    proto = row.get("protocol", "").strip()

    if not ip or not port or not proto:
        return

    key = f"{ip}:{port}"
    if key in seen:
        return
    seen.add(key)

    url = f"{proto}://www.visa.cn:{port}/cdn-cgi/trace"

    cmd = [
        "curl",
        "-s",
        "--max-time", str(TIMEOUT),
        "--connect-timeout", "3",
        "--resolve", f"www.visa.cn:{port}:{ip}",
        url
    ]

    try:
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()

        if "fl=" in result and "ip=" in result:
            print(f"[✔] 反代: {ip}:{port}")
        else:
            print(f"[✘] 无效: {ip}:{port}")

    except:
        print(f"[!] 错误: {ip}:{port}")

def main():
    rows = fetch_csv(CSV_URL)

    print(f"[+] 共 {len(rows)} 条数据，开始检测...\n")

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        pool.map(check, rows)

if __name__ == "__main__":
    main()
