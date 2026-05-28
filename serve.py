"""Static server for the project, with clean routes:
  /results  -> results/index.html   (the index-returns report)
  /tickr/   -> tickr/index.html      (the micro-cap screener)
Run: uv run serve.py [port]   (default 8000, localhost only)
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        p = (self.path.split("?", 1)[0]).rstrip("/") or "/"
        if p in ("/", "/index-returns"):
            self.path = "/results/index.html"
        elif p == "/countries":
            self.path = "/country/report.html"
        elif p == "/countries/compare":
            self.path = "/country/compare.html"
        elif p == "/countries/debt":
            self.path = "/country/debt.html"
        elif p.startswith("/countries/"):
            self.path = f"/country/report/{p[len('/countries/'):]}.html"
        elif p == "/screener":
            self.path = "/tickr/index.html"
        elif p.startswith("/screener/"):
            t = p[len("/screener/"):]
            self.path = f"/tickr/{t}" + ("" if t.endswith(".html") else ".html")
        # anything else (static assets, images) served as-is
        super().do_GET()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = partial(Handler, directory=".")
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"serving on http://127.0.0.1:{port}  "
          f"(/index-returns , /countries , /countries/compare , /screener )",
          flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
