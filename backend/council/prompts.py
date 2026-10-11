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


def role_name(path: str) -> str:
    return read(path).splitlines()[0].lstrip("# ").strip()
