"""HTTP server for the salmon report.

Three real paths:
  /, /index.html, /report.html  -> serves report.html (atomic-written by cron)
  /health                       -> JSON status (size + mtime + last regs refresh)
  /favicon.ico                  -> 204
  everything else               -> 404

Reads report.html on every GET; cron's atomic write means the next request
picks up the new content immediately.
"""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 7071
PROJECT_ROOT = Path(__file__).parent
log = logging.getLogger("fishing_server")


def build_handler(*, root: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                if self.path in ("/", "/index.html", "/report.html"):
                    return self._serve_report(root)
                if self.path == "/health":
                    return self._serve_health(root)
                if self.path == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                    return
                self.send_error(404)
            except BrokenPipeError:
                pass

        def log_message(self, format, *args):
            log.info("%s - %s", self.client_address[0], format % args)

        def _serve_report(self, root: Path):
            p = root / "report.html"
            if not p.exists():
                self.send_error(503, "report not generated yet")
                return
            body = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        def _serve_health(self, root: Path):
            p = root / "report.html"
            data_p = root / ".report_data.json"
            payload = {
                "report_html_size": p.stat().st_size if p.exists() else 0,
                "report_html_mtime": p.stat().st_mtime if p.exists() else 0,
                "report_data_mtime": data_p.stat().st_mtime if data_p.exists() else 0,
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

    return Handler


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    handler = build_handler(root=PROJECT_ROOT)
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    log.info("salmon report server listening on :%d", PORT)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
