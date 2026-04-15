import subprocess
import requests
import threading
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ===== 配置 =====
INPUT_URL = "https://example.com/your_input.txt"

THREADS = 100
TIMEOUT = 5

IP_API = "https://btapi.ipip.net/v2/trace"
IP_TOKEN = "你的token"

HTTP_FILE = "http_proxy.txt"
HTTPS_FILE = "https_proxy.txt"
MIDDLE_FILE = "middle_proxy.txt"

seen = set()
lock = threading.Lock()

ipinfo_cache = {}
ipinfo_lock = threading.Lock()

total = 0
checked = 0
ok = 0
middle = 0


# ================== 解析输入 ==================

def parse_line(line):
    line = line.strip()
    if not line:
        return []

    # 兼容中转格式
    if "|" in line:
        left = line.split("|")[0].strip()
        if left.count(":") == 2:
            try:
                proto, ip, port = left.split(":")
                return [(proto, ip, port)]
            except:
                return []

    # 指定协议
    if line.startswith("http:") or line.startswith("https:"):
        try:
            proto, ip, port = line.split(":")
            return [(proto, ip, port)]
        except:
            return []

    # 无协议 → 双测
    if ":" in line:
        try:
            ip, port = line.split(":")[:2]
            return [
                ("http", ip, port),
                ("https", ip, port)
            ]
        except:
            return []

    return []


def load_tasks():
    r = requests.get(INPUT_URL, timeout=10)
    lines = r.text.splitlines()

    tasks = []
    for line in lines:
        tasks.extend(parse_line(line))

    return tasks


# ================== IP 查询（只给中转用） ==================

def query_ip_info(ip):
    with ipinfo_lock:
        if ip in ipinfo_cache:
            return ipinfo_cache[ip]

    try:
        headers = {"token": IP_TOKEN}
        r = requests.get(IP_API, params={"ip": ip}, headers=headers, timeout=5)
        d = r.json()

        area = d.get("area", "").split("\t")[:5]
        area = " ".join(area)
        isp = d.get("isp_domain", "")

        result = f"{area} {isp}".strip()
    except:
        result = "查询失败"

    with ipinfo_lock:
        ipinfo_cache[ip] = result

    return result


# ================== 中转记录 ==================

def record_middle(proto, ip, port, returned_ip):
    global middle

    entry_info = query_ip_info(ip)
    exit_info = query_ip_info(returned_ip)

    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "OK"

    line = f"{proto}:{ip}:{port} | {entry_info} | {ip} | {returned_ip} | {exit_info} | {status} | {time_now}\n"

    with lock:
        middle += 1
        with open(MIDDLE_FILE, "a", encoding="utf-8") as f:
            f.write(line)

        print(f"[中转] {proto}:{ip}:{port} -> {returned_ip}")


# ================== 检测 ==================

def check(task):
    global checked, ok

    proto, ip, port = task
    key = f"{proto}:{ip}:{port}"

    with lock:
        if key in seen:
            return
        seen.add(key)

    if proto == "https":
        cmd = [
            "curl", "-s",
            "--max-time", str(TIMEOUT),
            "--resolve", f"www.visa.cn:{port}:{ip}",
            f"https://www.visa.cn:{port}/cdn-cgi/trace"
        ]
    else:
        cmd = [
            "curl", "-s",
            "--max-time", str(TIMEOUT),
            "--resolve", f"www.visa.cn:{port}:{ip}",
            f"http://www.visa.cn:{port}/cdn-cgi/trace"
        ]

    try:
        result = subprocess.check_output(cmd).decode()

        if "ip=" in result:
            returned_ip = re.search(r'ip=(.+)', result).group(1).strip()

            with lock:
                ok += 1

            # ===== 中转 =====
            if returned_ip != ip:
                record_middle(proto, ip, port, returned_ip)

            # ===== 直连 =====
            else:
                with lock:
                    if proto == "https":
                        with open(HTTPS_FILE, "a") as f:
                            f.write(f"{ip}:{port}\n")
                    else:
                        with open(HTTP_FILE, "a") as f:
                            f.write(f"{ip}:{port}\n")

                print(f"[直连] {proto}:{ip}:{port}")

    except:
        pass

    finally:
        with lock:
            checked += 1
            print(f"\r进度: {checked}/{total} 成功:{ok} 中转:{middle}", end="")


# ================== 主函数 ==================

def main():
    global total

    tasks = load_tasks()
    total = len(tasks)

    open(HTTP_FILE, "w").close()
    open(HTTPS_FILE, "w").close()
    open(MIDDLE_FILE, "w", encoding="utf-8").close()

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        pool.map(check, tasks)

    print("\n完成")


if __name__ == "__main__":
    main()
