"""OpenRouter chat client: cost tracking, per-run budget cap, retries, reasoning control, web search.

Reasoning models can spend the whole token limit on hidden thinking and return nothing, so every call sets a
reasoning effort, and an empty answer that was cut off is retried once with reasoning off and a bigger limit.
"""
import asyncio
import json
import re
from dataclasses import dataclass

import httpx

URL = "https://openrouter.ai/api/v1/chat/completions"
RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


class BudgetExceeded(Exception):
    pass


class OpenRouterError(Exception):
    pass


@dataclass
class ChatResult:
    text: str
    model: str
    cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str | None = None


class RunBudget:
    """Shared by every call in one run. Stops the run when the cap is reached."""

    def __init__(self, max_usd: float):
        self.max_usd, self.spent, self.calls = max_usd, 0.0, 0
        self.by_model: dict[str, float] = {}

    def check(self) -> None:
        if self.spent >= self.max_usd:
            raise BudgetExceeded(f"run stopped: spent ${self.spent:.4f} of the ${self.max_usd:.2f} cap")

    def add(self, model: str, cost: float) -> None:
        self.spent += cost
        self.calls += 1
        self.by_model[model] = self.by_model.get(model, 0.0) + cost


_sem: dict[int, asyncio.Semaphore] = {}


def _semaphore() -> asyncio.Semaphore:
    loop = id(asyncio.get_running_loop())
    return _sem.setdefault(loop, asyncio.Semaphore(8))


def _body(model, messages, max_tokens, effort, temperature, web_results) -> dict:
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "usage": {"include": True}}
    if model.endswith(":online"):  # explicit plugin so the number of search results (cost) is ours to set
        body["model"] = model[: -len(":online")]
        body["plugins"] = [{"id": "web", "max_results": web_results}]
    if effort not in (None, "default"):
        body["reasoning"] = {"effort": effort}
    if temperature is not None:
        body["temperature"] = temperature
    return body


async def chat(model: str, messages: list[dict], api_key: str, *, max_tokens: int = 800,
               reasoning_effort: str | None = "low", temperature: float | None = None,
               web_results: int = 3, budget: RunBudget | None = None,
               client: httpx.AsyncClient | None = None, retries: int = 4, on_length: str = "retry") -> ChatResult:
    if not api_key:
        raise OpenRouterError("no OpenRouter API key configured")
    own = client is None
    client = client or httpx.AsyncClient(timeout=120)
    effort, tokens, widened = reasoning_effort, max_tokens, False
    try:
        for attempt in range(retries + 1):
            if budget:
                budget.check()
            body = _body(model, messages, tokens, effort, temperature, web_results)
            try:
                async with _semaphore():
                    r = await client.post(URL, json=body, headers={
                        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                        "X-Title": "AutoInvestiage"})
            except httpx.TransportError as e:
                if attempt == retries:
                    raise OpenRouterError(f"{model}: network error {type(e).__name__}") from None
                await asyncio.sleep(1.5 * 2 ** attempt)
                continue
            if r.status_code in RETRY_STATUS and attempt < retries:
                wait = float(r.headers.get("retry-after", 0) or 0) or 1.5 * 2 ** attempt
                await asyncio.sleep(min(wait, 20))
                continue
            if r.status_code != 200:
                detail = ""
                try:
                    detail = r.json().get("error", {}).get("message", "")[:200]
                except Exception:
                    pass
                if r.status_code == 400 and "reasoning" in detail.lower() and effort in ("none", "minimal"):
                    effort = "low"  # this model cannot run with reasoning off: use the lowest it allows
                    continue
                raise OpenRouterError(f"{model}: HTTP {r.status_code} {detail}".strip())
            data = r.json()
            choice = data["choices"][0]
            usage = data.get("usage") or {}
            cost = float(usage.get("cost") or 0.0)
            if budget:
                budget.add(model, cost)
            text = (choice["message"].get("content") or "").strip()
            res = ChatResult(text, model, cost, usage.get("prompt_tokens", 0),
                             usage.get("completion_tokens", 0), choice.get("finish_reason"))
            if choice.get("finish_reason") == "length" and not widened and (not text or on_length == "retry"):
                effort, tokens, widened = "none", min(max_tokens * 2, 16000), True  # cut off: retry once with room
                continue
            if not text:
                raise OpenRouterError(f"{model}: empty reply (finish_reason={choice.get('finish_reason')})")
            return res
        raise OpenRouterError(f"{model}: gave up after retries")
    finally:
        if own:
            await client.aclose()


def extract_json(text: str):
    """First balanced JSON object in the text (handles code fences and chatter around it)."""
    t = re.sub(r"```(?:json)?", "", text)
    start = t.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(t)):
            c = t[i]
            if in_str:
                esc = (c == "\\" and not esc)
                if c == '"' and not esc:
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = t.find("{", start + 1)
    return None


async def chat_json(model: str, messages: list[dict], api_key: str, validate=None, *, attempts: int = 2, **kw):
    """Chat until the reply holds a JSON object that passes `validate` (returns an error string or None)."""
    msgs = list(messages)
    last = "no attempt"
    for _ in range(attempts + 1):
        res = await chat(model, msgs, api_key, **kw)
        obj = extract_json(res.text)
        err = "reply did not contain a JSON object" if obj is None else (validate(obj) if validate else None)
        if err is None:
            return obj, res
        last = err
        msgs = msgs + [{"role": "assistant", "content": res.text},
                       {"role": "user", "content": f"That was not valid: {err}. Reply with the JSON object only."}]
    raise OpenRouterError(f"{model}: JSON reply failed validation ({last})")


def trim_to_sentence(text: str) -> str:
    """Cut an answer that hit the token limit back to its last complete sentence."""
    cut = max(text.rfind(". "), text.rfind(".\n"), text.rfind("? "), text.rfind("! "))
    if text.rstrip().endswith((".", "?", "!")):
        return text.rstrip()
    return text[: cut + 1].rstrip() if cut > len(text) * 0.4 else text.rstrip() + "..."
