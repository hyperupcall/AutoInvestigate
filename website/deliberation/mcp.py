"""Minimal MCP client over Streamable HTTP (JSON-RPC 2.0).

Enough to list an MCP server's tools and call them, so an agent can use the
servers assigned to it (see defaults.MCP_CATALOG). Fail-safe by design: any
error is raised, and the caller falls back to a plain model call without tools.
"""
import asyncio
import json
import re
from urllib.parse import quote

import httpx

PROTOCOL_VERSION = "2025-06-18"


class MCPError(Exception):
    pass


def _parse(r: httpx.Response) -> dict:
    """A Streamable HTTP reply is either JSON or a one-event SSE stream."""
    ctype = r.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        for line in r.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    return json.loads(payload)
        raise MCPError("empty event stream")
    return r.json()


class MCPSession:
    """One connection to one MCP server. Use as an async context manager."""

    def __init__(self, url: str, api_key: str = "", timeout: float = 20):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout
        self.tools: list[dict] = []
        self._client: httpx.AsyncClient | None = None
        self._session: str | None = None
        self._id = 0

    async def __aenter__(self) -> "MCPSession":
        self._client = httpx.AsyncClient(timeout=self.timeout)
        await self._initialize()
        self.tools = (await self._rpc("tools/list", {})).get("tools", [])
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        if self._session:
            h["Mcp-Session-Id"] = self._session
        return h

    def _request_url(self) -> str:
        """Smithery's hosted endpoints authenticate with an `?api_key=` query parameter and
        reject a Bearer header with 401, so append the key to the URL. The Bearer header is
        kept for servers that use it; both together are accepted."""
        if not self.api_key or "api_key=" in self.url:
            return self.url
        sep = "&" if "?" in self.url else "?"
        return f"{self.url}{sep}api_key={quote(self.api_key, safe='')}"

    async def _post(self, body: dict) -> httpx.Response:
        r = await self._client.post(self._request_url(), json=body, headers=self._headers())
        sid = r.headers.get("mcp-session-id")
        if sid:
            self._session = sid
        if r.status_code >= 400:
            raise MCPError(f"HTTP {r.status_code} from {self.url}")
        return r

    async def _rpc(self, method: str, params: dict) -> dict:
        self._id += 1
        r = await self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        data = _parse(r)
        if "error" in data:
            raise MCPError(f"{method}: {data['error'].get('message', data['error'])}")
        return data.get("result") or {}

    async def _initialize(self) -> None:
        await self._rpc("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "AutoInvestigate", "version": "1.0"},
        })
        try:  # the initialized notification has no id and expects no reply
            await self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            pass

    async def call(self, name: str, arguments: dict | None = None) -> str:
        """Call a tool and return its text content (or a readable error)."""
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
        parts = []
        for item in result.get("content", []):
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "resource":
                parts.append(json.dumps(item.get("resource", {})))
        text = "\n".join(p for p in parts if p).strip()
        if result.get("isError"):
            return f"[tool error] {text or 'the tool reported an error'}"
        return text or "(no output)"


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(value)).strip("_").lower() or "mcp"


class MCPToolbox:
    """Opens every MCP server an agent can use, exposes their tools to the model,
    and routes a tool call back to the server that owns it.

    Tool names are prefixed with the server id (e.g. `arxiv__search`) so two
    servers can expose the same tool name without colliding."""

    def __init__(self, servers: list[dict], api_key: str = "", timeout: float = 20):
        self.servers = servers
        self.api_key = api_key
        self.timeout = timeout
        self.tools: list[dict] = []
        self._sessions: dict[str, MCPSession] = {}
        self._route: dict[str, tuple[str, str]] = {}

    async def _open(self, srv: dict) -> "MCPSession":
        sess = MCPSession(srv["url"], self.api_key, self.timeout)
        try:
            await sess.__aenter__()
        except Exception:
            await sess.__aexit__(None, None, None)
            raise
        return sess

    async def __aenter__(self) -> "MCPToolbox":
        # Connect to every server at once, so the setup costs one timeout, not one per server.
        sessions = await asyncio.gather(*[self._open(s) for s in self.servers], return_exceptions=True)
        for srv, sess in zip(self.servers, sessions):
            if isinstance(sess, BaseException):  # a server that is down just contributes no tools
                continue
            prefix = _slug(srv["id"])
            self._sessions[prefix] = sess
            for t in sess.tools:
                name = t.get("name")
                if not name:
                    continue
                full = f"{prefix}__{name}"
                self._route[full] = (prefix, name)
                self.tools.append({"type": "function", "function": {
                    "name": full,
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema") or {"type": "object", "properties": {}},
                }})
        return self

    async def __aexit__(self, *exc) -> None:
        for sess in self._sessions.values():
            await sess.__aexit__(*exc)

    async def call(self, name: str, arguments: dict | None = None) -> str:
        route = self._route.get(name)
        if not route:
            return f"[unknown tool {name}]"
        prefix, original = route
        try:
            return await self._sessions[prefix].call(original, arguments)
        except Exception as e:
            return f"[tool error] {type(e).__name__}: {e}"
