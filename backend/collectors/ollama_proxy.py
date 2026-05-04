"""
collectors/ollama_proxy.py

Transparent proxy: localhost:11435 → Ollama localhost:11434
Extracts minimal signals from requests. Raw prompts never stored.

What gets stored:
  "[ollama:codellama] task:debugging | domain:web | langs:python"

Usage:
  python -m collectors.ollama_proxy
  Then: OLLAMA_HOST=http://localhost:11435 ollama run llama3
"""

import json
import sys
import time
import logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import insert_feed_item  # noqa: E402
from collectors.signal_extractor import extract_signals, signals_to_content  # noqa: E402

logger = logging.getLogger(__name__)

OLLAMA_UPSTREAM = "http://localhost:11434"
PROXY_PORT = 11435


def get_text_and_model(body_bytes: bytes) -> tuple[str, str]:
    """Extract raw text + model name. Text used only for local signal extraction."""
    try:
        data = json.loads(body_bytes)
    except Exception:
        return "", ""

    model = data.get("model", "")

    if "prompt" in data:
        return str(data["prompt"]), model

    messages = data.get("messages", [])
    user_msgs = [m.get("content", "") for m in messages if m.get("role") == "user"]
    return " ".join(user_msgs), model


class ProxyHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        # Extract signals locally — raw text never stored
        raw_text, model = get_text_and_model(body)
        if raw_text and len(raw_text.strip()) > 4:
            signals = extract_signals(raw_text)
            content = signals_to_content(signals, f"ollama:{model}" if model else "ollama")
            if content:
                insert_feed_item(
                    source="ollama",
                    content_type="session_signals",
                    content=content,
                    author="user",
                    url=f"ollama://{model or 'local'}",
                    timestamp=int(time.time() * 1000),
                )

        # Forward to real Ollama — unmodified
        upstream_url = OLLAMA_UPSTREAM + self.path
        req = urllib.request.Request(
            upstream_url, data=body,
            headers={k: v for k, v in self.headers.items()
                     if k.lower() not in ("host", "content-length")},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding",):
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.URLError as exc:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Proxy error: {exc}".encode())

    def do_GET(self):
        req = urllib.request.Request(OLLAMA_UPSTREAM + self.path)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.URLError as exc:
            self.send_response(502)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [ollama-proxy] %(message)s")
    server = HTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    logger.info("Proxy :11435 → Ollama :11434 | raw prompts never stored")
    server.serve_forever()
