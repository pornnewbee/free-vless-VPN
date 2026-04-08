import re
import requests
from concurrent.futures import ThreadPoolExecutor

# ===== 配置 =====
INPUT_URLS = [
    # 你可以放多个源
    "https://your-source.com/data.txt"
]
THREADS = 50
TIMEOUT = 5

# ===== 核心解析函数 =====
def parse_fofa_text(text):
    rows = []

    # 按 IP 开头分块
    blocks = re.split(r'\n(?=\d{1,3}(?:\.\d{1,3}){3})', text)

    for block in blocks:
        block_lower = block.lower()

        # 必须含 cf-ray
        if "cf-ray" not in block_lower:
            continue

        ip = None
        port = None
        proto = None

        # https://IP:PORT
        m = re.search(r'(https?)://(\d{1,3}(?:\.\d{1,3}){3}):(\d+)', block)
        if m:
            proto, ip, port = m.groups()
            rows.append((ip, port, proto))
            continue

        # IP:PORT
        m = re.search(r'(\d{1,3}(?:\.\d{1,3}){3}):(\d+)', block)
        if m:
            ip, port = m.groups()

        # IP + 下一行 PORT
        if not ip:
            m_ip = re.search(r'\b(\d{1,3}(?:\.\d{1,3}){3})\b', block)
            if m_ip:
                ip = m_ip.group(1)
        if ip and not port:
            m_port = re.search(r'\n(\d{2,5})(?:\n|$)', block)
            if m_port:
                port = m_port.group(1)

        if not ip or not port:
            continue

        # 协议判断
        if "https://" in block_lower or "http/2" in block_lower:
            proto = "https"
        else:
            proto = "http"

        rows.append((ip, port, proto))

    return rows

# ===== 下载单个 URL =====
def fetch_url(url):
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            return parse_fofa_text(resp.text)
    except Exception as e:
        print(f"[ERROR] {url} -> {e}")
    return []

# ===== 主函数 =====
def main():
    all_rows = []

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(fetch_url, url) for url in INPUT_URLS]
        for future in futures:
            result = future.result()
            if result:
                all_rows.extend(result)

    # 去重
    all_rows = list(set(all_rows))

    # 输出
    for ip, port, proto in all_rows:
        print(f"{ip}:{port}:{proto}")

if __name__ == "__main__":
    main()
