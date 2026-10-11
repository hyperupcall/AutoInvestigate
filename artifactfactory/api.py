import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from . import mvp
from .service import Service
from .web import dashboard_html

# Origins allowed to call this API from a browser. The frontend may be served on
# its own port (run.sh defaults to 8000; the evaluation backend serves it on 8090)
# or opened straight from disk, where the browser sends "Origin: null". Override
# with AF_CORS_ORIGINS (comma-separated).
CORS_ORIGINS = {
    o.strip()
    for o in os.environ.get(
        "AF_CORS_ORIGINS",
        "null,"
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:8090,http://127.0.0.1:8090",
    ).split(",")
    if o.strip()
}

# Any port on the local machine is fine too, so run.sh can be started on a
# non-default port without the dashboard losing the API.
LOCAL_ORIGIN = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$")


def origin_allowed(origin: str) -> bool:
    return origin in CORS_ORIGINS or bool(LOCAL_ORIGIN.match(origin))


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    service: Service

    def log_message(self, format, *args):  # keep test/daemon output clean
        pass

    # ------------------------------------------------------------- responses
    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin and origin_allowed(origin):  # the frontend served on its own port, or file://
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
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

    def _send_html(self, status: int, document: str) -> None:
        body = document.encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, status: int, data: bytes, content_type: str,
                    filename: Optional[str] = None) -> None:
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
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

    def do_DELETE(self):
        self._handle("DELETE")

    def _handle(self, method: str) -> None:
        try:
            # Always drain the request body. With HTTP/1.1 keep-alive, any unread
            # bytes would be parsed as the next request line (and answered 501).
            self._body_bytes = b""
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                if length > 0:
                    self._body_bytes = self.rfile.read(length)
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            self._route(method, parsed.path, query)
        except ApiError as exc:
            self._send_json(exc.status, {"error": exc.message})
        except Exception as exc:  # noqa: BLE001 - surface unexpected errors as 500
            self._send_json(500, {"error": str(exc)})

    def _route(self, method: str, path: str, query: Dict[str, Any]) -> None:
        path = path.rstrip("/") or "/"

        if method == "GET" and path == "/":
            return self._send_html(200, self._render_home())
        if method == "GET" and path == "/info":
            return self._send_json(200, self._info())
        if method == "GET" and path == "/health":
            return self._send_json(200, {"status": "ok"})

        if method == "POST" and path == "/ideas":
            return self._post_ideas()
        if method == "GET" and path == "/ideas":
            return self._send_json(200, {"ideas": self.service.list_ideas()})

        m = re.fullmatch(r"/ideas/([^/]+)", path)
        if method == "GET" and m:
            idea = self.service.get_idea(m.group(1))
            if idea is None:
                raise ApiError(404, "idea not found")
            return self._send_json(200, idea)
        if method == "DELETE" and m:  # remove an evaluation: idea, plan and every artifact
            if not self.service.delete_idea(m.group(1)):
                raise ApiError(404, "idea not found")
            return self._send_json(200, {"ok": True})

        if method == "GET" and path == "/plans":
            return self._send_json(200, {"plans": self.service.list_plans()})

        m = re.fullmatch(r"/plans/([^/]+)/implement", path)
        if method == "POST" and m:
            job = self.service.start_implementation(m.group(1))
            if job is None:
                raise ApiError(404, "plan not found")
            return self._send_json(202, job)

        m = re.fullmatch(r"/plans/([^/]+)", path)
        if method == "GET" and m:
            plan = self.service.get_plan(m.group(1))
            if plan is None:
                raise ApiError(404, "plan not found")
            return self._send_json(200, plan)

        if method == "GET" and path == "/jobs":
            return self._send_json(200, {"jobs": self.service.list_jobs()})

        m = re.fullmatch(r"/jobs/([^/]+)", path)
        if method == "GET" and m:
            job = self.service.get_job(m.group(1))
            if job is None:
                raise ApiError(404, "job not found")
            return self._send_json(200, job)

        m = re.fullmatch(r"/artifacts/([^/]+)/view", path)
        if method == "GET" and m:  # the prototype page itself, for the frontend's preview and "open full screen"
            artifact = self.service.get_artifact(m.group(1))
            entry = mvp.entry_file((artifact or {}).get("files", []))
            if not entry or not self.service.storage.exists(entry):
                raise ApiError(404, "no viewable page for this artifact")
            body = mvp._inject_csp(self.service.storage.get_bytes(entry).decode("utf-8", "replace")).encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", mvp.CSP + "; sandbox allow-scripts")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        m = re.fullmatch(r"/artifacts/([^/]+)/run", path)
        if method == "POST" and m:  # run the built artifact as a local server
            server = self.service.start_artifact_server(m.group(1))
            if server is None:
                raise ApiError(404, "artifact not found")
            return self._send_json(201, {"server": server})

        m = re.fullmatch(r"/artifacts/([^/]+)/download", path)
        if method == "GET" and m:
            result = self.service.download_artifact(m.group(1))
            if result is None:
                raise ApiError(404, "artifact not found")
            filename, content_type, data = result
            return self._send_bytes(200, data, content_type, filename)

        m = re.fullmatch(r"/artifacts/([^/]+)", path)
        if method == "GET" and m:
            artifact = self.service.get_artifact(m.group(1))
            if artifact is None:
                raise ApiError(404, "artifact not found")
            return self._send_json(200, artifact)
        if method == "DELETE" and m:  # remove one artifact (its files too)
            if not self.service.delete_artifact(m.group(1)):
                raise ApiError(404, "artifact not found")
            return self._send_json(200, {"ok": True})

        if method == "GET" and path == "/servers":
            return self._send_json(200, {"servers": self.service.list_servers()})

        m = re.fullmatch(r"/servers/([^/]+)/stop", path)
        if method == "POST" and m:
            server = self.service.stop_artifact_server(m.group(1))
            if server is None:
                raise ApiError(404, "server not found")
            return self._send_json(200, {"server": server})

        m = re.fullmatch(r"/servers/([^/]+)", path)
        if method == "GET" and m:
            server = self.service.get_server(m.group(1))
            if server is None:
                raise ApiError(404, "server not found")
            return self._send_json(200, server)

        # A running artifact, proxied through the factory's own port so the URL works
        # when the factory runs in a container (the run's ephemeral port is not published).
        m = re.fullmatch(r"/run/([^/]+)(/.*)?", path)
        if method == "GET" and m:
            return self._proxy_server(m.group(1), m.group(2) or "/")

        # Everything else that is not an API route is a frontend static asset
        # (the dashboard page and its shared css/js).
        if method == "GET" and not path.startswith("/api/") and self._serve_static(path):
            return

        raise ApiError(404, f"no route for {method} {path}")

    def _proxy_server(self, server_id: str, rest: str) -> None:
        server = self.service.get_server(server_id)
        if server is None:
            raise ApiError(404, "server not found")
        if server.get("status") != "running":
            raise ApiError(409, "server is not running")
        target = f"http://127.0.0.1:{server['port']}{rest}"
        try:
            with urllib.request.urlopen(target, timeout=10) as resp:
                body = resp.read()
                ctype = resp.headers.get("Content-Type", "application/octet-stream")
        except urllib.error.HTTPError as exc:
            return self._send_bytes(exc.code, exc.read(),
                                    exc.headers.get("Content-Type", "text/plain; charset=utf-8"))
        except (urllib.error.URLError, OSError):
            raise ApiError(502, "the artifact server is not reachable")
        return self._send_bytes(200, body, ctype)

    def _render_home(self) -> str:
        return dashboard_html(self.service.config.frontend_dir)

    def _serve_static(self, path: str) -> bool:
        """Serve a file from the frontend directory (the dashboard's css/js)."""
        base = os.path.abspath(self.service.config.frontend_dir)
        rel = path.lstrip("/") or "artifactfactory.html"
        full = os.path.abspath(os.path.join(base, rel))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            return False
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send_bytes(200, f.read(), ctype)
        return True

    def _post_ideas(self) -> None:
        body = self._read_json()
        if not isinstance(body, dict):
            raise ApiError(400, "body must be a JSON object")
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ApiError(400, "field 'text' is required")
        result = self.service.add_idea(
            text=text,
            title=body.get("title", ""),
            validated=body.get("validated", True),
            metadata=body.get("metadata"),
            options=body.get("options"),
        )
        return self._send_json(201, result)

    def _info(self) -> Dict[str, Any]:
        return {
            "service": "artifactfactory",
            "name": "Artifact Factory",
            "version": "0.1.0",
            "routes": [
                "GET / (HTML dashboard, from the frontend)", "GET /info", "GET /health",
                "POST /ideas", "GET /ideas",
                "GET /ideas/{id}", "DELETE /ideas/{id}", "GET /plans", "GET /plans/{id}",
                "POST /plans/{id}/implement", "GET /jobs", "GET /jobs/{id}",
                "GET /artifacts/{id}", "DELETE /artifacts/{id}",
                "GET /artifacts/{id}/download", "GET /artifacts/{id}/view",
                "POST /artifacts/{id}/run", "GET /servers", "GET /servers/{id}",
                "POST /servers/{id}/stop", "GET /run/{id}/ (the running artifact)",
            ],
        }


def make_handler(service: Service):
    return type("BoundHandler", (Handler,), {"service": service})


def serve(config) -> None:
    service = Service(config)
    handler = make_handler(service)
    httpd = ThreadingHTTPServer((config.host, config.port), handler)
    url = f"http://{config.host}:{httpd.server_address[1]}"
    print(f"Artifact Factory listening on {url}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
