import csv
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor

THREADS = 50

def fetch_csv(url):
    print(f"[+] 下载CSV: {url}")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    lines = resp.text.splitlines()
    return list(csv.DictReader(lines))

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
    url = input("请输入CSV链接: ").strip()

    rows = fetch_csv(url)

    print(f"[+] 共 {len(rows)} 条数据，开始检测...\n")

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        pool.map(check, rows)

if __name__ == "__main__":
    main()
