"""
Simple server for PersonaLayer inbox-zero demo.
Serves demo-app/ on port 3001.
CORS-friendly — works alongside PersonaLayer on :7823.
"""
import http.server
import socketserver
import os

PORT = 3001
DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # quiet

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"PersonaLayer demo → http://localhost:{PORT}")
    print(f"PersonaLayer API  → http://localhost:7823")
    print("Ctrl+C to stop")
    httpd.serve_forever()
