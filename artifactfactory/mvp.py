"""MVP prototype: one self-contained, interactive HTML page that shows the idea as a product a person can click
through. This is what the frontend's Execute -> builds.

The brief comes from the idea and, when the idea came from an evaluation run, from its report: what the panel said
is worth building first, who the customers are and what worries them. One model call writes the page.

Safety: the page may not load or send anything. External scripts, stylesheets, frames and links to other hosts are
removed, network APIs are refused, and a strict Content-Security-Policy is injected (the factory also serves it
with that policy, and the frontend shows it in a sandboxed iframe). If generation fails, a plain page is built from
the idea text instead, so a build never fails because of this.
"""
import html
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from . import evaluation

MODEL = os.environ.get("AF_MVP_MODEL", "anthropic/claude-haiku-5.5")
MAX_BYTES = 400_000
# Every fetch directive listed explicitly (a blanket default-src 'none' blanks the page inside a sandboxed iframe):
# inline code only, images/fonts/media only as data, and no network, forms, frames, workers or plugins.
CSP = ("script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; "
       "media-src data: blob:; connect-src 'none'; form-action 'none'; base-uri 'none'; frame-src 'none'; "
       "child-src 'none'; object-src 'none'; worker-src 'none'; manifest-src 'none'")
NETWORK = re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts|navigator\.serviceWorker)\b")

# The house look, from website/frontend/css/styles.css and documentation/FRONTEND_STYLE.md: system font, black on white, 1px silver borders, square corners,
# no shadows or gradients, named colors used sparingly. Injected first in every page so prototypes match the app;
# the page's own styles can still build on it.
HOUSE_CSS = """*{box-sizing:border-box}
body{margin:0;font-family:system-ui,sans-serif;font-size:14px;line-height:1.5;color:black;background:white}
h1,h2,h3,h4,h5{margin:0 0 6px;font-weight:600}h1{font-size:15px}h2{font-size:14px}h3{font-size:13px}
p{margin:0 0 6px}a{color:blue}.muted{color:gray}.small{font-size:12px}
button,input,select,textarea{font:inherit}
.app-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 12px;border-bottom:1px solid silver}
.app-header p{font-size:12px;color:gray}
.main{padding:10px 12px;max-width:1100px;margin:0 auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px}
.card{border:1px solid silver;padding:8px 10px;margin-bottom:8px}
.label{font-size:12px;color:gray;margin:4px 0 6px}
.tag{font-size:11px;color:gray;border:1px solid silver;padding:0 4px}
.btn{padding:4px 10px;border:1px solid gray;background:whitesmoke;color:black;cursor:pointer}
.btn:hover{background:gainsboro}.btn.primary{font-weight:600}.btn:disabled{color:gray;cursor:not-allowed}
.tabs{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}
.tab{border:1px solid gray;background:white;padding:2px 8px;font-size:12px;cursor:pointer}
.tab:hover{background:whitesmoke}.tab.active{background:gainsboro;font-weight:600}
input[type=text],input[type=number],select,textarea{border:1px solid gray;padding:3px 5px;background:white}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid gainsboro;padding:4px 6px;text-align:left;font-size:13px}
th{font-size:12px;color:gray;font-weight:600}
tr.selected,.selected{background:aliceblue}
.ok{color:green}.warn{color:darkorange}.bad{color:red}
.bar{height:4px;border:1px solid silver}.bar>span{display:block;height:100%;background:gray}
details{border:1px solid silver;padding:6px 10px;margin-bottom:8px}summary{cursor:pointer;font-size:12px;color:gray}
@media (max-width:600px){.app-header{flex-wrap:wrap}}"""


