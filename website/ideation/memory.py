"""The memory — where the collective keeps the VERY IMPORTANT information.

Not a log: only entries the team judges important are promoted here, and they are
retrieved (by tag/keyword overlap) before a session so the team remembers what it
already learned and does not repeat itself. This is the "generate learnings for the
swarm" idea from IDEAS.md, made concrete.
"""
import re
from typing import Any, Dict, List

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "are", "be", "that", "this", "it", "as", "at", "by", "from", "we", "can",
}


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def relevant(store, topic: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    """The memory entries most relevant to a topic: tag/keyword overlap, then importance."""
    entries = store.list_memory()
    if not entries:
        return []
    topic_tags = {t.lower() for t in (topic.get("tags") or [])}
    topic_words = _tokens(" ".join((topic.get("keywords") or []) + [topic.get("name", ""),
                                                                    topic.get("description", "")]))

    def score(entry: Dict[str, Any]) -> float:
        tags = {t.lower() for t in (entry.get("tags") or [])}
        overlap = len(tags & topic_tags)
        words = _tokens(entry.get("text", ""))
        overlap += len(words & topic_words) * 0.5
        return overlap + (entry.get("importance", 5) / 10.0) + (2 if entry.get("pinned") else 0)

    ranked = sorted(entries, key=score, reverse=True)
    return [e for e in ranked[:limit] if score(e) > 0.5]


def format_memory(entries: List[Dict[str, Any]]) -> str:
    if not entries:
        return "(nothing remembered yet)"
    return "\n".join(f"- [{e.get('kind', 'fact')}] {e.get('text', '')}" for e in entries)


def promote(store, topic: Dict[str, Any], proposals: List[Dict[str, Any]],
            source_signal_ids: List[str] | None = None) -> List[Dict[str, Any]]:
    """Store the team's memory proposals that clear the importance bar."""
    kept = []
    for p in proposals or []:
        text = str(p.get("text", "")).strip()
        if not text:
            continue
        importance = int(p.get("importance", 5) or 5)
        if importance < 7:  # only the VERY IMPORTANT survives
            continue
        entry = store.add_memory({
            "id": _new_id("mem"),
            "kind": p.get("kind", "fact"),
            "text": text,
            "importance": importance,
            "tags": p.get("tags") or topic.get("tags") or [],
            "topic_id": topic.get("id"),
            "source_signal_ids": source_signal_ids or [],
        })
        kept.append(entry)
    return kept


def _new_id(prefix: str) -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
