/* api-backend.js — connects the UI to the real evaluation backend (the website backend in this repo).
 *
 * If the backend is reachable, Part 2 (idea evaluation) runs for real: every agent is its own AGNTCY/SLIM
 * endpoint and every model call goes through OpenRouter. Otherwise the mock in mock-backend.js keeps working.
 * Part 1 (idea generation) is still the mock.
 *
 * Where the backend is looked for:
 *   - the same origin, when the page is served by the backend (http://localhost:8090/), or
 *   - http://localhost:8090, when the page is served by ./run.sh on port 8000 (the backend allows that origin).
 *   Override with  window.EVAL_API = 'http://host:port'  before this script loads.
 *
 * It swaps Hack.mockBackend.buildReport / startEvaluation in place (actions.js looks them up on every call),
 * fills the settings popup with the backend's real groups and models, and loads past evaluations into the
 * "Research runs" list. Event kinds and the report are exactly what modal.js already renders
 * (report = evaluation-report.schema.json). Routes: see website/README.md.
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const mock = Hack.mockBackend;
  const fallback = { buildReport: mock.buildReport, startEvaluation: mock.startEvaluation };
  const info = (Hack.backendInfo = { live: false, base: '', settings: null, models: [] });
  const POLL_MS = 1000;

  async function getJSON(path, opts) {
    const r = await fetch(info.base + path, opts);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(body.error || `HTTP ${r.status}`), { status: r.status, body });
    return body;
  }
  const post = (path, body) => getJSON(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const put = (path, body) => getJSON(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

  /* The live "Agent View" page, served by the evaluation backend. With a run id it opens that
   * run directly (/live?run=<id>); without one it opens the newest run. Follows the detected
   * backend, so it works whether the page is served by the backend or by run.sh on another port. */
  function agentViewUrl(runId) {
    const base = info.live ? (info.base || '') : 'http://localhost:8090';
    return base + '/live' + (runId ? '?run=' + encodeURIComponent(runId) : '');
  }

  /* The agent cluster, before any event arrives (same report shape, nothing filled in yet).
   * `groupIds` (optional) keeps only those agent groups. */
  function buildReport(ideaText, groupIds) {
    if (!info.live || !info.settings) return fallback.buildReport(ideaText, groupIds);
    const s = info.settings;
    const keep = Array.isArray(groupIds) && groupIds.length ? new Set(groupIds) : null;
    const groups = keep ? s.groups.filter((g) => keep.has(g.id)) : s.groups;
    const now = new Date().toISOString();
    return {
      schema_version: '1.0', generated_at: now,
      run: { id: null, idea: ideaText, status: 'running', started_at: now, finished_at: null, duration_seconds: 0,
             cost_usd: 0, llm_calls: null, max_cost_usd: s.max_cost_usd },
      pipeline: { rounds: 0, extra_round: false, stop_go_decision: null },
      groups: groups.map((g) => ({
        id: g.id, name: g.name, style: g.consensus,
        agents: g.agents.map((a) => ({ id: a.id, name: a.name, model: a.model, mcp_servers: a.mcp_servers || [], question: a.question || null, who_they_are: null })),
        rounds: [], scores: {}, verdict_counts: {}, disagreements: [], stop_go: null, verdict: null,
      })),
      cross_group: { disagreements: [], agreements: [] }, stop_go: null, verdict: null,
      complex: s.complex ? {
        enabled: s.complex.enabled, decision: null, stopped_by: null, rounds: 0,
        stop_votes: s.complex.stop_votes, max_seconds: s.complex.max_seconds,
        stewards: (s.complex.stewards || []).map((st) => ({ id: st.id, name: st.name, objective: st.objective, model: st.model,
                                                          decision: null, confidence: null, reason: null, signals: [] })),
        history: [],
      } : null,
      agntcy: { transport: 'SLIM', protocol: 'A2A', slim_groups_opened: 0,
                endpoints: groups.flatMap((g) => g.agents.map((a) => `deliberation/agents/${a.id}`)) },
      analysis: null,
    };
  }

  function startEvaluation({ ideaText, settings, groupIds, onEvent, onDone }) {
    if (!info.live) return fallback.startEvaluation({ ideaText, settings, groupIds, onEvent, onDone });
    let cancelled = false, timer = null, since = 0;
    const handle = {
      runId: null, durationMs: null,
      cancel() {
        cancelled = true;
        clearTimeout(timer);
        if (handle.runId) post('/api/stop', { run_id: handle.runId }).catch(() => {});
      },
      finalize() {
        // Graceful stop: the swarm stops and the run writes its final verdict (unlike cancel).
        if (handle.runId) post('/api/finalize', { run_id: handle.runId }).catch(() => {});
      },
    };
    const fail = (msg) => { onEvent({ phase: 'Error', kind: 'phase', text: msg, ts: Date.now() }); onDone(buildReport(ideaText, groupIds)); };
    const overrides = { deliberation_seconds: settings && settings.deliberationSeconds, mode: (settings && settings.mode) || 'quick' };
    if (Array.isArray(groupIds) && groupIds.length) overrides.group_ids = groupIds;
    const serverSummarizer = info.settings && info.settings.stages.summarizer.model;
    if (settings && settings.summarizerModel && settings.summarizerModel !== serverSummarizer) overrides.summarizer_model = settings.summarizerModel;

    (async () => {
      try {
        handle.runId = (await post('/api/evaluate', { idea: ideaText, overrides })).run_id;
      } catch (e) {
        return fail(`Could not start the evaluation: ${e.message}`);
      }
      const poll = async () => {
        if (cancelled) return;
        try {
          const r = await getJSON(`/api/ui/runs/${handle.runId}/events?since=${since}`);
          since = r.next;
          r.events.forEach((ev) => onEvent(ev));
          const run = Hack.store && Hack.store.state.evaluation.runs.find((x) => x._handle === handle);
          if (run && r.current) { run.currentPhase = r.current.phase; run.currentAgent = r.current.agent_id; run.backendRunId = handle.runId; Hack.store.notify(); }
          if (!r.running) {
            const report = await getJSON(`/api/runs/${handle.runId}/report`).catch(() => null);
            return onDone(report || buildReport(ideaText, groupIds));
          }
        } catch (e) { /* transient: keep polling */ }
        timer = setTimeout(poll, POLL_MS);
      };
      poll();
    })();
    return handle;
  }

  /* Past evaluations from the backend, shown in "Research runs". */
  async function loadPastRuns() {
    const state = Hack.store.state;
    const runs = await getJSON('/api/runs');
    for (const r of runs.slice(0, 15).reverse()) {
      if (r.status === 'running' || state.evaluation.runs.some((x) => x.backendRunId === r.id)) continue;
      const [ev, report] = await Promise.all([
        getJSON(`/api/ui/runs/${r.id}/events`).catch(() => ({ events: [] })),
        getJSON(`/api/runs/${r.id}/report`).catch(() => null),
      ]);
      if (!report) continue;
      state.evaluation.runs.unshift({
        id: 'backend-' + r.id, backendRunId: r.id, ideaId: null, ideaText: r.idea, model: 'AGNTCY cluster',
        status: r.status === 'done' ? 'done' : 'cancelled', events: ev.events, report,
        cluster: report.groups.map((g) => ({ id: g.id, name: g.name, style: g.style,
          agents: g.agents.map((a) => ({ id: a.id, name: a.name, model: a.model, mcp_servers: a.mcp_servers || [], question: a.question, who_they_are: a.who_they_are })) })),
        complex: report.complex ? {
          agents: (report.complex.stewards || []).map((s) => ({ id: s.id, name: s.name, model: s.model, objective: s.objective })),
          decision: report.complex.decision, stoppedBy: report.complex.stopped_by, report: report.complex,
        } : null,
        startedAt: Date.parse(r.started), finishedAt: Date.parse(report.run.finished_at || r.started),
        currentPhase: 'Complete', currentAgent: '', _handle: null,
      });
    }
    Hack.store.notify();
  }

  function syncSettings(server, models) {
    const s = Hack.store.state.settings;
    info.settings = server;
    info.models = models;
    s.summarizerModel = server.stages.summarizer.model;
    s.evaluationModel = 'per agent (see settings)';
    s.deliberationSeconds = Math.max(6, Math.min(60, server.deliberation_seconds));
    s.mode = s.mode || server.mode || 'quick';
    s.groupPerspectives = server.groups.map((g) => ({
      id: g.id, name: g.name, blurb: g.description || '',
      agents: g.agents.map((a) => ({ id: a.id, name: a.name, role: a.question || '', lens: a.id, model: a.model, mcp_servers: a.mcp_servers || [] })),
    }));
    if (Hack.mcpServers && server.mcp_catalog) Hack.mcpServers.setCatalog(server.mcp_catalog);
  }

  /* Re-fetch the backend settings (used when the Settings popup opens and after a save). */
  async function refreshSettings() {
    if (!info.live) return;
    const [server, models] = await Promise.all([getJSON('/api/settings'), getJSON('/api/models').catch(() => [])]);
    syncSettings(server, models);
    Hack.store.notify();
  }

  const saveSettings = (s) => put('/api/settings', s);
  const resetSettings = () => post('/api/settings/reset', {});
  const forceFinalize = (runId) => post('/api/finalize', { run_id: runId });

  async function detect() {
    const candidates = window.EVAL_API !== undefined ? [window.EVAL_API] : ['', 'http://localhost:8090'];
    for (const base of candidates) {
      try {
        info.base = base;
        await getJSON('/api/status');
        info.live = true;
        break;
      } catch (e) { /* try the next one */ }
    }
    if (!info.live) { info.base = ''; return; }
    try {
      const [server, models] = await Promise.all([getJSON('/api/settings'), getJSON('/api/models').catch(() => [])]);
      syncSettings(server, models);
    } catch (e) { /* settings are optional for running */ }
    // The navbar reads Hack.backendInfo for the badge and the Agent View link.
    Hack.store.notify();
    loadPastRuns().catch(() => {});
    if (Hack.actions && document.getElementById('col-evaluation')) {
      Hack.actions.showToast('Connected to the backend: evaluations are real.', 'ok');
    }
  }

  mock.buildReport = buildReport;
  mock.startEvaluation = startEvaluation;
  Hack.agentViewUrl = agentViewUrl;
  Hack.apiBackend = { detect, loadPastRuns, refreshSettings, saveSettings, resetSettings, forceFinalize, agentViewUrl, info };
  window.addEventListener('load', detect);
})();
