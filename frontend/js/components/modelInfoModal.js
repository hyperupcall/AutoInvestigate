/* components/modelInfoModal.js — "Model info" popup: the models this app uses,
 * their OpenRouter pages and current input/output prices. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  let overlay = null;
  let bodyEl = null;

  function renderBody() {
    const info = Hack.modelInfo;
    const rows = info.MODELS.map((m) =>
      el('tr', {}, [
        el('td', {}, [
          el('a', { href: m.url, target: '_blank', rel: 'noopener', text: m.name }),
          el('div', { class: 'muted small', text: m.id }),
        ]),
        el('td', { class: 'muted', text: m.provider }),
        el('td', { class: 'num', text: info.price(m.input) }),
        el('td', { class: 'num', text: info.price(m.output) }),
      ])
    );

    return el('div', {}, [
      el('p', { class: 'muted small', text: 'The app only calls these models (see CHEAP_MODELS.md). Prices are USD per 1M tokens, from OpenRouter.' }),
      el('table', { class: 'model-table' }, [
        el('thead', {}, [
          el('tr', {}, [
            el('th', { text: 'Model' }),
            el('th', { text: 'Provider' }),
            el('th', { class: 'num', text: 'Input / 1M' }),
            el('th', { class: 'num', text: 'Output / 1M' }),
          ]),
        ]),
        el('tbody', {}, rows),
      ]),
      el('p', { class: 'muted small' }, [
        'Browse every model at ',
        el('a', { href: 'https://openrouter.ai/models', target: '_blank', rel: 'noopener', text: 'openrouter.ai/models' }),
        '.',
      ]),
    ]);
  }

  function mount(container) {
    root = container;

    bodyEl = el('div', { class: 'modal-body' });
    const dialog = el('div', { class: 'modal model-info-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Model info' }),
          el('p', { class: 'muted small', text: 'The models this app uses, with links and prices.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeModelInfo() }),
      ]),
      bodyEl,
    ]);

    overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeModelInfo() }, [dialog]);
    overlay.style.display = 'none';

    clear(root);
    root.appendChild(overlay);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && store.state.ui.modelInfoOpen) actions.closeModelInfo();
    });

    render();
  }

  function render() {
    if (!overlay) return;
    const open = store.state.ui.modelInfoOpen;
    overlay.style.display = open ? '' : 'none';
    if (!open) return;
    clear(bodyEl);
    bodyEl.appendChild(renderBody());
  }

  Hack.components.modelInfoModal = { mount, render };
})();