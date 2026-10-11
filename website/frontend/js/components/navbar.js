/* components/navbar.js — the app header (navbar), shared by every page so it looks
 * the same everywhere: the brand on the left, the primary links (Agent View,
 * Artifact Factory) in the middle, and the actions (agents running, backend badge,
 * Information, Settings) on the right. The links open in the same tab.
 *
 * The workspace (index.html) mounts it from app.js; the other pages mount it from
 * shell.js. The backend badge and the Idea Evaluation View href follow the detected backend
 * (Hack.backendInfo, set by api-backend.js), so the header stays correct on every
 * page without each page wiring it up itself. The "agents running" badge polls the
 * reachable backends' /api/status and shows the total number of active agents. It also
 * refreshes on demand — call Hack.refreshAgents() whenever agents are spawned or
 * destroyed (a run or session starts, stops or finishes) so the badge does not wait
 * for the next poll. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;

  let root = null;
  let lastSignature = null;

  /** The live view is served by the evaluation backend; follow the detected backend. */
  function agentViewHref() {
    if (typeof Hack.agentViewUrl === 'function') return Hack.agentViewUrl();
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

  /* ---- how many agents are running, across the reachable backends ---- */
  // Each service is probed at the same origin first, then at its default port. The `service`
  // field in the reply tells the two apart when a page is served by one of them.
  const SERVICES = [
    { name: 'Evaluation', expect: 'evaluation', candidates: ['', 'http://localhost:8090'], pick: (s) => s.agents || 0 },
    { name: 'Ideation', expect: 'ideation', candidates: ['', 'http://localhost:8091'], pick: (s) => s.running_agents || 0 },
  ];
  const agents = { total: 0, parts: [] };
  let agentsTimer = null;
  let loading = false;
  let pending = false;  // a refresh was asked for while one was in flight

  async function probe(base, expect) {
    // Bound each probe: a backend that accepts the connection but never answers must not
    // stall the whole refresh (which would freeze the badge on a stale count).
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 4000);
    try {
      const r = await fetch(base + '/api/status', { cache: 'no-store', signal: ctrl.signal });
      if (!r.ok) return null;
      const body = await r.json();
      if (body.service !== expect) return null;  // the other service (or something else) answered
      return body;
    } catch (e) { return null; }
    finally { clearTimeout(t); }
  }

  async function loadAgents() {
    if (loading) { pending = true; return; }  // coalesce: run once more when this one finishes
    loading = true;
    try {
      const parts = await Promise.all(SERVICES.map(async (svc) => {
        for (const base of svc.candidates) {
          const body = await probe(base, svc.expect);
          if (body) return { name: svc.name, count: svc.pick(body) };
        }
        return { name: svc.name, count: 0, offline: true };
      }));
      agents.parts = parts;
      agents.total = parts.reduce((n, p) => n + p.count, 0);
      renderAgents();
    } finally {
      loading = false;
      if (pending) { pending = false; loadAgents(); }
    }
  }

  function renderAgents() {
    const host = document.getElementById('agents-running');
    if (!host) return;
    const n = agents.total;
    const online = agents.parts.filter((p) => !p.offline);
    host.className = 'agents-running' + (n ? ' active' : '');
    host.title = online.length
      ? 'Agents running — ' + online.map((p) => `${p.name}: ${p.count}`).join(' · ')
      : 'No backend reachable';
    clear(host);
    if (n) host.appendChild(el('span', { class: 'dot-pulse' }));
    host.appendChild(el('span', { text: n === 1 ? '1 agent running' : `${n} agents running` }));
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
        el('p', { text: 'Automated research, ideation, evaluation, and artifact generation' }),
      ]),
    ]));

    root.appendChild(el('nav', { class: 'app-nav', 'aria-label': 'Primary' }, [
      navLink('ideation-view', 'Research and Ideation', 'ideation.html', 'The ideation collective: topics, sessions and generated ideas'),
      navLink('agent-view', 'Agent View', agentViewHref(), 'The live view served by the backend'),
      navLink('artifact-factory-view', 'Artifact Factory', 'artifactfactory.html', 'The Artifact Factory dashboard'),
    ]));

    root.appendChild(el('div', { class: 'header-actions' }, [
      el('span', { class: 'agents-running', id: 'agents-running', title: 'Agents running across the backends' }),
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
    renderAgents();
  }

  function mount(container) {
    root = container;
    lastSignature = null;
    render();
    if (agentsTimer) clearInterval(agentsTimer);
    loadAgents();
    agentsTimer = setInterval(loadAgents, 5000);
  }

  /* Refresh the badge now, instead of waiting for the next poll. Safe to call from any
   * page (it is a no-op when the navbar is not mounted). Call it whenever agents are
   * spawned or destroyed: a run or session starts, stops or finishes. */
  Hack.refreshAgents = function () { if (root) loadAgents(); };

  Hack.components.navbar = { mount, render, refresh: loadAgents };
})();