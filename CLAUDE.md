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

**Prompts** must be configurable via a file on the filesystem and selectable in
settings.

---

## 4. Frontend UI (as built)

Location: `frontend/`. **No build step** — vanilla JS, classic `<script>` tags, a
single `window.Hack` namespace. Open `frontend/index.html` directly, or serve it
(`python3 -m http.server`).

### Layout — three columns

| Column | Purpose |
| --- | --- |
| **1 · Idea Generation** | Seed box + the level tree of ideas. |
| **2 · Idea Evaluation** | Selected ideas + deeper-research runs. |
| **3 · Idea Execution** | **Blank for now** — reserved for turning a chosen idea into an artifact. |

**Settings is a popup**, opened from the **Settings** button in the header (not a
sidebar). The same content is also available as a standalone `frontend/settings.html`.

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
- **Evaluate →** copies the idea into the **Idea Evaluation** column (it does *not*
  start the run). Selection is only used for iterating.
- Each idea shows a **lineage label**, e.g. `Idea after 1 refinement`,
  `Idea after 3 variations`, `Idea after combining 2 ideas`,
  `Idea after 2 variations and 1 combination`.
- The **level terminology lives in the code** (`state.levels`, `level` numbers) but
  is **not shown in the interface** — no "Level N" labels.
- The column scrolls independently and auto-scrolls to the newest level.

### Column 2 — Idea Evaluation

- **Evaluate →** in column 1 copies an idea into the **Queued for evaluation** list
  here (duplicates are blocked; each queued item can be removed with ✕ or cleared
  with **Clear all**).
- Each queued idea has its own **Start Deeper Research** button, which starts the run
  and moves the idea into the **Research runs** list.
- Each run appears in the **Research runs** list. Clicking a run opens a large popup with
  **two tabs**:
  - **Cluster Status** — what is in the agent cluster (groups, agents, models,
    questions, who they are) plus the live stream of what each agent is saying:
    discussion turns, evaluations, summaries, cross-group analysis, the stop-or-go
    decision and the verdict, as the backend emits them.
  - **Evaluation** — the finished report, shaped exactly like
    `evaluation-report.schema.json`: run metadata, pipeline, stop-or-go, final
    verdict, cross-group disagreements/agreements, per-group scores/verdicts/
    disagreements, AGNTCY transport and the disagreement analysis. Includes a
    collapsible **Raw JSON** view of the whole report.

### Settings (popup)

Models (generation / evaluation / summarizer), deliberation seconds, prompt set,
and editable group perspectives (defaults: Research ×4, Private Equity ×4, Market
Reaction ×5). **API keys are intentionally not here** — they live on the backend.

### Design principles

- **Light mode only.**
- **Minimal styling** — plain layout, thin borders, system font.
- **HTML5 named colors, used sparingly** (`silver`, `gray`, `gainsboro`,
  `whitesmoke`, `aliceblue`, `green`, `red`, `darkorange`, `blue`). No hex colors,
  gradients, shadows, or blur.
- "We don't want it to look like slop."

---

## 5. Architecture

```
frontend/
  index.html              three-column workspace
  settings.html           standalone settings page
  css/styles.css          all styling (light, minimal)
  js/
    util.js               DOM + misc helpers (el, preserveView, seeded RNG, …)
    mock-data.js          fixtures: groups, archetypes, prompts, text templates
    mock-report.js        sample evaluation report (evaluation-report.schema.json)
    mock-backend.js       ← the MOCKED backend (swap for real calls)
    state.js              single source of truth + pub/sub + selectors
    actions.js            mutations + orchestration
    components/
      generation.js       column 1 (level tree)
      evaluation.js       column 2
      execution.js        column 3 (blank)
      settings.js         settings content (shared by popup + page)
      settingsModal.js    settings popup
      modal.js            the two-tab popup (cluster status / evaluation)
      toast.js            notifications
    app.js                bootstrap
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

---

## 6. Mock backend contract

`frontend/js/mock-backend.js` is the single swap point. Replace the bodies with
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

Event kinds streamed to `onEvent`: `phase`, `cluster`, `group-start`,
`round-start`, `turn`, `missed`, `evaluation`, `failed`, `summary`,
`cross-group`, `stop-go`, `verdict`. The **Cluster Status** tab renders these live;
the **Evaluation** tab renders the final `report`.

The report fixture (`js/mock-report.js`) is generated from
`20261011-014311-b2e9.json` and conforms to `evaluation-report.schema.json`.

---

## 7. Status & next steps

**Done (mocked):** three-column UI, level tree with per-level/per-idea iteration,
lineage labels, evaluation runs with the two-tab popup (**Cluster Status** live
stream + **Evaluation** report with raw JSON), settings popup + page,
light/minimal styling.

**Done (real): Part 2 backend** in `backend/` (see `backend/README.md`, routes documented there).
`frontend/js/api-backend.js` swaps the mock evaluation for the real one whenever the backend answers (same origin
on :8090, or `localhost:8090` from `run.sh` on :8000); otherwise the mock still runs. Past runs load into
"Research runs". Stop-or-go is shown as the deliberation outcome (Stopped / Extra round / Disagreement kept),
not as a verdict on the idea; the idea's verdict is the "Final verdict" block.

**Not done:**

- **Part 1 backend (idea generation)** — `generateIdeas` is still the mock.
- **Column 3 · Idea Execution** — currently blank (the "code and implement" stage).
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