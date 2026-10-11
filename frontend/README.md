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
| **2 · Idea Evaluation** | Selected ideas appear here; start deeper research and open runs. |
| **3 · Idea Execution** | Blank for now — reserved for turning a chosen idea into an artifact. |

**Settings** is a popup, opened from the **Settings** button in the header (not a sidebar).

### Column 1 — Idea Generation (a level tree)

- **Level 0** is the seed box `(A)`. Type an idea and press **Generate Level 1**.
- Generating from level 0 appends to the **level 1** list; generating from level N
  appends to the **level N+1** list. Ideas at the same level are **bunched into one
  plain list** (no per-generation boxes) — generating twice at the same level adds
  to the same list rather than creating a separate box.
- Every level has its **own iteration-type control** at the bottom
  (`Refinement`, `Variation & Generation`, `Consolidation`, `Free-form`), plus the
  matching extra inputs (variation count / free-form instruction).
- **Each idea can be iterated on its own** via its **Iterate →** button (uses the
  level's iteration type on that single idea). To combine several ideas, select
  them and press **Generate Level N+1** in the level's iteration bar
  (consolidation requires ≥ 2 selected ideas).
- Each idea shows the label derived from its lineage, e.g. `Idea after 1 refinement`,
  `Idea after 3 variations`, `Idea after combining 2 ideas`,
  `Idea after 2 variations and 1 combination`.
- The column scrolls independently and auto-scrolls to the newest level.

### Column 2 — Idea Evaluation

- Every selected idea shows up as an evaluation target with a
  **Start Deeper Research** button.
- Each run appears in the **Research runs** list. Click a run to open a popup with
  two tabs:
  - **Agent Thinking** — the live stream of what each agent is doing on the
    backend (phases, agents, summaries, the stop-or-go decision).
  - **Results** — the final structured output: per-group summaries, pros/cons,
    feasibility scores, agent verdicts, the stop-or-go decision and the conclusion.

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

// Part 2 — Idea evaluation (streams events, then results)
const handle = Hack.mockBackend.startEvaluation({
  ideaText,           // the single idea string to evaluate
  settings,           // { deliberationSeconds, groupPerspectives, ... }
  onEvent(ev),        // { phase, kind, group, agent, role, text, ts }
  onDone(results),    // { groups, stopOrGo, conclusion, generatedAt }
});
handle.cancel();
```

## Files

```
frontend/
  index.html              three-column workspace
  settings.html           standalone settings page
  css/styles.css          all styling
  js/
    util.js               DOM + misc helpers
    mock-data.js          fixtures: groups, archetypes, prompts, templates
    mock-backend.js       ← the mocked backend (swap this for real calls)
    state.js              single source of truth + pub/sub
    actions.js            mutations + orchestration
    components/
      generation.js       column 1
      evaluation.js       column 2
      execution.js        column 3 (blank)
      settings.js         settings content (shared)
      settingsModal.js    settings popup
      modal.js            the two-tab popup
      toast.js            notifications
    app.js                bootstrap
```

## Note on the third column

The third column is **Idea Execution**, intentionally blank for now. Settings was
moved into a popup opened from the header.