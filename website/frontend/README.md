# AutoInvestigate — Frontend

Frontend for **BACKEND Code B** (Idea generation + Idea evaluation) and the
**Artifact Factory** (Idea execution). Idea generation is still mocked; idea
evaluation and idea execution connect to the real backends when they are running
(see [Real backends](#real-backends)).

## Design system

The visual language (light-only, HTML5 named colors, spacing, typography, component
recipes) is documented in [`../STYLE.md`](../STYLE.md). Anything that renders UI — this app,
the Artifact Factory dashboard, backend-served pages — should follow it. The canonical
implementation is `css/styles.css`.

## Run it

No build step. Either:

```sh
# just open it
xdg-open index.html        # or: open index.html

# or serve it (recommended)
python3 -m http.server 8000
# then visit http://localhost:8000/
```

Pages:

- `index.html` — the three-column workspace (Settings opens as a popup)
- `artifactfactory.html` — the Artifact Factory dashboard (also served by the factory at `GET /`)

## The three columns

| Column | Purpose |
| --- | --- |
| **1 · Idea Generation** | The `(A)` seed box + iteration type, and the growing list of idea sections below it. |
| **2 · Idea Evaluation** | Ideas copied over with **Evaluate →**; start deeper research and open runs. |
| **3 · Idea Execution** | Turn a chosen idea into artifacts via the Artifact Factory. |

**Settings** is a popup, opened from the **Settings** button in the header (not a sidebar).

### Header (navbar)

The header is a navbar: the brand on the left, the primary links (**Agent View**,
**Artifact Factory**) in the middle, and the actions (**MOCK BACKEND** badge,
**Information**, **Settings**) on the right.

It is **one shared component** (`js/components/navbar.js`) mounted on every page, so
it looks and behaves the same on all routes. The workspace mounts it from `app.js`;
the other pages mount it (and the popups it opens) from `js/shell.js`. The links open
in the **same tab**, and the brand links back to the workspace. The backend-served
live view (`/live`, the **Agent View**) renders the same navbar too — it pulls in
`css/styles.css` and the shell scripts from this directory, and keeps its own controls
(past runs, replay speed, Replay, backend Settings) in a toolbar below it.

- **Agent View** opens the site served by the backend (`http://localhost:8090/live`).
- **Artifact Factory** opens `artifactfactory.html` — the dashboard listing every
  evaluation the factory was given. The page discovers the factory API itself
  (`window.AF_API`, same origin, or `localhost:8080`), so the link stays relative.
- **Information** opens a popup with everything about the app: what it does, which
  backends are connected, the models it uses (with OpenRouter links and prices) and
  useful links. The model list lives in `js/model-info.js`.

### Column 1 — Idea Generation (a level tree)

- **Level 0** is the seed box `(A)`. Type an idea and press **Generate**.
- Generating from level 0 appends to the **level 1** list; generating from level N
  appends to the **level N+1** list. Ideas at the same level are **bunched into one
  plain list** (no per-generation boxes) — generating twice at the same level adds
  to the same list rather than creating a separate box.
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
- The **level terminology lives in the code** (`state.levels`, `level` numbers) but
  is **not shown in the interface** — no "Level N" labels.
- Each level's control row (**Select all**, **Evaluate**, **Iterate**) stays pinned to
  the top of the column while you scroll that level's ideas.
- The column scrolls independently and auto-scrolls to the newest level.

### Column 2 — Idea Evaluation

- **Evaluate →** in column 1 copies an idea into this column's single list
  (duplicates are blocked; remove a queued idea with ✕ or **Clear queued**).
- Each queued idea has its own **Start Deeper Research** button, which starts the run
  and turns the entry into a run card in the same list.
- Click a run to open a large popup with two tabs:
  - **Evaluation Swarm** — each group is drawn as a **graph**: one circle per agent
    with the agent's name beside it (the agent currently speaking is highlighted).
    Clicking a circle shows that agent's stream — a **summary** of each of its
    discussion turns and evaluations (the full output is one click away) — in a
    panel under the graph. Below the graphs is the live stream of the whole run:
    summarized turns, evaluations, summaries, cross-group analysis, the stop-or-go
    decision and the verdict.
  - **Evaluation** — the finished report, shaped like
    `evaluation-report.schema.json`: run metadata, pipeline, stop-or-go, final
    verdict, cross-group disagreements/agreements, per-group scores/verdicts/
    disagreements, AGNTCY transport and the disagreement analysis, plus a
    collapsible **Raw JSON** view.

### Settings (popup)

Opened from the header **Settings** button. It is the **one** place to configure the
app: when the backend is connected it renders the backend's real settings (the same
fields as the backend `/settings` page) and saves them with `PUT /api/settings` —
mode, arXiv sources, deliberation time, cost cap, web
search, the per-stage token/effort table, the summarizer / judge / reality-check
models and keys, the MCP settings, and the group perspectives (name, discussion
style, arXiv use, and each agent's model, key, reasoning effort, prompt and MCP
servers). Without a backend it falls back to the in-memory mock settings (models,
prompts, group perspectives).

## Real backends

Two backends connect automatically when they are reachable; otherwise the mocks keep working.

- **Idea evaluation** — `js/api-backend.js` connects Part 2 to `..` when it is running
  (`cd .. && ./setup.sh`, then open http://localhost:8090/).
- **Idea execution** — `js/api-execution.js` connects column 3 to `artifactfactory/`
  (`python3 -m artifactfactory.daemon`, or the root `./run.sh`). The factory allows the
  frontend's origin via `AF_CORS_ORIGINS`; override the target with `window.AF_API`.

## Mock backend contract

`js/mock-backend.js` exposes two functions. Replace their bodies with `fetch()`
calls to the real routes; the shapes below are what the UI expects.

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
  settings,           // { deliberationSeconds, groupPerspectives, ... }
  onEvent(ev),        // { phase, kind, ts, ... } — see event kinds below
  onDone(report),     // the report, shaped like evaluation-report.schema.json
});
handle.cancel();
```

Event kinds streamed to `onEvent`: `phase`, `cluster`, `group-start`,
`round-start`, `turn`, `missed`, `evaluation`, `failed`, `summary`,
`cross-group`, `stop-go`, `verdict`. The **Evaluation Swarm** tab renders these live;
the **Evaluation** tab renders the final `report`. The report fixture
(`js/mock-report.js`) is generated from `20261011-014311-b2e9.json` and conforms to
`evaluation-report.schema.json`.

## Files

```
website/frontend/
  index.html              three-column workspace
  artifactfactory.html    Artifact Factory dashboard (also served by the factory)
  css/styles.css          all styling
  js/
    util.js               DOM + misc helpers
    model-info.js         the models used, with OpenRouter links + prices
    mcp-servers.js        the MCP servers agents can use, and which agent gets which
    mock-data.js          fixtures: groups, archetypes, prompts, templates
    mock-report.js        sample evaluation report (schema-conforming)
    mock-backend.js       mocked evaluation backend (Part 2)
    mock-execution.js     mocked artifact factory (column 3)
    api-backend.js        real evaluation backend client (swaps the mock)
    api-execution.js      real artifact factory client (swaps the mock)
    artifactfactory.js    the dashboard's data loading + rendering
    state.js              single source of truth + pub/sub
    actions.js            mutations + orchestration
    shell.js              shared chrome (navbar + popups) for non-workspace pages
    components/
      navbar.js           the shared app header (navbar)
      generation.js       column 1
      evaluation.js       column 2
      execution.js        column 3 (idea execution)
      settings.js         the settings form (backend settings when live, mock otherwise)
      settingsModal.js    settings popup
      infoModal.js        "Information" popup (about, connections, models, links)
      runConfigModal.js   per-run group picker (Start Deeper Research)
      modal.js            the two-tab popup (evaluation swarm / evaluation)
      toast.js            notifications
    app.js                bootstrap
```

## Note on the third column

The third column is **Idea Execution**: send an idea here with **Execute →** from a
research run in column 2, then **Build artifacts** to create a plan and implement it
through the Artifact Factory. Settings is a popup opened from the header.