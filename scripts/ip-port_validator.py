import subprocess
import requests
import threading
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# 支持IP:PORT格式，只检测noTLS
# ===== 配置 =====
INPUT_URL = "https://example.com/ips.txt"

THREADS = 100
TIMEOUT = 5

IP_API = "https://btapi.ipip.net/v2/trace"
IP_TOKEN = "068f269ea236dc57215574f3542c8161e27fbf70"

HTTP_FILE = "http_proxy.txt"
MIDDLE_FILE = "middle_proxy.txt"

seen = set()
lock = threading.Lock()

ipinfo_cache = {}
ipinfo_lock = threading.Lock()

total = checked = ok = middle = 0


# ================== 读取远程 ==================

def load_tasks():
    r = requests.get(INPUT_URL, timeout=10)
    lines = r.text.splitlines()

    tasks = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if ":" not in line:
            continue

        try:
            ip, port = line.split(":")[:2]
            tasks.append((ip, port))
        except:
            continue

    return tasks


# ================== IP 查询 ==================

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


# ================== 中转记录（核心输出） ==================

def async_query_middle(ip, port, returned_ip):
    global middle

    entry_info = query_ip_info(ip)
    exit_info = query_ip_info(returned_ip)

    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status = "OK" if returned_ip else "FAIL"

    line = f"{ip}:{port} | {entry_info} | {ip} | {returned_ip} | {exit_info} | {status} | {time_now}\n"

    with lock:
        middle += 1
        with open(MIDDLE_FILE, "a", encoding="utf-8") as f:
            f.write(line)

        print(f"[中转] {ip}:{port} -> {returned_ip}")


# ================== noTLS 检测 ==================

def check(task):
    global checked, ok

    ip, port = task
    key = f"{ip}:{port}"

    with lock:
        if key in seen:
            return
        seen.add(key)

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
                with open(HTTP_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{ip}:{port}\n")

            if returned_ip != ip:
                async_query_middle(ip, port, returned_ip)

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
    open(MIDDLE_FILE, "w", encoding="utf-8").close()

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        pool.map(check, tasks)

    print("\n完成")


if __name__ == "__main__":
    main()
