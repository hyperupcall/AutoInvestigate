"""Agent-side data access. The `planted` field is deliberately stripped here:
only eval/ may read it."""
import json
import os

DATA_DIR = os.getenv("DATA_DIR", "data")


def load_ideas() -> list[dict]:
    with open(os.path.join(DATA_DIR, "ideas.json")) as f:
        return [{k: v for k, v in i.items() if k != "planted"} for i in json.load(f)]


def load_notes(agent: str) -> str:
    with open(os.path.join(DATA_DIR, "private_notes", f"{agent}.md")) as f:
        return f.read()
