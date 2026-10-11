"""HTTP API for the ideation daemon.

Serves the JSON API and the Ideation View page (a frontend page, so all frontend
code lives in one place). Mirrors artifactfactory/api.py: a ThreadingHTTPServer,
JSON errors, CORS for the frontend served on its own port, and static assets from
the frontend directory.
"""
import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .service import Service

CORS_ORIGINS = {
    o.strip()
    for o in os.environ.get(
        "ID_CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:8090,http://127.0.0.1:8090,"
        "http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if o.strip()
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    service: Service
    scheduler: Any

    def log_message(self, format, *args):  # keep daemon output clean
        pass

    # ------------------------------------------------------------- responses
    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin in CORS_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> Dict[str, Any]:
        raw = getattr(self, "_body_bytes", b"")
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(400, f"invalid JSON body: {exc}")

    # -------------------------------------------------------------- dispatch
    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def _handle(self, method: str) -> None:
        try:
            self._body_bytes = b""
            if method in ("POST", "PUT"):
                length = int(self.headers.get("Content-Length") or 0)
                if length > 0:
                    self._body_bytes = self.rfile.read(length)
            parsed = urlparse(self.path)
            self._route(method, parsed.path, parse_qs(parsed.query))
        except ApiError as exc:
            self._send_json(exc.status, {"error": exc.message})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": str(exc)})

    def _route(self, method: str, path: str, query: Dict[str, Any]) -> None:
        path = path.rstrip("/") or "/"
        svc = self.service

        if method == "GET" and path == "/":
            return self._serve_static("/ideation.html")
        if method == "GET" and path == "/info":
            return self._send_json(200, self._info())
        if method == "GET" and path == "/health":
            return self._send_json(200, {"status": "ok"})

        # ---- topics
        if method == "GET" and path == "/api/topics":
            return self._send_json(200, {"topics": svc.store.list_topics()})
        if method == "POST" and path == "/api/topics":
            return self._post_topic()
        if method == "POST" and path == "/api/topics/draft":
            body = self._read_json()
            description = str(body.get("description", "")).strip()
            if not description:
                raise ApiError(400, "field 'description' is required")
            return self._send_json(200, svc.draft_topic(description))
        m = re.fullmatch(r"/api/topics/([^/]+)", path)
        if m and method == "PUT":
            topic = svc.store.update_topic(m.group(1), **self._read_json())
            if topic is None:
                raise ApiError(404, "topic not found")
            return self._send_json(200, topic)
        if m and method == "DELETE":
            if not svc.store.delete_topic(m.group(1)):
                raise ApiError(404, "topic not found")
            return self._send_json(200, {"deleted": m.group(1)})

        # ---- ideas
        if method == "GET" and path == "/api/ideas":
            kind = (query.get("kind") or [None])[0]
            topic_id = (query.get("topic_id") or [None])[0]
            return self._send_json(200, {"ideas": svc.store.list_ideas(topic_id=topic_id, kind=kind)})
        if method == "GET" and path == "/api/tree":
            return self._send_json(200, self._tree())
        m = re.fullmatch(r"/api/ideas/([^/]+)", path)
        if m and method == "GET":
            idea = svc.store.get_idea(m.group(1))
            if idea is None:
                raise ApiError(404, "idea not found")
            return self._send_json(200, idea)

        # ---- signals / memory
        if method == "GET" and path == "/api/signals":
            topic_id = (query.get("topic_id") or [None])[0]
            limit = int((query.get("limit") or ["50"])[0])
            return self._send_json(200, {"signals": svc.store.list_signals(topic_id=topic_id, limit=limit)})
        if method == "GET" and path == "/api/memory":
            return self._send_json(200, {"memory": svc.store.list_memory()})

        # ---- sessions
        if method == "GET" and path == "/api/sessions":
            return self._send_json(200, {"sessions": svc.store.list_sessions()})
        if method == "POST" and path == "/api/sessions":
            body = self._read_json()
            topic_id = body.get("topic_id")
            if not topic_id:
                raise ApiError(400, "field 'topic_id' is required")
            session = svc.start_session_async(topic_id, trigger=body.get("trigger", "manual"))
            if session is None:
                raise ApiError(404, "topic not found")
            return self._send_json(202, session)
        m = re.fullmatch(r"/api/sessions/([^/]+)/events", path)
        if m and method == "GET":
            since = int((query.get("since") or ["0"])[0])
            return self._send_json(200, {"events": svc.store.list_events(m.group(1), since=since)})
        m = re.fullmatch(r"/api/sessions/([^/]+)/report", path)
        if m and method == "GET":
            session = svc.store.get_session(m.group(1))
            if session is None:
                raise ApiError(404, "session not found")
            return self._send_json(200, session.get("report") or {})
        m = re.fullmatch(r"/api/sessions/([^/]+)", path)
        if m and method == "GET":
            session = svc.store.get_session(m.group(1))
            if session is None:
                raise ApiError(404, "session not found")
            return self._send_json(200, session)

        # ---- generation (the Part 1 contract)
        if method == "POST" and path == "/api/generate":
            return self._send_json(200, svc.generate(self._read_json()))

        # ---- control / settings
        if method == "POST" and path == "/api/poll":
            return self._send_json(200, svc.run_cycle(trigger="manual"))
        if method == "GET" and path == "/api/status":
            return self._send_json(200, {**svc.status(), "scheduler": self.scheduler.status()})
        if method == "GET" and path == "/api/settings":
            return self._send_json(200, svc.settings())
        if method == "PUT" and path == "/api/settings":
            return self._send_json(200, svc.update_settings(self._read_json()))

        # Everything else that is not an API route is a frontend static asset.
        if method == "GET" and not path.startswith("/api/") and self._serve_static(path):
            return
        raise ApiError(404, f"no route for {method} {path}")

    # ---------------------------------------------------------------- helpers
    def _post_topic(self) -> None:
        body = self._read_json()
        if not isinstance(body, dict) or not str(body.get("name", "")).strip():
            raise ApiError(400, "field 'name' is required")
        from .service import new_id
        topic = self.service.store.add_topic({
            "id": body.get("id") or new_id("topic"),
            "name": body["name"],
            "description": body.get("description", ""),
            "tags": body.get("tags", []),
            "keywords": body.get("keywords", []),
            "sources": body.get("sources", []),
            "priority": body.get("priority", 1),
            "enabled": 1 if body.get("enabled", True) else 0,
        })
        return self._send_json(201, topic)

    def _tree(self) -> Dict[str, Any]:
        """The generated ideas as the frontend's level tree: abstract at level 1, concrete at level 2."""
        topics = {t["id"]: t for t in self.service.store.list_topics()}
        levels: Dict[int, list] = {1: [], 2: []}
        for idea in self.service.store.list_ideas(limit=100000):
            level = 2 if idea.get("kind") == "concrete" else 1
            topic = topics.get(idea.get("topic_id"), {})
            levels[level].append({
                "id": idea["id"], "text": idea["text"], "kind": idea.get("kind", "abstract"),
                "justification": idea.get("justification", []), "sources": idea.get("sources", []),
                "tags": idea.get("tags", []), "score": idea.get("score", {}),
                "artifact_type": idea.get("artifact_type", ""), "topic_id": idea.get("topic_id"),
                "topic_name": topic.get("name", ""), "session_id": idea.get("session_id"),
                "created_at": idea.get("created_at"),
            })
        return {"levels": [{"level": lvl, "ideas": levels[lvl]} for lvl in (1, 2)]}

    def _serve_static(self, path: str) -> bool:
        base = os.path.abspath(self.service.config.frontend_dir)
        rel = path.lstrip("/") or "ideation.html"
        full = os.path.abspath(os.path.join(base, rel))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            return False
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send_bytes(200, f.read(), ctype)
        return True

    def _info(self) -> Dict[str, Any]:
        return {
            "service": "ideation", "name": "Ideation Collective", "version": "0.1.0",
            "routes": [
                "GET / (Ideation View)", "GET /info", "GET /health",
                "GET/POST /api/topics", "POST /api/topics/draft", "PUT/DELETE /api/topics/{id}",
                "GET /api/ideas", "GET /api/ideas/{id}", "GET /api/tree",
                "GET /api/signals", "GET /api/memory", "POST /api/generate",
                "GET/POST /api/sessions", "GET /api/sessions/{id}",
                "GET /api/sessions/{id}/events", "GET /api/sessions/{id}/report",
                "POST /api/poll", "GET /api/status", "GET/PUT /api/settings",
            ],
        }


def make_handler(service: Service, scheduler):
    return type("BoundHandler", (Handler,), {"service": service, "scheduler": scheduler})


def serve(config, service: Service, scheduler) -> None:
    handler = make_handler(service, scheduler)
    httpd = ThreadingHTTPServer((config.host, config.port), handler)
    url = f"http://{config.host}:{httpd.server_address[1]}"
    print(f"Ideation Collective listening on {url}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
