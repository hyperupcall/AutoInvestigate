"""HTTP routes + the run loop.

  POST /api/evaluate   {"idea": "...", "overrides": {"deliberation_seconds": 20, "summarizer_model": "..."}}
  POST /api/stop       {"run_id": "..."}  (no run_id: stop every running evaluation)
  GET  /api/status                        {"running": bool, "run_id": newest running, "running_ids": [...]}
  GET  /api/runs                          past and current runs, newest first
  GET  /api/runs/<id>/events?since=N      our raw events after index N
  GET  /api/runs/<id>/report              the run's JSON report (schema/evaluation-report.schema.json)
  GET  /api/results                       council_results/index.json: every exported run
  GET  /api/ui/runs/<id>/events?since=N   live events in the AutoInvestigate frontend's shape (orchestrator/compat.py)
  GET  /api/settings | PUT /api/settings  settings (keys masked) | save (validated)
  POST /api/settings/reset                back to defaults
  GET  /api/models                        OpenRouter text models with prices (cached)
  GET  /api/prompt?path=prompts/...       read a prompt file
Pages: /  the AutoInvestigate frontend (when mounted at FRONTEND_DIR), /live  the three-column live view,
       /settings  the bare settings page.
"""
import asyncio
import json
import mimetypes
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from deliberation import settings
from deliberation.prompts import ROOT
from orchestrator import compat
from orchestrator.bus import Bus
from orchestrator.pipeline import pipeline
from orchestrator.run import RUNS_DIR, Run

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
FRONTEND = os.path.abspath(os.getenv("FRONTEND_DIR", os.path.join(ROOT, "frontend")))
MAX_PARALLEL = int(os.getenv("MAX_PARALLEL_RUNS", "3"))
# One event loop and one SLIM client for the life of the process (the SDK holds one SLIM connection per process).
LOOP = asyncio.new_event_loop()
threading.Thread(target=LOOP.run_forever, daemon=True).start()
BUS = Bus()
RUNS: dict[str, tuple[Run, object]] = {}  # run_id -> (run, future)
LOCK = threading.Lock()
_models = {"at": 0.0, "data": []}


def running_ids() -> list[str]:
    return [rid for rid, (_, f) in RUNS.items() if not f.done()]


def apply_overrides(s: dict, o: dict) -> tuple[dict, str | None]:
    """Per-run tweaks from the frontend; the saved settings are untouched."""
    if not isinstance(o, dict):
        return s, None
    if o.get("mode") is not None:
        if o["mode"] not in ("quick", "deep"):
            return s, "mode must be quick or deep"
        s["mode"] = o["mode"]
    if "deliberation_seconds" in o:
        try:
            secs = int(o["deliberation_seconds"])
        except (TypeError, ValueError):
            return s, "deliberation_seconds must be a number"
        if not 5 <= secs <= 900:
            return s, "deliberation_seconds must be between 5 and 900"
        s["deliberation_seconds"] = secs
    m = str(o.get("summarizer_model") or "").strip()
    if m:
        known = {x["id"] for x in models()}
        if known and m not in known:
            return s, f"summarizer model {m} is not available on OpenRouter"
        s["stages"]["summarizer"]["model"] = m
    ids = o.get("group_ids")
    if ids is not None:
        if not isinstance(ids, list) or not ids:
            return s, "group_ids must be a non-empty list"
        known = {g["id"] for g in s["groups"]}
        unknown = [i for i in ids if i not in known]
        if unknown:
            return s, f"unknown group ids: {', '.join(map(str, unknown))}"
        keep = set(ids)
        s["groups"] = [g for g in s["groups"] if g["id"] in keep]
    return s, None


def start(idea: str, overrides: dict | None) -> tuple[int, dict]:
    s, err = apply_overrides(settings.load(), overrides or {})
    if err:
        return 400, {"error": err}
    with LOCK:
        if len(running_ids()) >= MAX_PARALLEL:
            return 409, {"error": f"{MAX_PARALLEL} evaluations are already running. Wait for one to finish.",
                         "running_ids": running_ids()}
        run = Run(idea, s, BUS)
        RUNS[run.id] = (run, asyncio.run_coroutine_threadsafe(pipeline(run), LOOP))
        return 200, {"run_id": run.id}


def read_events(run_id: str) -> list[dict]:
    path = os.path.join(RUNS_DIR, f"{os.path.basename(run_id)}.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def report_for(run_id: str) -> dict | None:
    f = os.path.join("council_results", f"{os.path.basename(run_id)}.json")
    if os.path.isfile(f):
        with open(f) as fh:
            return json.load(fh)
    ev = read_events(run_id)
    if not ev or not any(e["kind"] == "run_start" for e in ev):
        return None
    from deliberation.report import build
    return build(ev)


def list_runs() -> list[dict]:
    out, live = [], set(running_ids())
    for name in sorted(os.listdir(RUNS_DIR) if os.path.isdir(RUNS_DIR) else [], reverse=True)[:50]:
        ev = read_events(name[:-6])
        first = next((e for e in ev if e["kind"] == "run_start"), None)
        if not first:
            continue
        end = next((e for e in reversed(ev) if e["kind"] == "run_end"), None)
        out.append({"id": first["run"], "idea": first["idea"], "started": first["t"],
                    "status": "running" if first["run"] in live else (end["status"] if end else "incomplete"),
                    "spent": ev[-1].get("spent", 0)})
    return out


def models() -> list[dict]:
    if time.time() - _models["at"] > 3600:
        try:
            with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=20) as r:
                data = json.load(r)["data"]
            rows = []
            for m in data:
                if "text" not in m.get("architecture", {}).get("output_modalities", []):
                    continue
                p = m.get("pricing", {})
                try:
                    pin, pout = float(p["prompt"]) * 1e6, float(p["completion"]) * 1e6
                except Exception:
                    continue
                rows.append({"id": m["id"], "in": round(pin, 3), "out": round(pout, 3), "variable_price": pin < 0,
                             "context": m.get("context_length"), "expires": m.get("expiration_date")})
            _models.update(at=time.time(), data=sorted(rows, key=lambda r: (r["variable_price"], r["in"] + r["out"])))
        except Exception:
            pass
    return _models["data"]


