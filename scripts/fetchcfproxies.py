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
    结构优先端口提取（严格按行位置，不全局扫描）
    """

    rows = []

    total_blocks = 0
    cf_blocks = 0
    parsed_blocks = 0
    failed_blocks = 0

    # 更稳切块：以 IP 开头
    blocks = re.split(r'(?m)^(?=\d{1,3}(?:\.\d{1,3}){3})', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        total_blocks += 1

        # 必须是 CF
        if "cf-ray" not in block.lower():
            continue

        cf_blocks += 1

        lines = [l.strip() for l in block.splitlines() if l.strip()]

        ip = None
        port = None

        # =========================
        # ✅ 1. 第一行：IP:PORT
        # =========================
        first = lines[0]

        m = re.match(r'^(\d{1,3}(?:\.\d{1,3}){3}):(\d+)', first)
        if m:
            ip, port = m.groups()

        # =========================
        # ✅ 2. 第一行是 IP
        # =========================
        if not ip and re.match(r'^\d{1,3}(?:\.\d{1,3}){3}$', first):
            ip = first

            # ===== 第二行找端口 =====
            if len(lines) > 1:
                line2 = lines[1]

                # 80 / 8880 / 80http
                m = re.match(r'^(\d{2,5})', line2)
                if m:
                    port = m.group(1)

            # ===== 第三行兜底 =====
            if not port and len(lines) > 2:
                line3 = lines[2]

                # 跳过 token 行（含字母/符号）
                if re.match(r'^\d{2,5}$', line3):
                    port = line3

        # =========================
        # ❌ 不再做全块扫描端口（避免误判）
        # =========================

        # =========================
        # ✅ 成功
        # =========================
        if ip and port:
            rows.append((ip, port, "http"))
            rows.append((ip, port, "https"))
            parsed_blocks += 1
        else:
            failed_blocks += 1
            if ip:
                print(f"[失败] 无法提取端口: {ip}")

    # =========================
    # 📊 统计
    # =========================
    print(
        f"[parse_block_text] 总块:{total_blocks} | "
        f"CF块:{cf_blocks} | "
        f"成功:{parsed_blocks} | "
        f"失败:{failed_blocks}"
    )

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

    # 输出到文件
    with open("ips.txt", "w") as f:
        for row in all_rows:
            # 统一格式 IP:PORT:PROTO
            if len(row) == 3:
                ip, port, proto = row
                f.write(f"{ip}:{port}:{proto}\n")
            # 中转行忽略落地 IP
            elif len(row) == 4:
                ip, port, proto, _ = row
                f.write(f"{ip}:{port}:{proto}\n")

if __name__ == "__main__":
    main()
