#!/usr/bin/env python3
"""Story Studio — lightweight Python 3 stdlib static file server.

Serves the studio directory (index.html, story.json, styles.css, app.js) and,
when present, an audio/ folder plus audio/metadata.json.

Usage:
    python3 studio/serve.py [--port 8765] [--root <dir>]

  --port   Port to listen on (default: 8765).
  --root   Directory to serve. Default: the directory containing this file.
           Point it at any folder that has index.html + story.json + audio/.

This script only PRINTS the URL to open when run; it does not open a browser.
No third-party dependencies (http.server from the standard library only).
"""

import argparse
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class StudioRequestHandler(SimpleHTTPRequestHandler):
    """Static handler with correct MIME types and UTF-8 JSON."""

    # Ensure correct content types for the assets the studio uses.
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".json": "application/json",
        ".css": "text/css",
        ".html": "text/html",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
    }

    def guess_type(self, path):
        ctype = super().guess_type(path)
        # Serve text + JSON as UTF-8 so Devanagari renders correctly.
        if ctype in ("application/json", "text/javascript",
                     "text/css", "text/html", "text/plain"):
            return ctype + "; charset=utf-8"
        return ctype

    def end_headers(self):
        # Avoid stale cached story.json / metadata during local development.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("[studio] " + (fmt % args) + "\n")


def parse_args(argv):
    default_root = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Story Studio static server")
    parser.add_argument("--port", type=int, default=8765,
                        help="Port to listen on (default: 8765)")
    parser.add_argument("--root", default=default_root,
                        help="Directory to serve (default: this file's directory)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = os.path.abspath(args.root)

    if not os.path.isdir(root):
        sys.stderr.write("Error: root is not a directory: %s\n" % root)
        return 2

    index_path = os.path.join(root, "index.html")
    if not os.path.isfile(index_path):
        sys.stderr.write("Warning: no index.html found in %s\n" % root)

    handler = partial(StudioRequestHandler, directory=root)
    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), handler)

    url = "http://127.0.0.1:%d/" % args.port
    print("Story Studio serving %s" % root)
    print("Open: %s" % url)
    print("Press Ctrl+C to stop.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping…")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
