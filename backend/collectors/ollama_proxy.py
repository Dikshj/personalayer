"""
collectors/ollama_proxy.py

Transparent proxy for Ollama (and any OpenAI-compatible local LLM API).
Intercepts requests, logs user prompts to PersonaLayer, then forwards
to the real Ollama instance.

Usage:
  python -m collectors.ollama_proxy

Then point your tools to localhost:11435 instead of localhost:11434.
  OLLAMA_HOST=http://localhost:11435 ollama run llama3
  Or configure Cursor/Continue/OpenCode to use localhost:11435.

Ollama runs on :11434 by default. Proxy runs on :11435.
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

logger = logging.getLogger(__name__)

OLLAMA_UPSTREAM = "http://localhost:11434"
PROXY_PORT = 11435


def extract_prompt(body_bytes: bytes, path: str) -> str | None:
    """Extract user prompt from Ollama / OpenAI-compatible request body."""
    try:
        data = json.loads(body_bytes)
    except Exception:
        return None

    # Ollama /api/generate: {"model": "...", "prompt": "..."}
    if "prompt" in data:
        return str(data["prompt"])[:1500]

    # Ollama /api/chat or OpenAI /v1/chat/completions:
    # {"messages": [{"role": "user", "content": "..."}]}
    messages = data.get("messages", [])
    user_msgs = [m.get("content", "") for m in messages if m.get("role") == "user"]
    if user_msgs:
        return str(user_msgs[-1])[:1500]

    return None


class ProxyHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        # Extract and log the prompt
        prompt = extract_prompt(body, self.path)
        if prompt and len(prompt.strip()) > 4:
            model = ""
            try:
                model = json.loads(body).get("model", "")
            except Exception:
                pass
            insert_feed_item(
                source="ollama",
                content_type="prompt",
                content=f"[{model}] {prompt}".strip() if model else prompt,
                author="user",
                url=f"ollama://{model or 'local'}",
                timestamp=int(time.time() * 1000),
            )
            logger.info("Captured Ollama prompt (%d chars)", len(prompt))

        # Forward to real Ollama
        upstream_url = OLLAMA_UPSTREAM + self.path
        req = urllib.request.Request(
            upstream_url,
            data=body,
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
            self.wfile.write(f"Ollama proxy error: {exc}".encode())

    def do_GET(self):
        upstream_url = OLLAMA_UPSTREAM + self.path
        req = urllib.request.Request(upstream_url, method="GET")
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
            self.wfile.write(str(exc).encode())

    def log_message(self, fmt, *args):
        pass  # suppress default HTTP logs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [ollama-proxy] %(message)s")
    server = HTTPServer(("127.0.0.1", PROXY_PORT), ProxyHandler)
    logger.info(
        "PersonaLayer Ollama proxy running on :%d → forwarding to %s",
        PROXY_PORT, OLLAMA_UPSTREAM
    )
    logger.info("Point your tools to: http://localhost:%d", PROXY_PORT)
    server.serve_forever()
