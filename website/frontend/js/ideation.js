/* ideation.js — the Ideation View.
 *
 * The page for the ideation collective (website/ideation/). It shows the tagged
 * watchlist of topics, the refinement sessions, the ideas the team produced, and
 * the memory. A session is drawn as an agent graph — the same visual language as
 * the Evaluation Swarm — with the selected agent's messages beside it. Each
 * message is the large context the agent read, the one-sentence idea, and the
 * 3-4 bullet points justifying it.
 *
 * Where the daemon is looked for:
 *   - the same origin, when the page is served by the daemon, or
 *   - http://localhost:8091, when the page is served by the frontend server.
 *   Override with  window.ID_API = 'http://host:port'  before this script loads.
 */
(function () {
  const info = { base: '', live: false };
  const SVG_NS = 'http://www.w3.org/2000/svg';

  const state = {
    topics: [], sessions: [], sessionIdeas: [], memory: [], status: null, settings: null,
    selectedSessionId: null, selectedAgentId: null,
    session: null, lastSeq: 0, tab: 'session', pollTimer: null,
    settingsOpen: false, settingsStatus: null,
    topicModal: { open: false, description: '', draft: null, status: null, busy: false },
    discoverModal: { open: false, topics: [], selected: null, status: null, busy: false },
  };

  /* ------------------------------- helpers ------------------------------- */
  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const key of Object.keys(attrs)) {
        const value = attrs[key];
        if (value == null || value === false) continue;
        if (key === 'class') node.className = value;
        else if (key === 'text') node.textContent = value;
        else if (key === 'html') node.innerHTML = value;
        else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
        else node.setAttribute(key, value);
      }
    }
    append(node, children);
    return node;
  }

  function append(node, children) {
    if (children == null || children === false) return;
    for (const child of (Array.isArray(children) ? children : [children])) {
      if (child == null || child === false) continue;
      node.appendChild(typeof child === 'string' || typeof child === 'number'
        ? document.createTextNode(String(child)) : child);
    }
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function svg(tag, attrs, children) {
    const node = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (const key of Object.keys(attrs)) {
        const value = attrs[key];
        if (value == null || value === false) continue;
        if (key === 'text') node.textContent = value;
        else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
        else node.setAttribute(key, value);
      }
    }
    append(node, children);
    return node;
  }

  function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts);
    return isNaN(d) ? '' : d.toLocaleTimeString();
  }

  function formatCount(n) {
    if (n < 1000) return String(n);
    if (n < 1000000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
  }

  async function getJSON(path, opts) {
    const r = await fetch(info.base + path, opts);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(body.error || `HTTP ${r.status}`), { status: r.status });
    return body;
  }
  const post = (path, body) => getJSON(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}),
  });

  /* Ask the shared navbar badge to recount now (ideation agents spawned or destroyed). */
  function refreshAgents() {
    if (window.Hack && window.Hack.refreshAgents) window.Hack.refreshAgents();
  }

  /* ------------------------------- loading ------------------------------- */
  async function detect() {
    const candidates = window.ID_API !== undefined ? [window.ID_API] : ['', 'http://localhost:8091'];
    for (const base of candidates) {
      try { info.base = base; await getJSON('/health'); info.live = true; break; }
      catch (e) { info.base = ''; info.live = false; }
    }
    await load();
  }

  async function load() {
    setStatus();
    if (!info.live) { renderAll(); return; }
    try {
      const [topics, sessions, memory, status, settings] = await Promise.all([
        getJSON('/api/topics'), getJSON('/api/sessions'),
        getJSON('/api/memory'), getJSON('/api/status'), getJSON('/api/settings'),
      ]);
      state.topics = topics.topics || [];
      state.sessions = sessions.sessions || [];
      state.memory = memory.memory || [];
      state.status = status;
      state.settings = settings;
      if (!state.selectedSessionId && state.sessions.length) state.selectedSessionId = state.sessions[0].id;
    } catch (e) {
      info.live = false;
      setStatus();
    }
    renderAll();
    if (state.selectedSessionId) await openSession(state.selectedSessionId, false);
  }

  function setStatus() {
    const badge = document.getElementById('ideation-status');
    if (!badge) return;
    badge.textContent = info.live ? 'LIVE' : 'OFFLINE';
    badge.title = info.live ? 'Connected to the ideation daemon' : 'Ideation daemon not reachable';
    const summary = document.getElementById('ideation-summary');
    if (summary) {
      const s = state.status;
      summary.textContent = s
        ? `${s.enabled_topics} topics · ${s.signals} signals · ${s.ideas} ideas · ${s.memory} memories · every ${Math.round(s.poll_interval_seconds / 60)}m`
        : '';
    }
  }

  /* ------------------------------ rendering ------------------------------ */
  function renderAll() {
    renderTopics();
    renderSessions();
    renderTabs();
    renderDetail();
    renderSettings();
    renderTopicModal();
    renderDiscoverModal();
  }

  function renderTopics() {
    const host = document.getElementById('ideation-topics');
    if (!host) return;
    clear(host);
    document.getElementById('ideation-topic-count').textContent = state.topics.length ? `${state.topics.length}` : '';
    if (!state.topics.length) {
      host.appendChild(el('p', { class: 'empty small', text: info.live ? 'No topics yet.' : 'Daemon offline.' }));
    } else {
      for (const t of state.topics) {
        host.appendChild(el('div', { class: 'ideation-topic' + (t.enabled ? '' : ' off') }, [
          el('div', { class: 'ideation-topic-head' }, [
            el('span', { class: 'ideation-topic-title' }, [
              el('span', { class: 'ideation-topic-name', text: t.name }),
              t.origin === 'finder'
                ? el('span', { class: 'ideation-origin', title: t.rationale || 'Found by the topic finder', text: 'found' })
                : null,
            ]),
            el('button', {
              class: 'mini-btn', text: 'Run session', title: 'Start a refinement session for this topic',
              onclick: () => runSession(t.id),
            }),
          ]),
          t.description ? el('p', { class: 'ideation-topic-desc muted small', text: t.description }) : null,
          t.rationale ? el('p', { class: 'ideation-topic-rationale muted small', text: '↳ ' + t.rationale }) : null,
          el('div', { class: 'ideation-tags' }, (t.tags || []).map((tag) => el('span', { class: 'ideation-tag', text: tag }))),
        ]));
      }
    }
    if (info.live) {
      host.appendChild(el('button', {
        class: 'ideation-add-topic', type: 'button', text: '+ Add Topic',
        title: 'Describe a topic and let the AI fill in the details', onclick: openTopicModal,
      }));
    }
  }

  function renderSessions() {
    const host = document.getElementById('ideation-sessions');
    if (!host) return;
    clear(host);
    document.getElementById('ideation-session-count').textContent = state.sessions.length ? `${state.sessions.length}` : '';
    if (!state.sessions.length) {
      host.appendChild(el('p', { class: 'empty small', text: 'No sessions yet. Run one from a topic.' }));
      return;
    }
    for (const s of state.sessions) {
      const active = s.id === state.selectedSessionId;
      const running = s.status === 'running';
      host.appendChild(el('div', {
        class: 'ideation-session' + (active ? ' active' : ''),
        onclick: () => openSession(s.id, true),
      }, [
        el('div', { class: 'ideation-session-head' }, [
          el('span', { class: 'run-status ' + (s.status === 'done' ? 'done' : running ? 'running' : s.status === 'failed' ? 'failed' : 'cancelled') }, [
            running ? el('span', { class: 'dot-pulse' }) : null,
            s.status,
          ]),
          running
            ? el('button', {
                class: 'mini-btn danger', text: 'Terminate', title: 'Stop this session',
                onclick: (e) => { e.stopPropagation(); stopSession(s.id); },
              })
            : el('span', { class: 'muted small', text: s.trigger || '' }),
        ]),
        el('div', { class: 'ideation-session-topic', text: s.topic_name || s.topic_id }),
        el('div', { class: 'muted small', text: (s.started_at || '').replace('T', ' ').slice(0, 19) }),
      ]));
    }
  }

  function renderTabs() {
    const host = document.getElementById('ideation-tabs');
    if (!host) return;
    clear(host);
    const tabs = [['session', 'Session'], ['ideas', 'Ideas'], ['memory', 'Memory']];
    for (const [id, label] of tabs) {
      host.appendChild(el('button', {
        class: 'modal-tab' + (state.tab === id ? ' active' : ''), text: label,
        onclick: () => { state.tab = id; renderTabs(); renderDetail(); },
      }));
    }
  }

  function renderDetail() {
    const host = document.getElementById('ideation-detail-body');
    if (!host) return;
    clear(host);
    if (!info.live) {
      host.appendChild(el('p', { class: 'empty', text: 'The ideation daemon is not reachable. Start it with `python -m ideation.daemon` (port 8091).' }));
      return;
    }
    if (state.tab === 'ideas') return renderIdeas(host);
    if (state.tab === 'memory') return renderMemory(host);
    return renderSession(host);
  }

  /* ------------------------------- session ------------------------------- */
  async function openSession(id, scroll) {
    state.selectedSessionId = id;
    state.selectedAgentId = null;
    state.lastSeq = 0;
    state.session = null;
    state.sessionIdeas = [];
    state.tab = 'session';   // clicking a session always shows it in the main view
    try {
      const [meta, ev, ideas] = await Promise.all([
        getJSON(`/api/sessions/${id}`),
        getJSON(`/api/sessions/${id}/events?since=0`),
        getJSON(`/api/ideas?session_id=${encodeURIComponent(id)}`),
      ]);
      state.sessionIdeas = ideas.ideas || [];
      state.session = { meta, events: ev.events || [] };
      state.lastSeq = state.session.events.reduce((m, e) => Math.max(m, e.seq || 0), 0);
      const start = state.session.events.find((e) => e.kind === 'session-start');
      state.session.agents = (start && start.agents) || (meta.report && meta.report.agents) || [];
      state.session.topic = (start && start.topic) || { name: meta.topic_name };
      if (meta.status === 'running') startPolling(id);
    } catch (e) { /* leave empty */ }
    renderSessions();
    renderTabs();
    renderDetail();
    if (scroll) window.scrollTo({ top: 0 });
  }

  function startPolling(id) {
    stopPolling();
    state.pollTimer = setInterval(async () => {
      try {
        const ev = await getJSON(`/api/sessions/${id}/events?since=${state.lastSeq}`);
        const events = ev.events || [];
        if (events.length) {
          state.session.events.push(...events);
          state.lastSeq = events.reduce((m, e) => Math.max(m, e.seq || 0), state.lastSeq);
          if (state.tab === 'session') renderDetail();
        }
        if (events.some((e) => e.kind === 'done')) {
          stopPolling();
          const meta = await getJSON(`/api/sessions/${id}`);
          state.session.meta = meta;
          const ideas = await getJSON(`/api/ideas?session_id=${encodeURIComponent(id)}`);
          state.sessionIdeas = ideas.ideas || [];
          renderSessions();
          renderDetail();
          refreshAgents();  // the session's team has stopped
        }
      } catch (e) { stopPolling(); }
    }, 1500);
  }

  function stopPolling() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
  }

  async function runSession(topicId) {
    try {
      const session = await post('/api/sessions', { topic_id: topicId });
      state.sessions.unshift(session);
      refreshAgents();  // the session's team is running now
      renderSessions();
      await openSession(session.id, true);
      state.tab = 'session';
      renderTabs();
      renderDetail();
    } catch (e) {
      alert('Could not start the session: ' + e.message);
    }
  }

  /** Ask a running session to stop. The team finishes the turn it is on, then stops. */
  async function stopSession(id) {
    try {
      await post(`/api/sessions/${id}/stop`);
      refreshAgents();  // the team is winding down (it stops after the current turn)
      const meta = await getJSON(`/api/sessions/${id}`);
      const idx = state.sessions.findIndex((s) => s.id === id);
      if (idx >= 0) state.sessions[idx] = meta;
      const selected = state.session && state.session.meta && state.session.meta.id === id;
      if (selected) {
        state.session.meta = meta;
        // Keep polling so the "cancelled"/"done" events land in the log once the current turn ends.
        startPolling(id);
      }
      renderSessions();
      if (selected && state.tab === 'session') renderDetail();
      if (Hack.actions && Hack.actions.showToast) Hack.actions.showToast('Session terminated.', 'ok');
    } catch (e) {
      if (Hack.actions && Hack.actions.showToast) Hack.actions.showToast('Could not terminate the session: ' + e.message, 'error');
    }
  }

  /** Ask the topic finder to read the internet and propose new topics. */
  async function discoverTopics() {
    const btn = document.getElementById('ideation-discover');
    if (btn) { btn.disabled = true; btn.textContent = 'Generating…'; }
    try {
      const r = await post('/api/topics/discover', { preview: true });
      const proposed = r.proposed || [];
      if (proposed.length) openDiscoverModal(proposed);
      else if (Hack.actions && Hack.actions.showToast) Hack.actions.showToast('No new topics found.', 'warn');
    } catch (e) {
      if (Hack.actions && Hack.actions.showToast) Hack.actions.showToast('Could not find topics: ' + e.message, 'error');
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Generate topics'; }
  }

  /** Ask Gemini for ideas vaguely related to the watchlist topics. */
  async function relatedIdeas() {
    const btn = document.getElementById('ideation-related');
    if (btn) { btn.disabled = true; btn.textContent = 'Thinking…'; }
    try {
      const r = await post('/api/ideas/related');
      const n = (r.added || []).length;
      if (Hack.actions && Hack.actions.showToast) {
        Hack.actions.showToast(n ? `Added ${n} related idea${n === 1 ? '' : 's'}.` : 'No related ideas came back.', n ? 'ok' : 'warn');
      }
      await load();
    } catch (e) {
      if (Hack.actions && Hack.actions.showToast) Hack.actions.showToast('Could not generate related ideas: ' + e.message, 'error');
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Related ideas'; }
  }

  function renderSession(host) {
    const s = state.session;
    if (!s || !s.meta) {
      host.appendChild(el('p', { class: 'empty', text: 'Select a session on the left, or run one from a topic.' }));
      return;
    }
    const events = s.events || [];
    const turns = events.filter((e) => e.kind === 'turn');
    const final = events.filter((e) => e.kind === 'final').pop();
    const running = s.meta.status === 'running';

    host.appendChild(el('div', { class: 'cluster-status-bar' }, [
      el('span', { class: 'muted small', text: 'Click an agent to read its reasoning' }),
      el('span', { class: 'muted small', text: `${turns.length} messages · ${s.agents.length} agents · ${running ? 'running' : s.meta.status}` }),
      running
        ? el('button', {
            class: 'mini-btn danger', text: 'Terminate session', title: 'Stop this session',
            onclick: () => stopSession(s.meta.id),
          })
        : null,
    ]));

    host.appendChild(renderGraph(s.agents, turns, running));

    if (final) {
      host.appendChild(el('div', { class: 'ideation-final' }, [
        el('div', { class: 'ideation-final-head' }, [
          el('span', { class: 'ideation-kind ' + final.kind, text: final.kind }),
          final.artifact_type ? el('span', { class: 'ideation-artifact', text: final.artifact_type }) : null,
          el('span', { class: 'muted small', text: 'Final idea' }),
        ]),
        el('p', { class: 'ideation-idea', text: final.idea }),
        renderJustification(final.justification),
        renderBuild(final.build),
        renderAnalysis(final.analysis),
      ]));
    }

    // The streamed log of every message, newest last.
    const log = el('div', { class: 'thinking-log' });
    for (const ev of events) {
      const node = renderEvent(ev);
      if (node) log.appendChild(node);
    }
    if (running) {
      log.appendChild(el('div', { class: 'event-row kind-live' }, [
        el('span', { class: 'spinner small' }), el('span', { text: 'The team is working…' }),
      ]));
    }
    host.appendChild(log);
  }

  /* -------------------------------- graph -------------------------------- */
  function renderGraph(agents, turns, running) {
    if (!agents.length) return el('div', { class: 'empty-state small' }, [el('p', { class: 'muted', text: 'No agents yet.' })]);
    const selectedId = state.selectedAgentId || (agents[0] && agents[0].id);
    const spoken = new Set(turns.map((t) => t.agent_id));
    const selected = agents.find((a) => a.id === selectedId) || agents[0];
    const agentTurns = turns.filter((t) => t.agent_id === selected.id);

    return el('div', { class: 'cluster-graph' }, [
      el('div', { class: 'cluster-group-block' }, [
        el('div', { class: 'cluster-group-head' }, [
          el('span', { class: 'cluster-group-name', text: 'Ideation team' }),
          el('span', { class: 'cluster-style', text: 'collaborative' }),
          el('span', { class: 'muted small', text: `${agents.length} agents` }),
        ]),
        el('div', { class: 'cluster-graph-wrap' }, [
          renderGroupGraph(agents, selectedId, spoken, running),
          renderAgentStream(selected, agentTurns),
        ]),
      ]),
    ]);
  }

  function renderGroupGraph(agents, selectedId, spoken, running) {
    const n = agents.length;
    const W = 580, H = 300, cx = W / 2, cy = H / 2, R = 84, r = 22;
    const nodes = agents.map((a, i) => {
      const ang = (-90 + (360 / Math.max(n, 1)) * i) * (Math.PI / 180);
      return { agent: a, ang, x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) };
    });
    const edges = [];
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i], b = nodes[j];
        const touches = a.agent.id === selectedId || b.agent.id === selectedId;
        const both = spoken.has(a.agent.id) && spoken.has(b.agent.id);
        edges.push(svg('line', { class: 'graph-edge' + (touches ? ' selected' : both ? ' spoken' : ''), x1: a.x, y1: a.y, x2: b.x, y2: b.y }));
      }
    }
    const nodeEls = nodes.map((node) => {
      const a = node.agent;
      const isSel = a.id === selectedId;
      const cls = 'graph-node' + (isSel ? ' selected' : '') + (spoken.has(a.id) ? ' spoken' : '');
      const label = labelPlacement(node, r, a.name);
      return svg('g', { class: cls, onclick: () => { state.selectedAgentId = a.id; renderDetail(); } }, [
        svg('circle', { class: 'node-circle', cx: node.x, cy: node.y, r }),
        svg('text', { class: 'node-initials', x: node.x, y: node.y + 4, 'text-anchor': 'middle', text: initials(a.name) }),
        ...label.lines.map((line, i) => svg('text', {
          class: 'node-label', x: label.x, y: label.y + i * label.lineHeight, 'text-anchor': label.anchor, text: line,
        })),
      ]);
    });
    return el('div', { class: 'cluster-graph-canvas' }, [
      svg('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMid meet', role: 'img' }, [
        svg('g', { class: 'graph-edges' }, edges),
        svg('g', { class: 'graph-nodes' }, nodeEls),
      ]),
    ]);
  }

  function labelLines(name, maxChars) {
    const words = String(name || '').split(/\s+/).filter(Boolean);
    const lines = [];
    let cur = '';
    for (const w of words) {
      if (!cur) cur = w;
      else if ((cur + ' ' + w).length <= maxChars) cur += ' ' + w;
      else { lines.push(cur); cur = w; }
    }
    if (cur) lines.push(cur);
    if (lines.length > 2) {
      const rest = lines.slice(1).join(' ');
      lines.length = 1;
      lines.push(rest.length > maxChars ? rest.slice(0, maxChars - 1).trimEnd() + '…' : rest);
    }
    return lines.length ? lines : [''];
  }

  function labelPlacement(node, r, name) {
    const cos = Math.cos(node.ang), sin = Math.sin(node.ang);
    const lines = labelLines(name, 22);
    const lineHeight = 13;
    const span = (lines.length - 1) * lineHeight;
    if (cos > 0.35) return { x: node.x + r + 8, y: node.y + 4 - span / 2, anchor: 'start', lines, lineHeight };
    if (cos < -0.35) return { x: node.x - r - 8, y: node.y + 4 - span / 2, anchor: 'end', lines, lineHeight };
    return sin < 0
      ? { x: node.x, y: node.y - r - 8 - span, anchor: 'middle', lines, lineHeight }
      : { x: node.x, y: node.y + r + 16, anchor: 'middle', lines, lineHeight };
  }

  function initials(name) {
    const words = String(name || '').split(/\s+/).filter(Boolean);
    if (!words.length) return '?';
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return (words[0][0] + words[1][0]).toUpperCase();
  }

  function renderAgentStream(agent, turns) {
    if (!agent) return el('div', { class: 'agent-stream empty-state small' }, [el('p', { class: 'muted', text: 'No agents.' })]);
    const a = agentDetail(agent);
    const chars = turns.reduce((n, t) => n + ((t.context || '').length), 0);
    const head = el('div', { class: 'agent-stream-head' }, [
      el('div', { class: 'agent-stream-name', text: a.name }),
      el('div', { class: 'agent-stream-model', text: a.model || '' }),
      el('div', { class: 'agent-stream-stats muted small', text: `${turns.length} messages · ${formatCount(chars)} chars` }),
    ]);
    const about = el('div', { class: 'agent-stream-about' }, [
      a.role ? el('p', { class: 'cluster-agent-who muted small', text: a.role }) : null,
      renderAgentCapabilities(a),
      renderAgentPrompt(a),
    ]);
    const body = el('div', { class: 'agent-stream-body' });
    if (!turns.length) {
      body.appendChild(el('p', { class: 'muted small', text: 'This agent has not spoken yet.' }));
    } else {
      turns.forEach((t) => body.appendChild(renderTurn(t)));
    }
    return el('div', { class: 'agent-stream' }, [head, about, body]);
  }

  /** The session's agent record, enriched with the roster's prompt/skills/mcp when missing. */
  function agentDetail(agent) {
    if (!agent) return agent;
    const known = ((state.settings && state.settings.agents) || []).find((x) => x.id === agent.id) || {};
    return Object.assign({}, known, agent, {
      prompt_text: agent.prompt_text || known.prompt_text,
      mcp_servers: (agent.mcp_servers && agent.mcp_servers.length) ? agent.mcp_servers : (known.mcp_servers || []),
      skills: (agent.skills && agent.skills.length) ? agent.skills : (known.skills || []),
    });
  }

  /** The skills and MCP servers an agent can access. */
  function renderAgentCapabilities(agent) {
    const mcp = (Hack.mcpServers && Hack.mcpServers.forAgent(agent)) || [];
    const skills = agent.skills || [];
    if (!mcp.length && !skills.length) return null;
    const groups = [];
    if (skills.length) {
      groups.push(el('div', { class: 'agent-cap-group' }, [
        el('span', { class: 'agent-cap-label muted small', text: 'Skills' }),
        el('div', { class: 'agent-cap-chips' }, skills.map((s) =>
          el('span', { class: 'agent-cap-chip', title: s.description || '', text: s.name || s.id || String(s) }))),
      ]));
    }
    if (mcp.length) {
      groups.push(el('div', { class: 'agent-cap-group' }, [
        el('span', { class: 'agent-cap-label muted small', text: 'MCP servers' }),
        el('div', { class: 'agent-cap-chips' }, mcp.map((s) =>
          el('a', { class: 'agent-cap-chip', href: s.docs || s.url || '#', target: '_blank', rel: 'noopener', title: s.description || '', text: s.name }))),
      ]));
    }
    return el('div', { class: 'agent-capabilities' }, groups);
  }

  /** The full starting prompt an agent is given. */
  function renderAgentPrompt(agent) {
    if (!agent.prompt_text) return null;
    return el('details', { class: 'agent-prompt' }, [
      el('summary', { text: 'Starting prompt' }),
      el('pre', { class: 'agent-prompt-text', text: agent.prompt_text }),
    ]);
  }

  function renderTurn(t) {
    return el('div', { class: 'stream-item kind-thought' }, [
      el('div', { class: 'event-meta' }, [
        el('span', { class: 'event-role', text: t.round ? `Round ${t.round}` : 'Briefing' }),
        el('span', { class: 'event-role', text: t.model || '' }),
        el('span', { class: 'event-time', text: formatTime(t.ts) }),
      ]),
      el('p', { class: 'ideation-idea', text: t.idea }),
      renderJustification(t.justification),
      renderBuild(t.build),
      renderAnalysis(t.analysis),
      renderContext(t.context),
      renderSources(t.sources),
    ]);
  }

  function renderJustification(bullets) {
    if (!bullets || !bullets.length) return null;
    return el('ul', { class: 'ideation-justification' }, bullets.map((b) => el('li', { text: b })));
  }

  function renderContext(context) {
    if (!context) return null;
    return el('details', { class: 'ideation-context' }, [
      el('summary', { text: `Context (${formatCount(context.length)} chars)` }),
      el('p', { class: 'ideation-context-text', text: context }),
    ]);
  }

  function renderSources(sources) {
    if (!sources || !sources.length) return null;
    return el('div', { class: 'ideation-sources' }, sources.slice(0, 8).map((s) =>
      el('a', { class: 'ideation-source', href: s.url, target: '_blank', rel: 'noopener', text: s.title || s.url })));
  }

  function renderScore(score) {
    if (!score || !Object.keys(score).length) return null;
    return el('div', { class: 'ideation-score' }, Object.keys(score).map((k) =>
      el('span', { class: 'ideation-score-chip', text: `${k} ${score[k]}` })));
  }

  /** The Builder's buildability score. */
  function renderBuild(build) {
    if (!build || (build.mvp == null && build.artifact == null)) return null;
    return el('div', { class: 'ideation-build' }, [
      build.mvp != null ? el('span', { class: 'ideation-score-chip', text: `MVP ${build.mvp}/10` }) : null,
      build.artifact != null ? el('span', { class: 'ideation-score-chip', text: `Artifact ${build.artifact}/10` }) : null,
      build.effort ? el('span', { class: 'ideation-score-chip', text: build.effort }) : null,
      ...(build.blockers || []).map((b) => el('span', { class: 'ideation-blocker', text: b })),
    ]);
  }

  /** The Analyzer's verdict on whether the idea makes sense. */
  function renderAnalysis(analysis) {
    if (!analysis || !analysis.verdict) return null;
    const cls = analysis.verdict === 'makes_sense' ? 'ok' : analysis.verdict === 'nonsense' ? 'bad' : 'warn';
    return el('div', { class: 'ideation-analysis' }, [
      el('span', { class: 'ideation-verdict ' + cls, text: String(analysis.verdict).replace(/_/g, ' ') }),
      analysis.confidence != null ? el('span', { class: 'ideation-score-chip', text: `${analysis.confidence}%` }) : null,
      ...(analysis.findings || []).slice(0, 4).map((f) => el('span', { class: 'ideation-finding', text: f })),
      ...(analysis.blockers || []).map((b) => el('span', { class: 'ideation-blocker', text: b })),
    ]);
  }

  /* -------------------------------- events -------------------------------- */
  function renderEvent(ev) {
    switch (ev.kind) {
      case 'phase':
        return el('div', { class: 'phase-divider' }, [el('span', { text: ev.text })]);
      case 'turn':
        return el('div', { class: 'event-row kind-turn' }, [
          el('div', { class: 'event-meta' }, [
            el('span', { class: 'event-role', text: ev.agent_name || ev.agent_id }),
            el('span', { class: 'event-role', text: ev.round ? `Round ${ev.round}` : 'Briefing' }),
            el('span', { class: 'event-time', text: formatTime(ev.ts) }),
          ]),
          el('p', { class: 'ideation-idea', text: ev.idea }),
          renderJustification(ev.justification),
          renderContext(ev.context),
        ]);
      case 'final':
        return el('div', { class: 'event-row kind-final' }, [
          el('div', { class: 'event-meta' }, [
            el('span', { class: 'event-kind', text: 'Final idea' }),
            el('span', { class: 'ideation-kind ' + ev.kind, text: ev.kind }),
          ]),
          el('p', { class: 'ideation-idea', text: ev.idea }),
          renderBuild(ev.build),
          renderAnalysis(ev.analysis),
        ]);
      case 'memory':
        return el('div', { class: 'event-row kind-memory' }, [
          el('span', { class: 'event-kind', text: `Memory · ${ev.kind} · ${ev.importance}` }),
          el('span', { class: 'event-text', text: ' ' + ev.text }),
        ]);
      case 'failed':
        return el('div', { class: 'event-row kind-muted' }, [
          el('span', { class: 'event-text', text: `${ev.agent_id} failed${ev.reason ? ' — ' + ev.reason : ''}` }),
        ]);
      case 'cancelled':
        return el('div', { class: 'event-row kind-muted' }, [
          el('span', { class: 'event-text', text: 'Session terminated by the user.' }),
        ]);
      case 'interrupted':
        return el('div', { class: 'event-row kind-muted' }, [
          el('span', { class: 'event-text', text: ev.reason || 'Session interrupted.' }),
        ]);
      case 'done':
        return el('div', { class: 'event-row kind-done' }, [
          el('span', { class: 'event-text', text: ev.cancelled
            ? 'Session terminated'
            : `Session complete · $${(ev.cost || 0).toFixed(4)}` }),
        ]);
      default:
        return null;
    }
  }

  /* -------------------------------- ideas -------------------------------- */
  /** Hand this idea to the workspace's Idea Evaluation column (column 2). */
  function addIdeaToList(idea) {
    if (!Hack.ideaHandoff) return;
    const ok = Hack.ideaHandoff.push({ text: idea.text, source: 'ideation' });
    if (Hack.actions && Hack.actions.showToast) {
      Hack.actions.showToast(ok
        ? 'Added to Idea Evaluation. Open the workspace to see it.'
        : 'Already waiting in Idea Evaluation.', ok ? 'ok' : 'warn');
    }
  }

  function renderIdeas(host) {
    if (!state.selectedSessionId) {
      host.appendChild(el('p', { class: 'empty', text: 'Select a session to see the ideas it produced.' }));
      return;
    }
    const session = state.sessions.find((s) => s.id === state.selectedSessionId);
    const label = (session && (session.topic_name || session.topic_id)) || state.selectedSessionId;
    host.appendChild(el('p', { class: 'muted small', text: `Ideas from session · ${label}` }));
    if (!state.sessionIdeas.length) {
      host.appendChild(el('p', { class: 'empty', text: 'This session has not produced an idea yet.' }));
      return;
    }
    for (const idea of state.sessionIdeas) {
      host.appendChild(el('div', { class: 'ideation-idea-card' }, [
        el('div', { class: 'ideation-final-head' }, [
          el('span', { class: 'ideation-kind ' + idea.kind, text: idea.kind }),
          idea.artifact_type ? el('span', { class: 'ideation-artifact', text: idea.artifact_type }) : null,
          el('span', { class: 'muted small', text: idea.topic_name || idea.topic_id || '' }),
          el('span', { class: 'spacer' }),
          el('span', { class: 'muted small', text: (idea.created_at || '').replace('T', ' ').slice(0, 19) }),
          el('button', {
            class: 'btn small',
            type: 'button',
            text: 'Add to idea list',
            title: 'Copy this idea into the Idea Evaluation column of the workspace',
            onclick: () => addIdeaToList(idea),
          }),
        ]),
        el('p', { class: 'ideation-idea', text: idea.text }),
        renderJustification(idea.justification),
        renderBuild((idea.score || {}).build),
        renderAnalysis((idea.score || {}).analysis),
        renderSources(idea.sources),
        el('div', { class: 'ideation-tags' }, (idea.tags || []).map((tag) => el('span', { class: 'ideation-tag', text: tag }))),
      ]));
    }
  }

  /* -------------------------------- memory -------------------------------- */
  function renderMemory(host) {
    if (!state.memory.length) {
      host.appendChild(el('p', { class: 'empty', text: 'Nothing remembered yet. Only the very important findings are kept.' }));
      return;
    }
    for (const m of state.memory) {
      host.appendChild(el('div', { class: 'ideation-memory' }, [
        el('div', { class: 'event-meta' }, [
          el('span', { class: 'event-kind', text: m.kind }),
          el('span', { class: 'event-role', text: `importance ${m.importance}` }),
          el('span', { class: 'muted small', text: m.topic_id || '' }),
        ]),
        el('p', { class: 'event-text', text: m.text }),
      ]));
    }
  }

  /* ------------------------------ add topic ------------------------------ */
  function splitList(value) {
    return String(value || '').split(',').map((s) => s.trim()).filter(Boolean);
  }

  function openTopicModal() {
    state.topicModal = { open: true, description: '', draft: null, status: null, busy: false };
    renderTopicModal();
  }

  function closeTopicModal() {
    state.topicModal.open = false;
    renderTopicModal();
  }

  async function draftTopic() {
    const tm = state.topicModal;
    const description = (tm.description || '').trim();
    if (!description) {
      tm.status = { ok: false, text: 'Describe the topic first.' };
      renderTopicModal();
      return;
    }
    tm.busy = true;
    tm.status = null;
    renderTopicModal();
    try {
      const draft = await post('/api/topics/draft', { description });
      tm.draft = {
        name: draft.name || '', description: draft.description || '',
        tags: (draft.tags || []).join(', '), keywords: (draft.keywords || []).join(', '),
      };
      tm.status = { ok: true, text: 'Draft ready — edit anything, then add it.' };
    } catch (e) {
      tm.status = { ok: false, text: 'Could not draft: ' + e.message };
    }
    tm.busy = false;
    renderTopicModal();
  }

  async function addTopic() {
    const tm = state.topicModal;
    const d = tm.draft || {};
    if (!(d.name || '').trim()) {
      tm.status = { ok: false, text: 'A name is required.' };
      renderTopicModal();
      return;
    }
    try {
      await post('/api/topics', {
        name: d.name.trim(),
        description: (d.description || '').trim(),
        tags: splitList(d.tags),
        keywords: splitList(d.keywords),
      });
      closeTopicModal();
      await load();
    } catch (e) {
      tm.status = { ok: false, text: 'Could not add: ' + e.message };
      renderTopicModal();
    }
  }

  function renderTopicModal() {
    const host = document.getElementById('ideation-topic-root');
    if (!host) return;
    clear(host);
    const tm = state.topicModal;
    if (!tm || !tm.open) return;

    const draft = tm.draft;
    const content = el('div', { class: 'settings-content' }, [
      el('div', { class: 'field' }, [
        el('label', { text: 'Describe the topic you want to watch' }),
        el('textarea', {
          class: 'input-prompt', rows: 3,
          placeholder: 'e.g. "new ways to run large models on phones and small devices"',
          value: tm.description,
          oninput: (e) => { tm.description = e.target.value; },
        }),
      ]),
      el('div', { class: 'settings-actions' }, [
        el('button', { class: 'btn primary', type: 'button', text: tm.busy ? 'Drafting…' : 'Draft with AI', disabled: tm.busy, onclick: draftTopic }),
        tm.status ? el('span', { class: 'settings-status ' + (tm.status.ok ? 'ok' : 'err'), text: tm.status.text }) : null,
      ]),
      draft ? el('div', { class: 'settings-section' }, [
        el('h3', { class: 'settings-title', text: 'Topic' }),
        el('div', { class: 'settings-body' }, [
          settingsField('Name', el('input', { class: 'text-input', value: draft.name, oninput: (e) => { draft.name = e.target.value; } })),
          settingsField('Description', el('textarea', { class: 'input-prompt', rows: 2, value: draft.description, oninput: (e) => { draft.description = e.target.value; } })),
          settingsField('Tags (comma-separated)', el('input', { class: 'text-input', value: draft.tags, oninput: (e) => { draft.tags = e.target.value; } })),
          settingsField('Keywords (comma-separated)', el('input', { class: 'text-input', value: draft.keywords, oninput: (e) => { draft.keywords = e.target.value; } })),
        ]),
      ]) : null,
      el('div', { class: 'settings-actions' }, [
        el('button', { class: 'btn primary', type: 'button', text: 'Add topic', disabled: !draft, onclick: addTopic }),
        el('button', { class: 'btn ghost', type: 'button', text: 'Cancel', onclick: closeTopicModal }),
      ]),
    ]);

    const dialog = el('div', { class: 'modal settings-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Add Topic' }),
          el('p', { class: 'muted small', text: 'Describe it; the AI fills in the name, description, tags and keywords.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: closeTopicModal }),
      ]),
      el('div', { class: 'modal-body' }, [content]),
    ]);
    host.appendChild(el('div', { class: 'modal-overlay', onclick: closeTopicModal }, [dialog]));
  }

  /* --------------------------- topic finder popup --------------------------- */
  function openDiscoverModal(topics) {
    state.discoverModal = {
      open: true, topics: topics.slice(),
      selected: new Set(topics.map((t) => t.id)),
      status: null, busy: false,
    };
    renderDiscoverModal();
  }

  function closeDiscoverModal() {
    state.discoverModal.open = false;
    renderDiscoverModal();
  }

  function toggleDiscoverAll(checked) {
    const dm = state.discoverModal;
    dm.selected = checked ? new Set(dm.topics.map((t) => t.id)) : new Set();
    renderDiscoverModal();
  }

  async function addSelectedTopics() {
    const dm = state.discoverModal;
    const chosen = dm.topics.filter((t) => dm.selected.has(t.id));
    if (!chosen.length) {
      dm.status = { ok: false, text: 'Select at least one topic.' };
      renderDiscoverModal();
      return;
    }
    dm.busy = true;
    dm.status = null;
    renderDiscoverModal();
    let added = 0;
    try {
      for (const t of chosen) {
        await post('/api/topics', {
          name: t.name, description: t.description,
          tags: t.tags || [], keywords: t.keywords || [], sources: t.sources || [],
        });
        added += 1;
      }
      closeDiscoverModal();
      if (Hack.actions && Hack.actions.showToast) {
        Hack.actions.showToast(`Added ${added} topic${added === 1 ? '' : 's'}.`, 'ok');
      }
      await load();
    } catch (e) {
      dm.busy = false;
      dm.status = { ok: false, text: `Added ${added} of ${chosen.length} — ${e.message}` };
      renderDiscoverModal();
    }
  }

  function renderDiscoverModal() {
    const host = document.getElementById('ideation-discover-root');
    if (!host) return;
    clear(host);
    const dm = state.discoverModal;
    if (!dm || !dm.open) return;

    const allSelected = dm.topics.length > 0 && dm.selected.size === dm.topics.length;
    const rows = dm.topics.map((t) => el('label', { class: 'discover-topic' }, [
      el('input', {
        type: 'checkbox', checked: dm.selected.has(t.id),
        onchange: (e) => {
          if (e.target.checked) dm.selected.add(t.id); else dm.selected.delete(t.id);
          renderDiscoverModal();
        },
      }),
      el('div', { class: 'discover-topic-body' }, [
        el('div', { class: 'discover-topic-head' }, [
          el('span', { class: 'ideation-topic-name', text: t.name }),
          t.origin === 'finder' ? el('span', { class: 'ideation-origin', text: 'found' }) : null,
        ]),
        t.description ? el('p', { class: 'muted small', text: t.description }) : null,
        t.rationale ? el('p', { class: 'ideation-topic-rationale muted small', text: '↳ ' + t.rationale }) : null,
        el('div', { class: 'ideation-tags' }, (t.tags || []).map((tag) => el('span', { class: 'ideation-tag', text: tag }))),
      ]),
    ]));

    const content = el('div', { class: 'settings-content' }, [
      el('div', { class: 'discover-toolbar' }, [
        el('label', { class: 'discover-select-all' }, [
          el('input', {
            type: 'checkbox', checked: allSelected,
            onchange: (e) => toggleDiscoverAll(e.target.checked),
          }),
          el('span', { text: 'Select all' }),
        ]),
        el('span', { class: 'muted small', text: `${dm.selected.size} of ${dm.topics.length} selected` }),
      ]),
      el('div', { class: 'discover-list' }, rows),
      el('div', { class: 'settings-actions' }, [
        el('button', {
          class: 'btn primary', type: 'button',
          text: dm.busy ? 'Adding…' : `Add selected (${dm.selected.size})`,
          disabled: dm.busy, onclick: addSelectedTopics,
        }),
        el('button', { class: 'btn ghost', type: 'button', text: 'Cancel', disabled: dm.busy, onclick: closeDiscoverModal }),
        dm.status ? el('span', { class: 'settings-status ' + (dm.status.ok ? 'ok' : 'err'), text: dm.status.text }) : null,
      ]),
    ]);

    const dialog = el('div', { class: 'modal settings-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Topics found' }),
          el('p', { class: 'muted small', text: 'Pick the ones to add to the watchlist on the left.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: closeDiscoverModal }),
      ]),
      el('div', { class: 'modal-body' }, [content]),
    ]);
    host.appendChild(el('div', { class: 'modal-overlay', onclick: closeDiscoverModal }, [dialog]));
  }

  /* ------------------------------- settings ------------------------------- */
  function modelSelect(value, onchange) {
    const models = (Hack.modelInfo && Hack.modelInfo.MODELS) || [];
    const ids = models.map((m) => m.id);
    if (value && !ids.includes(value)) ids.unshift(value);
    return el('select', { class: 'select', onchange: (e) => onchange(e.target.value) },
      ids.map((id) => {
        const m = models.find((x) => x.id === id);
        return el('option', { value: id, text: m ? m.name : id, selected: id === value });
      }));
  }

  /** A model dropdown with a "Thinking" toggle beside it. */
  function modelRow(label, model, thinking, onModel, onThinking) {
    return el('div', { class: 'field model-row' }, [
      el('label', { text: label }),
      el('div', { class: 'model-row-controls' }, [
        modelSelect(model, onModel),
        el('label', { class: 'thinking-toggle', title: 'Reasoning / thinking mode' }, [
          el('input', { type: 'checkbox', checked: !!thinking, onchange: (e) => onThinking(e.target.checked) }),
          el('span', { text: 'Thinking' }),
        ]),
      ]),
    ]);
  }

  function settingsSection(title, children) {
    return el('div', { class: 'settings-section' }, [
      el('h3', { class: 'settings-title', text: title }),
      el('div', { class: 'settings-body' }, children),
    ]);
  }

  function settingsField(label, node) {
    return el('div', { class: 'field' }, [el('label', { text: label }), node]);
  }

  function numberField(label, value, oninput, opts) {
    return settingsField(label, el('input', Object.assign({
      type: 'number', class: 'num-input', value,
      oninput: (e) => oninput(Number(e.target.value)),
    }, opts || {})));
  }

  function openSettings() {
    state.settingsOpen = true;
    state.settingsStatus = null;
    renderSettings();
  }

  function closeSettings() {
    state.settingsOpen = false;
    renderSettings();
  }

  async function saveSettings() {
    try {
      const saved = await getJSON('/api/settings', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state.settings),
      });
      state.settings = saved;
      state.settingsStatus = { ok: true, text: 'Saved. Applies to the next session.' };
    } catch (e) {
      state.settingsStatus = { ok: false, text: 'Could not save: ' + e.message };
    }
    renderSettings();
  }

  function renderSettings() {
    const host = document.getElementById('ideation-settings-root');
    if (!host) return;
    clear(host);
    if (!state.settingsOpen || !state.settings) return;
    const s = state.settings;
    s.agent_models = s.agent_models || {};
    s.agent_thinking = s.agent_thinking || {};

    const dialog = el('div', { class: 'modal settings-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Ideation settings' }),
          el('p', { class: 'muted small', text: 'The models the ideation agents use, and how the daemon runs.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: closeSettings }),
      ]),
      el('div', { class: 'modal-body' }, [
        el('div', { class: 'settings-content' }, [
          settingsSection('Models', [
            modelRow('Default model (agents without their own)', s.model, s.thinking,
              (v) => { s.model = v; }, (v) => { s.thinking = v; }),
            ...(s.agents || []).map((a) => el('div', { class: 'agent-config' }, [
              modelRow(a.name + ' — ' + a.role, a.model, a.thinking,
                (v) => { s.agent_models[a.id] = v; }, (v) => { s.agent_thinking[a.id] = v; }),
              renderAgentCapabilities(a),
              renderAgentPrompt(a),
            ])),
            modelRow('Topic drafting model', s.topic_model || s.model, s.topic_thinking,
              (v) => { s.topic_model = v; }, (v) => { s.topic_thinking = v; }),
          ]),
          settingsSection('Topic finder', [
            settingsField('Let the finder add topics on its own',
              el('input', { type: 'checkbox', checked: !!s.discovery_enabled, onchange: (e) => { s.discovery_enabled = e.target.checked; } })),
            numberField('Find topics every (seconds)', s.discovery_interval_seconds,
              (v) => { s.discovery_interval_seconds = v; }, { min: 60 }),
            modelRow('Topic finder model', s.finder_model || s.model, s.finder_thinking,
              (v) => { s.finder_model = v; }, (v) => { s.finder_thinking = v; }),
          ]),
          settingsSection('Related ideas', [
            modelRow('Related-idea model (ideas vaguely related to the topics)',
              s.related_model || s.model, s.related_thinking,
              (v) => { s.related_model = v; }, (v) => { s.related_thinking = v; }),
          ]),
          settingsSection('Daemon', [
            numberField('Poll interval (seconds)', s.poll_interval_seconds,
              (v) => { s.poll_interval_seconds = v; }, { min: 30 }),
            numberField('Cost cap per session (USD)', s.max_cost_usd,
              (v) => { s.max_cost_usd = v; }, { min: 0.01, step: 0.01 }),
            numberField('Refinement rounds', s.rounds,
              (v) => { s.rounds = v; }, { min: 1, max: 5 }),
            numberField('Signals per session', s.signals_per_topic,
              (v) => { s.signals_per_topic = v; }, { min: 1, max: 50 }),
            settingsField('Start the scheduler with the daemon',
              el('input', { type: 'checkbox', checked: !!s.autostart, onchange: (e) => { s.autostart = e.target.checked; } })),
          ]),
          settingsSection('MCP servers', [
            settingsField('Let agents call their MCP servers',
              el('input', { type: 'checkbox', checked: !!s.mcp_enabled, onchange: (e) => { s.mcp_enabled = e.target.checked; } })),
            numberField('Tool calls per agent turn', s.mcp_max_tool_calls,
              (v) => { s.mcp_max_tool_calls = v; }, { min: 0, max: 8 }),
            numberField('Server timeout (seconds)', s.mcp_timeout_seconds,
              (v) => { s.mcp_timeout_seconds = v; }, { min: 1, max: 120 }),
          ]),
          el('div', { class: 'settings-actions' }, [
            el('button', { class: 'btn primary', type: 'button', text: 'Save settings', onclick: saveSettings }),
            state.settingsStatus
              ? el('span', { class: 'settings-status ' + (state.settingsStatus.ok ? 'ok' : 'err'), text: state.settingsStatus.text })
              : null,
          ]),
        ]),
      ]),
    ]);
    host.appendChild(el('div', { class: 'modal-overlay', onclick: closeSettings }, [dialog]));
  }

  /* ------------------------------- controls ------------------------------- */
  const refresh = document.getElementById('ideation-refresh');
  if (refresh) refresh.addEventListener('click', load);
  const poll = document.getElementById('ideation-poll');
  if (poll) poll.addEventListener('click', async () => {
    poll.disabled = true;
    try { await post('/api/poll'); await load(); } catch (e) { /* ignore */ }
    poll.disabled = false;
  });
  const discover = document.getElementById('ideation-discover');
  if (discover) discover.addEventListener('click', discoverTopics);
  const related = document.getElementById('ideation-related');
  if (related) related.addEventListener('click', relatedIdeas);
  const settingsBtn = document.getElementById('ideation-settings');
  if (settingsBtn) settingsBtn.addEventListener('click', openSettings);
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (state.discoverModal.open) closeDiscoverModal();
    else if (state.topicModal.open) closeTopicModal();
    else if (state.settingsOpen) closeSettings();
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', detect);
  else detect();
})();
