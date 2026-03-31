import csv
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor

# ===== 配置区 =====
CSV_URL = "https://raw.githubusercontent.com/femboyenjoy/free-vless-VPN/refs/heads/main/nodes/cfcn/202603311900%E8%B5%84%E4%BA%A7%E6%95%B0%E6%8D%AE.csv"
THREADS = 50
TIMEOUT = 5

seen = set()

# 输出文件
HTTP_FILE = "http_proxy.txt"
HTTPS_FILE = "https_proxy.txt"
MIDDLE_PROXY_FILE = "middle_proxy.txt"  # 中转反代专用文件

def fetch_csv(url):
    print(f"[+] 下载CSV: {url}")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    lines = resp.text.splitlines()
    return list(csv.DictReader(lines))

def check(row):
    ip = row.get("ip", "").strip()
    port = row.get("port", "").strip()
    proto = row.get("protocol", "").strip().lower()  # 强制小写

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
            # 默认输出到原有文件
            file_path = HTTPS_FILE if proto == "https" else HTTP_FILE
            with open(file_path, "a") as f:
                f.write(f"{ip}:{port}\n")

            # 提取返回的 ip
            returned_ip = None
            for line in result.splitlines():
                if line.startswith("ip="):
                    returned_ip = line.split("=", 1)[1]
                    break

            # 判断是否中转反代
            if returned_ip and returned_ip != ip:
                print(f"[✔] 中转反代: {ip}:{port} ({proto}) -> 落地IP: {returned_ip}")
                with open(MIDDLE_PROXY_FILE, "a") as f:
                    f.write(f"{ip}:{port} ({proto}) -> 落地IP: {returned_ip}\n")
            else:
                print(f"[✔] 反代: {ip}:{port} ({proto})")

        else:
            print(f"[✘] 无效: {ip}:{port} ({proto})")

    except Exception as e:
        print(f"[!] 错误: {ip}:{port} ({proto}) - {e}")

def main():
    rows = fetch_csv(CSV_URL)

    print(f"[+] 共 {len(rows)} 条数据，开始检测...\n")

    # 清空旧文件
    open(HTTP_FILE, "w").close()
    open(HTTPS_FILE, "w").close()
    open(MIDDLE_PROXY_FILE, "w").close()

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        pool.map(check, rows)

    print("\n[+] 检测完成！")
    print(f"[+] HTTP反代已保存: {HTTP_FILE}")
    print(f"[+] HTTPS反代已保存: {HTTPS_FILE}")
    print(f"[+] 中转反代已保存: {MIDDLE_PROXY_FILE}")

if __name__ == "__main__":
    main()
