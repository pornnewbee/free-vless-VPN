import os
import yaml
import urllib.parse
#把Clash订阅转换成vless标准链接
OUTPUT_FILE = "vless.txt"
NODES_DIR = "nodes"


def build_vless(node):
    try:
        uuid = node.get("uuid")
        server = node.get("server")
        port = node.get("port")

        if not uuid or not server or not port:
            return None

        params = {
            "encryption": "none",
        }

        # TLS
        if node.get("tls") or node.get("security") == "tls":
            params["security"] = "tls"

        # WS
        if node.get("network") == "ws":
            params["type"] = "ws"
            ws_opts = node.get("ws-opts", {})

            path = ws_opts.get("path", "/")
            params["path"] = path

            headers = ws_opts.get("headers", {})
            host = headers.get("Host")
            if host:
                params["host"] = host

        # SNI
        if node.get("servername"):
            params["sni"] = node.get("servername")

        # 拼接参数
        query = urllib.parse.urlencode(params, safe="/")

        name = node.get("name", server)

        return f"vless://{uuid}@{server}:{port}?{query}#{urllib.parse.quote(name)}"

    except Exception:
        return None


def extract():
    results = []

    for root, _, files in os.walk(NODES_DIR):
        for file in files:
            if not file.endswith((".yml", ".yaml")):
                continue

            path = os.path.join(root, file)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except Exception:
                continue

            if not data or "proxies" not in data:
                continue

            for node in data["proxies"]:
                if node.get("type") == "vless":
                    link = build_vless(node)
                    if link:
                        results.append(link)

    return results


def main():
    links = extract()

    # 去重
    links = list(set(links))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(links))

    print(f"✅ 输出 {len(links)} 条 VLESS 链接")


if __name__ == "__main__":
    main()
