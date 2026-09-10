"""
行业分析工作台 - 代理服务器
功能：① 托管静态文件（index.html） ② 转发 /api/* 到上游 AI 网关并注入 CORS 头
      支持 Anthropic Messages 与 OpenAI Responses 两种上游协议。
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

# 上游默认配置（前端可通过 __baseUrl / __apiKey / __provider 覆盖）
UPSTREAM_BASE = "https://yourURL"
DEFAULT_KEY = "yourKey"
DEFAULT_MODEL = "yourModel"

# 流式响应的块大小（字节）
STREAM_CHUNK_SIZE = 4096


def _extract_system_text(payload):
    """从 Anthropic 请求体的 system 字段提取纯文本。"""
    system = payload.get("system", "")
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts = []
        for s in system:
            if isinstance(s, dict) and s.get("type") == "text":
                parts.append(s.get("text", ""))
        return "\n".join(parts)
    return ""


def _anthropic_content_to_text(content):
    """把 Anthropic 的 content（字符串或 block 数组）转成纯文本。"""
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                parts.append(c["text"])
        return "\n".join(parts)
    return ""


def _to_openai_responses_body(payload):
    """把 Anthropic Messages 请求体转成 OpenAI Responses API 请求体。"""
    system_text = _extract_system_text(payload)
    messages = []
    if system_text:
        messages.append({"role": "system", "content": system_text})

    for m in payload.get("messages", []):
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        text = _anthropic_content_to_text(m.get("content"))
        if text:
            messages.append({"role": role, "content": text})

    tools = []
    for t in payload.get("tools", []):
        ttype = t.get("type", "")
        name = t.get("name", "")
        if ttype == "web_search_20260209" or name == "web_search" or ttype == "web_search":
            tools.append({"type": "web_search", "web_search": {"search_context_size": "medium"}})

    body = {
        "model": payload.get("model", DEFAULT_MODEL),
        "input": messages,
        "stream": payload.get("stream", True),
        "max_output_tokens": payload.get("max_tokens", 64000),
        "truncation": "auto",
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    return body


def _encode_sse(event_type, data_obj):
    """把 JSON 对象编码成一条 SSE 数据行。"""
    return f"event: {event_type}\ndata: {json.dumps(data_obj, ensure_ascii=False)}\n\n".encode("utf-8")


def _translate_responses_chunk(chunk_bytes, ctx):
    """
    把 OpenAI Responses API 的 SSE 原始字节翻译成 Anthropic Messages 风格的 SSE 字节。
    兼容带/不带 "response." 前缀的事件名（DeepSeek 用 response.output_text.delta，
    标准 OpenAI 用 output_text.delta）。
    ctx 是字典，记录状态。
    返回：bytes（翻译后的事件） + 更新后的 ctx。
    """
    out = b""
    text = chunk_bytes.decode("utf-8", errors="replace")

    # 只要有任何事件到达，立即建立消息骨架（message_start + 空 text 块），
    # 让前端立刻脱离“无响应/挂起”状态（模型可能正处于 reasoning 阶段）。
    if not ctx.get("message_started") and "event:" in text:
        out += _encode_sse("message_start", {"type": "message_start", "message": {"usage": {}}})
        ctx["message_started"] = True
        out += _encode_sse("content_block_start", {
            "type": "content_block_start",
            "index": ctx["text_index"],
            "content_block": {"type": "text", "text": ""}
        })

    for raw_event in text.split("\n\n"):
        raw_event = raw_event.strip()
        if not raw_event:
            continue
        lines = [ln.strip() for ln in raw_event.split("\n") if ln.strip()]
        event_type = None
        data_str = ""
        for ln in lines:
            if ln.startswith("event:"):
                event_type = ln[len("event:"):].strip()
            elif ln.startswith("data:"):
                data_str = ln[len("data:"):].strip()
        if not event_type or not data_str:
            continue
        try:
            data = json.loads(data_str)
        except Exception:
            continue

        et = data.get("type", event_type)

        # 1. 正文文本：response.output_text.delta / output_text.delta -> text_delta
        if et == "output_text.delta" or et.endswith(".output_text.delta"):
            delta_text = data.get("delta", "")
            if delta_text:
                out += _encode_sse("content_block_delta", {
                    "type": "content_block_delta",
                    "index": ctx["text_index"],
                    "delta": {"type": "text_delta", "text": delta_text}
                })
            continue

        # 2. 推理过程（思考链）：response.reasoning_text.delta -> 静默跳过，不展示给用户
        if et == "reasoning_text.delta" or et.endswith(".reasoning_text.delta"):
            continue

        # 3. 各种 *.done / created / item.added / web_search_call.* 等：暂不翻译，避免干扰正文流
        #    （检索型问题若触发 web_search，其结果会被模型整合进 output_text，正文照常显示）
        if et in ("response.completed", "response.failed", "response.incomplete"):
            resp = data.get("response", {})
            usage = resp.get("usage", {}) if isinstance(resp, dict) else {}
            msg_delta = {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}
            if usage:
                msg_delta["usage"] = {
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0)
                }
            out += _encode_sse("message_delta", msg_delta)
            out += _encode_sse("message_stop", {"type": "message_stop"})
            ctx["finished"] = True
            continue

    return out, ctx


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
        """转发 POST /api/proxy 到上游 AI 网关（支持 Anthropic Messages 或 OpenAI Responses）。"""
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
            try:
                payload = json.loads(raw_body.decode("utf-8", errors="replace"), strict=False)
            except Exception:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":{"type":"bad_request","message":"Invalid JSON"}}')
                return

        # 提取上游配置
        base = payload.pop("__baseUrl", UPSTREAM_BASE).rstrip("/")
        key = payload.pop("__apiKey", DEFAULT_KEY)
        provider = payload.pop("__provider", "anthropic").lower()
        model = payload.get("model", DEFAULT_MODEL)
        is_stream = payload.get("stream", False)

        if provider == "openai-responses":
            target_url = base.rstrip("/") + "/responses"
            upstream_body = _to_openai_responses_body(payload)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            }
        else:
            # Anthropic Messages 格式（默认）
            if base.endswith("/v1/messages"):
                target_url = base
            elif base.endswith("/v1"):
                target_url = base + "/messages"
            elif base.endswith("/messages"):
                target_url = base
            else:
                target_url = base + "/v1/messages"
            upstream_body = payload
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "anthropic-version": "2023-06-01",
            }

        data = json.dumps(upstream_body, ensure_ascii=False).encode("utf-8")

        print(
            f"[PROXY] → {target_url}  provider={provider}  model={model}  stream={is_stream}  body≈{len(data)}B",
            flush=True)
        # 诊断：打印请求体前 1200 字符，便于确认 tools 是否正确携带
        debug_body = data.decode("utf-8", errors="replace")
        if len(debug_body) > 1200:
            debug_body = debug_body[:1200] + " ... [truncated]"
        print(f"[PROXY] → body preview: {debug_body}", flush=True)

        try:
            parsed = urllib.parse.urlparse(target_url)
            conn = http.client.HTTPSConnection(
                parsed.hostname, parsed.port or 443, timeout=15)
            conn.connect()
            conn.sock.settimeout(180)
            conn.request("POST", parsed.path + ("?" + parsed.query if parsed.query else ""), data, headers)
            resp = conn.getresponse()
            status = resp.status
            ct = resp.getheader("Content-Type", "application/json")

            self.send_response(status)
            self.send_header("Content-Type", ct)
            if not is_stream:
                body = resp.read()
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                print(f"[PROXY] ← {status}  {len(body)}B  {ct}", flush=True)
            else:
                self.end_headers()
                total = 0
                if provider == "openai-responses":
                    ctx = {
                        "text_index": 0,
                        "search_index": 1,
                        "message_started": False,
                        "search_started": False,
                        "search_stopped": False,
                        "finished": False,
                    }
                    while not ctx.get("finished"):
                        chunk = resp.read(STREAM_CHUNK_SIZE)
                        if not chunk:
                            break
                        translated, ctx = _translate_responses_chunk(chunk, ctx)
                        if translated:
                            self.wfile.write(translated)
                            self.wfile.flush()
                            total += len(translated)
                    # 若上游未正常结束，补一个 message_stop
                    if not ctx.get("finished"):
                        self.wfile.write(_encode_sse("message_stop", {"type": "message_stop"}))
                        self.wfile.flush()
                else:
                    while True:
                        chunk = resp.read(STREAM_CHUNK_SIZE)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                        total += len(chunk)
                print(f"[PROXY] ← {status}  stream≈{total}B  {ct}", flush=True)

            conn.close()

        except Exception as e:
            print(f"[PROXY] ✗ ERROR: {type(e).__name__}: {e}", flush=True)
            try:
                if not is_stream:
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(
                        {"error": {"type": "proxy_error", "message": str(e)}}).encode())
                else:
                    try:
                        self.wfile.write(("data: " + json.dumps(
                            {"type": "error", "error": {"message": "上游代理中断/超时: " + str(e)}}).encode("utf-8") + b"\n\n"))
                        self.wfile.flush()
                    except Exception:
                        pass
            except Exception:
                pass


if __name__ == "__main__":
    import socket as _socket
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    base_port = PORT
    server = None

    def port_has_listener(port):
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        s.settimeout(0.4)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            s.close()

    for attempt in range(20):
        try:
            PORT = base_port + attempt
            if port_has_listener(PORT):
                print(f"[SKIP] port {PORT} already has a live instance, trying next...", flush=True)
                continue
            server = http.server.ThreadingHTTPServer(
                ("0.0.0.0", PORT), ProxyHandler)
            break
        except OSError as e:
            if e.winerror == 10013 or "Address already in use" in str(e):
                continue
            raise
    if not server:
        print(f"ERROR: Ports {base_port}-{base_port+19} all in use.", flush=True)
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
