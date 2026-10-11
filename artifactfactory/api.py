import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .service import Service


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
    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, status: int, data: bytes, content_type: str,
                    filename: Optional[str] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
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

    def _handle(self, method: str) -> None:
        try:
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

        raise ApiError(404, f"no route for {method} {path}")

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
                "GET /", "GET /health", "POST /ideas", "GET /ideas",
                "GET /ideas/{id}", "GET /plans", "GET /plans/{id}",
                "POST /plans/{id}/implement", "GET /jobs", "GET /jobs/{id}",
                "GET /artifacts/{id}", "GET /artifacts/{id}/download",
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