CORS_ORIGINS = {o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if o.strip()}


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin")
        if origin in CORS_ORIGINS:  # the frontend served by its own run.sh on another port
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send(self, code: int, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _file(self, base: str, rel: str) -> bool:
        full = os.path.abspath(os.path.join(base, rel.lstrip("/")))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            return False
        with open(full, "rb") as f:
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            self._send(200, f.read(), ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""))
        return True

    def do_GET(self):
        path, _, query = self.path.partition("?")
        q = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        if path in ("/live", "/live/"):
            return self._file(STATIC, "index.html")
        if path in ("/settings", "/settings/"):
            return self._file(STATIC, "settings.html")
        if path == "/" and not os.path.isfile(os.path.join(FRONTEND, "index.html")):
            return self._file(STATIC, "index.html")  # no frontend mounted: the live view is the home page
        if path == "/api/status":
            ids = running_ids()
            return self._send(200, {"running": bool(ids), "run_id": ids[-1] if ids else None, "running_ids": ids,
                                    "max_parallel": MAX_PARALLEL})
        if path == "/api/runs":
            return self._send(200, list_runs())
        parts = path.strip("/").split("/")
        if path.startswith("/api/runs/") and len(parts) == 4:
            run_id, what = os.path.basename(parts[2]), parts[3]
            if what == "events":
                ev = read_events(run_id)
                since = int(q.get("since", 0) or 0)
                return self._send(200, {"events": ev[since:], "next": len(ev), "running": run_id in running_ids()})
            if what == "report":
                rep = report_for(run_id)
                return self._send(200, rep) if rep else self._send(404, {"error": "no such run"})
        if path.startswith("/api/ui/runs/") and len(parts) == 5 and parts[4] == "events":
            run_id = os.path.basename(parts[3])
            ev = read_events(run_id)
            if not ev:
                return self._send(404, {"error": "no such run"})
            end = next((e for e in reversed(ev) if e["kind"] == "run_end"), None)
            ui = compat.ui_events(ev)
            since = int(q.get("since", 0) or 0)
            live = run_id in running_ids()
            return self._send(200, {"events": ui[since:], "next": len(ui), "running": live,
                                    "status": "running" if live else (end or {}).get("status", "incomplete"),
                                    "current": compat.current(ev)})
        if path == "/api/results":
            f = os.path.join("council_results", "index.json")
            if not os.path.isfile(f):
                return self._send(200, {"runs": []})
            with open(f, "rb") as fh:
                return self._send(200, fh.read())
        if path == "/api/settings":
            return self._send(200, settings.public_view(settings.load()))
        if path == "/api/models":
            return self._send(200, models())
        if path == "/api/prompt":
            rel = urllib.request.unquote(q.get("path", ""))
            full = os.path.abspath(os.path.join(ROOT, rel))
            if not full.startswith(os.path.join(ROOT, "prompts") + os.sep) or not os.path.isfile(full):
                return self._send(404, {"error": "not a prompt file"})
            with open(full, "rb") as f:
                return self._send(200, f.read(), "text/plain; charset=utf-8")
        if not path.startswith("/api/") and self._file(FRONTEND, "index.html" if path == "/" else path):
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/evaluate":
            body = self._body()
            idea = str(body.get("idea", "")).strip()
            if not idea or len(idea) > 4000:
                return self._send(400, {"error": "Send an idea of 1 to 4000 characters."})
            code, out = start(idea, body.get("overrides"))
            return self._send(code, out)
        if self.path == "/api/stop":
            target = self._body().get("run_id")
            for rid, (_, f) in list(RUNS.items()):
                if (target in (None, rid)) and not f.done():
                    f.cancel()
            return self._send(200, {"ok": True})
        if self.path == "/api/settings/reset":
            if os.path.exists(settings.path()):
                os.remove(settings.path())
            return self._send(200, {"ok": True})
        if self.path == "/api/settings":
            return self.do_PUT()
        self._send(404, {"error": "not found"})

    def do_PUT(self):
        if self.path != "/api/settings":
            return self._send(404, {"error": "not found"})
        body = self._body()
        body.pop("archetype_library", None)
        errors = settings.save(body)
        self._send(400 if errors else 200, {"ok": not errors, "errors": errors})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8090"))
    print(f"AutoInvestiage on http://localhost:{port} (frontend: {FRONTEND if os.path.isdir(FRONTEND) else 'not mounted'})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
