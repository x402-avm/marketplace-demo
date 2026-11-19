"""Unit & Integration Tests for Standalone Frontend Server (Port 10001).
Tests HTTP asset delivery, MIME types, CORS headers, and reverse proxy functionality.
"""

import time
import threading
import urllib.request
from http.server import HTTPServer
import pytest

import socket
from frontend.serve_frontend import GeminiNanoUIHandler, PORT, FRONTEND_DIR

def _get_free_test_port():
    for p in range(10050, 10100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', p)) != 0:
                return p
    return 10088

TEST_PORT = _get_free_test_port()

@pytest.fixture(scope="module")
def run_test_frontend_server():
    server = None
    assigned_port = None
    for p in range(10050, 10100):
        try:
            class ReusableHTTPServer(HTTPServer):
                allow_reuse_address = True
            server = ReusableHTTPServer(("127.0.0.1", p), GeminiNanoUIHandler)
            assigned_port = p
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError("No free port available for test frontend server")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)  # Allow server to bind and start
    yield f"http://127.0.0.1:{assigned_port}"
    server.shutdown()
    server.server_close()

def test_default_port_in_allowed_range():
    """Verify that default port adheres strictly to 10000-10100."""
    assert 10000 <= PORT <= 10100, f"Frontend default port {PORT} outside 10000-10100"
    assert PORT == 10001

def test_serve_index_html(run_test_frontend_server):
    url = f"{run_test_frontend_server}/"
    with urllib.request.urlopen(url) as resp:
        assert resp.status == 200
        content = resp.read().decode("utf-8")
        assert "Gemini Nano" in content
        assert "Banana Edition" in content
        assert "canvas" in content
        # Check CORS
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

def test_serve_css_assets_mime_type(run_test_frontend_server):
    url = f"{run_test_frontend_server}/css/variables.css"
    with urllib.request.urlopen(url) as resp:
        assert resp.status == 200
        ct = resp.headers.get("Content-Type", "")
        assert "text/css" in ct
        content = resp.read().decode("utf-8")
        assert "--gemini-purple" in content

def test_serve_js_assets_mime_type(run_test_frontend_server):
    url = f"{run_test_frontend_server}/js/api.js"
    with urllib.request.urlopen(url) as resp:
        assert resp.status == 200
        ct = resp.headers.get("Content-Type", "")
        assert "application/javascript" in ct or "text/javascript" in ct
        content = resp.read().decode("utf-8")
        assert "ApiClient" in content

def test_cors_options_preflight(run_test_frontend_server):
    req = urllib.request.Request(
        f"{run_test_frontend_server}/api/generate",
        method="OPTIONS"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")

def test_proxy_to_backend(run_test_frontend_server):
    """Verify reverse-proxying of /health and /api requests to backend."""
    from http.server import BaseHTTPRequestHandler
    
    class MockBackendHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"mock_healthy","device":"cpu"}')
            else:
                self.send_error(404)
        def log_message(self, format, *args):
            pass

    backend_server = None
    backend_port = None
    for bp in range(10080, 10099):
        try:
            class ReusableHTTPServer(HTTPServer):
                allow_reuse_address = True
            backend_server = ReusableHTTPServer(("127.0.0.1", bp), MockBackendHandler)
            backend_port = bp
            break
        except OSError:
            continue
    if backend_server is None:
        raise RuntimeError("No free port available for mock backend server")
    b_thread = threading.Thread(target=backend_server.serve_forever, daemon=True)
    b_thread.start()
    time.sleep(0.1)

    import frontend.serve_frontend as sf
    orig_backend = sf.BACKEND_URL
    sf.BACKEND_URL = f"http://127.0.0.1:{backend_port}"

    try:
        url = f"{run_test_frontend_server}/health"
        with urllib.request.urlopen(url) as resp:
            assert resp.status == 200
            data = resp.read().decode("utf-8")
            assert "mock_healthy" in data
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
    finally:
        sf.BACKEND_URL = orig_backend
        backend_server.shutdown()
        backend_server.server_close()
