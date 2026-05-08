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
