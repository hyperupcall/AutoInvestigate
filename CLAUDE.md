# CLAUDE.md

Context and working notes for the **UCSC AI Hackathon** project in this repo.
Read this before making changes — it captures the research, the backend contract,
and the frontend UI we've built so far.

---

## 1. The hackathon

- **Event:** UCSC AI Hackathon.
- **Track:** Cloud AI — themed **"CLOUD AI TRACK · CISCO OUTSHIFT | AGNTCY"**.
- **Cisco Outshift:** Cisco's internal incubator (<https://outshift.cisco.com/>).
  Focus areas: **Agentic AI, Superintelligence, Quantum**. They want to accelerate
  research of emerging technologies for **ROI** — new products or IP.
- **Our angle:** appeal to their capitalist mindset — show tangible, investable output.

### The challenge prompt

> **When AI Agents Disagree — From collaboration to collective intelligence.**
> Build AI agents that work together, adapt to changing conditions, and make
> decisions even when they disagree.

**LEVEL 3 · BUILD A COLLECTIVE INTELLIGENCE:** at least **three autonomous agents
with competing objectives** that deliberate, negotiate, and try to reach consensus
**without a central decision-maker**. Success criteria:

- genuine disagreement,
- a real deliberation / negotiation mechanism,
- the effect of new information,
- a comparison against a simpler baseline.

Consensus is **not always** the right outcome — the system should explain when to
stop, keep the disagreement, or ask a human.

---

## 2. Product vision (from `IDEAS.md`)

Working name: **"Automated Cisco Researcher Thing"**. A website that finds emerging
technologies and generates, refines, scores, and eventually implements ideas for
using them.

The pipeline, roughly:

1. **Find emerging technologies** — MVP: list well-known ones (quantum computing,
   edge AI, ML artifacts, robot servants). Stretch: mine arXiv.
2. **Create implementation ideas** — MVP: a small coding experiment. Stretch: a
   market solution, a UI, or IP (patent).
3. **Generate variants of an idea** — vary the market/niche, the regulatory context
   (US vs EU), the scope (up/down), or the underlying technology.
4. **Score ideas** on **tech risk, market, Cisco fit, market horizon** (decision
   models / simulation). The user picks the variations they like and continues.
5. **Code and implement** — MVP: a tangible artifact. Stretch: a larger project.
   Borrow from related repos (<https://github.com/orgs/cisco/repositories>).
6. **Generate learnings for the swarm** at each stage.

**Value generated:** MVP — give code snippets / ideas / projects to people in the
Outshift org to continue. Stretch — whole products / OSS projects / patents that
automate part of a role.

**Noted:** smaller projects may be better. Our small ideas/code can be handed to
better (more expensive) agents for further refinement.

**User's perspective:** give it abstract objectives (e.g. "homomorphic encryption"
— computing on encrypted data).

---

## 3. Backend spec — "BACKEND Code B"

The backend has parts; for each, a markdown file should document how the frontend
uses the routes. Two parts are specified:

### Part 1 — Idea generation

**Input:** a model identifier, API keys (always backend-side), **one or more ideas**,
and an **"idea iteration type"**:

- **Refinement** — take rough idea(s) and make them specific using real-world
  research, projects, and context.
- **Variation & Generation** — take good idea(s) and produce multiple variations
  (configurable count). May target different markets; use an agent/skill with a
  specialization (business person, software person, …).
- **Consolidation** — take one or more ideas and merge them usefully given the
  background research.

The pipeline should be simple and use **models configured by the user**.

### Part 2 — Idea evaluation

- Routes expect a **single idea string** to evaluate.
- The same idea string is fed into each **GROUP PERSPECTIVE**.
- Group perspectives are an **array of objects**, each with an `agents` property.
  Each agent has a `model` and an `api_key`.
- Models are configurable via the frontend; the spec asks for a **`/settings` page
  that is as bare HTML as possible** (JS only where needed).

**Default group perspectives:**

| Perspective | Default agents | Focus |
| --- | --- | --- |
| **Professional Research Group** | 4 | Stage of research, feasibility to scale, long-term-only implementations. |
| **Private Equity / Business** | 4 | PE partners maximizing returns; one per criterion: **tech risk, market, cisco_fit, horizon**. |
| **Market Reaction** | 5 | The people being served (customer archetypes, e.g. "power user", "free-tier lover"). They do **not** naturally reach consensus. |

