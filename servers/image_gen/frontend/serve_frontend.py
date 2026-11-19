#!/usr/bin/env python3
"""Dedicated Frontend Web Server for Gemini Nano & Banana UI.
Strictly runs in the 10000-10100 port range (default: Port 10001).
"""

import os
import sys
import mimetypes
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import urllib.error

FRONTEND_DIR = Path(__file__).resolve().parent
PORT = int(os.environ.get("FRONTEND_PORT", "10001"))
HOST = os.environ.get("FRONTEND_HOST", "0.0.0.0")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:10000")

# Ensure proper MIME types
mimetypes.init()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("text/html", ".html")

class GeminiNanoUIHandler(SimpleHTTPRequestHandler):
    """Custom HTTP Handler serving UI assets with CORS and optional backend proxy."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def end_headers(self):
        # Enable CORS for local cross-port operations
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # If requesting API or Health endpoint, proxy to backend Port 10000
        if self.path.startswith("/api/") or self.path == "/health":
            self.proxy_to_backend("GET")
            return
            
        # Serve index.html on root
        if self.path == "/" or self.path == "":
            self.path = "/index.html"
            
        super().do_GET()

    def do_HEAD(self):
        if self.path.startswith("/api/") or self.path == "/health":
            self.proxy_to_backend("HEAD")
            return
        super().do_HEAD()

    def do_POST(self):
        # Proxy API POST requests to backend Port 10000
        if self.path.startswith("/api/") or self.path == "/health":
            self.proxy_to_backend("POST")
            return
        self.send_error(404, "Not Found")

    def do_PUT(self):
        # Proxy API PUT requests to backend Port 10000
        if self.path.startswith("/api/") or self.path == "/health":
            self.proxy_to_backend("PUT")
            return
        self.send_error(404, "Not Found")

    def do_DELETE(self):
        # Proxy API DELETE requests to backend Port 10000
        if self.path.startswith("/api/") or self.path == "/health":
            self.proxy_to_backend("DELETE")
            return
        self.send_error(404, "Not Found")

    def proxy_to_backend(self, method: str):
        target_url = f"{BACKEND_URL}{self.path}"
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=headers,
                method=method
            )
            
            with urllib.request.urlopen(req, timeout=900) as resp:
                self.send_response(resp.status)
                for header, val in resp.getheaders():
                    if header.lower() not in ("transfer-encoding", "content-length") and not header.lower().startswith("access-control-"):
                        self.send_header(header, val)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            if "content-type" in e.headers:
                self.send_header("Content-Type", e.headers["content-type"])
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Proxy error connecting to backend {target_url}: {str(e)}".encode("utf-8"))

def run_server():
    server_address = (HOST, PORT)
    httpd = HTTPServer(server_address, GeminiNanoUIHandler)
    print(f"================================================================")
    print(f" Gemini Nano & Banana Web UI Server")
    print(f" Running at: http://127.0.0.1:{PORT}")
    print(f" Connected to Backend API at: {BACKEND_URL}")
    print(f" Port range compliance: 10000-10100 (Port {PORT})")
    print(f"================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Gemini Nano UI server...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
