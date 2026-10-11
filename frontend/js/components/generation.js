/* components/generation.js — LEFT column: idea generation as a level tree.
 *
 * Level 0 is the seed box. Generating from it appends to the level 1 list.
 * Generating from a level N list appends to the level N+1 list. Ideas at the
 * same level are bunched into one plain list (no per-generation boxes). Each
 * level has its own iteration-type control, and each idea can be iterated on
 * its own ("Iterate") or together with other selected ideas ("Generate Level N+1").
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, preserveView } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  const ITERATION_TYPES = [
    { id: 'refinement', label: 'Refinement', hint: 'Sharpen one or more rough ideas into something specific.' },
    { id: 'variation', label: 'Variation & Generation', hint: 'Generate multiple variations of the selected ideas.' },
    { id: 'consolidation', label: 'Consolidation', hint: 'Merge two or more ideas into one.' },
    { id: 'freeform', label: 'Free-form', hint: 'Apply a custom instruction to the selected ideas.' },
  ];

  let refs = {};
  let lastLevelCount = 0;

  /* ------------------------------- mount ------------------------------- */
  function mount(container) {
    clear(container);

    const header = el('div', { class: 'column-head' }, [
      el('div', { class: 'column-title' }, [
        el('span', { class: 'column-index', text: '1' }),
        el('h2', { text: 'Idea Generation' }),
      ]),
      el('p', { class: 'column-sub', text: 'Seed an idea, then iterate ideas at any level to grow the tree.' }),
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

    const typeRow = el('div', { class: 'segmented', role: 'tablist' });
    ITERATION_TYPES.forEach((t) => {
      typeRow.appendChild(el('button', {
        class: 'seg-btn', type: 'button', dataset: { type: t.id }, title: t.hint, text: t.label,
        onclick: () => { store.state.seed.iterationType = t.id; syncSeed(); updateSeedButton(); },
      }));
    });

    const variationWrap = el('div', { class: 'field inline' }, [
      el('label', { text: 'Variations' }),
      el('input', {
        type: 'number', min: 1, max: 8, value: 2, class: 'num-input', id: 'variation-count',
        oninput: (e) => { store.state.seed.variationCount = Math.max(1, Math.min(8, Number(e.target.value) || 1)); },
      }),
    ]);

    const freeformWrap = el('div', { class: 'field' }, [
      el('label', { text: 'Free-form instruction' }),
      el('textarea', {
        class: 'input-prompt', rows: 2, id: 'freeform-prompt',
        placeholder: 'e.g. "reduce scope to a single deployable component and target the EU market"',
        oninput: (e) => { store.state.seed.freeformPrompt = e.target.value; },
      }),
    ]);

    const btn = el('button', {
      class: 'btn primary', type: 'button', id: 'submit-seed',
      onclick: () => actions.submitSeed(),
    }, [el('span', { class: 'btn-label', text: 'Generate Level 1' })]);

    const hint = el('div', { class: 'input-hint' });

    const card = el('div', { class: 'input-card level-0' }, [
      el('div', { class: 'input-card-head' }, [
        el('span', { class: 'level-badge', text: 'Level 0' }),
        el('span', { class: 'input-card-title', text: 'Seed idea / prompt' }),
      ]),
      textarea,
      el('div', { class: 'field' }, [el('label', { text: 'Iteration type' }), typeRow]),
      variationWrap,
      freeformWrap,
      el('div', { class: 'input-actions' }, [hint, btn]),
    ]);

    refs.seedTextarea = textarea;
    refs.seedTypeRow = typeRow;
    refs.seedVariationWrap = variationWrap;
    refs.seedFreeformWrap = freeformWrap;
    refs.seedBtn = btn;
    refs.seedHint = hint;
    return card;
  }

  function syncSeed() {
    const s = store.state.seed;
    if (document.activeElement !== refs.seedTextarea) refs.seedTextarea.value = s.text;
    refs.seedTypeRow.querySelectorAll('.seg-btn').forEach((b) => {
      b.classList.toggle('active', b.dataset.type === s.iterationType);
    });
    refs.seedVariationWrap.style.display = s.iterationType === 'variation' ? '' : 'none';
    refs.seedFreeformWrap.style.display = s.iterationType === 'freeform' ? '' : 'none';
    const vc = refs.seedVariationWrap.querySelector('input');
    if (vc && document.activeElement !== vc) vc.value = s.variationCount;
    const ff = refs.seedFreeformWrap.querySelector('textarea');
    if (ff && document.activeElement !== ff) ff.value = s.freeformPrompt;
  }

  function updateSeedButton() {
    const s = store.state.seed;
    const hasText = s.text.trim().length > 0;
    refs.seedBtn.disabled = !hasText || s.submitting;
    refs.seedBtn.querySelector('.btn-label').textContent = s.submitting ? 'Working…' : 'Generate Level 1';
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
          el('div', { class: 'empty-mark', text: '◈' }),
          el('p', { text: 'No ideas yet.' }),
          el('p', { class: 'muted', text: 'Type a seed idea above and press Generate to create level 1.' }),
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
      el('span', { class: 'level-badge', text: 'Level ' + lvl.level }),
      el('span', { class: 'muted small', text: lvl.ideas.length + (lvl.ideas.length === 1 ? ' idea' : ' ideas') }),
      lvl.ideas.length
        ? el('button', { class: 'link-btn', text: allSelected ? 'Deselect all' : 'Select all', onclick: () => actions.selectLevelIdeas(lvl.level) })
        : null,
    ]);

    const list = el('div', { class: 'level-list' });
    lvl.ideas.forEach((idea) => list.appendChild(renderIdeaRow(lvl, idea)));
    if (lvl.pending > 0) {
      list.appendChild(el('div', { class: 'level-loading' }, [el('div', { class: 'spinner' }), el('span', { text: 'Generating…' })]));
    }
    if (lvl.error) list.appendChild(el('div', { class: 'section-error', text: lvl.error }));

    const children = [head, list];
    if (lvl.ideas.length) children.push(renderIterationBar(lvl));

    return el('div', {
      class: 'level-group',
      style: { marginLeft: Math.min(lvl.level - 1, 4) * 14 + 'px' },
      dataset: { level: lvl.level },
    }, children);
  }

  function renderIdeaRow(lvl, idea) {
    const selected = store.state.selectedIdeaIds.includes(idea.id);
    const canIterate = lvl.iteration.type !== 'consolidation';

    return el('div', {
      class: 'idea-row' + (selected ? ' selected' : ''),
      dataset: { ideaId: idea.id },
      onclick: () => actions.toggleIdeaSelection(idea.id),
    }, [
      el('div', { class: 'idea-check', text: selected ? '✓' : '' }),
      el('div', { class: 'idea-body' }, [
        el('p', { class: 'idea-text', text: idea.text }),
        el('div', { class: 'idea-meta' }, [
          idea.label ? el('span', { class: 'idea-label', text: idea.label }) : null,
          el('button', {
            class: 'mini-btn', text: 'Iterate →', disabled: !canIterate,
            title: canIterate ? 'Generate the next level from this idea alone' : 'Consolidation needs multiple ideas',
            onclick: (e) => { e.stopPropagation(); actions.iterateIdea(lvl.level, idea.id); },
          }),
          el('button', {
            class: 'mini-btn', text: 'Evaluate →',
            onclick: (e) => { e.stopPropagation(); actions.selectOnly(idea.id); actions.startEvaluation(idea.id); },
          }),
        ]),
      ]),
    ]);
  }

  function renderIterationBar(lvl) {
    const it = lvl.iteration;
    const typeRow = el('div', { class: 'segmented' });
    ITERATION_TYPES.forEach((t) => {
      typeRow.appendChild(el('button', {
        class: 'seg-btn' + (it.type === t.id ? ' active' : ''), type: 'button', dataset: { type: t.id },
        title: t.hint, text: t.label,
        onclick: () => actions.setLevelIteration(lvl.level, { type: t.id }),
      }));
    });

    const children = [el('div', { class: 'field' }, [el('label', { text: 'Iteration type' }), typeRow])];

    if (it.type === 'variation') {
      children.push(el('div', { class: 'field inline' }, [
        el('label', { text: 'Variations' }),
        el('input', {
          type: 'number', min: 1, max: 8, class: 'num-input', value: it.variationCount,
          'data-focus-key': 'var-' + lvl.level,
          oninput: (e) => { it.variationCount = Math.max(1, Math.min(8, Number(e.target.value) || 1)); },
        }),
      ]));
    }
    if (it.type === 'freeform') {
      children.push(el('div', { class: 'field' }, [
        el('label', { text: 'Free-form instruction' }),
        el('textarea', {
          class: 'input-prompt', rows: 2, value: it.freeformPrompt,
          'data-focus-key': 'ff-' + lvl.level,
          placeholder: 'e.g. "reduce scope to a single deployable component"',
          oninput: (e) => { it.freeformPrompt = e.target.value; },
        }),
      ]));
    }

    const selectedCount = lvl.ideas.filter((i) => store.state.selectedIdeaIds.includes(i.id)).length;
    children.push(el('div', { class: 'input-actions' }, [
      el('span', { class: 'input-hint', text: selectedCount ? selectedCount + ' selected' : 'select ideas above' }),
      el('button', {
        class: 'btn primary small', type: 'button',
        text: 'Generate Level ' + (lvl.level + 1),
        onclick: () => actions.generateFromLevel(lvl.level),
      }),
    ]));

    return el('div', { class: 'level-iteration' }, children);
  }

  Hack.components.generation = { mount, render };
})();