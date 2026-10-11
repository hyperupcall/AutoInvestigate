/* artifactfactory.js — the Artifact Factory dashboard.
 *
 * This page used to be rendered by the Python daemon (artifactfactory/web.py).
 * It now lives in the frontend and talks to the factory's JSON API, so all
 * frontend code sits in one place. It lists every evaluation (idea) the factory
 * has been given, with its plan status and artifact count.
 *
 * Where the factory is looked for:
 *   - the same origin, when the page is served by the factory, or
 *   - http://localhost:8080, when the page is served by the frontend server.
 *   Override with  window.AF_API = 'http://host:port'  before this script loads.
 */
(function () {
  const info = { base: '', live: false };

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const key of Object.keys(attrs)) {
        const value = attrs[key];
        if (value == null || value === false) continue;
        if (key === 'class') node.className = value;
        else if (key === 'text') node.textContent = value;
        else if (key === 'href') node.setAttribute('href', value);
        else node.setAttribute(key, value);
      }
    }
    append(node, children);
    return node;
  }

  function append(node, children) {
    if (children == null || children === false) return;
    const list = Array.isArray(children) ? children : [children];
    for (const child of list) {
      if (child == null || child === false) continue;
      node.appendChild(typeof child === 'string' || typeof child === 'number'
        ? document.createTextNode(String(child)) : child);
    }
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  async function getJSON(path) {
    const r = await fetch(info.base + path);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(body.error || `HTTP ${r.status}`), { status: r.status });
    return body;
  }

  function deriveTitle(idea, plan) {
    if (plan && plan.title) return plan.title;
    const title = (idea.title || '').trim();
    if (title) return title;
    const text = (idea.text || '').trim();
    if (!text) return 'Untitled idea';
    const first = text.split('.')[0].trim();
    return (first || text).slice(0, 80);
  }

  function statusClass(status) {
    return ['implemented', 'failed', 'implementing'].indexOf(status) >= 0 ? status : '';
  }

  function row(index, idea, plan) {
    const title = deriveTitle(idea, plan);
    const text = (idea.text || '').trim();
    const received = idea.created_at || '';
    const planId = (plan && plan.id) || idea.plan_id;
    const status = plan ? (plan.status || 'planned') : 'no plan';
    const artifacts = ((plan && plan.artifact_ids) || []).length;

    const planCell = el('td', {}, [
      el('span', { class: 'status ' + statusClass(status), text: status }),
      planId ? el('div', {}, [el('a', { href: `/plans/${encodeURIComponent(planId)}`, text: planId })]) : null,
    ]);

    return el('tr', {}, [
      el('td', { class: 'num', text: String(index) }),
      el('td', {}, [
        el('div', { class: 'title', text: title }),
        el('div', { class: 'text', text }),
      ]),
      el('td', { class: 'muted small', text: received }),
      planCell,
      el('td', { class: 'num', text: String(artifacts) }),
    ]);
  }

  function render(ideas, plans, version) {
    const body = document.getElementById('factory-body');
    clear(body);

    const plansByIdea = {};
    for (const p of plans) plansByIdea[p.idea_id] = p;

    const ordered = ideas.slice().sort((a, b) =>
      String(b.created_at || '').localeCompare(String(a.created_at || '')));

    if (ordered.length) {
      body.appendChild(el('table', { class: 'factory-table' }, [
        el('thead', {}, [el('tr', {}, [
          el('th', { class: 'num', text: '#' }),
          el('th', { text: 'Evaluation' }),
          el('th', { text: 'Received' }),
          el('th', { text: 'Plan' }),
          el('th', { class: 'num', text: 'Artifacts' }),
        ])]),
        el('tbody', {}, ordered.map((idea, i) => row(i + 1, idea, plansByIdea[idea.id]))),
      ]));
    } else {
      body.appendChild(el('p', { class: 'empty', text: 'No evaluations yet. Send an idea from the Idea Evaluation column ("Execute →") and it will appear here.' }));
    }

    const footer = document.getElementById('factory-footer');
    clear(footer);
    footer.appendChild(el('span', { text: `Artifact Factory ${version || ''}`.trim() }));
    footer.appendChild(document.createTextNode(' · '));
    footer.appendChild(el('a', { href: info.base + '/info', text: 'JSON API' }));
    footer.appendChild(document.createTextNode(' · '));
    footer.appendChild(el('a', { href: info.base + '/health', text: 'health' }));
  }

  function setStatus(live) {
    const badge = document.getElementById('factory-status');
    if (!badge) return;
    badge.textContent = live ? 'LIVE' : 'OFFLINE';
    badge.title = live ? 'Connected to the Artifact Factory API' : 'Artifact Factory API not reachable';
  }

  async function load() {
    const body = document.getElementById('factory-body');
    clear(body);
    body.appendChild(el('p', { class: 'muted', text: 'Loading…' }));
    try {
      const [ideasRes, plansRes, infoRes] = await Promise.all([
        getJSON('/ideas'), getJSON('/plans'), getJSON('/info').catch(() => ({})),
      ]);
      info.live = true;
      setStatus(true);
      render(ideasRes.ideas || [], plansRes.plans || [], infoRes.version);
    } catch (e) {
      info.live = false;
      setStatus(false);
      clear(body);
      body.appendChild(el('p', { class: 'empty', text: `Could not reach the Artifact Factory API (${e.message}).` }));
    }
  }

  async function detect() {
    const candidates = window.AF_API !== undefined ? [window.AF_API] : ['', 'http://localhost:8080'];
    for (const base of candidates) {
      try {
        info.base = base;
        await getJSON('/health');
        break;
      } catch (e) { info.base = ''; }
    }
    load();
  }

  const refresh = document.getElementById('factory-refresh');
  if (refresh) refresh.addEventListener('click', load);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', detect);
  else detect();
})();