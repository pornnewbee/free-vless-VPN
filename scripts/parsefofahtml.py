import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# ===== 配置 =====
URLS = [
    "https://github.com/femboyenjoy/free-vless-VPN/raw/refs/heads/main/nodes/cfcn/raw/http1.txt",
]

THREADS = 5
TIMEOUT = 10


def fetch_html(url):
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[!] 下载失败 {url}: {e}")
        return ""


def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    items = soup.find_all("div", class_="hsxa-meta-data-item")

    for item in items:
        try:
            # IP
            ip_tag = item.select_one(".hsxa-host a")
            ip = ip_tag.text.strip() if ip_tag else ""

            # PORT
            port_tag = item.select_one(".hsxa-port")
            port = port_tag.text.strip() if port_tag else ""

            # 地理位置
            location = item.select_one(".hsxa-one-line span.el-tooltip__trigger")
            location_text = location.text.strip() if location else ""

            # ASN
            asn_tag = item.select_one('a[href*="YXNu"]')
            asn = asn_tag.text.strip() if asn_tag else ""

            # 组织
            org_tag = item.select_one('a[href*="b3Jn"]')
            org = org_tag.text.strip() if org_tag else ""

            # Header
            header_span = item.select_one(".hsxa-body-content span")
            header = header_span.text.strip() if header_span else ""

            is_cf = "cloudflare" in header.lower()

            if ip and port:
                results.append({
                    "ip": ip,
                    "port": port,
                    "location": location_text,
                    "asn": asn,
                    "org": org,
                    "cloudflare": is_cf
                })

        except Exception as e:
            print("解析失败:", e)

    return results


def worker(url):
    html = fetch_html(url)
    if not html:
        return []

    return parse_html(html)


if __name__ == "__main__":
    all_results = []

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futures = [pool.submit(worker, url) for url in URLS]

        for f in futures:
            all_results.extend(f.result())

    # ===== 去重 =====
    unique = {}
    for i in all_results:
        key = f'{i["ip"]}:{i["port"]}'
        unique[key] = i

    data = list(unique.values())

    # ===== 过滤 Cloudflare =====
    data = [x for x in data if x["cloudflare"]]

    # ===== 输出 =====
    for i in data:
        with open("ips.txt", "w", encoding="utf-8") as f:
            for i in data:
                line = f'{i["ip"]}:{i["port"]} | AS{i["asn"]} | {i["org"]}\n'
                f.write(line)
