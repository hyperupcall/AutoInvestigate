/* app.js — bootstrap: mount columns, wire the store subscription. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const store = Hack.store;

  function boot() {
    const header = document.getElementById('app-header');
    const generation = document.getElementById('col-generation');
    const evaluation = document.getElementById('col-evaluation');
    const execution = document.getElementById('col-execution');
    const modalRoot = document.getElementById('modal-root');
    const settingsRoot = document.getElementById('settings-root');
    const infoRoot = document.getElementById('info-root');
    const runConfigRoot = document.getElementById('run-config-root');
    const variationsRoot = document.getElementById('variations-root');
    const artifactRoot = document.getElementById('artifact-root');
    const toastRoot = document.getElementById('toast-root');

    if (!generation || !evaluation || !execution) {
      console.error('[app] missing column containers');
      return;
    }

    Hack.components.navbar.mount(header);
    Hack.components.generation.mount(generation);
    Hack.components.evaluation.mount(evaluation);
    Hack.components.execution.mount(execution);
    Hack.components.modal.mount(modalRoot);
    Hack.components.settingsModal.mount(settingsRoot);
    Hack.components.infoModal.mount(infoRoot);
    Hack.components.runConfigModal.mount(runConfigRoot);
    Hack.components.variationsModal.mount(variationsRoot);
    Hack.components.artifactModal.mount(artifactRoot);
    Hack.components.toast.mount(toastRoot);

    store.subscribe(() => {
      Hack.components.navbar.render();
      Hack.components.generation.render();
      Hack.components.evaluation.render();
      Hack.components.execution.render();
      Hack.components.modal.render();
      Hack.components.settingsModal.render();
      Hack.components.infoModal.render();
      Hack.components.runConfigModal.render();
      Hack.components.variationsModal.render();
      Hack.components.artifactModal.render();
      Hack.components.toast.render();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();