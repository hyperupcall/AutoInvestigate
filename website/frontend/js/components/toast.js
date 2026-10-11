/* components/toast.js — transient notifications. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;
  const store = Hack.store;

  let root = null;

  function mount(container) {
    root = container;
    render();
  }

  function render() {
    if (!root) return;
    const toast = store.state.ui.toast;
    clear(root);
    if (!toast) return;
    root.appendChild(el('div', { class: 'toast ' + toast.kind, text: toast.message }));
  }

  Hack.components.toast = { mount, render };
})();