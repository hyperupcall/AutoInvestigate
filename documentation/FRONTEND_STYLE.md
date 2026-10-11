# AutoInvestigate — Style Guide

The design system for **AutoInvestigate**'s user interface. This is the shared
reference for anyone building UI anywhere in this repo — the three-column app in
`website/frontend/`, the Artifact Factory dashboard (`website/frontend/artifactfactory.html`), and
any backend-served page.

> **Canonical source:** `website/frontend/css/styles.css`. That file is the reference
> implementation of every token and recipe below. When this document and the
> stylesheet disagree, **the stylesheet wins** — update this doc to match.

The goal is that every surface in the project — however it is rendered (hand-written
classic `<script>` frontend, a Python f-string, a server-rendered page) — looks like
it came from the same hand. "We don't want it to look like slop."

---

## 1. Principles

These are non-negotiable. They are why the UI reads as calm and deliberate rather
than as default-bootstrap filler.

1. **Light mode only.** White page, black text, no dark theme, no theme toggle.
2. **Minimal.** Plain layout, thin `1px` borders, system font. No decoration for its
   own sake.
3. **HTML5 named colors, used sparingly.** `silver`, `gray`, `gainsboro`,
   `whitesmoke`, `aliceblue`, `white`, `blue`, `green`, `red`, `darkorange`. **No hex
   colors.** The only exception anywhere is the modal backdrop's `rgba(0, 0, 0, 0.4)`.
4. **No `border-radius`, no `box-shadow`, no gradients, no blur.** Corners are square.
   Depth is communicated by borders and background fills, never by shadow. (The only
   circles are the spinner and the `.dot-pulse` dot.)
5. **No `transition`.** Hover and state changes are instant background/border swaps.
   Motion is limited to the spinner rotation and the pulsing node ring.
6. **Color is a status signal, not decoration.** Green = good, red = bad/stop,
   darkorange = in-progress/warn, blue = interactive/selected, gray = muted. A color
   is always paired with a word or label, so meaning never depends on color alone.
7. **No build step.** Plain CSS, plain HTML, classic `<script>` tags.

---

## 2. Design tokens

### 2.1 Palette

All named HTML5 colors. Use them only in the roles listed.

| Token | Named color | Role |
| --- | --- | --- |
| Text (primary) | `black` | Body copy, headings, values. |
| Text (muted) | `gray` | Labels, meta, hints, secondary copy, disabled text. |
| Link / accent | `blue` | Links, `.link-btn`, active/selected accent. |
| Success | `green` | Done, go, implemented, resolved, support. |
| Danger | `red` | Error, stop, failed, danger, oppose. |
| Warning / live | `darkorange` | Running, pending, warn, conditional, hold, kept, live. |
| Border (structure) | `silver` | Column, card, header, footer, table-head, major dividers. |
| Border (divider) | `gainsboro` | Inner dividers: list-row bottoms, section separators. |
| Border (control) | `gray` | Buttons, inputs, selects, popover, modal frame. |
| Surface (base) | `white` | Page background, cards, ghost/modal backgrounds. |
| Surface (fill) | `whitesmoke` | Button fill, hover fills, code/JSON background. |
| Surface (hover) | `gainsboro` | Button hover, active segment. |
| Surface (selected) | `aliceblue` | Selected row / selected graph node. |
| Backdrop | `rgba(0,0,0,0.4)` | Modal overlay only. |

**Border widths:** `1px` everywhere; `2px`/`2.5px` for the spinner and selected graph
node; `3px` for the left accent bar on verdicts and disagreements.

### 2.2 Semantic status colors

Follow this mapping so the same state always looks the same across columns.

| State | Color | Example class |
| --- | --- | --- |
| Success / done / go | `green` | `.run-status.done`, `.decision-banner.go .decision-value`, `.status.implemented` |
| Running / pending / warn | `darkorange` | `.run-status.running`, `.kind-live`, `.decision-banner.hold` |
| Error / stop / danger | `red` | `.section-error`, `.icon-btn.danger:hover`, `.status.failed` |
| Link / active / selected / extra | `blue` | `a`, `.graph-node.selected`, `.decision-banner.extra` |
| Muted / neutral / stopped | `gray` | `.muted`, `.run-status`, `.decision-banner.stopped` |

### 2.3 Typography

- **Family:** `system-ui, sans-serif` for everything; `monospace` for logs, endpoints,
  model ids, and raw JSON.
- **Base:** `14px`, `line-height: 1.5`, `color: black`.
- **Weights:** `400` normal, `600` semibold (headings, labels, `.primary`, selected
  items, names), `700` bold (the big decision value).

