/* components/navbar.js — the app header (navbar), shared by every page so it looks
 * the same everywhere: the brand on the left, the primary links (Agent View,
 * Artifact Factory) in the middle, and the actions (backend badge, Information,
 * Settings) on the right. The links open in the same tab.
 *
 * The workspace (index.html) mounts it from app.js; the other pages mount it from
 * shell.js. The backend badge and the Agent View href follow the detected backend
 * (Hack.backendInfo, set by api-backend.js), so the header stays correct on every
 * page without each page wiring it up itself. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;

  let root = null;
  let lastSignature = null;

  /** The live view is served by the evaluation backend; follow the detected backend. */
  function agentViewHref() {
    const info = Hack.backendInfo;
    if (info && info.live) return (info.base || '') + '/live';
    return 'http://localhost:8090/live';
  }

  function navLink(id, label, href, title) {
    return el('a', { class: 'nav-link', id, href, title, text: label });
  }

  function headerButton(id, label, title, onclick) {
    return el('button', { class: 'btn small', id, type: 'button', title, text: label, onclick });
  }

  /** Open a popup when the shell is present; otherwise fall back to a page. */
  function open(name, fallback) {
    const actions = Hack.actions;
    if (actions && typeof actions[name] === 'function') actions[name]();
    else if (fallback) window.location.href = fallback;
  }

  /** The brand goes home to the workspace; on the workspace itself, don't reload
   *  (the app keeps its state in memory). */
  function onHomeClick(e) {
    if (document.getElementById('col-generation')) e.preventDefault();
  }

  function render() {
    if (!root) return;
    const info = Hack.backendInfo || { live: false, base: '' };
    const signature = (info.live ? '1' : '0') + '|' + (info.base || '');
    if (signature === lastSignature && root.childElementCount) return;
    lastSignature = signature;
    clear(root);

    root.appendChild(el('a', { class: 'brand', href: 'index.html', title: 'Back to the workspace', onclick: onHomeClick }, [
      el('img', { class: 'brand-mark', src: 'favicon.svg', alt: '', width: 20, height: 20 }),
      el('div', { class: 'brand-text' }, [
        el('h1', { text: 'AutoInvestigate' }),
        el('p', { text: 'Automated research — generate, refine and stress-test ideas' }),
      ]),
    ]));

    root.appendChild(el('nav', { class: 'app-nav', 'aria-label': 'Primary' }, [
      navLink('agent-view', 'Agent View', agentViewHref(), 'The live view served by the backend'),
      navLink('artifact-factory-view', 'Artifact Factory', 'artifactfactory.html', 'The Artifact Factory dashboard'),
    ]));

    root.appendChild(el('div', { class: 'header-actions' }, [
      el('span', {
        class: 'mock-badge',
        id: 'backend-badge',
        title: info.live
          ? 'Evaluations run on the real backend (generation is still mocked)'
          : 'All backend calls are mocked for now',
        text: info.live ? 'LIVE BACKEND' : 'MOCK BACKEND',
      }),
      headerButton('open-info', 'Information', 'App, backend and model information', () => open('openInfo', 'index.html')),
      headerButton('open-settings', 'Settings', 'Models, keys, groups and MCP servers', () => open('openSettings', 'index.html')),
    ]));
  }

  function mount(container) {
    root = container;
    lastSignature = null;
    render();
  }

  Hack.components.navbar = { mount, render };
})();