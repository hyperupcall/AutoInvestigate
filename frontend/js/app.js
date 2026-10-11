/* app.js — bootstrap: mount columns, wire the store subscription. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const store = Hack.store;

  function boot() {
    const generation = document.getElementById('col-generation');
    const evaluation = document.getElementById('col-evaluation');
    const execution = document.getElementById('col-execution');
    const modalRoot = document.getElementById('modal-root');
    const settingsRoot = document.getElementById('settings-root');
    const toastRoot = document.getElementById('toast-root');

    if (!generation || !evaluation || !execution) {
      console.error('[app] missing column containers');
      return;
    }

    Hack.components.generation.mount(generation);
    Hack.components.evaluation.mount(evaluation);
    Hack.components.execution.mount(execution);
    Hack.components.modal.mount(modalRoot);
    Hack.components.settingsModal.mount(settingsRoot);
    Hack.components.toast.mount(toastRoot);

    const openSettingsBtn = document.getElementById('open-settings');
    if (openSettingsBtn) openSettingsBtn.addEventListener('click', () => Hack.actions.openSettings());

    store.subscribe(() => {
      Hack.components.generation.render();
      Hack.components.evaluation.render();
      Hack.components.execution.render();
      Hack.components.modal.render();
      Hack.components.settingsModal.render();
      Hack.components.toast.render();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();