| Size | Use |
| --- | --- |
| `20px` | `.brand-mark` / `.empty-mark` icon. |
| `18px` | `.decision-value`. |
| `15px` | Brand `h1`. |
| `14px` | Column titles (`h2`), modal title, base body. |
| `13px` | Idea text, card titles, most content values. |
| `12.5px` | Event text, meta rows, list items. |
| `12px` | Secondary text, labels, `.small`, small buttons, `.muted` context. |
| `11px` | Tags, badges, `.mock-badge`, chips, `.idea-label`, model ids. |

Headings carry no margin (`h1..h5 { margin: 0 }`); use spacing utilities/wrappers for
gaps. `p` also has `margin: 0`.

### 2.4 Spacing

A small, consistent scale. Prefer these values over arbitrary ones.

`2 · 4 · 6 · 8 · 10 · 12 · 16 · 24` (px)

Common pairings: `8px` card padding, `10px` column-body and modal-head padding,
`12px` modal-body padding, `0 16px` app-header padding, `6–8px` gaps in flex rows, `4px` tight gaps.

### 2.5 Shape and depth

- **`border-radius: 0`** everywhere (spinner/dot only).
- **`box-shadow: none`** everywhere. If something needs to float, it is an overlay with
  a `rgba(0,0,0,0.4)` backdrop.
- **Layering (z-index):** modal overlay `50`, iterate popover `60`, toast root `80`.

### 2.6 Motion

- `.spinner` — `0.7s linear infinite` rotation.
- `.graph-node.live .node-ring` — `1.1s` opacity pulse.
- Everything else: no animation, no transition.

---

## 3. Layout skeletons

### App header

```html
<header class="app-header">
  <div class="brand">
    <img class="brand-mark" src="favicon.svg" alt="" width="20" height="20" />
    <div class="brand-text">
      <h1>AutoInvestigate</h1>
      <p>Automated research, ideation, evaluation, and artifact generation.</p>
    </div>
  </div>
  <nav class="app-nav">
    <a class="nav-link">Agent View</a>
    <a class="nav-link">Artifact Factory</a>
  </nav>
  <div class="header-actions">
    <span class="mock-badge">MOCK BACKEND</span>
    <button class="btn small">Settings</button>
  </div>
</header>
```

A proper navbar: `display:flex; align-items:center; gap:24px; min-height:56px; padding:0 16px;`
with a `whitesmoke` background and a `1px solid silver` bottom border. The brand sits on the
left, `.app-nav` holds the primary links (`.nav-link` is a full-height tab with a transparent
bottom border that turns `gray` on hover), and `.header-actions` is pushed right with
`margin-left:auto` (its `.btn`s are `white` so they read against the bar).

### Columns (the workspace body)

```html
<main class="columns">
  <section class="column"><!-- head + body --></section>
  <section class="column">…</section>
  <section class="column">…</section>
</main>
```

- `.columns`: `grid`, `grid-template-columns: 1fr 1fr 1fr`, `gap: 8px`, `padding: 8px`.
- `.column`: flex column, `border: 1px solid silver`, `min-height: 0`.
- `.column-head`: `padding: 8px 10px; border-bottom: 1px solid silver`.
- `.column-body`: `flex: 1; min-height: 0; overflow-y: auto; padding: 10px`.
- Responsive: `@media (max-width: 1000px)` collapses to a single stacked column.

---

## 4. Component cookbook

### Buttons

```html
<button class="btn">Default</button>
<button class="btn primary">Primary</button>   <!-- semibold only, no fill change -->
<button class="btn ghost">Ghost</button>        <!-- white fill -->
<button class="btn small">Small</button>
<a class="btn" href="…">Link button</a>
<button class="link-btn">Inline link</button>
<button class="icon-btn" title="Remove">✕</button>
<button class="icon-btn danger" title="Delete">✕</button>
<button class="mini-btn">mini</button>
```

Hierarchy is carried by **weight**, not color: `.primary` is just `font-weight: 600`.
Hover swaps fill (`whitesmoke` → `gainsboro`). Disabled is `color: gray` +
`cursor: not-allowed`.

### Segmented control

```html
<div class="segmented">
  <button class="seg-btn active">Refinement</button>
  <button class="seg-btn">Variation</button>
</div>
```

Active = `background: gainsboro; font-weight: 600`.

### Inputs and fields

