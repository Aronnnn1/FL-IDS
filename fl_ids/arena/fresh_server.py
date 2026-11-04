"""Dummy web target for the fresh-traffic experiment. Runs only inside an isolated network namespace in the VM.
It has no real data and no real vulnerabilities: it just answers requests so the attack tools get realistic replies.
"""
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/item":
            v = q.get("id", ["1"])[0]
            if "'" in v or "--" in v or " " in v:
                return self._send(500, "<html>You have an error in your SQL syntax near '%s'</html>" % v[:20])
            return self._send(200, "<html><h1>Item %s</h1></html>" % v)
        if u.path == "/search":
            return self._send(200, "<html>Results for %s</html>" % q.get("q", [""])[0])
        return self._send(200, "<html><h1>Test shop</h1><a href='/item?id=1'>item</a></html>")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        data = self.rfile.read(n).decode(errors="ignore")
        u = urlparse(self.path)
        if u.path == "/login":
            f = parse_qs(data)
            ok = f.get("user", [""])[0] == "admin" and f.get("pass", [""])[0] == "s3cret"
            return self._send(200 if ok else 401, "welcome" if ok else "denied")
        if u.path == "/upload":
            return self._send(200, "uploaded")
        return self._send(404, "no")


if __name__ == "__main__":
    ThreadingHTTPServer((sys.argv[1], 8000), H).serve_forever()
