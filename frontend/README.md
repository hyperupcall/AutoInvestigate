# AutoInvestigate — Frontend

Frontend for **BACKEND Code B** (Idea generation + Idea evaluation). All backend
calls are **mocked** for now — see [`js/mock-backend.js`](js/mock-backend.js).

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
- `settings.html` — optional standalone settings page (same settings content)

## The three columns

| Column | Purpose |
| --- | --- |
| **1 · Idea Generation** | The `(A)` seed box + iteration type, and the growing list of idea sections below it. |
| **2 · Idea Evaluation** | Ideas copied over with **Evaluate →**; start deeper research and open runs. |
| **3 · Idea Execution** | Blank for now — reserved for turning a chosen idea into an artifact. |

**Settings** is a popup, opened from the **Settings** button in the header (not a sidebar).

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
- **Evaluate →** copies the idea into the **Idea Evaluation** column (it does *not*
  start the run). Selection is only used for iterating.
- Each idea shows the label derived from its lineage, e.g. `Idea after 1 refinement`,
  `Idea after 3 variations`, `Idea after combining 2 ideas`,
  `Idea after 2 variations and 1 combination`.
- The **level terminology lives in the code** (`state.levels`, `level` numbers) but
  is **not shown in the interface** — no "Level N" labels.
- The column scrolls independently and auto-scrolls to the newest level.

### Column 2 — Idea Evaluation

- **Evaluate →** in column 1 copies an idea into the **Queued for evaluation** list
  here (duplicates are blocked; remove one with ✕ or clear all).
- Each queued idea has its own **Start Deeper Research** button, which starts the run
  and moves the idea into the **Research runs** list.
- Click a run to open a large popup with two tabs:
  - **Cluster Status** — what is in the agent cluster (groups, agents, models,
    questions, who they are) plus the live stream of what each agent is saying:
    discussion turns, evaluations, summaries, cross-group analysis, the stop-or-go
    decision and the verdict.
  - **Evaluation** — the finished report, shaped like
    `evaluation-report.schema.json`: run metadata, pipeline, stop-or-go, final
    verdict, cross-group disagreements/agreements, per-group scores/verdicts/
    disagreements, AGNTCY transport and the disagreement analysis, plus a
    collapsible **Raw JSON** view.

### Settings (popup)

Opened from the header **Settings** button. Contains models (generation /
evaluation / summarizer), deliberation seconds, prompt set, and the group
perspectives (defaults: Professional Research ×4, Private Equity ×4, Market
Reaction ×5). API keys are intentionally **not** here — they live on the backend.
The same content is also available as a standalone page at `settings.html`.

## Real backend

`js/api-backend.js` connects Part 2 to the real backend in `../backend` when it is running
(`cd ../backend && ./setup.sh`, then open http://localhost:8090/). Without it, everything below stays mocked.

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
`cross-group`, `stop-go`, `verdict`. The **Cluster Status** tab renders these live;
the **Evaluation** tab renders the final `report`. The report fixture
(`js/mock-report.js`) is generated from `20261011-014311-b2e9.json` and conforms to
`evaluation-report.schema.json`.

## Files

```
frontend/
  index.html              three-column workspace
  settings.html           standalone settings page
  css/styles.css          all styling
  js/
    util.js               DOM + misc helpers
    mock-data.js          fixtures: groups, archetypes, prompts, templates
    mock-report.js        sample evaluation report (schema-conforming)
    mock-backend.js       ← the mocked backend (swap this for real calls)
    state.js              single source of truth + pub/sub
    actions.js            mutations + orchestration
    components/
      generation.js       column 1
      evaluation.js       column 2
      execution.js        column 3 (blank)
      settings.js         settings content (shared)
      settingsModal.js    settings popup
      modal.js            the two-tab popup (cluster status / evaluation)
      toast.js            notifications
    app.js                bootstrap
```

## Note on the third column

The third column is **Idea Execution**, intentionally blank for now. Settings was
moved into a popup opened from the header.