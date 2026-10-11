/* components/infoModal.js — the "Information" popup: everything about the app in
 * one place — what it does, which backends are connected, the models it uses
 * (with OpenRouter links and prices) and the useful links. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  let overlay = null;
  let bodyEl = null;

  function section(title, children) {
    return el('section', { class: 'info-section' }, [
      el('h4', { class: 'info-section-title', text: title }),
      ...children,
    ]);
  }

  function connection(label, live, base, note) {
    const status = el('span', { class: 'info-status ' + (live ? 'live' : 'offline'), text: live ? 'live' : 'mock' });
    const detail = live
      ? el('a', { href: base, target: '_blank', rel: 'noopener', text: base })
      : el('span', { class: 'muted', text: 'not reachable — the mock is used' });
    return el('li', {}, [
      el('div', { class: 'info-row' }, [
        el('span', { class: 'info-label', text: label }),
        status,
      ]),
      el('div', { class: 'muted small', text: note }),
      el('div', { class: 'small' }, [detail]),
    ]);
  }

  function modelsTable() {
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
    ]);
  }

  function renderBody() {
    const backend = Hack.backendInfo || { live: false, base: '' };
    const factory = Hack.artifactFactoryInfo || { live: false, base: '' };

    return el('div', {}, [
      section('About', [
        el('p', { text: 'AutoInvestigate generates, refines and stress-tests research ideas with competing AI agents, then turns a chosen idea into artifacts.' }),
        el('p', { class: 'muted small', text: 'Idea generation is mocked; idea evaluation and idea execution connect to the real backends when they are running.' }),
      ]),
      section('Connections', [
        el('ul', { class: 'info-list' }, [
          connection('Evaluation backend', backend.live, backend.base || 'http://localhost:8090', 'Idea evaluation (column 2) — AGNTCY/SLIM agents over OpenRouter.'),
          connection('Artifact Factory', factory.live, factory.base || 'http://localhost:8080', 'Idea execution (column 3) — plans and artifacts.'),
        ]),
      ]),
      section('Models', [modelsTable()]),
      section('Links', [
        el('ul', { class: 'info-list' }, [
          el('li', {}, [el('a', { href: 'https://openrouter.ai/models', target: '_blank', rel: 'noopener', text: 'OpenRouter — browse every model' })]),
          el('li', {}, [el('a', { href: 'https://outshift.cisco.com/', target: '_blank', rel: 'noopener', text: 'Cisco Outshift' })]),
        ]),
      ]),
    ]);
  }

  function mount(container) {
    root = container;

    bodyEl = el('div', { class: 'modal-body' });
    const dialog = el('div', { class: 'modal info-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Information' }),
          el('p', { class: 'muted small', text: 'About the app, its backends, the models it uses and useful links.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeInfo() }),
      ]),
      bodyEl,
    ]);

    overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeInfo() }, [dialog]);
    overlay.style.display = 'none';

    clear(root);
    root.appendChild(overlay);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && store.state.ui.infoOpen) actions.closeInfo();
    });

    render();
  }

  function render() {
    if (!overlay) return;
    const open = store.state.ui.infoOpen;
    overlay.style.display = open ? '' : 'none';
    if (!open) return;
    clear(bodyEl);
    bodyEl.appendChild(renderBody());
  }

  Hack.components.infoModal = { mount, render };
})();