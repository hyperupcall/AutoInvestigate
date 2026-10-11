/* components/variationsModal.js — the "Create variations" popup.
 *
 * Opened from an idea, a level or the seed. It generates a set of variations up
 * front, lets you regenerate them, and shows a checkbox beside each one. The
 * checked variations are added to the idea list (the left column) with
 * "Select ideas". */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  let overlay = null;
  let bodyEl = null;

  function renderVariationRow(item) {
    return el('label', { class: 'variation-row' + (item.selected ? ' selected' : '') }, [
      el('input', {
        type: 'checkbox', checked: item.selected,
        onchange: () => actions.toggleVariation(item.id),
      }),
      el('span', { class: 'variation-text', text: item.text }),
    ]);
  }

  function renderBody() {
    const v = store.state.ui.variations;
    const selectedCount = v.items.filter((i) => i.selected).length;

    const head = el('div', { class: 'variations-head' }, [
      el('div', { class: 'field inline' }, [
        el('label', { text: 'Variations' }),
        el('input', {
          type: 'number', min: 1, max: 8, class: 'num-input', value: v.count,
          onchange: (e) => actions.setVariationCount(Number(e.target.value)),
        }),
      ]),
      el('button', {
        class: 'btn small', type: 'button', text: 'Regenerate',
        disabled: v.loading,
        title: 'Generate a fresh set of variations',
        onclick: () => actions.regenerateVariations(),
      }),
    ]);

    let list;
    if (v.loading) {
      list = el('div', { class: 'level-loading' }, [el('div', { class: 'spinner' }), el('span', { text: 'Generating…' })]);
    } else if (v.error) {
      list = el('div', { class: 'section-error', text: v.error });
    } else if (!v.items.length) {
      list = el('p', { class: 'muted small', text: 'No variations yet.' });
    } else {
      list = el('div', { class: 'variations-list' }, v.items.map(renderVariationRow));
    }

    return el('div', {}, [
      head,
      v.items.length && !v.loading
        ? el('div', { class: 'variations-toolbar' }, [
            el('span', { class: 'muted small', text: `${selectedCount} of ${v.items.length} selected` }),
            el('div', { class: 'level-head-actions' }, [
              el('button', { class: 'link-btn', text: 'Select all', onclick: () => actions.setAllVariations(true) }),
              el('button', { class: 'link-btn', text: 'Select none', onclick: () => actions.setAllVariations(false) }),
            ]),
          ])
        : null,
      list,
      el('div', { class: 'run-config-actions' }, [
        el('button', { class: 'btn small ghost', text: 'Cancel', onclick: () => actions.closeVariations() }),
        el('button', {
          class: 'btn small primary', text: 'Select ideas',
          disabled: selectedCount === 0 || v.loading,
          title: selectedCount === 0 ? 'Select at least one variation' : 'Add the selected variations to the idea list',
          onclick: () => actions.confirmVariations(),
        }),
      ]),
    ]);
  }

  function mount(container) {
    root = container;

    bodyEl = el('div', { class: 'modal-body' });
    const dialog = el('div', { class: 'modal run-config-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Create variations' }),
          el('p', { class: 'muted small', text: 'Pick the variations to keep; they are added to the idea list.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeVariations() }),
      ]),
      bodyEl,
    ]);

    overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeVariations() }, [dialog]);
    overlay.style.display = 'none';

    clear(root);
    root.appendChild(overlay);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && store.state.ui.variations.open) actions.closeVariations();
    });

    render();
  }

  function render() {
    if (!overlay) return;
    const open = store.state.ui.variations.open;
    overlay.style.display = open ? '' : 'none';
    if (!open) return;
    clear(bodyEl);
    bodyEl.appendChild(renderBody());
  }

  Hack.components.variationsModal = { mount, render };
})();