```html
<div class="field">
  <label>Prompt set</label>
  <select class="select"><option>default</option></select>
</div>
<div class="field inline">
  <label>Deliberation seconds</label>
  <input class="num-input" type="number" value="60">
</div>
```

`label` is `12px` `gray`. Textareas/inputs use `border: 1px solid gray`. `.field`
has `margin-top: 8px`; `.field.inline` puts label and control on one row.

### Cards / panels

One recipe, reused: `border: 1px solid silver; padding: 8px` (or `10px` for larger
cards). Existing examples: `.eval-target`, `.run-card`, `.exec-idea`, `.exec-plan`,
`.exec-artifact`, `.group-card`, `.result-group`, `.cluster-group-block`,
`.input-card`. Hoverable cards add `:hover { background: whitesmoke }` and
`cursor: pointer`.

### Badges, tags, pills, chips

The "pill" recipe — `font-size: 11px; color: gray; border: 1px solid silver; padding: 0 4px`:

```html
<span class="tag">A</span>
<span class="mock-badge">MOCK BACKEND</span>
<span class="level-badge">3 ideas</span>
<span class="exec-plan-status">planned</span>
<span class="cluster-style">open</span>
<span class="run-decision stop">stop</span>
```

Status pills tint the **text and border** (never the fill): `.run-decision.go`
(green), `.run-decision.stop` (red), `.run-decision.extra` (blue), `.run-decision.kept`
(darkorange). `.chip` uses a `1px solid silver` fill-free chip with a `.chip-key`
muted label.

### Tables

`.model-table` (the general table): `width: 100%; border-collapse: collapse`. `th` is
`12px gray semibold`; cells are `padding: 6px 8px; border-bottom: 1px solid silver`.
`.num` right-aligns and nowrap. For key/value blocks use `.meta-table` +
`.meta-row`/`.meta-key`/`.meta-val`.

### Lists and rows

- `.idea-row`: `border-bottom: 1px solid gainsboro`, `:hover` → `whitesmoke`,
  `.selected` → `aliceblue`. `:last-child` drops the border.
- `.event-row`: `border-bottom: 1px dotted gainsboro`.
- Content lists (steps, endpoints, pros/cons): `padding-left: 18px`, no bullets
  styling beyond the browser default.

### Modal and tabs

```html
<div class="modal-overlay">
  <div class="modal">
    <div class="modal-head">
      <div><div class="modal-eyebrow">…</div><h3 class="modal-title">…</h3></div>
      <div class="modal-head-actions">…</div>
    </div>
    <div class="modal-tabs">
      <button class="modal-tab active">Evaluation Swarm</button>
      <button class="modal-tab">Evaluation</button>
    </div>
    <div class="modal-body">…</div>
  </div>
</div>
```

`.modal-overlay` is `fixed; inset: 0; background: rgba(0,0,0,0.4)`, centered. `.modal`
is a flex column with a `1px solid gray` frame, sized to `90vw × 90vh` so every
popup covers 90% of the screen. Size variants: `.settings-modal`, `.model-info-modal`,
`.report-modal` (all also `90vw × 90vh`).

### Empty states

```html
<div class="empty-state">
  <img class="empty-mark" src="favicon.svg" alt="" width="20" height="20" />
  <p>Nothing here yet.</p>
</div>
```

`text-align: center; padding: 24px 12px; color: gray`. `.empty-state.small` = `12px`.

### Progress and score bars

```html
<!-- progress (4px tall) -->
<div class="run-progress"><div class="run-progress-bar" style="width: 40%"></div></div>

<!-- score (6px tall, with label row) -->
<div class="score-top"><span>Market</span><span class="score-val">7 / 10</span></div>
<div class="score-bar"><div class="score-fill" style="width: 70%"></div></div>
```

Bar widths are the one thing set **inline** (`style="width: N%"`) — classes own the
look, inline styles own the data-driven size. Bars are bordered (`1px solid silver`)
with a `gray` fill.

### Loading and feedback

```html
<span class="spinner"></span>          <!-- 14px -->
<span class="spinner small"></span>    <!-- 10px -->
<span class="dot-pulse"></span>        <!-- 6px currentColor dot -->
<div class="toast ok">Saved</div>      <!-- .toast.ok / .warn / .error -->
```

Toasts mount at `#toast-root` (fixed, bottom-center) and tint their **border** by
state: `green`, `darkorange`, `red`.

### Status text

`.run-status` is `12px gray`; `.running` → darkorange, `.done` → green. Prefer a word
("Running", "Done") alongside the color.

### Cluster graph (SVG)

