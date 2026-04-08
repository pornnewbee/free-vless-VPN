import csv
import requests
import re
from concurrent.futures import ThreadPoolExecutor

# ===== 配置 =====
INPUT_URLS = [
    "https://github.com/femboyenjoy/free-vless-VPN/raw/refs/heads/main/nodes/cfcn/raw/http1.txt"
]

THREADS = 10
TIMEOUT = 10

OUTPUT_FILE = "ips.txt"

# ================== 解析 ==================

def smart_extract(text):
    rows = []
    matches = re.findall(
        r'(?:(https?)://)?(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?',
        text,
        re.IGNORECASE
    )

    for proto, ip, port in matches:
        proto = proto.lower() if proto else None

        if not port:
            port = "443" if proto == "https" else "80"

        if not proto:
            rows.append((ip, port, "http"))
            rows.append((ip, port, "https"))
        else:
            rows.append((ip, port, proto))

    return rows


def parse_scan_text(text):
    rows = []
    blocks = re.split(r'(?=https?://)', text)

    for block in blocks:
        if "cf-ray" not in block.lower():
            continue

        m = re.search(r'(https?)://([\d\.]+)(?::(\d+))?', block)
        if not m:
            continue

        proto, ip, port = m.groups()
        if not port:
            port = "443" if proto == "https" else "80"

        rows.append((ip, port, proto))

    return rows


def parse_middle_text(text):
    rows = []
    for line in text.splitlines():
        if "->" not in line:
            continue

        try:
            src, _ = line.split("->", 1)

            ip_port_proto = src.strip()
            if "(" in ip_port_proto:
                ip_port, proto = ip_port_proto.split("(")
                proto = proto.replace(")", "").strip()
            else:
                ip_port = ip_port_proto
                proto = "http"

            ip, port = ip_port.strip().split(":")
            rows.append((ip, port, proto))
        except:
            continue

    return rows


def parse_csv(text):
    rows = []
    reader = csv.DictReader(text.splitlines())

    for r in reader:
        ip = r.get("ip", "").strip()
        port = r.get("port", "").strip()
        proto = r.get("protocol", "").lower()

        if not ip or not port:
            continue

        if proto in ("http", "https"):
            rows.append((ip, port, proto))
        else:
            rows.append((ip, port, "http"))
            rows.append((ip, port, "https"))

    return rows


# ================== 下载 ==================

def fetch_one(url):
    try:
        print(f"[+] 下载: {url}")
        text = requests.get(url, timeout=TIMEOUT).text

        if "->" in text:
            return parse_middle_text(text)

        if "ip" in text.splitlines()[0].lower():
            return parse_csv(text)

        if "cf-ray" in text.lower():
            rows = parse_scan_text(text)
            if rows:
                return rows

        return smart_extract(text)

    except Exception as e:
        print(f"[ERR] {url} | {e}")
        return []


def main():
    all_rows = []

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        results = pool.map(fetch_one, INPUT_URLS)

    for r in results:
        all_rows.extend(r)

    # 去重
    all_rows = list(set(all_rows))

    print(f"[+] 总条目: {len(all_rows)}")

    # 输出
    with open(OUTPUT_FILE, "w") as f:
        for ip, port, proto in sorted(all_rows):
            f.write(f"{ip}:{port}:{proto}\n")

    print(f"[+] 已写入 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
