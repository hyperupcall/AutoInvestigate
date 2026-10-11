/* shell.js — the shared app chrome for pages that are not the full workspace
 * (artifactfactory.html): the navbar and the popups it opens (Information,
 * Settings) plus toasts. The workspace (index.html) mounts the same components
 * from app.js.
 *
 * Every mount is optional: a component is only mounted when its root element is
 * present, so a page can include just the parts it needs. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const store = Hack.store;
  const C = Hack.components;

  const CHROME = [
    ['app-header', () => C.navbar],
    ['info-root', () => C.infoModal],
    ['settings-root', () => C.settingsModal],
    ['toast-root', () => C.toast],
  ];

  function boot() {
    const mounted = [];
    for (const [id, get] of CHROME) {
      const node = document.getElementById(id);
      const component = get();
      if (node && component && typeof component.mount === 'function') {
        component.mount(node);
        mounted.push(component);
      }
    }
    store.subscribe(function () {
      for (const component of mounted) {
        if (typeof component.render === 'function') component.render();
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();