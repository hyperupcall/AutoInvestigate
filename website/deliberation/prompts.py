"""Markdown prompt loading. Templates use <<NAME>> placeholders (JSON braces stay literal)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path: str) -> str:
    full = path if os.path.isabs(path) else os.path.join(ROOT, path)
    with open(full) as f:
        return f.read()


def render(template: str, **values: str) -> str:
    """Replace <<KEY>> with values. A missing value is an error, not a silent blank."""
    def sub(m):
        key = m.group(1)
        if key not in values:
            raise KeyError(f"prompt placeholder <<{key}>> has no value")
        return str(values[key])
    return re.sub(r"<<([A-Z_]+)>>", sub, template)


def system(name: str, **values: str) -> str:
    return render(read(f"prompts/system/{name}.md"), **values)


def consensus_instruction(kind: str) -> str:
    """kind is 'converge' or 'diverge' (see prompts/system/consensus_instructions.md)."""
    text = read("prompts/system/consensus_instructions.md")
    m = re.search(rf"\[{kind}\]\n(.*?)(?:\n\n\[|\Z)", text, re.S)
    if not m:
        raise KeyError(kind)
    return m.group(1).strip()


def resolve_consensus(group: dict) -> str:
    """The discussion style for a group: 'converge' or 'diverge'.

    A group may set 'auto' to let the backend decide. The backend picks 'diverge' for
    groups of customer archetypes — the people being served, who are not expected to
    agree — and 'converge' for groups of specialists working toward a shared view."""
    kind = str(group.get("consensus") or "converge").strip().lower()
    if kind in ("converge", "diverge"):
        return kind
    hay = " ".join([str(group.get("id", "")), str(group.get("name", "")), str(group.get("description", ""))]
                   + [str(a.get("prompt", "")) for a in group.get("agents", [])]).lower()
    return "diverge" if any(w in hay for w in ("market", "customer", "archetype")) else "converge"


def role_name(path: str) -> str:
    return read(path).splitlines()[0].lstrip("# ").strip()
