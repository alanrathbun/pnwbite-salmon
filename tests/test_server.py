import threading
import time
import urllib.request
import json
from pathlib import Path
import pytest

from fishing_server import build_handler


@pytest.fixture
def server(tmp_path):
    # Write a fake report.html
    (tmp_path / "report.html").write_text("<html>hello</html>")
    from http.server import ThreadingHTTPServer
    handler = build_handler(root=tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    th = threading.Thread(target=httpd.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def test_root_returns_report_html(server):
    body = urllib.request.urlopen(server + "/").read().decode()
    assert "<html>hello</html>" in body


def test_health_returns_json(server):
    body = json.loads(urllib.request.urlopen(server + "/health").read().decode())
    assert "report_html_size" in body
    assert "report_html_mtime" in body


def test_favicon_returns_204(server):
    resp = urllib.request.urlopen(server + "/favicon.ico")
    assert resp.status == 204


def test_unknown_returns_404(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(server + "/nonsense")
    assert e.value.code == 404


def test_robots_txt(server):
    body = urllib.request.urlopen(server + "/robots.txt").read().decode()
    assert "User-agent: *" in body
    assert "Allow: /" in body
    assert "Disallow: /health" in body
    assert "Sitemap:" in body


def test_sitemap_xml(server):
    body = urllib.request.urlopen(server + "/sitemap.xml").read().decode()
    assert "<urlset" in body
    assert "<loc>" in body
    assert "<priority>1.0</priority>" in body


def test_static_route_serves_planner_js(tmp_path):
    """The /static/planner.js endpoint should return the file with a JS content-type."""
    import http.client
    import threading
    from http.server import ThreadingHTTPServer
    from pathlib import Path
    from fishing_server import build_handler

    # Ensure planner.js exists under the project root
    project_root = Path(__file__).resolve().parent.parent
    planner_path = project_root / "static" / "planner.js"
    assert planner_path.exists(), "static/planner.js must be present for this test"

    handler = build_handler(root=tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port)
        conn.request("GET", "/static/planner.js")
        resp = conn.getresponse()
        assert resp.status == 200
        assert resp.getheader("Content-Type", "").startswith("application/javascript")
        body = resp.read()
        assert b"plannerPayload" in body or b"planner" in body
    finally:
        httpd.shutdown()


def test_static_route_404s_for_unwhitelisted_filename(tmp_path):
    import http.client
    import threading
    from http.server import ThreadingHTTPServer
    from fishing_server import build_handler

    handler = build_handler(root=tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port)
        conn.request("GET", "/static/secret.txt")
        resp = conn.getresponse()
        assert resp.status == 404
    finally:
        httpd.shutdown()
