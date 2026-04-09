import re
import csv
import requests
from concurrent.futures import ThreadPoolExecutor

# ===== 配置 =====
INPUT_URLS = [
    "https://github.com/femboyenjoy/free-vless-VPN/raw/refs/heads/main/nodes/cfcn/raw/http1.txt",
    "https://github.com/femboyenjoy/free-vless-VPN/raw/refs/heads/main/nodes/cfcn/raw/http2.txt",
    "https://github.com/femboyenjoy/free-vless-VPN/raw/refs/heads/main/nodes/cfcn/raw/http3.txt",
]
THREADS = 50
TIMEOUT = 5

# ===== 解析函数 =====

def parse_block_text(text):
    """
    解析块状文本（旧版格式 + cf-ray 过滤）
    """
    rows = []
    blocks = re.split(r'\n(?=\d{1,3}(?:\.\d{1,3}){3})', text)
    for block in blocks:
        if "cf-ray" not in block.lower():
            continue

        ip = port = proto = None

        # https://IP:PORT
        m = re.search(r'(https?)://(\d{1,3}(?:\.\d{1,3}){3}):(\d+)', block)
        if m:
            proto, ip, port = m.groups()
            rows.append((ip, port, proto))
            continue

        # IP:PORT 直接格式
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

        if ip and port:
            proto = "https" if "https://" in block.lower() or "http/2" in block.lower() else "http"
            rows.append((ip, port, proto))
    return rows

def parse_scan_text(text):
    """
    解析扫描日志，仅保留含 Cf-Ray 的块
    """
    rows = []
    blocks = re.split(r'(?=https?://)', text)
    for block in blocks:
        block = block.strip()
        if not block or "cf-ray" not in block.lower():
            continue
        m = re.search(r'(https?)://([\d\.]+)(?::(\d+))?', block)
        if not m:
            continue
        proto, ip, port = m.groups()
        if not port:
            port = "443" if proto == "https" else "80"
        rows.append((ip, port, proto))
    return rows

def parse_csv(text):
    """
    解析 CSV 格式
    """
    rows = []
    reader = csv.DictReader(text.splitlines())
    for r in reader:
        ip = r.get("ip", "").strip()
        port = r.get("port", "").strip()
        proto = r.get("protocol", "").strip().lower()
        if not ip or not port:
            continue
        if proto in ("http", "https"):
            rows.append((ip, port, proto))
        else:
            rows.append((ip, port, "http"))
            rows.append((ip, port, "https"))
    return rows

def parse_middle_text(text):
    """
    解析中转落地 IP 格式
    103.44.255.90:443 (https) -> 落地IP: 154.23.128.6
    返回 (源IP, 端口, 协议, 落地IP)
    """
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "->" not in line:
            continue
        if not re.match(r"^\d+\.\d+\.\d+\.\d+:\d+", line):
            continue
        try:
            src, dst = line.split("->", 1)
            ip_port_proto = src.strip()
            if "(" in ip_port_proto and ")" in ip_port_proto:
                ip_port, proto = ip_port_proto.split("(")
                proto = proto.replace(")", "").strip().lower()
            else:
                ip_port = ip_port_proto
                proto = "http"
            ip, port = ip_port.split(":", 1)
            dst_ip = dst.split(":")[-1].strip()
            rows.append((ip, port, proto, dst_ip))
        except Exception as e:
            print(f"[WARN] 解析中转行失败: {line} | {e}")
    return rows

# ===== 下载并解析 URL =====
def fetch_url(url):
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        text = resp.text
        result = []
        result.extend(parse_block_text(text))
        result.extend(parse_scan_text(text))
        try:
            result.extend(parse_csv(text))
        except Exception:
            pass
        result.extend(parse_middle_text(text))
        return result
    except Exception as e:
        print(f"[ERROR] {url} -> {e}")
        return []

# ===== 主函数 =====
def main():
    all_rows = []

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(fetch_url, url) for url in INPUT_URLS]
        for future in futures:
            res = future.result()
            if res:
                all_rows.extend(res)

    # 去重
    all_rows = list(set(all_rows))

    # 输出到终端
    for row in all_rows:
        print(row)

    # ✅ 输出到文件 all.txt，只写 IP:PORT 协议格式
    with open("all.txt", "w", encoding="utf-8") as f:
        for row in all_rows:
            # 支持 parse_middle_text 的四元组，如果有第四个元素，写成 源IP:端口 协议
            if len(row) == 4:
                ip, port, proto, _ = row
            else:
                ip, port, proto = row
            f.write(f"{ip}:{port} {proto}\n")

if __name__ == "__main__":
    main()
