"""A loopback server for saved pages: bytes in memory, served as they are, with no way out to the internet.

    site = Site({"/a/x.html": b"<html>..."})      routes: path -> bytes (or (bytes, content type))
    site.url  ->  http://127.0.0.1:<port>          site.stop()

A saved page may name scripts, images and ads of the real site. The Content-Security-Policy below lets a page run its own inline
code and use its own address, and nothing else, so the browser asks no third party for anything: the page is the frozen file, and
the run does not depend on, or load, a site that has changed since the file was saved. The brain's address guard lets the port
through when the scratch brain is started with it (`Brain(..., site_port)`).
"""
import http.server
import socket
import threading

CSP = "default-src 'self' data: 'unsafe-inline' 'unsafe-eval'"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Site:
    def __init__(self, routes, port=None):
        self.routes, self.served = dict(routes), []
        self.port = port or free_port()
        site = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                path = self.path.split("?", 1)[0]
                site.served.append(path)
                hit = site.routes.get(path)
                if hit is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                body, ctype = hit if isinstance(hit, tuple) else (hit, "text/html")
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Security-Policy", CSP)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # a request log would cost time inside a timed call
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
