import asyncio
import json
import os
import tempfile

import httpx

from deliberation import openrouter as orr
from deliberation import prompts, settings
from deliberation.defaults import archetype_library, default_settings


def mock(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def ok(text, cost=0.001, finish="stop"):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}, "finish_reason": finish}],
                                     "usage": {"cost": cost, "prompt_tokens": 10, "completion_tokens": 5}})


def run(coro):
    return asyncio.run(coro)


def test_cost_budget_and_stop():
    b = orr.RunBudget(0.0025)
    c = mock(lambda r: ok("hi", 0.001))
    async def go():
        for _ in range(4):  # the cap is checked before each call, so the 3rd call lands and the 4th is refused
            await orr.chat("m/x", [{"role": "user", "content": "q"}], "k", budget=b, client=c)
    try:
        run(go()); assert False, "should have stopped"
    except orr.BudgetExceeded:
        pass
    assert abs(b.spent - 0.003) < 1e-9 and b.calls == 3


def test_retry_on_429_then_success():
    n = {"i": 0}
    def h(r):
        n["i"] += 1
        return httpx.Response(429, headers={"retry-after": "0"}) if n["i"] == 1 else ok("fine")
    res = run(orr.chat("m/x", [{"role": "user", "content": "q"}], "k", client=mock(h)))
    assert res.text == "fine" and n["i"] == 2


def test_truncated_empty_reply_retries_with_reasoning_off():
    seen = []
    def h(r):
        body = json.loads(r.content); seen.append(body)
        return ok("", finish="length") if len(seen) == 1 else ok('{"ok": true}')
    res = run(orr.chat("m/x", [{"role": "user", "content": "q"}], "k", max_tokens=100, reasoning_effort="low", client=mock(h)))
    assert res.text == '{"ok": true}'
    assert seen[0]["reasoning"] == {"effort": "low"} and seen[1]["reasoning"] == {"effort": "none"}
    assert seen[1]["max_tokens"] == 200


def test_online_suffix_becomes_plugin_with_result_cap():
    seen = []
    def h(r):
        seen.append(json.loads(r.content)); return ok("x")
    run(orr.chat("a/b:online", [{"role": "user", "content": "q"}], "k", web_results=2, client=mock(h)))
    assert seen[0]["model"] == "a/b" and seen[0]["plugins"] == [{"id": "web", "max_results": 2}]


def test_http_error_message_never_contains_key():
    c = mock(lambda r: httpx.Response(401, json={"error": {"message": "bad key"}}))
    try:
        run(orr.chat("m/x", [{"role": "user", "content": "q"}], "SECRET-KEY-123", client=c)); assert False
    except orr.OpenRouterError as e:
        assert "SECRET-KEY-123" not in str(e) and "401" in str(e)


def test_extract_json_handles_fences_and_chatter():
    assert orr.extract_json('Sure!\n```json\n{"a": {"b": "}"}, "c": 1}\n```\nDone') == {"a": {"b": "}"}, "c": 1}
    assert orr.extract_json("no json here") is None


def test_chat_json_retries_until_valid():
    n = {"i": 0}
    def h(r):
        n["i"] += 1
        return ok("not json") if n["i"] == 1 else ok('{"decision": "stop"}')
    obj, _ = run(orr.chat_json("m/x", [{"role": "user", "content": "q"}], "k",
                               lambda o: None if o.get("decision") else "missing decision", client=mock(h)))
    assert obj == {"decision": "stop"} and n["i"] == 2


def test_prompt_rendering_requires_every_placeholder():
    assert prompts.render("hi <<NAME>>", NAME="x") == "hi x"
    try:
        prompts.render("hi <<NAME>>"); assert False
    except KeyError:
        pass
    assert "agree" in prompts.consensus_instruction("diverge") or "expected" in prompts.consensus_instruction("diverge")


def test_defaults_shape_and_every_prompt_exists():
    s = default_settings()
    assert [g["id"] for g in s["groups"]] == ["research", "private_equity", "market"]
    assert [len(g["agents"]) for g in s["groups"]] == [4, 4, 5]
    assert settings.validate(s) == []
    assert len(archetype_library()) >= 10


