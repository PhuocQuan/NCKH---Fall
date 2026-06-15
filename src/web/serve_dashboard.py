"""Serve dashboard HTML + CSS (không cần AI backend).

Chạy:
    python -m src.web.serve_dashboard

Mở trình duyệt:
    http://127.0.0.1:5500/index.html

Nếu cần server AI (camera + API), dùng riêng:
    python -m src.web.server
"""

from __future__ import annotations

import argparse
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)


class ReuseHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve FallGuard dashboard (HTML + CSS only).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5500)
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/index.html"
    print("=== FallGuard Dashboard (HTML + CSS) ===")
    print(f"Mo trinh duyet: {url}")
    print("Dang nhap demo: admin / nckh2025")
    print("(Khong can backend AI — chi xem giao dien)")
    print("Nhan Ctrl+C de dung.\n")

    try:
        server = ReuseHTTPServer((args.host, args.port), DashboardHandler)
        server.serve_forever()
    except OSError as exc:
        if getattr(exc, "winerror", None) == 10048 or exc.errno in {48, 98, 10048}:
            print(f"Loi: Port {args.port} dang duoc dung.", file=sys.stderr)
            print(f"Thu port khac: python -m src.web.serve_dashboard --port 5501", file=sys.stderr)
        else:
            raise
    except KeyboardInterrupt:
        print("\nDa dung server.")


if __name__ == "__main__":
    main()