def brief(idea: str, rep: Optional[Dict[str, Any]]) -> str:
    lines = [f"Idea: {idea}"]
    if not rep:
        return "\n".join(lines)
    v = rep.get("verdict") or {}
    lines.append(f"Panel verdict: {v.get('headline', '')} {v.get('conclusion', '')}")
    sg = rep.get("stop_go") or {}
    if sg.get("resolve_next"):
        lines.append(f"Still open: {sg['resolve_next']}")
    for g in rep.get("groups", []):
        gv = g.get("verdict") or {}
        lines.append(f"\n{g['name']}: {gv.get('headline', '')}")
        for label in ("pros", "cons"):
            for x in (gv.get(label) or [])[:3]:
                lines.append(f"  {label[:-1]}: {x}")
        if g.get("style") == "diverge":  # the customer archetypes: who the product is for
            for a in g.get("agents", []):
                pos = (a.get("final_position") or {}).get("role_verdict") or {}
                lines.append(f"  customer {a['name']} ({a.get('question') or ''}): {pos.get('label', '')} {pos.get('value', '')}".rstrip())
    for d in ((rep.get("cross_group") or {}).get("disagreements") or [])[:3]:
        lines.append(f"Disagreement: {d.get('topic')}")
    return "\n".join(lines)[:7000]


PROMPT = """You are a product designer and front-end engineer. Build a clickable MVP prototype of this idea as ONE
self-contained HTML file that a person can open and immediately understand and try.

{brief}

What to build:
- The narrow first version the panel says is worth testing (if there is a verdict), shown as the product its target
  user would actually use: a realistic app screen, not a landing page or a slide.
- Walk through the core workflow end to end (3 to 5 steps, tabs, or screens) with realistic sample data, clearly
  labeled "Demo data".
- Real interactivity: buttons, toggles, sliders, a step-through or a simulated run that changes what is shown.
- At least one live visualization drawn with inline SVG or <canvas> (no libraries) that reacts to the controls.
- Make the panel's top concerns visible in the product (for example an approval step, a cost estimate, a privacy
  indicator, a confidence level), so the prototype answers the evaluation.
- A header with a plain product name you invent and a one-line value proposition, and a collapsible "Why this design"
  panel listing 3 short findings from the evaluation it reflects.

Look and feel (important): the prototype must look like it belongs to the app it is shown in, which is plain and
minimal. This stylesheet is injected into your page automatically, so use its classes and do not restyle them:
  .app-header (top bar, with a <p> for the value proposition), .main (page body), .grid, .card, .label (small gray
  section label), .tag, .btn and .btn.primary, .tabs with .tab / .tab.active, table, .selected, details/summary,
  .bar > span (progress bar), .muted, .small, and the status colors .ok (green), .warn (darkorange), .bad (red).
- Black text on white, system font, 1px silver borders, square corners. No gradients, shadows, rounded cards, emoji,
  icons, hero banners, big headlines or decorative illustrations. Headings stay 13-15px.
- Color only carries meaning (status, selection, one data series highlighted); everything else is black, gray,
  silver, gainsboro, whitesmoke or white. Charts: gray and black strokes, at most one accent color.
- HTML5 named colors only (black, gray, silver, gainsboro, whitesmoke, white, aliceblue, blue, green, red,
  darkorange), never hex or rgb. A color is always paired with a word, so meaning never depends on color alone.
- No CSS transitions or decorative animation; state changes are instant. .btn.primary is bold, not a filled block.
- Exception: if the product itself is inherently visual (a game, a drawing or design tool, a consumer brand
  experience, a children's app), color and richer visuals are allowed inside the product's content area only; the
  header and controls still follow the house style.
- Dense and functional like a working tool: compact spacing, real labels, no marketing copy.

Rules:
- One file: inline <style> and <script>, vanilla JavaScript. No external scripts, stylesheets, fonts, images or links
  to other sites. No fetch, XMLHttpRequest, WebSocket or other network calls. It runs in a sandboxed iframe.
- No forms that collect personal data, passwords or payment details. No alert(), confirm() or prompt().
- Readable on a laptop screen and a phone. Accessible labels on controls.
- Under 600 lines. Reply with only the HTML document, starting with <!DOCTYPE html>.
"""


