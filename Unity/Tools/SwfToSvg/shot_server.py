#!/usr/bin/env python3
"""Static file server with a POST sink, for the static chip review.

Serves the Art tree (so `/.tmp-static/...` and `/Unity/...` both work) and
accepts POST /shot?name=p0001, writing the body to .tmp-static/shots/p0001.png.

    python3 Tools/SwfToSvg/shot_server.py [port]
"""
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # .../Unity/Tools/SwfToSvg -> Art
SHOTS = os.path.join(ROOT, ".tmp-static", "shots")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/shot":
            self.send_error(404)
            return
        name = (parse_qs(url.query).get("name") or ["shot"])[0]
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        os.makedirs(SHOTS, exist_ok=True)
        with open(os.path.join(SHOTS, name + ".png"), "wb") as f:
            f.write(body)
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8139
    print("serving", ROOT, "on", port, flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
