"""Tests for the ideation collective: the SQLite store, the topic watchlist, the
level tree, the message validation and the HTTP routes. No model calls are made."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from ideation import agents, memory
from ideation.api import make_handler
from ideation.config import Config
from ideation.scheduler import Scheduler
from ideation.service import Service
from ideation.store import Store
from ideation.topics import seed_if_empty


@pytest.fixture()
def service(tmp_path):
    config = Config(data_dir=str(tmp_path))
    store = Store(config.db_path)
    seed_if_empty(store)
    return Service(config, store)


def test_seed_topics(service):
    assert len(service.store.list_topics()) == 13  # seeded by the fixture
    assert seed_if_empty(service.store) == 0     # idempotent


def test_signal_dedup(service):
    topic = service.store.list_topics()[0]
    sig = {"id": "sig-1", "topic_id": topic["id"], "source": "arxiv",
           "title": "A paper", "url": "http://x", "text": "body", "hash": "h1"}
    assert service.store.add_signal(dict(sig)) is True
    assert service.store.add_signal({**sig, "id": "sig-2"}) is False  # same hash
    assert service.store.count_signals(topic["id"]) == 1


def test_tree_groups_abstract_and_concrete(service):
    topic = service.store.list_topics()[0]
    service.store.add_idea({"id": "i1", "topic_id": topic["id"], "kind": "abstract",
                            "text": "An abstract direction.", "justification": ["a", "b", "c"]})
    service.store.add_idea({"id": "i2", "topic_id": topic["id"], "kind": "concrete",
                            "text": "A concrete thing.", "justification": ["a", "b", "c"]})
    levels = {1: [], 2: []}
    for idea in service.store.list_ideas():
        levels[2 if idea["kind"] == "concrete" else 1].append(idea["id"])
    assert levels[1] == ["i1"]
    assert levels[2] == ["i2"]


def test_team_is_three_agents():
    assert [a["id"] for a in agents.AGENTS] == ["idea_generator", "builder", "analyzer"]
    assert agents.TEAM_ORDER == ["idea_generator", "builder", "analyzer"]


def test_message_validation():
    good = {"context": "lots of text", "idea": "One sentence.", "justification": ["a", "b", "c"]}
    assert agents.validate_message(good) is None
    assert agents.validate_message({**good, "context": ""}) is not None
    assert agents.validate_message({**good, "justification": ["only one"]}) is not None
    assert agents.validate_message({**good, "idea": "x" * 500}) is not None
    assert agents.validate_builder({**good, "build": {"mvp": 7, "artifact": 6}}) is None
    assert agents.validate_builder({**good}) is not None
    assert agents.validate_analyzer({**good, "analysis": {"verdict": "makes_sense"}}) is None
    assert agents.validate_analyzer({**good, "analysis": {"verdict": "maybe"}}) is not None


def test_memory_promotion_keeps_only_important(service):
    topic = service.store.list_topics()[0]
    kept = memory.promote(service.store, topic, [
        {"kind": "constraint", "text": "X is impossible.", "importance": 9},
        {"kind": "fact", "text": "Minor detail.", "importance": 3},
    ])
    assert [e["text"] for e in kept] == ["X is impossible."]
    assert len(service.store.list_memory()) == 1


def test_settings_agent_models(service):
    s = service.settings()
    assert len(s["agents"]) == 3
    assert s["agent_models"] == {}
    assert all(a["model"] == service.config.model for a in s["agents"])

    service.update_settings({"agent_models": {"builder": "google/gemma-3-4b-it", "bogus": "x"}, "rounds": 3})
    s2 = service.settings()
    assert s2["agent_models"] == {"builder": "google/gemma-3-4b-it"}  # unknown agent id dropped
    assert s2["rounds"] == 3
    assert service._model("builder") == "google/gemma-3-4b-it"
    assert service._model("analyzer") == service.config.model
    builder = next(a for a in s2["agents"] if a["id"] == "builder")
    assert builder["model"] == "google/gemma-3-4b-it"


def test_settings_thinking_and_topic_model(service):
    s = service.settings()
    assert s["thinking"] is True and s["topic_thinking"] is True
    assert all(a["thinking"] is True for a in s["agents"])

    service.update_settings({
        "thinking": True,
        "agent_thinking": {"builder": False, "bogus": True},
        "topic_model": "google/gemma-3-4b-it",
        "topic_thinking": False,
    })
    s2 = service.settings()
    assert s2["agent_thinking"] == {"builder": False}   # unknown agent id dropped
    assert service._thinking("builder") is False
    assert service._thinking("analyzer") is True
    assert service._topic_model() == "google/gemma-3-4b-it"
    assert s2["topic_thinking"] is False
    builder = next(a for a in s2["agents"] if a["id"] == "builder")
    assert builder["thinking"] is False


def test_stop_session_marks_cancelled(service):
    topic = service.store.list_topics()[0]
    service.store.create_session({"id": "session-1", "topic_id": topic["id"],
                                  "topic_name": topic["name"], "status": "running"})
    assert service.stop_session("bogus") is None
    stopped = service.stop_session("session-1")
    assert stopped["status"] == "cancelled" and stopped["finished_at"]
    events = service.store.list_events("session-1")
    assert [e["kind"] for e in events] == ["cancelled", "done"]
    assert events[-1]["cancelled"] is True


def test_http_routes(service):
    seed_if_empty(service.store)
    scheduler = Scheduler(service, 900)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service, scheduler))
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    def get(path):
        with urllib.request.urlopen(base + path) as r:
            return r.status, json.loads(r.read())

    def send(method, path, body=None):
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())

    try:
        status, health = get("/health")
        assert status == 200 and health["status"] == "ok"

        status, topics = get("/api/topics")
        assert status == 200 and len(topics["topics"]) == 13

        status, tree = get("/api/tree")
        assert status == 200 and [lvl["level"] for lvl in tree["levels"]] == [1, 2]

        status, created = send("POST", "/api/topics", {"name": "Test topic", "tags": ["x"]})
        assert status == 201 and created["name"] == "Test topic"

        status, updated = send("PUT", f"/api/topics/{created['id']}", {"priority": 5})
        assert status == 200 and updated["priority"] == 5

        status, deleted = send("DELETE", f"/api/topics/{created['id']}")
        assert status == 200 and deleted["deleted"] == created["id"]

        status, info = get("/info")
        assert status == 200 and info["service"] == "ideation"

        status, settings = get("/api/settings")
        assert status == 200 and len(settings["agents"]) == 3

        # terminating a session that is not actually running marks it cancelled
        service.store.create_session({"id": "session-stop", "topic_id": topics["topics"][0]["id"],
                                      "topic_name": "x", "status": "running"})
        status, stopped = send("POST", "/api/sessions/session-stop/stop")
        assert status == 200 and stopped["status"] == "cancelled"
        try:
            send("POST", "/api/sessions/missing/stop")
            assert False, "expected a 404"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404

        status, saved = send("PUT", "/api/settings", {"agent_models": {"analyzer": "openai/gpt-oss-120b"}})
        assert status == 200 and saved["agent_models"] == {"analyzer": "openai/gpt-oss-120b"}

        # drafting without a description is a 400 (no model call is made)
        try:
            send("POST", "/api/topics/draft", {})
            assert False, "expected a 400"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        httpd.shutdown()
        httpd.server_close()
