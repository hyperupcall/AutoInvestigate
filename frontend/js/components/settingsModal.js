/* components/settingsModal.js — settings as a POPUP (not a sidebar). */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  let overlay = null;
  let bodyEl = null;
  let lastSignature = null;

  function signature() {
    const g = store.state.settings.groupPerspectives;
    return g.map((x) => x.id + ':' + x.agents.map((a) => a.id).join(',')).join('|');
  }

  function mount(container) {
    root = container;

    bodyEl = el('div', { class: 'modal-body' });
    const dialog = el('div', { class: 'modal settings-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Settings' }),
          el('p', { class: 'muted small', text: 'Models, prompts and group perspectives. API keys always live on the backend.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeSettings() }),
      ]),
      bodyEl,
    ]);

    overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeSettings() }, [dialog]);
    overlay.style.display = 'none';

    clear(root);
    root.appendChild(overlay);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && store.state.ui.settingsOpen) actions.closeSettings();
    });

    render();
  }

  function render() {
    if (!overlay) return;
    const open = store.state.ui.settingsOpen;
    overlay.style.display = open ? '' : 'none';
    if (!open) return;

    // Rebuild only when the group/agent structure changes, so live evaluation
    // events never steal focus from a settings input mid-typing.
    const sig = signature();
    if (sig === lastSignature && bodyEl.childElementCount) return;
    lastSignature = sig;
    clear(bodyEl);
    bodyEl.appendChild(Hack.components.settings.renderContent());
  }

  Hack.components.settingsModal = { mount, render };
})();