import csv
import subprocess
import requests
import threading
from concurrent.futures import ThreadPoolExecutor

# ===== 配置 =====
INPUT_URL = "你的地址"
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


def fetch():
    print(f"[+] 下载数据: {INPUT_URL}")
    text = requests.get(INPUT_URL, timeout=10).text
    if "ip" in text.splitlines()[0].lower():
        print("[+] CSV格式")
        return parse_csv(text)
    else:
        print("[+] 文本格式")
        return parse_text(text)


# ===== IP 查询函数（去重 + 缓存） =====
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
    info = query_ip_info(returned_ip)
    with lock:
        global middle
        middle += 1
        with open(MIDDLE_FILE, "a") as f:
            f.write(f"{ip}:{port} ({proto}) -> {returned_ip} [{info}]\n")
        print(f"[中转] {ip}:{port} ({proto}) -> {returned_ip} | {info}")


# ===== 检测逻辑 =====
def check(task):
    global checked, ok
    ip, port, proto = task
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
            returned_ip = None
            for line in result.splitlines():
                if line.startswith("ip="):
                    returned_ip = line.split("=")[1]
                    break

            with lock:
                ok += 1
                # 分类写入
                file_path = HTTPS_FILE if proto == "https" else HTTP_FILE
                with open(file_path, "a") as f:
                    f.write(f"{ip}:{port}\n")

            # 中转反代立即查询
            if returned_ip and returned_ip != ip:
                t = threading.Thread(target=async_query_middle, args=(ip, port, proto, returned_ip))
                t.start()
            else:
                print(f"[OK] {ip}:{port} ({proto})")
        else:
            print(f"[FAIL] {ip}:{port} ({proto})")
    except:
        print(f"[ERR] {ip}:{port} ({proto})")
    finally:
        with lock:
            global checked
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
