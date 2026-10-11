"""Minimal HTML dashboard for the Artifact Factory.

The daemon is otherwise a JSON API. This module renders a plain, light-mode page
listing every evaluation (idea) the factory has been given, with its plan and
artifact status. It is deliberately bare: no JavaScript, no build step, no
third-party dependencies — just enough HTML to make the server browsable.

The JSON API is unchanged; the dashboard is served at ``GET /`` and the old
service-info payload moved to ``GET /info``.
"""

import html
from typing import Any, Dict, List, Optional


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _derive_title(idea: Dict[str, Any], plan: Optional[Dict[str, Any]]) -> str:
    if plan and plan.get("title"):
        return plan["title"]
    title = (idea.get("title") or "").strip()
    if title:
        return title
    text = (idea.get("text") or "").strip()
    if not text:
        return "Untitled idea"
    first = text.split(".")[0].strip()
    return (first or text)[:80]


def _status_class(status: str) -> str:
    if status in ("implemented", "failed", "implementing"):
        return status
    return ""


def _row(index: int, idea: Dict[str, Any], plan: Optional[Dict[str, Any]]) -> str:
    title = _derive_title(idea, plan)
    text = (idea.get("text") or "").strip()
    received = idea.get("created_at") or ""

    plan_id = (plan or {}).get("id") or idea.get("plan_id")
    if plan:
        status = plan.get("status") or "planned"
    else:
        status = "no plan"
    artifacts = len((plan or {}).get("artifact_ids") or [])

    plan_cell = f'<span class="status {_status_class(status)}">{_esc(status)}</span>'
    if plan_id:
        plan_cell += f'<br><a href="/plans/{_esc(plan_id)}">{_esc(plan_id)}</a>'

    return (
        "<tr>"
        f'<td class="num">{index}</td>'
        f'<td><div class="title">{_esc(title)}</div>'
        f'<div class="text">{_esc(text)}</div></td>'
        f'<td class="muted small">{_esc(received)}</td>'
        f"<td>{plan_cell}</td>"
        f'<td class="num">{artifacts}</td>'
        "</tr>"
    )


def render_evaluations(ideas: List[Dict[str, Any]],
                       plans_by_idea: Dict[str, Dict[str, Any]],
                       info: Optional[Dict[str, Any]] = None) -> str:
    """Render the evaluations dashboard as a complete HTML document."""
    info = info or {}
    version = _esc(info.get("version", ""))

    ordered = sorted(ideas, key=lambda i: i.get("created_at") or "", reverse=True)
    if ordered:
        rows = "\n".join(
            _row(n, idea, plans_by_idea.get(str(idea.get("id") or "")))
            for n, idea in enumerate(ordered, start=1)
        )
        body = (
            "<table>"
            "<thead><tr>"
            '<th class="num">#</th><th>Evaluation</th><th>Received</th>'
            '<th>Plan</th><th class="num">Artifacts</th>'
            "</tr></thead>"
            f"<tbody>{rows}</tbody>"
            "</table>"
        )
    else:
        body = (
            '<p class="empty">No evaluations yet. Send an idea from the '
            'Idea Evaluation column ("Execute →") and it will appear here.</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Artifact Factory — Evaluations</title>
<style>
  body {{ margin: 0; font-family: system-ui, sans-serif; font-size: 14px;
         line-height: 1.5; color: black; background: white; }}
  header {{ padding: 12px 16px; border-bottom: 1px solid silver;
           display: flex; align-items: baseline; justify-content: space-between;
           gap: 12px; }}
  h1 {{ font-size: 16px; margin: 0; font-weight: 600; }}
  .sub {{ color: gray; font-size: 12px; }}
  main {{ padding: 16px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; vertical-align: top; padding: 8px;
           border-bottom: 1px solid gainsboro; }}
  th {{ font-size: 12px; color: gray; font-weight: 600;
       border-bottom: 1px solid silver; }}
  td.num, th.num {{ color: gray; white-space: nowrap; }}
  .title {{ font-weight: 600; }}
  .text {{ white-space: pre-wrap; }}
  .muted {{ color: gray; }}
  .small {{ font-size: 12px; }}
  .status {{ font-size: 12px; }}
  .status.implemented {{ color: green; }}
  .status.failed {{ color: red; }}
  .status.implementing {{ color: darkorange; }}
  a {{ color: blue; }}
  .empty {{ color: gray; padding: 24px 0; }}
  footer {{ padding: 12px 16px; color: gray; font-size: 12px;
           border-top: 1px solid silver; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Artifact Factory</h1>
    <div class="sub">Evaluations received — the ideas handed to the factory for implementation.</div>
  </div>
  <div class="sub"><a href="/">Refresh</a></div>
</header>
<main>
{body}
</main>
<footer>Artifact Factory {version} · <a href="/info">JSON API</a> · <a href="/health">health</a></footer>
</body>
</html>
"""