def test_settings_mask_roundtrip_and_permissions():
    with tempfile.TemporaryDirectory() as d:
        os.environ["SETTINGS_PATH"] = os.path.join(d, "settings.json")
        old_env = os.environ.get("OPENROUTER_API_KEY")
        os.environ["OPENROUTER_API_KEY"] = "sk-or-env"
        s = default_settings(); s["groups"][0]["agents"][0]["api_key"] = "sk-agent"
        assert settings.save(s) == []
        view = settings.public_view(settings.load())
        assert "sk-or-env" not in json.dumps(view)
        assert view["groups"][0]["agents"][0]["api_key"] == settings.MASK
        assert settings.save(view | {"deliberation_seconds": 30}) == []  # masked values keep the stored keys
        again = settings.load()
        assert again["groups"][0]["agents"][0]["api_key"] == "sk-agent"
        assert again["deliberation_seconds"] == 30
        assert oct(os.stat(os.environ["SETTINGS_PATH"]).st_mode & 0o777) == "0o600"
        assert settings.resolve_key("", again) == "sk-or-env" and settings.resolve_key("own", again) == "own"
        bad = settings.load(); bad["deliberation_seconds"] = 1
        assert settings.save(bad) and settings.load()["deliberation_seconds"] == 30  # invalid input is not stored
        del os.environ["SETTINGS_PATH"]
        if old_env is None: os.environ.pop("OPENROUTER_API_KEY", None)
        else: os.environ["OPENROUTER_API_KEY"] = old_env


def test_mcp_key_prefers_env_over_stored():
    s = default_settings(); s["mcp"]["api_key"] = "stored-smithery"
    saved = os.environ.pop(settings.MCP_KEY_ENV, None)  # ignore any real .env loaded at import
    try:
        assert settings.mcp_key(s) == "stored-smithery"  # no env: the stored setting is used
        assert settings.public_view(s)["mcp"]["api_key_env"] is False
        os.environ[settings.MCP_KEY_ENV] = "env-smithery"
        assert settings.mcp_key(s) == "env-smithery"  # .env wins over the stored setting
        view = settings.public_view(s)
        assert view["mcp"]["api_key"] == settings.MASK and view["mcp"]["api_key_env"] is True
        assert "env-smithery" not in json.dumps(view)
    finally:
        os.environ.pop(settings.MCP_KEY_ENV, None)
        if saved is not None:
            os.environ[settings.MCP_KEY_ENV] = saved


def test_reasoning_mandatory_model_falls_back_to_low():
    seen = []
    def h(r):
        body = json.loads(r.content); seen.append(body.get("reasoning"))
        if body["reasoning"]["effort"] == "none":
            return httpx.Response(400, json={"error": {"message": "Reasoning is mandatory for this endpoint and cannot be disabled."}})
        return ok("done")
    res = run(orr.chat("m/x", [{"role": "user", "content": "q"}], "k", reasoning_effort="none", client=mock(h)))
    assert res.text == "done" and seen == [{"effort": "none"}, {"effort": "low"}]


def test_trim_to_sentence():
    assert orr.trim_to_sentence("This is a complete first sentence. The second is cut off and the") == "This is a complete first sentence."
    assert orr.trim_to_sentence("Complete sentence.") == "Complete sentence."


def test_cut_off_reply_is_retried_with_more_room_unless_trimming():
    seen = []
    def h(r):
        b = json.loads(r.content); seen.append(b["max_tokens"])
        return ok("partial answer", finish="length") if len(seen) == 1 else ok("full answer.")
    res = run(orr.chat("m/x", [{"role": "user", "content": "q"}], "k", max_tokens=100, client=mock(h)))
    assert res.text == "full answer." and seen == [100, 200]
    seen.clear()
    res = run(orr.chat("m/x", [{"role": "user", "content": "q"}], "k", max_tokens=100, on_length="trim", client=mock(h)))
    assert res.text == "partial answer" and seen == [100]
