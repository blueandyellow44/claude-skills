#!/usr/bin/env python3
"""ssrf_probe.py - a local trap for testing an app's outbound fetcher.

Serves, on 127.0.0.1, URLs that a public-addresses-only fetcher must REFUSE,
and prints the list of direct and redirect cases to feed into the app's
fetch path (a feed URL, an image URL, a webhook target). Synthetic only: it
never touches a real internal service; the redirect targets are addresses the
fetcher must stop at before connecting.

  ssrf_probe.py            serve on a free port and print the cases (Ctrl-C to stop)
  ssrf_probe.py --list     print the direct cases only (no server)
  ssrf_probe.py --self-test   start, check every redirect route answers, stop

A guarded fetcher (a news-scoring app's src/lib/safeFetch.ts, 2026-10-07)
refuses every one of these at URL, DNS, connect or redirect time.
"""
import http.server, socketserver, sys, threading, urllib.request

DIRECT = [
    "http://127.0.0.1/", "http://localhost/", "http://[::1]/", "http://0.0.0.0/",
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    "http://10.0.0.1/", "http://172.16.0.1/", "http://192.168.1.1/", "http://100.64.0.1/",
    "http://2130706433/",  # 127.0.0.1 written as one number
    "http://0x7f000001/",  # 127.0.0.1 in hex
    "http://[::ffff:127.0.0.1]/",  # IPv4-mapped IPv6
    "http://[fe80::1]/", "http://[fc00::1]/",
    "http://localtest.me/",  # public DNS name that resolves to 127.0.0.1
    "http://example.com:22/",  # public host, non-web port
    "file:///etc/passwd", "gopher://127.0.0.1/",
]
REDIRECTS = {
    "/to-loopback": "http://127.0.0.1:9/",
    "/to-metadata": "http://169.254.169.254/latest/meta-data/",
    "/to-private": "http://10.0.0.1/",
    "/to-ipv6-loopback": "http://[::1]/",
    "/to-file": "file:///etc/passwd",
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/big":
            self.send_response(200)
            self.send_header("content-type", "text/plain")
            self.end_headers()
            for _ in range(64):  # 64 MiB: a size cap must stop this
                self.wfile.write(b"x" * (1 << 20))
            return
        target = REDIRECTS.get(self.path)
        if not target:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(302)
        self.send_header("location", target)
        self.end_headers()

    def log_message(self, *a):
        pass


class NoFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def serve():
    srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> int:
    if "--list" in sys.argv:
        print("\n".join(DIRECT))
        return 0
    srv = serve()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    if "--self-test" in sys.argv:
        opener = urllib.request.build_opener(NoFollow)
        bad = 0
        for path, target in REDIRECTS.items():
            try:
                opener.open(base + path, timeout=5)
                got = None
            except urllib.error.HTTPError as e:
                got = (e.code, e.headers.get("location"))
            ok = got == (302, target)
            bad += not ok
            print(("ok  " if ok else "FAIL") + f" {path} -> {got}")
        srv.shutdown()
        return 1 if bad else 0
    print("Feed each of these to the app's fetcher; every one must be refused.")
    print("Direct:")
    for u in DIRECT:
        print("  " + u)
    print("Through a redirect (the first hop is loopback too, so test with the fetcher's")
    print("first-hop check relaxed for 127.0.0.1 in a test policy, as the reference app's tests do):")
    for p, t in REDIRECTS.items():
        print(f"  {base}{p}   -> {t}")
    print(f"Size cap: {base}/big streams 64 MiB")
    print("Serving; Ctrl-C to stop.")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
