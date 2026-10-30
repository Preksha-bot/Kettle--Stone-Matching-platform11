"""Kettle & Stone platform screens: upload, openings, sync log.

    python serve.py              then open http://localhost:8000 on this computer

Only this computer can open it. Uses the database in data/kettle.db and writes the output files to out/,
the same as sync.py. Stop it with Ctrl+C.
"""
import argparse
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server

from kettle.config import DEFAULT_CONFIG
from webapp.app import Platform


class ThreadingServer(ThreadingMixIn, WSGIServer):
    """One thread per connection: a browser keeps a spare connection open, which would block a one-at-a-time server."""
    daemon_threads = True


def main(argv=None):
    ap = argparse.ArgumentParser(description="Start the platform screens on this computer.")
    ap.add_argument("--db", default="data/kettle.db")
    ap.add_argument("--out", default="out")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="the settings file (default config/clinic.json)")
    args = ap.parse_args(argv)
    with make_server("127.0.0.1", args.port, Platform(args.db, args.out, args.config), server_class=ThreadingServer) as server:
        print(f"Kettle & Stone platform: open http://localhost:{args.port} on this computer. Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopped.")


if __name__ == "__main__":
    main()