**Evaluation flow:**

0. **Reality check** (added): before any group deliberates, one outside call asks
   whether the idea makes sense in the real world at all — coherent and physically,
   legally and logically possible — and returns a structured verdict
   (`grounded` / `questionable` / `nonsense`, a category, a one-line summary,
   real-world blockers, and assumptions that may be false). It is advisory: if the
   call fails the run continues without it. The result is fed into the stop-or-go
   and final prompts (a `nonsense` idea cannot get a plain "Go") and shown to the
   user as a banner. This is the guard against a bad idea slipping through: the
   three groups all argue *inside* the idea, so none of them steps outside to ask
   whether it is real.
1. Give the idea string to each group perspective; tell them to **deliberate for a
   configurable number of seconds** and output an evaluation. Encourage use of the
   **Jev/TypeSafe AI** model and open decision models. **All models via OpenRouter.**
2. For each group, **summarize** the main pros/cons (keep important detail). The
   summarizer model is configurable in settings.
3. Feed the summarized models back to each group; generate pros/cons and
   feasibility scores on sensible metrics. Provide a good default markdown doc.
4. **Do this one more time.**
5. Run a **"should we stop or go"** prompt — should they actually reach consensus?
   Produce pros/cons and rationales. **This is shown to the user, so it must not
   look like LLM text.**
6. If *continue* → deliberate **one more time**, then **always finish**.
   If *stop* → stop. Give the final text/conclusions for each group.
7. **Final report** (added): the `final` stage (`prompts/system/final.md`, stage `final` in
   settings, its own model/key/token budget) writes the comprehensive verdict shown to the
   submitter. It is fed the **raw material**, not just the twice-squeezed summaries: each
   group's latest evaluations in full, the latest discussion, the arXiv papers, the
   stop-or-go decision and the reality check. It returns a structured report — headline,
   recommendation, a multi-paragraph executive summary, the idea as evaluated, the case for
   and against, an **ordered action plan** (steps with timeframe/cost/owner), **kill
   criteria**, risks with mitigations, open questions, and what would change the verdict —
   plus a richer per-group verdict (headline, conclusion, findings, pros/cons, scores).
   This is the fix for the old thin verdict: the format was tiny, the writer only saw
   summaries, and nothing asked for a plan.

**Prompts** must be configurable via a file on the filesystem and selectable in
settings.

---

## 4. Frontend UI (as built)

Location: `website/frontend/`. **No build step** — vanilla JS, classic `<script>` tags, a
single `window.Hack` namespace. Open `website/frontend/index.html` directly, or serve it
(`python3 -m http.server`).

### Layout — three columns

| Column | Purpose |
| --- | --- |
| **1 · Idea Generation** | Seed box + the level tree of ideas. |
| **2 · Idea Evaluation** | Selected ideas + deeper-research runs. |
| **3 · Idea Execution** | **Blank for now** — reserved for turning a chosen idea into an artifact. |

**Settings is a popup**, opened from the **Settings** button in the header (not a
sidebar). It is the one settings surface: when the backend is connected it renders
the backend's real settings and saves them (`PUT /api/settings`); without a backend
it falls back to the in-memory mock settings.

The header is a **navbar**: the brand on the left, the primary links (**Agent View**,
**Artifact Factory**) in the middle, and the actions (**MOCK BACKEND** badge,
**Information**, **Settings**) on the right. It is **one
shared component** (`website/frontend/js/components/navbar.js`) mounted on every page, so it
looks and behaves the same on all routes — the workspace mounts it from `app.js`, the
other pages from `website/frontend/js/shell.js` (which also mounts the popups it opens). The
links open in the **same tab**.

An **Agent View** link opens the site rendered by the backend server (the `web`
service, `http://localhost:8090/live` — the live view). Its `href` defaults to
`http://localhost:8090/live` and follows the detected backend (`window.EVAL_API`, same
origin, or `localhost:8090`) via `Hack.backendInfo`, which `api-backend.js` fills in.
The live view itself now renders **the same shared navbar**: it loads
`website/frontend/css/styles.css` and the shell scripts from the frontend directory (the
backend serves them), and its own controls (past runs, replay speed, Replay, backend
Settings) sit in a `.live-toolbar` below the navbar.

