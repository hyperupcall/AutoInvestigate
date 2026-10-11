"""Tiny stdlib server: static UI + /api/events (events.jsonl) + /api/ideas.
Never exposes the `planted` field (eval-only)."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.getenv("EVENTS_LOG", os.path.join(ROOT, "..", "logs", "events.jsonl"))
LOGDIR = os.path.dirname(LOG)
EVAL = os.getenv("EVAL_JSON", os.path.join(ROOT, "..", "eval", "results.json"))
IDEAS = os.getenv("IDEAS_JSON", os.path.join(ROOT, "..", "data", "ideas.json"))


def events():
    try:
        with open(LOG) as f:
            return [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []


def ideas():
    with open(IDEAS) as f:
        return [{k: v for k, v in i.items() if k != "planted"} for i in json.load(f)]


class H(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def _state(self):
        try:
            with open(os.path.join(LOGDIR, "status.json")) as f:
                return json.load(f).get("state", "idle")
        except Exception:
            return "unavailable"

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}
        if path == "/api/start":
            st = self._state()
            if st != "idle":
                return self._json({"ok": False, "state": st}, 409)
            cfg = {"pace": min(max(float(body.get("pace", 4)), 0), 15), "news": bool(body.get("news", True))}
            with open(os.path.join(LOGDIR, "trigger.json"), "w") as f:
                json.dump(cfg, f)
            return self._json({"ok": True})
        if path == "/api/stop":
            open(os.path.join(LOGDIR, "cancel"), "w").close()
            return self._json({"ok": True})
        self.send_error(404)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/events":
            self._send(json.dumps(events()).encode(), "application/json")
        elif path == "/api/status":
            self._json({"state": self._state()})
        elif path == "/api/eval":
            try:
                self._send(open(EVAL, "rb").read(), "application/json")
            except FileNotFoundError:
                self._send(b"null", "application/json")
        elif path == "/api/ideas":
            self._send(json.dumps(ideas()).encode(), "application/json")
        elif path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                self._send(f.read(), "text/html; charset=utf-8")
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8090"))
    print(f"Research Council UI on http://localhost:{port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
