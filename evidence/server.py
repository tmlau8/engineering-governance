"""Authenticated loopback-only read API; collection is not an HTTP write route."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import parse_qs, urlsplit
from collect import ROOT
from store import Store
from views import dispatch

VIEWS = {"overview", "summary", "changes", "rules", "sessions", "decisions", "health", "history", "attempts"}


def make_handler(runtime, token, port, grafana_port, repos):
    class Handler(BaseHTTPRequestHandler):
        server_version = "GovernanceEvidence/0.1"
        sys_version = ""

        def log_message(self, *args):
            pass

        def respond(self, status, payload):
            raw = json.dumps(payload, ensure_ascii=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def authorised(self):
            if self.headers.get("Host") not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                self.respond(403, {"error": "HOST_REJECTED"}); return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{grafana_port}", f"http://localhost:{grafana_port}"}:
                self.respond(403, {"error": "ORIGIN_REJECTED"}); return False
            if not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.respond(401, {"error": "AUTH_REQUIRED"}); return False
            return True

        def do_GET(self):
            if not self.authorised():
                return
            try:
                url = urlsplit(self.path)
                view = url.path.removeprefix("/api/")
                query = parse_qs(url.query, keep_blank_values=True)
                if not url.path.startswith("/api/") or view not in VIEWS:
                    self.respond(404, {"error": "NOT_FOUND"}); return
                if set(query) - {"repo"} or len(query.get("repo", ["all"])) != 1:
                    self.respond(400, {"error": "INVALID_QUERY"}); return
                repo = query.get("repo", ["all"])[0]
                if repo not in {"all", *repos}:
                    self.respond(400, {"error": "INVALID_REPOSITORY"}); return
                store = Store(Path(runtime) / "data/evidence.sqlite", readonly=True)
                try:
                    payload = dispatch(store, view, repo)
                finally:
                    store.close()
                self.respond(200, payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.respond(503, {"error": "EVIDENCE_UNAVAILABLE"})

        def reject_write(self):
            self.respond(405, {"error": "READ_ONLY_API"})

        do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = reject_write
    return Handler


def serve(runtime, host="127.0.0.1"):
    if host != "127.0.0.1":
        raise ValueError("NON_LOOPBACK_BINDING_FORBIDDEN")
    runtime = Path(runtime)
    settings = json.loads((runtime / "settings.json").read_text())
    token = json.loads((runtime / "secrets/credentials.json").read_text())["api_token"]
    port = settings["api_port"]
    server = ThreadingHTTPServer((host, port), make_handler(runtime, token, port, settings["grafana_port"], settings["repositories"]))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime", type=Path, default=ROOT / ".runtime")
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()
    serve(args.runtime, args.host)