An **Artifact Factory** link opens the Artifact Factory dashboard — now a frontend
page (`website/frontend/artifactfactory.html`, script `website/frontend/js/artifactfactory.js`) that
lists every evaluation (idea) the factory has been given, with its plan and artifact
status. The page discovers the factory API itself (`window.AF_API`, same origin, or
`localhost:8080`), so the link stays relative. The daemon serves the same page at
`GET /` (and its assets from the frontend directory); its JSON service info lives at
`GET /info`.

An **Information** button opens a popup with everything about the app: what it does,
which backends are connected, the models it uses (each linked to its OpenRouter page
with its input/output price per 1M tokens) and useful links. The model list lives in
`website/frontend/js/model-info.js` (the single source of truth for the settings dropdown too).

The **MCP server catalog** (the servers agents can use, grouped by category) lives in the
**Settings** popup, under the group perspectives: each agent shows the servers it can
reach, and the full catalog is listed below. (The old **Configure Agent Groups** popup
was removed and its information moved here.) The same list is what a run is given;
which of the groups take part is chosen per run (see Column 2).

### MCP servers (agents can use tools)

Agents can be given MCP servers to use. The catalog is curated from
[Smithery](https://smithery.ai/servers) across three categories — **Academic
Research**, **Finance** and **Reasoning** — and lives in `website/frontend/js/mcp-servers.js`
(display) and `website/council/defaults.py` (`MCP_CATALOG`, the access source of
truth; the backend serves it in `/api/settings` as `mcp_catalog`, and the frontend
prefers it when live).

Each agent carries `mcp_servers` (catalog ids), correlated with its role:

| Agent | MCP servers |
| --- | --- |
| Research · Feasibility Scientist | arXiv, Semantic Scholar, Thoughtbox |
| Research · Systems Architect | arXiv, Crossref, Math & Logic |
| Research · AI Systems Researcher | arXiv, Paper Search, Scholar Feed, Thoughtbox |
| Research · Critical Reviewer | Citation Checker, CiteMe, Crossref, Logic Verifier, Invinoveritas |
| PE · Technical Risk Partner | arXiv, Crossref, Logic Verifier, Invinoveritas |
| PE · Market and Revenue Partner | Finance MCP, Flatland, PreReason, OpenAlex |
| PE · Competitive Strategy Partner | Finance MCP, Flatland, Semantic Scholar |
| PE · Horizon and Returns Partner | Finance MCP, PreReason, Quorum |
| Market · Power User | Thoughtbox, Clear Thought |
| Market · Enterprise Decision-Maker | Invinoveritas, Decide Runtime, SecureLend |
| Market · Skeptical Technical Critic | Citation Checker, Crossref, Logic Verifier |
| Market · Startup Builder | Finance MCP, EveryCalc, Thoughtbox |
| Market · Free-Tier Maximizer | EveryCalc, MonsiTools, Clear Thought |

**Access:** the agent host (`website/agent_host/executor.py`) connects to the agent's
servers over Streamable HTTP (`website/council/mcp.py`), lists their tools, and offers
them to the model via OpenRouter tool-calling (`council/openrouter.py`
`chat_with_tools`). Tool names are prefixed with the server id (`arxiv__search`) so
two servers can expose the same name. It runs for the `evaluate` / `cross_review`
stages only (deep mode), bounded by `mcp.max_tool_calls`, and is **fail-safe**: if a
server is down or the call fails, the agent answers without tools. The Smithery key is
read from `SMITH_API_KEY` in the root `.env` (`council/settings.py` `mcp_key()`); a
stored `mcp.api_key` is only a fallback. Other settings: `mcp.enabled`,
`mcp.timeout_seconds`, `mcp.max_tool_calls`.

**Editing:** add or remove a server for any agent on the backend `/settings` page —
each agent row has an "MCP servers" line with a chip per server (✕ to remove) and a
dropdown to add another. Save, and the next run uses it. The frontend's Settings
popup then reflects it (it syncs from the backend).

### Column 1 — Idea Generation (a level tree)

- **Level 0** is the seed box `(A)`. Type an idea and press **Generate**. The seed
  text is **not cleared** after generating.
- Generating from level 0 appends to the **level 1** list; generating from level N
  appends to the **level N+1** list.
- Ideas at the same level are **bunched into one plain list** — there are **no
  separate boxes per generation**. Generating twice at the same level adds to the
  same list.
- The **iteration type is not shown inline**. Each level (and the seed) has a single
  **Iterate** button; clicking it opens a small **popover** with the iteration type
  (`Refinement`, `Variation & Generation`, `Consolidation`, `Free-form`) and its
  matching extra inputs (variation count / free-form instruction).
- Iterating a level uses the **selected** ideas in that level, or the **whole level**
  when nothing is selected (consolidation requires ≥ 2 ideas).
- Each level also has an **Evaluate** button next to **Iterate**; it uses the same
  selection rule and copies the chosen ideas into the **Idea Evaluation** column (it
  does *not* start the run).
- **Evaluate →** on an individual idea copies just that idea into the **Idea
  Evaluation** column.
- Ideas do **not** show a lineage label (no `Idea after N …` text).
- The **level terminology lives in the code** (`state.levels`, `level` numbers) but
  is **not shown in the interface** — no "Level N" labels.
- Each level's control row (**Select all**, **Evaluate**, **Iterate**) stays pinned to
  the top of the column while you scroll that level's ideas.
- The column scrolls independently and auto-scrolls to the newest level.

### Column 2 — Idea Evaluation

- **Evaluate →** in column 1 copies an idea into this column's **single list**
  (duplicates are blocked; each queued item can be removed with ✕ or cleared with
  **Clear queued**).
- Each queued idea has its own **Start Deeper Research** button. It opens a popup
  (`website/frontend/js/components/runConfigModal.js`) that lists the agent groups with
  checkboxes (all selected by default) so you can include or exclude groups for that
  run; **Start research** then starts the run and turns the entry into a run card in
  the same list. The chosen group ids are passed to the run (`startEvaluation({ …,
  groupIds })`): the mock filters the report (`Hack.util.filterReportGroups`), and the
  real backend receives `overrides.group_ids` and keeps only those groups.
- Queued ideas and runs share **one regular list** (no separate "Queued" / "Research
  runs" sections). A running run can be **cancelled** (from its card or the popup
  header); any run can be **hidden** with ✕, and **Hide finished** clears all
  completed/cancelled runs. Clicking a run opens a large popup with **two tabs**:
  - **Evaluation Swarm** — each group is drawn as a **graph**: one circle per agent
    with the agent's name beside it (the agent currently speaking is highlighted).
    Clicking a circle shows that agent's stream — a **summary** of each of its
    discussion turns and evaluations (the full output is one click away) — in a
    panel under the graph. Below the graphs is the live stream of the whole run:
    summarized turns, evaluations, summaries, cross-group analysis, the stop-or-go
    decision and the verdict, as the backend emits them.
  - **Evaluation** — the finished report, shaped exactly like
    `evaluation-report.schema.json`: run metadata, pipeline, stop-or-go, the **final report**
    (headline, recommendation, executive summary, case for/against, ordered plan, kill
    criteria, risks, open questions, scores), cross-group disagreements/agreements, per-group
    scores/verdicts/findings/disagreements, AGNTCY transport and the disagreement analysis.
    Includes a collapsible **Raw JSON** view of the whole report.

### Settings (popup)

One settings surface. When the backend is connected the popup renders the backend's
real settings — the same fields as the backend `/settings` page — and saves them with
`PUT /api/settings`: mode, arXiv sources, the default OpenRouter key, deliberation
time, cost cap, web search, the per-stage token/effort table, the summarizer / judge /
final / reality-check models and keys, the MCP settings, the MCP server catalog, and the group
perspectives (name, discussion style — **automatic** lets the backend pick per group,
`converge` or `diverge` — arXiv use, and each agent's model, key, reasoning effort,
prompt and MCP servers). Without a backend it falls back to the in-memory mock settings
(models, prompts, group perspectives). **API keys live on the backend** and are masked in
the public view.

### Design principles

The full design system — tokens, semantic status colors, component recipes and a
standalone-page base block — lives in [`STYLE.md`](STYLE.md). The canonical
implementation is `website/frontend/css/styles.css`. Summary:

- **Light mode only.**
- **Minimal styling** — plain layout, thin borders, system font.
- **HTML5 named colors, used sparingly** (`silver`, `gray`, `gainsboro`,
  `whitesmoke`, `aliceblue`, `green`, `red`, `darkorange`, `blue`). No hex colors,
  gradients, shadows, or blur.
- "We don't want it to look like slop."

---

## 5. Architecture

```
website/frontend/
  index.html              three-column workspace
  artifactfactory.html    Artifact Factory dashboard (also served by the factory)
  css/styles.css          all styling (light, minimal)
  js/
    util.js               DOM + misc helpers (el, preserveView, seeded RNG, …)
    model-info.js         the models used, with OpenRouter links + prices
    mcp-servers.js        the MCP servers agents can use, and which agent gets which
    mock-data.js          fixtures: groups, archetypes, prompts, text templates
    mock-report.js        sample evaluation report (evaluation-report.schema.json)
    mock-backend.js       ← the MOCKED backend (swap for real calls)
    state.js              single source of truth + pub/sub + selectors
    actions.js            mutations + orchestration
    shell.js              shared chrome (navbar + popups) for non-workspace pages
    components/
      navbar.js           the shared app header (navbar)
      generation.js       column 1 (level tree)
      evaluation.js       column 2
      execution.js        column 3 (blank)
      settings.js         the settings form (backend settings when live, mock otherwise)
      settingsModal.js    settings popup
      infoModal.js        "Information" popup (about, connections, models, links)
      runConfigModal.js   per-run group picker (Start Deeper Research)
      modal.js            the two-tab popup (evaluation swarm / evaluation)
      toast.js            notifications
    app.js                bootstrap
  artifactfactory.html    Artifact Factory dashboard (served by the factory at GET /)
  js/artifactfactory.js   the dashboard's data loading + rendering
```

**State shape (key parts):**

```js
state = {
  seed: { text, iterationType, variationCount, freeformPrompt, submitting }, // level 0
  levels: [ { level, ideas, iteration, pending, error } ],                    // level 1+
  selectedIdeaIds: [],
  evaluation: { queue: [ { id, text, level, sourceIdeaId, addedAt } ],
                runs: [ { id, ideaId, ideaText, status, events, report, cluster, … } ], activeRunId },
  settings: { generationModel, evaluationModel, summarizerModel,
              deliberationSeconds, promptSet, groupPerspectives },
  ui: { modal: { open, runId, tab }, settingsOpen, toast },
}
```

**Conventions:**

- Components expose `mount(container)` and `render()`; `app.js` subscribes to the
  store and calls every component's `render()` on change.
- Inputs mutate state directly **without** notifying (to avoid re-render on
  keystrokes); structural changes call `store.notify()`.
- `preserveView()` restores focus/scroll across re-renders; text inputs use
  `data-focus-key`.
- The mock output is **deterministic per idea** (seeded PRNG), so the same idea
  always yields the same mock result.

**Environment / API keys:** everything runs on a **single `OPENROUTER_API_KEY`** in one
root `.env` (template: `.env.example`), plus an optional **`SMITH_API_KEY`** for the
agents' MCP servers. There are no per-directory `.env` files and no other provider keys. Each service reads that one file: the root `docker-compose.yml`
defines the evaluation backend with `env_file: .env` (and `website/setup.sh` /
`website/Makefile` drive it via `docker compose -f ../docker-compose.yml --env-file
../.env`), `evalreport/` via `load_dotenv(<repo-root>/.env)` (OpenAI SDK pointed at
OpenRouter), and `artifactfactory/run.sh` sources it.

---

## 6. Mock backend contract

`website/frontend/js/mock-backend.js` is the single swap point. Replace the bodies with
`fetch()` calls to the real routes; the shapes below are what the UI expects.

```js
// Part 1 — Idea generation
await Hack.mockBackend.generateIdeas({
  sourceIdeas,        // [{ text, lineage }]
  iterationType,      // 'refinement' | 'variation' | 'consolidation' | 'freeform'
  variationCount,     // number (variation only)
  freeformPrompt,     // string (freeform only)
  model,              // model id
  seedText,           // string (used when no sourceIdeas)
});
// -> { label, lineage, operation, model, ideas: [{ text }] }

// Part 2 — Idea evaluation (streams cluster events, then delivers the report)
const report = Hack.mockBackend.buildReport(ideaText); // full report, available up front
const handle = Hack.mockBackend.startEvaluation({
  ideaText,           // the single idea string to evaluate
  settings,           // { deliberationSeconds, groupPerspectives, … }
  onEvent(ev),        // { phase, kind, ts, … } — see event kinds below
  onDone(report),     // the report, shaped like evaluation-report.schema.json
});
handle.cancel();
```

Event kinds streamed to `onEvent`: `phase`, `cluster`, `reality-check`,
`group-start`, `round-start`, `turn`, `missed`, `evaluation`, `failed`, `summary`,
`cross-group`, `stop-go`, `verdict`. The **Evaluation Swarm** tab renders these live;
the **Evaluation** tab renders the final `report`.

The report fixture (`js/mock-report.js`) is generated from
`20261011-014311-b2e9.json` and conforms to `evaluation-report.schema.json`.

---

## 7. Status & next steps

**Done (mocked):** three-column UI, level tree with per-level/per-idea iteration,
lineage labels, evaluation runs with the two-tab popup (**Evaluation Swarm** live
stream + **Evaluation** report with raw JSON), settings popup + page,
light/minimal styling.

**Done (real): Part 2 backend** in `website/` (see `website/README.md`, routes documented there).
`website/frontend/js/api-backend.js` swaps the mock evaluation for the real one whenever the backend answers (same origin
on :8090, or `localhost:8090` from `run.sh` on :8000); otherwise the mock still runs. Past runs load into
"Research runs". Stop-or-go is shown as the deliberation outcome (Stopped / Extra round / Disagreement kept),
not as a verdict on the idea; the idea's verdict is the "Final report" block.

**Done (real): Final report** — the `final` stage (`prompts/system/final.md`, stage `final` in settings, its own
model/key/token budget, default 9000 tokens) writes the comprehensive verdict. It is fed the raw material (each
group's latest evaluations in full, the latest discussion, the arXiv papers, the stop-or-go decision, the reality
check), not just the summaries, and returns a structured report: headline, recommendation, a multi-paragraph
executive summary, the idea as evaluated, the case for and against, an ordered action plan with timeframe/cost/owner,
kill criteria, risks with mitigations, open questions, and what would change the verdict. Per-group verdicts gained
`findings` and `scores`. The report schema (`verdict` and group `verdict`) and the mock report mirror it.

**Done (real): Reality check** — a stage before the groups (`prompts/system/reality_check.md`, stage
`reality_check` in settings) that judges whether the idea makes sense in the real world at all and returns a
structured verdict (`grounded` / `questionable` / `nonsense` + category, summary, blockers, assumptions). It is
advisory (a failed call does not stop the run), feeds the stop-or-go and final prompts so a `nonsense` idea
cannot get a plain "Go", lands in the report as `reality_check`, and shows as a banner in the Evaluation tab and
a `reality-check` event in Evaluation Swarm. The mock mirrors it with a small keyword heuristic.

**Done (real): Column 3 · Idea Execution** — `website/frontend/js/api-execution.js` swaps the mock for the real
`artifactfactory/` service whenever it answers (same origin, or `localhost:8080` from `run.sh` on :8000; the
factory allows that origin via `AF_CORS_ORIGINS`). "Execute →" on a research run sends its idea to column 3,
which creates a plan, implements it and lists the artifacts with download links. Artifact content is still dummy.

**Not done:**

- **Part 1 backend (idea generation)** — `generateIdeas` is still the mock.
- **Settings persistence** — currently in-memory only.
- **Prompt files** — the spec wants prompts loaded from the filesystem and
  selectable in settings; currently only preset names are mocked.

**Open questions:**

- Selection is currently **global** (shared by a level's "Generate from selected"
  and the evaluation column). Should selection be scoped per level instead?
- Should the level tree show **parent/child links** between an idea and the ideas
  it produced? (`parentIdeaIds` is already stored on each idea.)
- The spec says the backend has "three parts" but only two are described — confirm
  what the third is.