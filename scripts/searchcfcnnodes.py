import csv
import subprocess
import requests
import threading
import re
from concurrent.futures import ThreadPoolExecutor

# ===== 配置 =====
INPUT_URLS = [
    "https://github.com/femboyenjoy/free-vless-VPN/raw/refs/heads/main/nodes/cfcn/raw/http1.txt"
]
THREADS = 100
TIMEOUT = 5

# ===== IP 查询接口 =====
IP_API = "https://btapi.ipip.net/v2/trace"
IP_TOKEN = "068f269ea236dc57215574f3542c8161e27fbf70"

# 输出文件
HTTP_FILE = "http_proxy.txt"
HTTPS_FILE = "https_proxy.txt"
MIDDLE_FILE = "middle_proxy.txt"

# 全局变量
seen = set()
lock = threading.Lock()

# 中转 IP 查询缓存
ipinfo_cache = {}
ipinfo_lock = threading.Lock()

total = 0
checked = 0
ok = 0
middle = 0

# ===== 数据解析 =====
def parse_text(text):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        ip_port = parts[0]
        if ":" not in ip_port:
            continue
        ip, port = ip_port.split(":", 1)
        if len(parts) > 1:
            proto = parts[1].lower()
            if proto not in ("http", "https"):
                proto = "http"
            rows.append((ip, port, proto))
        else:
            rows.append((ip, port, "http"))
            rows.append((ip, port, "https"))
    return rows

def parse_scan_text(text):
    """
    解析扫描日志（仅保留带 Cf-Ray 的）
    """
    rows = []

    # 按 http(s) 分块
    blocks = re.split(r'(?=https?://)', text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # ✅ 只保留含 Cf-Ray 的块
        if "cf-ray" not in block.lower():
            continue

        # 提取 URL
        m = re.search(r'(https?)://([\d\.]+)(?::(\d+))?', block)
        if not m:
            continue

        proto, ip, port = m.groups()

        # 默认端口
        if not port:
            port = "443" if proto == "https" else "80"

        rows.append((ip, port, proto))

    return rows

def parse_csv(text):
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
    解析中转落地 IP 格式：
    103.44.255.90:443 (https) -> 落地IP: 154.23.128.6
    返回 (源IP, 端口, 协议, 落地IP)
    """
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "->" not in line:
            continue
        # 只处理 IP:PORT 开头的行
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

# ===== 下载与解析 =====
def fetch_one(url):
    try:
        print(f"[+] 下载: {url}")
        text = requests.get(url, timeout=10).text
        if not text.strip():
            return []

        # ✅ 中转格式（优先）
        if "->" in text and "落地IP" in text:
            return parse_middle_text(text)

        # ✅ CSV
        elif "ip" in text.splitlines()[0].lower():
            return parse_csv(text)

        # ✅ 扫描日志（必须含 Cf-Ray）
        elif "cf-ray" in text.lower():
            return parse_scan_text(text)

        # ✅ 普通文本
        else:
            return parse_text(text)

    except Exception as e:
        print(f"[ERR] 下载失败: {url} | {e}")
        return []

def fetch():
    all_rows = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = pool.map(fetch_one, INPUT_URLS)
    for rows in results:
        all_rows.extend(rows)

    # 去重
    all_rows = list(set(all_rows))

    print(f"[+] 合并后总条目（去重后）: {len(all_rows)}")
    return all_rows

# ===== IP 查询函数（缓存） =====
def query_ip_info(ip):
    with ipinfo_lock:
        if ip in ipinfo_cache:
            return ipinfo_cache[ip]
    try:
        headers = {}
        if IP_TOKEN:
            headers["token"] = IP_TOKEN
        resp = requests.get(IP_API, params={"ip": ip}, headers=headers, timeout=5)
        data = resp.json()
        area = data.get("area", "")
        isp = data.get("isp_domain", "")
        if area:
            parts = area.split("\t")
            area = "\t".join(parts[:5])
        result = f"{area} | {isp}".strip(" |")
    except:
        result = "查询失败"
    with ipinfo_lock:
        ipinfo_cache[ip] = result
    return result

# ===== 中转 IP 异步查询 =====
def async_query_middle(ip, port, proto, returned_ip):
    global middle

    # ✅ 查询入口IP + 落地IP
    src_info = query_ip_info(ip)
    dst_info = query_ip_info(returned_ip)

    # 👉 可选：把 \t 换成空格（更美观）
    src_info = src_info.replace("\t", " ")
    dst_info = dst_info.replace("\t", " ")

    with lock:
        middle += 1
        with open(MIDDLE_FILE, "a") as f:
            # ✅ 第一行（结构行）
            f.write(f"{ip}:{port} ({proto}) -> 落地IP: {returned_ip}\n")

            # ✅ 第二行（合并信息行）
            f.write(f"入口IP: {src_info} | 落地IP: {dst_info}\n\n")

        print(
            f"[中转] {ip}:{port} ({proto}) -> {returned_ip}\n"
            f"        入口: {src_info} | 落地: {dst_info}"
        )

# ===== 检测逻辑 =====
def check(task):
    global checked, ok
    if len(task) == 4:
        ip, port, proto, returned_ip = task
    else:
        ip, port, proto = task
        returned_ip = None

    key = f"{ip}:{port}:{proto}"
    with lock:
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
            returned_ip_detected = None
            for line in result.splitlines():
                if line.startswith("ip="):
                    returned_ip_detected = line.split("=")[1]
                    break

            with lock:
                ok += 1
                file_path = HTTPS_FILE if proto == "https" else HTTP_FILE
                with open(file_path, "a") as f:
                    f.write(f"{ip}:{port}\n")

            if returned_ip_detected and returned_ip_detected != ip:
                async_query_middle(ip, port, proto, returned_ip_detected)
            else:
                print(f"[OK] {ip}:{port} ({proto})")
        else:
            print(f"[FAIL] {ip}:{port} ({proto})")
    except:
        print(f"[ERR] {ip}:{port} ({proto})")
    finally:
        with lock:
            checked += 1
            show_progress()

# ===== 进度条 =====
def show_progress():
    percent = (checked / total) * 100
    print(f"\r进度: {checked}/{total} | 成功: {ok} | 中转: {middle} | {percent:.1f}%", end="")

# ===== 主函数 =====
def main():
    global total
    tasks = fetch()
    total = len(tasks)
    print(f"[+] 总任务: {total}")

    # 清空文件
    open(HTTP_FILE, "w").close()
    open(HTTPS_FILE, "w").close()
    open(MIDDLE_FILE, "w").close()

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        pool.map(check, tasks)

    print("\n\n[+] 完成")
    print(f"HTTP: {HTTP_FILE}")
    print(f"HTTPS: {HTTPS_FILE}")
    print(f"中转: {MIDDLE_FILE}")

if __name__ == "__main__":
    main()