Agent nodes are SVG circles: white fill, `gray` stroke; `.spoken` black stroke;
`:hover` blue stroke; `.selected` aliceblue fill + blue stroke. Edges are `gainsboro`,
turning `silver` (spoken) or `blue` (selected). `.node-ring` (darkorange) pulses when
`.live`. Labels use `paint-order: stroke` with a white halo so they stay legible over
edges.

---

## 5. Utilities

- `.muted` → `color: gray`.
- `.small` → `font-size: 12px`.

That is the entire utility set. Compose layout with flex/grid in the component's own
class rather than adding one-off utilities.

---

## 6. Conventions

- **Class naming:** lowercase `kebab-case`, block-first — `run-card`, `eval-target`,
  `event-row`. Sub-parts are prefixed with the block: `.run-head`, `.run-foot`,
  `.run-status`. No camelCase, no BEM `__`/`--` (modifiers are a second class).
- **State modifiers** are separate classes: `.active`, `.selected`, `.done`,
  `.running`, `.spoken`, `.live`, `.open`, `.resolved`. Never encode state in colors
  alone.
- **Structure vs. divider borders:** structural edges are `silver`; inner dividers are
  `gainsboro`; interactive controls are `gray`. Keep this distinction.
- **Flex/grid, not floats/positioning** for layout. Use `gap` for spacing between
  children rather than margins.
- **Repeat a recipe, don't reinvent it.** If you need a card, use the card recipe. If
  you need a pill, use the pill recipe. New one-off styles should be rare and should
  reuse the tokens above.
- **Accessibility:** `black` on `white` for all real content; `gray` only for
  secondary/meta text that is not load-bearing; state is always spelled out in words,
  not signaled by color alone.

---

## 7. Do / Don't

| Do | Don't |
| --- | --- |
| Use HTML5 named colors in the listed roles. | Introduce hex colors, `rgb()`, or new hues. |
| Keep `border-radius: 0` and no shadows. | Round corners or add drop shadows/gradients/blur. |
| Signal state with `green`/`red`/`darkorange`/`blue` + a word. | Use color as the only carrier of meaning. |
| Reuse `silver` for structure, `gainsboro` for dividers, `gray` for controls. | Mix border colors arbitrarily. |
| Carry hierarchy with `600` weight. | Add colored button fills or badge backgrounds. |
| Set dynamic bar widths inline. | Restyle core components per page. |
| Keep instant hover swaps. | Add CSS `transition`/`animation` beyond spinner + node pulse. |

---

## 8. Using this system from another service

### Inside `website/frontend/`

Link the stylesheet and use the classes as-is — do **not** add page-local CSS:

```html
<link rel="stylesheet" href="css/styles.css" />
```

### In a standalone page (e.g. `artifactfactory/web.py`, backend-rendered HTML)

Some services can't import `website/frontend/css/styles.css`. Inline a small base block and
reuse the same token values and class names so the pages match. This is the approved
base:

```css
/* AutoInvestigate base — paste into a standalone page's <style> */
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: black;
  background: white;
}
h1, h2, h3, h4, h5 { margin: 0; font-weight: 600; }
p { margin: 0; }
button { font: inherit; }
a { color: blue; }
.muted { color: gray; }
.small { font-size: 12px; }

header { padding: 8px 12px; border-bottom: 1px solid silver; }
main { padding: 16px; }

table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 8px;
         border-bottom: 1px solid gainsboro; }
th { font-size: 12px; color: gray; font-weight: 600;
     border-bottom: 1px solid silver; }

.status { font-size: 12px; }
.status.implemented { color: green; }
.status.failed { color: red; }
.status.implementing { color: darkorange; }

footer { padding: 12px 16px; color: gray; font-size: 12px;
         border-top: 1px solid silver; }
```

Then reuse the same class names (`muted`, `small`, `status`, `tag`, `btn`) and the same
status-color mapping, so that a future refactor can lift shared pieces into the
stylesheet without renaming anything.

**If the page can be served by the frontend**, prefer linking `css/styles.css` over
inlining — one source of truth beats two.

---

## 9. Extending the system

1. Add the token/recipe to `website/frontend/css/styles.css` first, in the appropriate,
   comment-delimited section.
2. Reuse existing named colors and the `2·4·6·8·10·12·16·24` spacing scale. Adding a
   color or a `border-radius` requires a strong reason and a note here.
3. Update this document to match — new components belong in the cookbook (§4), new
   state colors in the status table (§2.2).
4. Reflect any user-visible change in `website/frontend/README.md` and `CLAUDE.md` if it
   affects documented behavior.
