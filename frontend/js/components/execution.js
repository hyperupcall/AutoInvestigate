/* components/execution.js — RIGHT column: Idea Execution (blank for now). */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;

  function mount(container) {
    clear(container);
    container.appendChild(el('div', { class: 'column-head' }, [
      el('div', { class: 'column-title' }, [
        el('span', { class: 'column-index', text: '3' }),
        el('h2', { text: 'Idea Execution' }),
      ]),
      el('p', { class: 'column-sub', text: 'Turn a chosen idea into a tangible artifact.' }),
    ]));
    container.appendChild(el('div', { class: 'column-body' }));
  }

  function render() { /* intentionally blank */ }

  Hack.components.execution = { mount, render };
})();