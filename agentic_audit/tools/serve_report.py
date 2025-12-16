"""Serve the exports directory over HTTP for quick preview of the HTML report."""
import http.server
import socketserver
import webbrowser
import os
from pathlib import Path
import argparse


def serve(dirpath: Path, port: int = 8000, open_browser: bool = True):
    handler = http.server.SimpleHTTPRequestHandler
    prev_cwd = Path.cwd()
    try:
        server_dir = str(dirpath.resolve())
        print(f"Serving {server_dir} on http://localhost:{port}")
        # change cwd so the SimpleHTTPRequestHandler serves from exports
        os.chdir(server_dir)
        with socketserver.TCPServer(("", port), handler) as httpd:
            if open_browser:
                webbrowser.open(f"http://localhost:{port}/report.html")
            httpd.serve_forever()
    finally:
        # restore cwd
        os.chdir(str(prev_cwd))


def main():
    p = argparse.ArgumentParser(description="Serve exported audit report for preview")
    p.add_argument("--outdir", default="exports", help="Directory containing report.html")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-open", action="store_true", help="Do not auto-open browser")
    args = p.parse_args()

    out = Path(args.outdir)
    if not out.exists():
        raise SystemExit(f"Directory not found: {out}")

    serve(out, port=args.port, open_browser=not args.no_open)


if __name__ == '__main__':
    main()
