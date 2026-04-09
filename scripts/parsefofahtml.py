from bs4 import BeautifulSoup

def parse_html(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    results = []

    # 每个节点块
    items = soup.find_all("div", class_="hsxa-meta-data-item")

    for item in items:
        try:
            # ===== IP =====
            ip_tag = item.select_one(".hsxa-host a")
            ip = ip_tag.text.strip() if ip_tag else ""

            # ===== PORT =====
            port_tag = item.select_one(".hsxa-port")
            port = port_tag.text.strip() if port_tag else ""

            # ===== 国家/地区/城市 =====
            location = item.select_one(".hsxa-one-line span.el-tooltip__trigger")
            location_text = location.text.strip() if location else ""

            # ===== ASN =====
            asn_tag = item.select_one('a[href*="YXNu"]')
            asn = asn_tag.text.strip() if asn_tag else ""

            # ===== 组织 =====
            org_tag = item.select_one('a[href*="b3Jn"]')
            org = org_tag.text.strip() if org_tag else ""

            # ===== 时间 =====
            date_tag = item.find("p", string=lambda x: x and "202" in x)
            date = date_tag.text.strip() if date_tag else ""

            # ===== Header =====
            header_span = item.select_one(".hsxa-body-content span")
            header = header_span.text.strip() if header_span else ""

            # ===== 是否 Cloudflare =====
            is_cf = "cloudflare" in header.lower()

            results.append({
                "ip": ip,
                "port": port,
                "location": location_text,
                "asn": asn,
                "org": org,
                "date": date,
                "cloudflare": is_cf
            })

        except Exception as e:
            print("解析失败:", e)

    return results


if __name__ == "__main__":
    data = parse_html("input.html")

    for i in data:
        print(f'{i["ip"]}:{i["port"]} | {i["location"]} | AS{i["asn"]} | {i["org"]} | CF={i["cloudflare"]}')
