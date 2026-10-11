"""Run a built artifact as a local HTTP server.

A person can start the generated prototype, open it at a URL, and stop it again.
Each run is a real ``ThreadingHTTPServer`` on an ephemeral port (``AF_RUN_HOST``,
default ``127.0.0.1``) that serves the artifact's files from storage: the entry
page (``index.html``) at ``/`` and every other file at its path relative to the
artifact's key. Only files that belong to the artifact are served; anything else
is a 404.

The factory also exposes each run through its own port at ``/run/{server-id}/``
(see ``api.py``), so the URL is reachable when the factory runs in a container,
where the run's ephemeral port is not published. Stopping the run shuts the
server down, so that URL stops working too.
"""
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlparse

from .models import new_id, now_iso


def _entry(files: List[str], key: str) -> str:
    """The file to serve at ``/``: the artifact's ``index.html``, else its first file."""
    prefix = key + "/" if key else ""
    for f in files:
        if f.endswith("/index.html"):
            return f[len(prefix):] if f.startswith(prefix) else f
    for f in files:
        if f.startswith(prefix):
            return f[len(prefix):]
    return ""


def _content_type(key: str) -> str:
    ctype = mimetypes.guess_type(key)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype.endswith("javascript"):
        ctype += "; charset=utf-8"
    return ctype


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ArtifactFactory/0.1"

    def log_message(self, *args):  # keep the daemon output clean
        pass

    def do_GET(self):
        run = self.server.run  # type: ignore[attr-defined]
        rel = unquote(urlparse(self.path).path).lstrip("/")
        key = run.resolve(rel)
        if key is None:
            return self._send(404, b"not found\n", "text/plain; charset=utf-8")
        return self._send(200, run.storage.get_bytes(key), _content_type(key))

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class ArtifactServer:
    """One running artifact: a real HTTP server serving its files."""

    def __init__(self, artifact: Dict[str, Any], storage, host: str):
        self.artifact = artifact
        self.storage = storage
        self.host = host
        self.id = new_id("server")
        self.key = artifact.get("key") or ""
        self.files = list(artifact.get("files") or [])
        self.entry = _entry(self.files, self.key)
        self.status = "stopped"
        self.port: Optional[int] = None
        self.url: Optional[str] = None
        self.started_at: Optional[str] = None
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def resolve(self, rel: str) -> Optional[str]:
        """The storage key for a request path, or None if it is not this artifact's."""
        rel = rel or self.entry
        if not rel:
            return None
        candidate = f"{self.key}/{rel}" if self.key else rel
        return candidate if candidate in self.files else None

    def start(self) -> None:
        self._httpd = ThreadingHTTPServer((self.host, 0), _Handler)
        self._httpd.run = self  # type: ignore[attr-defined]
        self.port = self._httpd.server_address[1]
        host = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        self.url = f"http://{host}:{self.port}/"
        self.status = "running"
        self.started_at = now_iso()
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        self.status = "stopped"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "artifact_id": self.artifact.get("id"),
            "plan_id": self.artifact.get("plan_id"),
            "type": self.artifact.get("type"),
            "name": self.artifact.get("name"),
            "status": self.status,
            "host": self.host,
            "port": self.port,
            "url": self.url,
            "path": f"/run/{self.id}/",  # through the factory's own port (see api.py)
            "started_at": self.started_at,
            "files": self.files,
        }


class Runtime:
    """The set of running artifact servers (in-memory; they stop with the process)."""

    def __init__(self, storage, host: str = "127.0.0.1"):
        self.storage = storage
        self.host = host
        self._servers: Dict[str, ArtifactServer] = {}
        self._lock = threading.RLock()

    def start(self, artifact: Dict[str, Any]) -> Dict[str, Any]:
        server = ArtifactServer(artifact, self.storage, self.host)
        server.start()
        with self._lock:
            self._servers[server.id] = server
        return server.to_dict()

    def stop(self, server_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            server = self._servers.get(server_id)
        if server is None:
            return None
        server.stop()
        return server.to_dict()

    def get(self, server_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            server = self._servers.get(server_id)
        return server.to_dict() if server is not None else None

    def list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in self._servers.values()]