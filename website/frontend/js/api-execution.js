/* api-execution.js — connects column 3 (Idea Execution) to the real Artifact
 * Factory backend in the repo's artifactfactory/.
 *
 * If the factory is reachable, building an idea produces real artifacts (the
 * content is still dummy for now — see artifactfactory/README.md). Otherwise the
 * mock in mock-execution.js keeps working.
 *
 * Where the factory is looked for:
 *   - the same origin, when the page is served by the factory, or
 *   - http://localhost:8080, when the page is served by ./run.sh on port 8000
 *     (the factory allows that origin — see AF_CORS_ORIGINS in api.py).
 *   Override with  window.AF_API = 'http://host:port'  before this script loads.
 *
 * It swaps Hack.mockExecution's functions in place (actions.js looks them up on
 * every call), so the UI code does not change. Routes: see artifactfactory/README.md.
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const mock = Hack.mockExecution;
  const fallback = {
    createIdea: mock.createIdea, implementPlan: mock.implementPlan, getJob: mock.getJob,
    getPlan: mock.getPlan, listPlans: mock.listPlans, artifactUrl: mock.artifactUrl,
    startServer: mock.startServer, stopServer: mock.stopServer,
  };
  const info = (Hack.artifactFactoryInfo = { live: false, base: '' });

  async function getJSON(path, opts) {
    const r = await fetch(info.base + path, opts);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(body.error || `HTTP ${r.status}`), { status: r.status, body });
    return body;
  }
  const post = (path, body) => getJSON(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });

  function createIdea(args) {
    if (!info.live) return fallback.createIdea(args);
    return post('/ideas', { text: args.text, title: args.title || '', options: args.options, metadata: args.metadata })
      .then((r) => ({ idea: r.idea, plan: r.plan }));
  }

  function implementPlan(planId) {
    if (!info.live) return fallback.implementPlan(planId);
    return post(`/plans/${planId}/implement`).then((job) => ({ job }));
  }

  function getJob(jobId) {
    if (!info.live) return fallback.getJob(jobId);
    return getJSON(`/jobs/${jobId}`);
  }

  function getPlan(planId) {
    if (!info.live) return fallback.getPlan(planId);
    return getJSON(`/plans/${planId}`);
  }

  function listPlans() {
    if (!info.live) return fallback.listPlans();
    return getJSON('/plans').then((r) => r.plans || []);
  }

  /** The prototype page, served by the factory with a strict no-network policy (null when on the mock). */
  function viewUrl(artifactId) {
    return info.live ? `${info.base}/artifacts/${artifactId}/view` : null;
  }

  function artifactUrl(artifactId) {
    return info.live ? `${info.base}/artifacts/${artifactId}/download` : fallback.artifactUrl(artifactId);
  }

  /** Run a built artifact as a local server; returns the server (with its URL). */
  function startServer(artifactId) {
    if (!info.live) return fallback.startServer(artifactId);
    return post(`/artifacts/${artifactId}/run`).then((r) => r.server);
  }

  function stopServer(serverId) {
    if (!info.live) return fallback.stopServer(serverId);
    return post(`/servers/${serverId}/stop`).then((r) => r.server);
  }

  /** The URL to open a running server at: through the factory's own port when live. */
  function serverUrl(server) {
    if (!server) return null;
    return info.live ? info.base + server.path : server.url;
  }

  async function detect() {
    const candidates = window.AF_API !== undefined ? [window.AF_API] : ['', 'http://localhost:8080'];
    for (const base of candidates) {
      try {
        info.base = base;
        await getJSON('/health');
        info.live = true;
        break;
      } catch (e) { /* try the next one */ }
    }
    if (!info.live) { info.base = ''; return; }
    // The Artifact Factory dashboard is a frontend page (artifactfactory.html);
    // it discovers the factory API itself, so the header link stays relative.
    Hack.store.notify();
    if (Hack.actions && document.getElementById('col-execution')) {
      Hack.actions.showToast('Artifact Factory connected: execution is real.', 'ok');
    }
  }

  mock.createIdea = createIdea;
  mock.implementPlan = implementPlan;
  mock.getJob = getJob;
  mock.getPlan = getPlan;
  mock.listPlans = listPlans;
  mock.artifactUrl = artifactUrl;
  mock.viewUrl = viewUrl;
  mock.startServer = startServer;
  mock.stopServer = stopServer;
  mock.serverUrl = serverUrl;
  Hack.apiExecution = { detect, info };
  window.addEventListener('load', detect);
})();