def _strip_external(doc: str) -> str:
    ext = r"""(?:https?:)?//"""
    doc = re.sub(rf"<script\b[^>]*\bsrc\s*=\s*['\"]?{ext}[^>]*>\s*</script>", "", doc, flags=re.I)
    doc = re.sub(rf"<link\b[^>]*\bhref\s*=\s*['\"]?{ext}[^>]*>", "", doc, flags=re.I)
    doc = re.sub(r"<(iframe|frame|object|embed|base)\b[^>]*>(\s*</\1>)?", "", doc, flags=re.I)
    doc = re.sub(r"<meta\b[^>]*http-equiv\s*=\s*['\"]?(refresh|content-security-policy)[^>]*>", "", doc, flags=re.I)
    doc = re.sub(rf"(href|src)\s*=\s*(['\"]){ext}[^'\"]*\2", r'\1="#"', doc, flags=re.I)
    return doc


def _inject_csp(doc: str) -> str:
    """Adds the CSP and the house stylesheet at the top of <head> (the page's own styles come after and win)."""
    doc = re.sub(r"<meta\b[^>]*http-equiv\s*=\s*['\"]?content-security-policy[^>]*>", "", doc, flags=re.I)
    meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP}"><style id="house">{HOUSE_CSS}</style>'
    m = re.search(r"<head[^>]*>", doc, flags=re.I)
    return doc[:m.end()] + meta + doc[m.end():] if m else meta + doc


def clean(text: Optional[str]) -> Tuple[Optional[str], str]:
    """(document, problem). The model's reply cut to the HTML document, made safe; None if unusable."""
    if not text:
        return None, "no reply"
    text = re.sub(r"^```(?:html)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    start = min([i for i in (text.lower().find("<!doctype"), text.lower().find("<html")) if i != -1], default=-1)
    end = text.lower().rfind("</html>")
    if start == -1 or end == -1:
        return None, "the reply was not a complete HTML document"
    doc = text[start:end + len("</html>")]
    if len(doc.encode()) > MAX_BYTES:
        return None, "the page is too large"
    if "<script" not in doc.lower():
        return None, "the page has no interactivity"
    if NETWORK.search(doc):
        return None, "the page tries to use the network"
    return _inject_csp(_strip_external(doc)), ""


def fallback(idea: str, rep: Optional[Dict[str, Any]], reason: str) -> str:
    v = (rep or {}).get("verdict") or {}
    rows = "".join(f"<li><b>{html.escape(g['name'])}</b>: {html.escape((g.get('verdict') or {}).get('headline') or '')}</li>"
                   for g in (rep or {}).get("groups", []))
    return _inject_csp(f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Prototype</title></head>
<body><header class="app-header"><h1>Prototype</h1></header><div class="main"><div class="card"><p>{html.escape(idea)}</p></div>
{f'<div class="card"><b>Panel verdict:</b> {html.escape(v.get("headline") or "")}<ul>{rows}</ul></div>' if v else ''}
<p class="muted small">The interactive prototype could not be generated ({html.escape(reason)}). Press Build again to retry.</p></div>
<script>/* placeholder page */</script></body></html>""")


def generate(idea: str, rep: Optional[Dict[str, Any]]) -> Tuple[str, bool, str]:
    """(html document, generated?, note). Two attempts, then the plain fallback page."""
    prompt = PROMPT.format(brief=brief(idea, rep))
    problem = ""
    for _ in range(2):
        doc, problem = clean(evaluation.chat(prompt + (f"\n\nYour previous reply was rejected: {problem}." if problem else ""),
                                             max_tokens=16000, model=MODEL, timeout=180))
        if doc:
            return doc, True, ""
    return fallback(idea, rep, problem), False, problem


def entry_file(files: List[str]) -> Optional[str]:
    return next((f for f in files if f.endswith("/index.html")), None)
