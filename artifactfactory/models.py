from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Idea:
    id: str
    text: str
    title: str = ""
    validated: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    plan_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Artifact:
    id: str
    plan_id: str
    job_id: str
    type: str
    name: str
    key: str
    uri: str
    files: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    id: str
    idea_id: str
    idea_text: str
    title: str
    status: str = "planned"
    artifact_specs: List[Dict[str, Any]] = field(default_factory=list)
    artifact_ids: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    error: Optional[str] = None  # why the last implementation failed, shown in the dashboard
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Job:
    id: str
    plan_id: str
    status: str = "queued"
    artifact_ids: List[str] = field(default_factory=list)
    error: Optional[str] = None
    created_at: str = field(default_factory=now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
