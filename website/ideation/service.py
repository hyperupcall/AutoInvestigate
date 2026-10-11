"""Orchestration for the ideation collective.

Two things happen here:

  * a **cycle** — poll every enabled topic's sources, store the new signals;
  * a **session** — a team of agents reads a topic's newest signals and works
    together, round by round, to refine them into one idea.

Everything is fail-safe: a dead source, a missing key or a model error is recorded
as an event and the session carries on with what it has.
"""
import json
import os
import threading
import uuid
from typing import Any, Dict, List, Optional

from deliberation import openrouter

from . import agents, memory, sources
from .store import now_iso

# Settings that can be changed from the Ideation View. Persisted next to the database.
SETTING_FIELDS = ("model", "thinking", "poll_interval_seconds", "max_cost_usd", "rounds",
                  "signals_per_topic", "autostart", "agent_models", "agent_thinking",
                  "topic_model", "topic_thinking")
# Fields whose value is a map of agent id -> value (filtered against the known agents).
AGENT_MAP_FIELDS = ("agent_models", "agent_thinking")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class Service:
    def __init__(self, config, store):
        self.config = config
        self.store = store
        self._lock = threading.RLock()
        self._running: set[str] = set()   # session ids currently running

    # ------------------------------------------------------------- polling
    def poll_topic(self, topic: Dict[str, Any], limit_per_source: int = 5) -> int:
        """Fetch a topic's sources and store the new signals. Returns how many were new."""
        found = sources.poll_topic(topic, limit_per_source=limit_per_source)
        new = 0
        for sig in found:
            sig["id"] = new_id("sig")
            sig["topic_id"] = topic["id"]
            if self.store.add_signal(sig):
                new += 1
        self.store.update_topic(topic["id"], last_polled_at=now_iso())
        return new

    def run_cycle(self, trigger: str = "schedule") -> Dict[str, Any]:
        """Poll every enabled topic; run a session for any topic that found new signals."""
        summary = {"trigger": trigger, "topics": [], "sessions": []}
        for topic in self.store.list_topics(enabled_only=True):
            new = self.poll_topic(topic)
            summary["topics"].append({"id": topic["id"], "name": topic["name"], "new_signals": new})
            if new:
                session = self.run_session(topic["id"], trigger=trigger)
                if session:
                    summary["sessions"].append(session["id"])
        return summary

    # ------------------------------------------------------------- sessions
    def _create_session(self, topic_id: str, trigger: str) -> Optional[Dict[str, Any]]:
        topic = self.store.get_topic(topic_id)
        if topic is None:
            return None
        return self.store.create_session({
            "id": new_id("session"), "topic_id": topic_id, "topic_name": topic["name"],
            "status": "running", "model": self.config.model, "trigger": trigger,
        })

    def start_session_async(self, topic_id: str, trigger: str = "manual") -> Optional[Dict[str, Any]]:
        """Start a session in a background thread. Returns the session row immediately."""
        session = self._create_session(topic_id, trigger)
        if session is None:
            return None
        with self._lock:
            self._running.add(session["id"])
        threading.Thread(target=self._run_session_thread, args=(session["id"],), daemon=True).start()
        return session

    def _run_session_thread(self, session_id: str) -> None:
        try:
            self.run_session_by_id(session_id)
        finally:
            with self._lock:
                self._running.discard(session_id)

    def run_session(self, topic_id: str, trigger: str = "manual") -> Optional[Dict[str, Any]]:
        """Run a session synchronously (used by the scheduler)."""
        session = self._create_session(topic_id, trigger)
        if session is None:
            return None
        with self._lock:
            self._running.add(session["id"])
        try:
            self.run_session_by_id(session["id"])
        finally:
            with self._lock:
                self._running.discard(session["id"])
        return self.store.get_session(session["id"])

    def _emit(self, session_id: str, kind: str, data: Dict[str, Any]) -> None:
        self.store.add_event(session_id, kind, data)

    def run_session_by_id(self, session_id: str) -> None:
        session = self.store.get_session(session_id)
        if session is None:
            return
        topic = self.store.get_topic(session["topic_id"]) or {"id": session["topic_id"], "name": session["topic_name"]}
        budget = openrouter.RunBudget(self.config.max_cost_usd)
        roster = agents.public_agents(self.config.model, self.config.agent_models,
                                      self.config.thinking, self.config.agent_thinking)
        signals = self.store.list_signals(topic["id"], limit=self.config.signals_per_topic)
        remembered = memory.relevant(self.store, topic)

        self._emit(session_id, "session-start", {
            "session": {"id": session_id, "topic_id": topic["id"], "topic_name": topic.get("name", ""),
                        "status": "running", "model": self.config.model, "trigger": session.get("trigger", "manual")},
            "topic": {"id": topic["id"], "name": topic.get("name", ""), "tags": topic.get("tags", []),
                      "description": topic.get("description", "")},
            "agents": roster,
            "signal_count": len(signals),
            "memory_count": len(remembered),
        })

        report: Dict[str, Any] = {"session": session, "topic": topic, "agents": roster,
                                  "signals": signals, "rounds": [], "idea": None, "memory": []}
        transcript: List[Dict[str, Any]] = []

        # The team speaks in a fixed order each round: generate, then score, then analyze.
        for r in range(1, self.config.rounds + 1):
            self._emit(session_id, "phase", {"text": f"Round {r}"})
            round_turns = []
            for agent_id in agents.TEAM_ORDER:
                agent = agents.agent_by_id(agent_id)
                try:
                    msg = agents.run_agent(
                        agent, self._prompt_for(agent_id, topic, transcript, signals, remembered, r),
                        model=self._model(agent_id), thinking=self._thinking(agent_id), budget=budget)
                    transcript.append(msg)
                    round_turns.append(msg)
                    self._emit(session_id, "turn", self._turn_event(msg, round=r))
                except Exception as exc:  # noqa: BLE001
                    self._emit(session_id, "failed", {"agent_id": agent_id, "round": r, "reason": str(exc)})
            report["rounds"].append({"round": r, "turns": round_turns})

        # The final idea is the generator's latest; the build score and the analysis
        # come from the builder and the analyzer.
        generator = self._last(transcript, "idea_generator") or (transcript[-1] if transcript else None)
        builder = self._last(transcript, "builder")
        analyzer = self._last(transcript, "analyzer")
        build = (builder or {}).get("build") or {}
        analysis = (analyzer or {}).get("analysis") or {}

        if generator and generator.get("idea"):
            kind = "concrete" if float(build.get("mvp", 0) or 0) >= 6 else "abstract"
            idea = self.store.add_idea({
                "id": new_id("idea"), "topic_id": topic["id"], "session_id": session_id,
                "kind": kind, "text": generator["idea"],
                "justification": generator.get("justification", []),
                "context": generator.get("context", ""),
                "sources": generator.get("sources", []), "tags": topic.get("tags", []),
                "parent_idea_ids": [], "artifact_type": "",
                "score": {"build": build, "analysis": analysis},
            })
            report["idea"] = idea
            self._emit(session_id, "final", {
                "idea": idea["text"], "kind": idea["kind"], "justification": idea["justification"],
                "build": build, "analysis": analysis, "idea_id": idea["id"],
            })

            proposals: List[Dict[str, Any]] = []
            for m in transcript:
                proposals.extend(m.get("memory") or [])
            promoted = memory.promote(self.store, topic, proposals,
                                      source_signal_ids=[s["id"] for s in signals])
            report["memory"] = promoted
            for entry in promoted:
                self._emit(session_id, "memory", {"text": entry["text"], "kind": entry["kind"],
                                                  "importance": entry["importance"]})

        report["session"] = {**session, "status": "done", "cost": budget.spent, "finished_at": now_iso()}
        self.store.update_session(session_id, status="done", cost=budget.spent,
                                  finished_at=now_iso(), report=report)
        self._emit(session_id, "done", {"cost": budget.spent, "idea_id": (report["idea"] or {}).get("id")})

    # ------------------------------------------------------------- prompts
    def _prompt_for(self, agent_id, topic, transcript, signals, remembered, round_no) -> str:
        head = (f"TOPIC: {topic.get('name', '')}\n"
                f"DESCRIPTION: {topic.get('description', '')}\n"
                f"ROUND: {round_no}\n\n")
        said = f"WHAT THE TEAM HAS SAID SO FAR:\n{agents.format_transcript(transcript)}\n\n"
        if agent_id == "idea_generator":
            return head + (
                f"WHAT WE ALREADY REMEMBER:\n{memory.format_memory(remembered)}\n\n"
                f"THE NEWEST SIGNALS (read them in full):\n{agents.format_signals(signals)}\n\n"
                + said +
                "Given the description of the idea, do extra research and produce a more finalized idea — "
                "or, if the evidence points elsewhere, a completely different one."
            )
        current = self._current_idea(transcript)
        if agent_id == "builder":
            return head + f"THE IDEA SO FAR: {current}\n\n" + said + \
                "Score how well this idea can be built as an MVP or artifact."
        if agent_id == "analyzer":
            return head + f"THE IDEA SO FAR: {current}\n\n" + said + \
                "Analyze the idea: does it make sense? Do internet research. Is it nonsense?"
        return head + said

    @staticmethod
    def _current_idea(transcript: List[Dict[str, Any]]) -> str:
        for m in reversed(transcript):
            if m.get("agent_id") == "idea_generator" and m.get("idea"):
                return m["idea"]
        return transcript[-1].get("idea", "") if transcript else ""

    @staticmethod
    def _last(transcript: List[Dict[str, Any]], agent_id: str) -> Optional[Dict[str, Any]]:
        for m in reversed(transcript):
            if m.get("agent_id") == agent_id:
                return m
        return None

    @staticmethod
    def _turn_event(msg: Dict[str, Any], round: int) -> Dict[str, Any]:
        return {
            "agent_id": msg.get("agent_id"), "agent_name": msg.get("agent_name"),
            "model": msg.get("model"), "round": round,
            "context": msg.get("context", ""), "idea": msg.get("idea", ""),
            "justification": msg.get("justification", []), "sources": msg.get("sources", []),
            "build": msg.get("build"), "analysis": msg.get("analysis"),
            "cost": msg.get("cost", 0.0),
        }

    # ---------------------------------------------------------- generation
    def draft_topic(self, description: str) -> Dict[str, Any]:
        """Turn a short description into a watchlist topic (name, summary, tags, keywords)."""
        budget = openrouter.RunBudget(self.config.max_cost_usd)
        return agents.draft_topic(description, model=self._topic_model(),
                                  thinking=self.config.topic_thinking, budget=budget)

    def generate(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """The Part 1 contract (mock-backend.generateIdeas): seed/iterate ideas in one call."""
        iteration_type = body.get("iterationType", "refinement")
        variation_count = int(body.get("variationCount", 2) or 2)
        freeform_prompt = body.get("freeformPrompt", "") or ""
        budget = openrouter.RunBudget(self.config.max_cost_usd)
        result = agents.generate_ideas(
            source_ideas=body.get("sourceIdeas") or [],
            iteration_type=iteration_type,
            variation_count=variation_count,
            freeform_prompt=freeform_prompt,
            seed_text=body.get("seedText", "") or "",
            model=self._model("idea_generator"), thinking=self._thinking("idea_generator"), budget=budget)
        operation = {"type": iteration_type, "variationCount": variation_count,
                     "freeformPrompt": freeform_prompt}
        return {
            "label": f"{iteration_type} · {len(result['ideas'])} idea(s)",
            "lineage": [operation],
            "operation": operation,
            "model": result["model"],
            "subject": result.get("subject", ""),
            "ideas": [{"text": i.get("text", ""), "justification": i.get("justification", [])}
                      for i in result.get("ideas", [])],
        }

    # ------------------------------------------------------------ settings
    def _settings_path(self) -> str:
        return os.path.join(self.config.data_dir, "settings.json")

    def _model(self, agent_id: str) -> str:
        """The model an agent uses, honouring the per-agent overrides in settings."""
        return agents.model_for(agent_id, self.config.model, self.config.agent_models)

    def _thinking(self, agent_id: str) -> bool:
        """Whether an agent runs with thinking on, honouring the per-agent overrides."""
        return agents.thinking_for(agent_id, self.config.thinking, self.config.agent_thinking)

    def _topic_model(self) -> str:
        return self.config.topic_model or self.config.model

    def load_settings(self) -> None:
        """Apply persisted settings over the config on startup."""
        try:
            with open(self._settings_path()) as f:
                stored = json.load(f)
        except (FileNotFoundError, ValueError):
            return
        for key in SETTING_FIELDS:
            if key in stored:
                setattr(self.config, key, stored[key])

    def settings(self) -> Dict[str, Any]:
        out = {key: getattr(self.config, key) for key in SETTING_FIELDS}
        out["agents"] = agents.public_agents(self.config.model, self.config.agent_models,
                                             self.config.thinking, self.config.agent_thinking)
        return out

    def update_settings(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        known = {a["id"] for a in agents.AGENTS}
        for key in SETTING_FIELDS:
            if key not in patch:
                continue
            value = patch[key]
            if key == "agent_models":
                value = {str(k): str(v) for k, v in (value or {}).items()
                         if k in known and str(v).strip()}
            elif key == "agent_thinking":
                value = {str(k): bool(v) for k, v in (value or {}).items() if k in known}
            elif key in ("poll_interval_seconds", "rounds", "signals_per_topic"):
                value = int(value)
            elif key == "max_cost_usd":
                value = float(value)
            elif key in ("autostart", "thinking", "topic_thinking"):
                value = bool(value)
            setattr(self.config, key, value)
        os.makedirs(self.config.data_dir, exist_ok=True)
        with open(self._settings_path(), "w") as f:
            json.dump({key: getattr(self.config, key) for key in SETTING_FIELDS}, f, indent=2)
        return self.settings()

    # -------------------------------------------------------------- status
    def status(self) -> Dict[str, Any]:
        with self._lock:
            running = sorted(self._running)
        return {
            "service": "ideation",
            "topics": len(self.store.list_topics()),
            "enabled_topics": len(self.store.list_topics(enabled_only=True)),
            "signals": self.store.count_signals(),
            "ideas": len(self.store.list_ideas(limit=100000)),
            "memory": len(self.store.list_memory(limit=100000)),
            "running_sessions": running,
            "poll_interval_seconds": self.config.poll_interval_seconds,
            "model": self.config.model,
        }
