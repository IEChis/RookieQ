"""
行业分析工作台 - 代理服务器
功能：① 托管静态文件（index.html） ② 转发 /api/* 到上游 AI 网关并注入 CORS 头
用法：python server.py          # 默认端口
      python server.py 9090     # 指定端口
浏览器打开 http://localhost:xxxx 即可
"""

import http.server
import json
import sys
import http.client
import urllib.parse
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 54321

# 上游默认配置（前端可通过 __baseUrl / __apiKey 覆盖）
UPSTREAM_BASE = "https://yourURL"
DEFAULT_KEY = "yourKey"
DEFAULT_MODEL = "yourModel"

# 流式响应的块大小（字节）
STREAM_CHUNK_SIZE = 4096


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    # 空闲连接（如 Chrome preconnect 预连接）超过此秒数未发请求就断开，
    # 防止单个 handler 线程永久卡在 readline 上
    timeout = 120

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}", flush=True)

    def end_headers(self):
        """所有响应都注入 CORS 头。"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        """CORS 预检请求直接返回 200。"""
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        """转发 POST /api/proxy 到上游 Anthropic 兼容网关（支持流式 SSE）。"""
        if not self.path.startswith("/api/"):
            self.send_response(404)
            self.end_headers()
            return

        # 读请求体
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(raw_body, strict=False)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 容错：尝试忽略编码错误
            try:
                payload = json.loads(raw_body.decode(
                    "utf-8", errors="replace"), strict=False)
            except Exception:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    b'{"error":{"type":"bad_request","message":"Invalid JSON"}}')
                return

        # 提取上游配置
        base = payload.pop("__baseUrl", UPSTREAM_BASE).rstrip("/")
        key = payload.pop("__apiKey", DEFAULT_KEY)
        model = payload.get("model", DEFAULT_MODEL)

        # 智能拼接 URL（避免 /v1 重复）
        if base.endswith("/v1/messages"):
            target_url = base
        elif base.endswith("/v1"):
            target_url = base + "/messages"
        elif base.endswith("/messages"):
            target_url = base
        else:
            target_url = base + "/v1/messages"

        # 上游请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "anthropic-version": "2023-06-01",
        }

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        is_stream = payload.get("stream", False)

        print(
            f"[PROXY] → {target_url}  model={model}  stream={is_stream}  body≈{len(data)}B", flush=True)

        try:
            parsed = urllib.parse.urlparse(target_url)
            conn = http.client.HTTPSConnection(
                parsed.hostname, parsed.port or 443, timeout=120)
            conn.request("POST", parsed.path + ("?" +
                         parsed.query if parsed.query else ""), data, headers)
            resp = conn.getresponse()
            status = resp.status
            ct = resp.getheader("Content-Type", "application/json")

            self.send_response(status)
            self.send_header("Content-Type", ct)
            # 流式响应不提前声明 Content-Length，让浏览器按 chunked 接收
            if not is_stream:
                body = resp.read()
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                print(f"[PROXY] ← {status}  {len(body)}B  {ct}", flush=True)
            else:
                # 流式转发：边读边写，不缓冲
                self.end_headers()
                total = 0
                while True:
                    chunk = resp.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()  # 立即推给浏览器
                    total += len(chunk)
                print(f"[PROXY] ← {status}  stream≈{total}B  {ct}", flush=True)

            conn.close()

        except Exception as e:
            print(f"[PROXY] ✗ ERROR: {type(e).__name__}: {e}", flush=True)
            # 如果还没发送过响应头，发送错误；否则只能默默失败（HTTP 不允许回头改状态码）
            try:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(
                    {"error": {"type": "proxy_error", "message": str(e)}}).encode())
            except Exception:
                pass  # 响应头已发送，无法回退


if __name__ == "__main__":
    import socket as _socket
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    base_port = PORT
    server = None

    def port_has_listener(port):
        """主动探测端口是否已有实例在监听。
        Windows 上 SO_REUSEADDR 允许双重绑定（bind 不报错但连接路由混乱），
        仅靠 bind 抛错检测不到僵尸实例，必须实际连一下。"""
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(0.4)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            s.close()
    for attempt in range(20):  # 最多尝试 20 个端口
        try:
            PORT = base_port + attempt
            if port_has_listener(PORT):
                print(
                    f"[SKIP] port {PORT} already has a live instance, trying next...", flush=True)
                continue
            # 多线程：每条连接独立线程处理。单线程 HTTPServer 会被浏览器的
            # preconnect 空闲连接卡死（连接建立了但不发请求），导致页面永远空白
            server = http.server.ThreadingHTTPServer(
                ("0.0.0.0", PORT), ProxyHandler)
            break
        except OSError as e:
            if e.winerror == 10013 or "Address already in use" in str(e):
                continue
            raise
    if not server:
        print(
            f"ERROR: Ports {base_port}-{base_port+19} all in use.", flush=True)
        sys.exit(1)
    print(f"\n{'='*50}", flush=True)
    print(f"  Industry Analysis Server", flush=True)
    print(f"  http://localhost:{PORT}", flush=True)
    print(f"{'='*50}\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.", flush=True)
        server.shutdown()
