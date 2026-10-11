/* components/generation.js — LEFT column: idea generation as a level tree.
 *
 * Level 0 is the seed box. Generating from it appends to the level 1 list.
 * Generating from a level N list appends to the level N+1 list. Ideas at the
 * same level are bunched into one plain list (no per-generation boxes).
 *
 * The iteration type is NOT shown inline. Each level (and the seed) has a single
 * "Iterate" button; clicking it opens a small menu with just two choices:
 * "Create variations" (a popup that generates variations you can pick from) and
 * "Text input" (a free-form instruction). The level terminology stays in the
 * code but is not surfaced in the interface.
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, preserveView } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let refs = {};
  let lastLevelCount = 0;
  let popoverEl = null;

  /* ------------------------------- mount ------------------------------- */
  function mount(container) {
    clear(container);

    const header = el('div', { class: 'column-head' }, [
      el('div', { class: 'column-title' }, [
        el('span', { class: 'column-index', text: '1' }),
        el('h2', { text: 'Idea Generation' }),
      ]),
      el('p', { class: 'column-sub', text: 'Seed an idea, then iterate to grow the tree.' }),
    ]);

    const seedCard = buildSeedCard();
    const sections = el('div', { class: 'sections' });

    container.appendChild(header);
    container.appendChild(seedCard);
    container.appendChild(el('div', { class: 'column-body', 'data-scroll-key': 'gen-body' }, [sections]));

    refs.sections = sections;
    lastLevelCount = 0;
    syncSeed();
    render();
  }

  /* ------------------------------ seed card ------------------------------ */
  function buildSeedCard() {
    const textarea = el('textarea', {
      class: 'input-idea', id: 'seed-idea', 'data-focus-key': 'seed-idea', rows: 3,
      placeholder: 'Describe the initial idea… e.g. "Use homomorphic encryption so agents can compute on encrypted customer telemetry."',
      oninput: (e) => { store.state.seed.text = e.target.value; updateSeedButton(); },
    });

    const btn = el('button', {
      class: 'btn primary', type: 'button', id: 'submit-seed',
      onclick: (e) => openIterateMenu(e.currentTarget, { kind: 'seed' }),
    }, [el('span', { class: 'btn-label', text: 'Generate' })]);

    const hint = el('div', { class: 'input-hint' });

    const card = el('div', { class: 'input-card level-0' }, [
      el('div', { class: 'input-card-head' }, [
        el('span', { class: 'input-card-title', text: 'Seed idea / prompt' }),
      ]),
      textarea,
      el('div', { class: 'input-actions' }, [hint, btn]),
    ]);

    refs.seedTextarea = textarea;
    refs.seedBtn = btn;
    refs.seedHint = hint;
    return card;
  }

  function syncSeed() {
    const s = store.state.seed;
    if (document.activeElement !== refs.seedTextarea) refs.seedTextarea.value = s.text;
  }

  function updateSeedButton() {
    const s = store.state.seed;
    const hasText = s.text.trim().length > 0;
    refs.seedBtn.disabled = !hasText || s.submitting;
    refs.seedBtn.querySelector('.btn-label').textContent = s.submitting ? 'Working…' : 'Generate';
    refs.seedHint.textContent = hasText ? '' : 'enter a seed idea';
  }

  /* ------------------------------- render ------------------------------- */
  function render() {
    syncSeed();
    updateSeedButton();

    preserveView(refs.sections, () => {
      clear(refs.sections);
      const s = store.state;
      if (!s.levels.length) {
        refs.sections.appendChild(el('div', { class: 'empty-state' }, [
          el('img', { class: 'empty-mark', src: 'favicon.svg', alt: '', width: 20, height: 20 }),
          el('p', { text: 'No ideas yet.' }),
          el('p', { class: 'muted', text: 'Type a seed idea above and press Generate.' }),
        ]));
        return;
      }
      s.levels.forEach((lvl) => refs.sections.appendChild(renderLevel(lvl)));
    });

    if (store.state.levels.length > lastLevelCount) {
      const body = refs.sections.closest('.column-body');
      if (body) requestAnimationFrame(() => { body.scrollTop = body.scrollHeight; });
    }
    lastLevelCount = store.state.levels.length;
  }

  /* ------------------------------- levels ------------------------------- */
  function renderLevel(lvl) {
    const s = store.state;
    const selectedInLevel = lvl.ideas.filter((i) => s.selectedIdeaIds.includes(i.id)).length;
    const allSelected = lvl.ideas.length > 0 && selectedInLevel === lvl.ideas.length;

    const head = el('div', { class: 'level-group-head' }, [
      el('span', { class: 'muted small', text: lvl.ideas.length + (lvl.ideas.length === 1 ? ' idea' : ' ideas') }),
      el('div', { class: 'level-head-actions' }, [
        lvl.ideas.length
          ? el('button', { class: 'link-btn', text: allSelected ? 'Deselect all' : 'Select all', onclick: () => actions.selectLevelIdeas(lvl.level) })
          : null,
        lvl.ideas.length
          ? el('button', {
              class: 'btn small', type: 'button', text: 'Evaluate',
              title: 'Copy the selected ideas (or the whole level) to Idea Evaluation',
              onclick: () => actions.queueLevelForEvaluation(lvl.level),
            })
          : null,
        lvl.ideas.length
          ? el('button', {
              class: 'btn small', type: 'button', text: 'Iterate',
              title: 'Create variations or apply a text instruction',
              onclick: (e) => openIterateMenu(e.currentTarget, { kind: 'level', level: lvl.level }),
            })
          : null,
      ]),
    ]);

    const list = el('div', { class: 'level-list' });
    lvl.ideas.forEach((idea) => list.appendChild(renderIdeaRow(lvl, idea)));
    if (lvl.pending > 0) {
      list.appendChild(el('div', { class: 'level-loading' }, [el('div', { class: 'spinner' }), el('span', { text: 'Generating…' })]));
    }
    if (lvl.error) list.appendChild(el('div', { class: 'section-error', text: lvl.error }));

    return el('div', { class: 'level-group', dataset: { level: lvl.level } }, [head, list]);
  }

  function renderIdeaRow(lvl, idea) {
    const selected = store.state.selectedIdeaIds.includes(idea.id);

    return el('div', {
      class: 'idea-row' + (selected ? ' selected' : ''),
      dataset: { ideaId: idea.id },
      onclick: () => actions.toggleIdeaSelection(idea.id),
    }, [
      el('div', { class: 'idea-check', text: selected ? '✓' : '' }),
      el('div', { class: 'idea-body' }, [
        el('p', { class: 'idea-text', text: idea.text }),
        el('div', { class: 'idea-meta' }, [
          el('button', {
            class: 'mini-btn', text: 'Iterate',
            title: 'Create variations of this idea or apply a text instruction',
            onclick: (e) => { e.stopPropagation(); openIterateMenu(e.currentTarget, { kind: 'idea', ideaId: idea.id }); },
          }),
          el('button', {
            class: 'mini-btn', text: 'Evaluate →',
            title: 'Copy this idea to the Idea Evaluation column',
            onclick: (e) => { e.stopPropagation(); actions.queueIdeaForEvaluation(idea.id); },
          }),
        ]),
      ]),
    ]);
  }

  /* --------------------------- iterate menu --------------------------- */
  function selectionHint(target) {
    if (target.kind === 'seed') return 'the seed idea';
    if (target.kind === 'idea') return 'this idea';
    const lvl = store.state.levels.find((l) => l.level === target.level);
    if (!lvl) return '';
    const sel = lvl.ideas.filter((i) => store.state.selectedIdeaIds.includes(i.id)).length;
    if (sel) return sel + ' selected';
    return 'all ' + lvl.ideas.length + (lvl.ideas.length === 1 ? ' idea' : ' ideas');
  }

  /** The small menu opened by "Iterate"/"Generate": two choices only. */
  function openIterateMenu(anchor, target) {
    closeIteratePopover();

    const pop = el('div', { class: 'iterate-popover' }, [
      el('div', { class: 'iterate-popover-title', text: 'Iterate ' + selectionHint(target) }),
      el('button', {
        class: 'menu-item', type: 'button',
        onclick: () => { closeIteratePopover(); actions.openVariations(target); },
      }, [
        el('span', { class: 'menu-item-label', text: 'Create variations' }),
        el('span', { class: 'menu-item-hint', text: 'Generate options and pick the ones to keep.' }),
      ]),
      el('button', {
        class: 'menu-item', type: 'button',
        onclick: () => { closeIteratePopover(); openTextInput(anchor, target); },
      }, [
        el('span', { class: 'menu-item-label', text: 'Text input' }),
        el('span', { class: 'menu-item-hint', text: 'Apply a free-form instruction.' }),
      ]),
    ]);

    showPopover(pop, anchor);
  }

  /** The "Text input" popover: a free-form instruction applied to the target. */
  function openTextInput(anchor, target) {
    closeIteratePopover();

    const textarea = el('textarea', {
      class: 'input-prompt', rows: 3,
      placeholder: 'e.g. "reduce scope to a single deployable component and target the EU market"',
    });

    const pop = el('div', { class: 'iterate-popover' }, [
      el('div', { class: 'iterate-popover-title', text: 'Text input · ' + selectionHint(target) }),
      textarea,
      el('div', { class: 'iterate-popover-actions' }, [
        el('span', { class: 'input-hint' }),
        el('button', {
          class: 'btn primary small', type: 'button', text: 'Generate',
          onclick: () => {
            const text = textarea.value;
            closeIteratePopover();
            actions.iterateWithText(target, text);
          },
        }),
      ]),
    ]);

    showPopover(pop, anchor);
    textarea.focus();
  }

  function showPopover(pop, anchor) {
    document.body.appendChild(pop);

    const r = anchor.getBoundingClientRect();
    const top = Math.min(r.bottom + 4, window.innerHeight - pop.offsetHeight - 8);
    const left = Math.min(r.left, window.innerWidth - pop.offsetWidth - 8);
    pop.style.top = Math.max(8, top) + 'px';
    pop.style.left = Math.max(8, left) + 'px';

    popoverEl = pop;
    document.addEventListener('mousedown', onDocMouseDown, true);
    document.addEventListener('keydown', onDocKeyDown, true);
  }

  function closeIteratePopover() {
    if (popoverEl) { popoverEl.remove(); popoverEl = null; }
    document.removeEventListener('mousedown', onDocMouseDown, true);
    document.removeEventListener('keydown', onDocKeyDown, true);
  }

  function onDocMouseDown(e) {
    if (popoverEl && !popoverEl.contains(e.target)) closeIteratePopover();
  }

  function onDocKeyDown(e) {
    if (e.key === 'Escape') closeIteratePopover();
  }

  Hack.components.generation = { mount, render };
})();