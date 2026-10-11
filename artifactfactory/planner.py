from typing import Any, Dict, List, Optional

from .artifacts import slugify
from .models import new_id, now_iso

DEFAULT_ARTIFACTS: List[Dict[str, Any]] = [
    {"type": "source_repository", "params": {"language": "python"}},
    {"type": "npm_package", "params": {}},
    {"type": "docker_image", "params": {}},
    {"type": "literature_review", "params": {}},
    {"type": "tarball", "params": {}},
]

_STEP_LABELS = {
    "source_repository": "Scaffold source repository",
    "npm_package": "Scaffold NPM package",
    "docker_image": "Build Docker image manifest",
    "literature_review": "Write literature review",
    "tarball": "Package all artifacts into a tarball",
    "mvp_prototype": "Build an interactive prototype (MVP) of the idea",
}


def _derive_title(idea: Dict[str, Any]) -> str:
    title = (idea.get("title") or "").strip()
    if title:
        return title
    text = (idea.get("text") or "").strip()
    if not text:
        return "Untitled Idea"
    first = text.split(".")[0].strip()
    return (first or text)[:80]


def create_plan(idea: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    options = options or {}
    title = _derive_title(idea)
    name = slugify(title)

    raw_specs = options.get("artifacts")
    if raw_specs:
        specs: List[Dict[str, Any]] = []
        for raw in raw_specs:
            if isinstance(raw, str):
                specs.append({"type": raw, "params": {}})
            else:
                specs.append({"type": raw["type"], "params": dict(raw.get("params") or {})})
    else:
        specs = [{"type": a["type"], "params": dict(a["params"])} for a in DEFAULT_ARTIFACTS]

    language = options.get("language")
    if language:
        for s in specs:
            if s["type"] == "source_repository":
                s["params"]["language"] = language

    artifact_specs = [
        {"type": s["type"], "name": name, "params": s["params"], "status": "pending"}
        for s in specs
    ]

    steps: List[str] = []
    for s in artifact_specs:
        label = _STEP_LABELS.get(s["type"], f"Build {s['type']}")
        if s["type"] == "source_repository":
            label += f" ({s['params'].get('language', 'python')})"
        steps.append(label)

    now = now_iso()
    return {
        "id": new_id("plan"),
        "idea_id": idea["id"],
        "idea_text": idea.get("text", ""),
        "title": title,
        "status": "planned",
        "artifact_specs": artifact_specs,
        "artifact_ids": [],
        "steps": steps,
        "created_at": now,
        "updated_at": now,
    }
