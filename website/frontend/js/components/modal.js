/* components/modal.js — large popup for one research run.
 *
 * Two tabs:
 *   Evaluation Swarm — the agent swarm and a streamed summary of what each
 *                      agent is thinking, as the backend emits events. Full
 *                      outputs are one click away (they are not printed whole).
 *   Evaluation       — the finished evaluation report, shaped exactly like
 *                      evaluation-report.schema.json (plus a raw-JSON view).
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, truncate, formatTime } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  const selectedAgentByGroup = {}; // groupId -> agentId whose stream is open
  const stickByKey = {};           // scrollKey -> follow the tail? (default true for streams)
  const expandedThoughts = new Set(); // event keys whose full output is shown
  const SVG_NS = 'http://www.w3.org/2000/svg';

  // Caps so a long run cannot grow the DOM without bound (and lag the page).
  const LOG_MAX_EVENTS = 200;      // cluster log: newest N events
  const STREAM_MAX_ITEMS = 40;     // per-agent stream: newest N outputs
  const STREAM_MAX_CHARS = 24000;  // per-agent stream: newest N characters

  const isTailKey = (key) => key === 'cluster-log' || key === 'complex-log'
    || key.startsWith('agent-stream:') || key.startsWith('complex-stream:');

  /** A stable key for one streamed event, so an expanded thought stays open
   *  across the re-renders that happen as new events arrive. */
  function eventKey(run, ev) {
    return [run.id, ev.kind, ev.groupId || ev.group, ev.agent_id, ev.round, ev.turn, ev.ts].join(':');
  }

  /** A short, readable summary of an agent's output — the first sentence or two,
   *  capped so the swarm stream stays scannable. The full text is one click away. */
  function summarizeThought(text, max) {
    const limit = max || 240;
    const s = String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
    if (s.length <= limit) return { summary: s, truncated: false };
    const slice = s.slice(0, limit);
    const cut = Math.max(slice.lastIndexOf('. '), slice.lastIndexOf('! '), slice.lastIndexOf('? '));
    const summary = cut > limit * 0.5 ? slice.slice(0, cut + 1) : slice.trimEnd() + '…';
    return { summary, truncated: true };
  }

  function toggleThought(key) {
    if (expandedThoughts.has(key)) expandedThoughts.delete(key);
    else expandedThoughts.add(key);
  }

  /** The summarized thought for an event, with a toggle to reveal the full output.
   *  The toggle swaps the two paragraphs in place (no re-render), so expanding an
   *  older thought does not jump the stream to the bottom. */
  function renderThought(run, ev) {
    const key = eventKey(run, ev);
    const expanded = expandedThoughts.has(key);
    const { summary, truncated } = summarizeThought(ev.text);
    if (!truncated) return [el('p', { class: 'event-text', text: summary })];

    const summaryP = el('p', { class: 'event-text', text: summary });
    const fullP = el('p', { class: 'event-text', text: ev.text });
    summaryP.style.display = expanded ? 'none' : '';
    fullP.style.display = expanded ? '' : 'none';
    const btn = el('button', { class: 'thought-toggle', text: expanded ? 'Show summary' : 'Show full output' });
    btn.addEventListener('click', () => {
      const nowExpanded = !expandedThoughts.has(key);
      toggleThought(key);
      summaryP.style.display = nowExpanded ? 'none' : '';
      fullP.style.display = nowExpanded ? '' : 'none';
      btn.textContent = nowExpanded ? 'Show summary' : 'Show full output';
    });
    return [summaryP, fullP, btn];
  }

  function formatCount(n) {
    if (n < 1000) return String(n);
    if (n < 1000000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
  }

  function formatDuration(seconds) {
    if (!seconds) return '0s';
    if (seconds < 60) return seconds.toFixed(1).replace(/\.0$/, '') + 's';
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  }

  /** el() for SVG nodes (document.createElement won't build SVG). */
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
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach((child) => {
        if (child == null || child === false) return;
        node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
      });
    }
    return node;
  }

  function mount(container) {
    root = container;
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && store.state.ui.modal.open) actions.closeModal();
    });
    render();
  }

  function render() {
    if (!root) return;
    const modal = store.state.ui.modal;
    if (!modal.open) { clear(root); return; }
    const run = store.runById(modal.runId);
    if (!run) { clear(root); return; }

    const dialog = el('div', { class: 'modal report-modal', onclick: (e) => e.stopPropagation() }, [
      renderHead(run),
      renderTabs(modal.tab),
      modal.tab === 'cluster' ? renderCluster(run, modal.tab)
        : modal.tab === 'complex' ? renderComplex(run, modal.tab)
        : renderEvaluation(run, modal.tab),
    ]);

    // Remember where each scrollable pane was before we rebuild the DOM.
    const scrolls = {};
    root.querySelectorAll('[data-scroll-key]').forEach((node) => {
      scrolls[node.dataset.scrollKey] = node.scrollTop;
    });

    const overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeModal() }, [dialog]);
    clear(root);
    root.appendChild(overlay);

    // Restore scroll synchronously (reading scrollHeight forces layout) so panes
    // never flash back to the top while events keep streaming in. Tail panes
    // follow the newest output until the user scrolls up; the rest stay pinned.
    dialog.querySelectorAll('[data-scroll-key]').forEach((node) => {
      const key = node.dataset.scrollKey;
      const stick = isTailKey(key) && stickByKey[key] !== false;
      node.scrollTop = stick ? node.scrollHeight : (scrolls[key] || 0);
      node.addEventListener('scroll', () => {
        stickByKey[key] = (node.scrollHeight - node.scrollTop - node.clientHeight) < 48;
      });
    });
  }

  /* ------------------------------- head ------------------------------- */
  function renderHead(run) {
    const statusText = run.status === 'running' ? 'Running' : run.status === 'done' ? 'Complete' : 'Cancelled';
    const report = run.report;
    const agentCount = (run.cluster || []).reduce((n, g) => n + g.agents.length, 0);
    const meta = [];
    if (run.cluster) meta.push(`${run.cluster.length} groups`);
    if (agentCount) meta.push(`${agentCount} agents`);
    if (report && report.pipeline) meta.push(`${report.pipeline.rounds} rounds`);

    return el('div', { class: 'modal-head' }, [
      el('div', { class: 'modal-head-main' }, [
        el('div', { class: 'modal-eyebrow' }, [
          el('span', { class: 'run-status ' + run.status }, [
            run.status === 'running' ? el('span', { class: 'dot-pulse' }) : null,
            statusText,
          ]),
          el('span', { class: 'muted small', text: 'Idea evaluation · ' + (run.model || '') }),
          meta.length ? el('span', { class: 'muted small', text: '· ' + meta.join(' · ') }) : null,
        ]),
        el('h3', { class: 'modal-title', text: truncate(run.ideaText, 200) }),
      ]),
      el('div', { class: 'modal-head-actions' }, [
        run.backendRunId
          ? el('a', {
              class: 'btn small', href: Hack.agentViewUrl(run.backendRunId),
              title: 'Open this run in the full Agent View', text: 'Agent View →',
            })
          : null,
        run.status === 'running'
          ? el('button', { class: 'btn small', text: 'Force stop & finalize', title: 'Stop the swarm now and write the final verdict', onclick: () => actions.forceFinalize(run.id) })
          : null,
        run.status === 'running'
          ? el('button', { class: 'btn small', text: 'Cancel run', title: 'Stop this run', onclick: () => actions.cancelEvaluation(run.id) })
          : null,
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeModal() }),
      ]),
    ]);
  }

  function renderTabs(active) {
    const tabs = [
      { id: 'cluster', label: 'Evaluation Swarm' },
      { id: 'complex', label: 'Evaluation Complex' },
      { id: 'evaluation', label: 'Evaluation' },
    ];
    return el('div', { class: 'modal-tabs' }, tabs.map((t) =>
      el('button', {
        class: 'modal-tab' + (active === t.id ? ' active' : ''),
        text: t.label,
        onclick: () => actions.setModalTab(t.id),
      })
    ));
  }

  /* =========================== Evaluation Swarm =========================== */
  function renderCluster(run, tab) {
    const body = el('div', { class: 'modal-body cluster-body', 'data-scroll-key': 'modal-body:' + tab });

    const chars = run.events.reduce((n, ev) => n + ((ev.text || '').length), 0);
    const elapsed = ((run.finishedAt || Date.now()) - run.startedAt) / 1000;
    body.appendChild(el('div', { class: 'cluster-status-bar' }, [
      el('span', { class: 'muted small', text: 'Click an agent to read its reasoning' }),
      el('span', { class: 'muted small', text: `${run.events.length} events · ${formatCount(chars)} chars · ${formatDuration(elapsed)}` }),
    ]));

    // The agent swarm as a graph — one circle per agent, click to read its stream.
    body.appendChild(renderClusterGraph(run));

    // The streamed activity log (newest events only, so it cannot grow forever).
    const log = el('div', { class: 'thinking-log', 'data-scroll-key': 'cluster-log' });
    const start = Math.max(0, run.events.length - LOG_MAX_EVENTS);
    if (start > 0) {
      log.appendChild(el('div', { class: 'event-row kind-muted', text: `${start} earlier events trimmed to keep this panel fast.` }));
    }
    let lastPhase = null;
    for (let i = start; i < run.events.length; i += 1) {
      const ev = run.events[i];
      if (String(ev.kind || '').startsWith('complex-')) continue;  // the complex has its own tab
      if (ev.phase !== lastPhase) {
        lastPhase = ev.phase;
        log.appendChild(el('div', { class: 'phase-divider' }, [el('span', { text: ev.phase })]));
      }
      log.appendChild(renderEvent(run, ev));
    }

    if (run.status === 'running') {
      log.appendChild(el('div', { class: 'event-row kind-live' }, [
        el('span', { class: 'spinner small' }),
        el('span', { text: `${run.currentPhase}${run.currentAgent ? ' · ' + agentName(run, run.currentAgent) + ' is working…' : '…'}` }),
      ]));
    }

    body.appendChild(log);
    return body;
  }

  /* ------------------------- cluster graph + stream ------------------------- */

  /** Index the streamed events by group and by agent so the graph can look them up. */
  function indexEvents(run) {
    const idx = {};
    const idByName = {};
    for (const g of run.cluster || []) {
      idx[g.id] = { events: [], byAgent: {} };
      idByName[g.name] = g.id;
    }
    for (const ev of run.events) {
      const gid = ev.groupId || idByName[ev.group];
      const bucket = gid && idx[gid];
      if (!bucket) continue;
      bucket.events.push(ev);
      if (ev.agent_id) (bucket.byAgent[ev.agent_id] = bucket.byAgent[ev.agent_id] || []).push(ev);
    }
    return idx;
  }

  function renderClusterGraph(run) {
    const groups = run.cluster || [];
    if (!groups.length) {
      return el('div', { class: 'empty-state small' }, [el('p', { class: 'muted', text: 'No cluster yet.' })]);
    }
    const idx = indexEvents(run);
    const empty = { events: [], byAgent: {} };
    return el('div', { class: 'cluster-graph' }, groups.map((g) => renderGroupBlock(run, g, idx[g.id] || empty)));
  }

  function renderGroupBlock(run, group, bucket) {
    const agents = group.agents || [];
    const selectedId = selectedAgentByGroup[group.id] || (agents[0] && agents[0].id);
    const selected = agents.find((a) => a.id === selectedId) || agents[0] || null;
    const agentEvents = selected ? (bucket.byAgent[selected.id] || []) : [];

    return el('div', { class: 'cluster-group-block' }, [
      el('div', { class: 'cluster-group-head' }, [
        el('span', { class: 'cluster-group-name', text: group.name }),
        el('span', { class: 'cluster-style', text: group.style }),
        el('span', { class: 'muted small', text: `${agents.length} agents` }),
      ]),
      el('div', { class: 'cluster-graph-wrap' }, [
        renderGroupGraph(run, group, bucket, selectedId),
        renderAgentStream(run, group, selected, agentEvents),
      ]),
    ]);
  }

  /** One circle per agent, arranged on a ring, with names beside them and
   *  edges between everyone. Clicking a circle opens that agent's stream. */
  function renderGroupGraph(run, group, bucket, selectedId, liveId) {
    const agents = group.agents || [];
    const n = agents.length;
    const W = 580, H = 300, cx = W / 2, cy = H / 2, R = 84, r = 22;
    const nodes = agents.map((a, i) => {
      const ang = (-90 + (360 / Math.max(n, 1)) * i) * (Math.PI / 180);
      return { agent: a, ang, x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) };
    });
    const spoken = (id) => (bucket.byAgent[id] || []).some((ev) => ev.kind === 'turn' || ev.kind === 'evaluation' || ev.kind === 'complex-turn');

    // Edges: everyone can hear everyone. Solid once both ends have spoken.
    const edges = [];
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i], b = nodes[j];
        const touchesSelected = a.agent.id === selectedId || b.agent.id === selectedId;
        const bothSpoken = spoken(a.agent.id) && spoken(b.agent.id);
        const cls = 'graph-edge' + (touchesSelected ? ' selected' : bothSpoken ? ' spoken' : '');
        edges.push(svg('line', { class: cls, x1: a.x, y1: a.y, x2: b.x, y2: b.y }));
      }
    }

    const nodeEls = nodes.map((node) => {
      const a = node.agent;
      const isSelected = a.id === selectedId;
      const isLive = run.status === 'running' && (liveId || run.currentAgent) === a.id;
      const cls = 'graph-node' + (isSelected ? ' selected' : '') + (isLive ? ' live' : '') + (spoken(a.id) ? ' spoken' : '');
      const label = labelPlacement(node, r, a.name);
      return svg('g', { class: cls, onclick: () => selectAgent(group.id, a.id) }, [
        isLive ? svg('circle', { class: 'node-ring', cx: node.x, cy: node.y, r: r + 5 }) : null,
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

  /** Wrap a name to at most two short lines so it stays beside its circle. */
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

  /** Put the name label outside the ring, on the side the node sits. */
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

  function selectAgent(groupId, agentId) {
    selectedAgentByGroup[groupId] = agentId;
    store.notify();
  }

  /** The selected agent's full reasoning, streamed to the right of the graph. */
  function renderAgentStream(run, group, agent, agentEvents) {
    if (!agent) {
      return el('div', { class: 'agent-stream empty-state small' }, [el('p', { class: 'muted', text: 'No agents in this group.' })]);
    }

    const items = agentEvents.filter((ev) => ev.kind === 'turn' || ev.kind === 'evaluation' || ev.kind === 'missed' || ev.kind === 'failed');
    const chars = items.reduce((n, ev) => n + ((ev.text || '').length), 0);
    const seconds = items.reduce((n, ev) => n + (ev.elapsed_seconds || 0), 0);

    const head = el('div', { class: 'agent-stream-head' }, [
      el('div', { class: 'agent-stream-name', text: agent.name }),
      el('div', { class: 'agent-stream-model', text: agent.model || '' }),
      el('div', { class: 'agent-stream-stats muted small', text: `${items.length} outputs · ${formatCount(chars)} chars · ${formatDuration(seconds)}` }),
    ]);
    const about = el('div', { class: 'agent-stream-about' }, [
      agent.question ? el('p', { class: 'cluster-agent-q', text: agent.question }) : null,
      agent.who_they_are ? el('p', { class: 'cluster-agent-who muted small', text: agent.who_they_are }) : null,
    ]);

    const body = el('div', { class: 'agent-stream-body', 'data-scroll-key': 'agent-stream:' + group.id });
    if (!items.length) {
      body.appendChild(el('p', { class: 'muted small', text: run.status === 'running' ? 'Nothing yet — this agent has not spoken.' : 'This agent produced no output.' }));
    } else {
      const { kept, trimmed } = windowItems(items);
      if (trimmed) {
        body.appendChild(el('p', { class: 'muted small', text: `${trimmed} older output${trimmed === 1 ? '' : 's'} trimmed to keep this panel fast.` }));
      }
      kept.forEach((ev) => body.appendChild(renderAgentEvent(run, ev)));
    }

    return el('div', { class: 'agent-stream' }, [head, about, body]);
  }

  /** Keep only the newest outputs that fit the caps, so the panel stays bounded. */
  function windowItems(items) {
    const kept = [];
    let chars = 0;
    for (let i = items.length - 1; i >= 0; i -= 1) {
      const len = (items[i].text || '').length;
      if (kept.length >= STREAM_MAX_ITEMS || (kept.length && chars + len > STREAM_MAX_CHARS)) break;
      kept.push(items[i]);
      chars += len;
    }
    kept.reverse();
    return { kept, trimmed: items.length - kept.length };
  }

  function renderAgentEvent(run, ev) {
    if (ev.kind === 'turn') {
      return el('div', { class: 'stream-item kind-thought' }, [
        el('div', { class: 'event-meta' }, [
          el('span', { class: 'event-role', text: `Round ${ev.round}` }),
          el('span', { class: 'event-role', text: `turn ${ev.turn}` }),
          ev.elapsed_seconds != null ? el('span', { class: 'event-role', text: `${ev.elapsed_seconds}s` }) : null,
          el('span', { class: 'event-time', text: formatTime(ev.ts) }),
        ]),
        ...renderThought(run, ev),
      ]);
    }
    if (ev.kind === 'evaluation') {
      return el('div', { class: 'stream-item kind-evaluation' }, [
        el('div', { class: 'event-meta' }, [
          el('span', { class: 'event-role', text: `Round ${ev.round}` }),
          el('span', { class: 'event-kind', text: 'evaluation' }),
          ev.complete === false ? el('span', { class: 'event-role warn', text: 'incomplete' }) : null,
          el('span', { class: 'event-time', text: formatTime(ev.ts) }),
        ]),
        renderVerdictLine(ev),
        renderScoreChips(ev.template_scores),
        renderRoleScores(ev.role_scores),
        ...renderThought(run, ev),
      ]);
    }
    return el('div', { class: 'stream-item kind-muted' }, [
      el('p', { class: 'event-text', text: `${ev.kind === 'missed' ? 'Missed this turn' : 'Evaluation failed'}${ev.reason ? ' — ' + ev.reason : ''}` }),
    ]);
  }

  function renderEvent(run, ev) {
    switch (ev.kind) {
      case 'phase':
        return el('div', { class: 'event-row kind-phase', text: ev.text });
      case 'cluster':
        return el('div', { class: 'event-row kind-phase', text: ev.text });
      case 'group-start':
        return el('div', { class: 'group-divider' }, [
          el('span', { text: ev.group }),
          el('span', { class: 'cluster-style', text: ev.style || '' }),
        ]);
      case 'round-start':
        return el('div', { class: 'round-divider', text: ev.text });
      case 'missed':
        return el('div', { class: 'event-row kind-muted', text: `${agentName(run, ev.agent_id)} missed this turn — ${ev.reason}` });
      case 'failed':
        return el('div', { class: 'event-row kind-muted', text: `${agentName(run, ev.agent_id)} evaluation failed — ${ev.reason}` });
      case 'turn':
        return el('div', { class: 'event-row kind-thought' }, [
          el('div', { class: 'event-meta' }, [
            el('span', { class: 'event-agent', text: agentName(run, ev.agent_id) }),
            el('span', { class: 'event-role', text: ev.model || '' }),
            el('span', { class: 'event-role', text: `turn ${ev.turn}` }),
            ev.elapsed_seconds != null ? el('span', { class: 'event-role', text: `${ev.elapsed_seconds}s` }) : null,
            el('span', { class: 'event-time', text: formatTime(ev.ts) }),
          ]),
          ...renderThought(run, ev),
        ]);
      case 'evaluation':
        return el('div', { class: 'event-row kind-evaluation' }, [
          el('div', { class: 'event-meta' }, [
            el('span', { class: 'event-agent', text: agentName(run, ev.agent_id) }),
            el('span', { class: 'event-role', text: ev.model || '' }),
            el('span', { class: 'event-kind', text: 'evaluation' }),
            ev.complete === false ? el('span', { class: 'event-role warn', text: 'incomplete' }) : null,
            el('span', { class: 'event-time', text: formatTime(ev.ts) }),
          ]),
          renderVerdictLine(ev),
          renderScoreChips(ev.template_scores),
          renderRoleScores(ev.role_scores),
          ...renderThought(run, ev),
        ]);
      case 'summary':
        return el('div', { class: 'event-row kind-summary' }, [
          el('div', { class: 'event-meta' }, [
            el('span', { class: 'event-group', text: ev.group }),
            el('span', { class: 'event-kind', text: `summary · round ${ev.round}` }),
          ]),
          renderSummary(ev.summary),
        ]);
      case 'cross-group':
        return el('div', { class: 'event-row kind-decision' }, [
          el('span', { class: 'event-kind', text: 'Cross-group analysis' }),
          renderCrossGroup(ev.cross_group),
        ]);
      case 'reality-check':
        return el('div', { class: 'event-row kind-decision' }, [
          el('span', { class: 'event-kind', text: 'Reality check' }),
          renderRealityCheck(ev.reality_check),
        ]);
      case 'stop-go':
        return el('div', { class: 'event-row kind-decision' }, [
          el('span', { class: 'event-kind', text: 'Stop-or-Go' }),
          renderStopGo(ev.stop_go),
        ]);
      case 'verdict':
        return el('div', { class: 'event-row kind-conclusion' }, [
          el('span', { class: 'event-kind', text: 'Verdict' }),
          renderVerdict(ev.verdict),
        ]);
      case 'complex-cluster':
        return el('div', { class: 'event-row kind-phase', text: ev.text });
      case 'complex-turn':
        return el('div', { class: 'event-row kind-evaluation' }, [
          el('div', { class: 'event-meta' }, [
            el('span', { class: 'event-agent', text: ev.name || ev.agent_id }),
            el('span', { class: 'event-role', text: ev.model || '' }),
            ev.decision ? el('span', { class: 'complex-vote ' + (ev.decision === 'stop' ? 'stop' : 'go'), text: ev.decision }) : null,
            ev.confidence != null ? el('span', { class: 'event-role', text: ev.confidence + '%' }) : null,
            el('span', { class: 'event-time', text: formatTime(ev.ts) }),
          ]),
          ...renderThought(run, ev),
        ]);
      case 'complex-verdict':
        return el('div', { class: 'event-row kind-decision' }, [
          el('span', { class: 'event-kind', text: `Complex vote · round ${ev.round}` }),
          renderComplexVerdict(run, ev),
        ]);
      case 'complex-stop':
        return el('div', { class: 'event-row kind-decision' }, [
          el('span', { class: 'event-kind', text: 'Complex stop' }),
          el('p', { class: 'event-text', text: ev.reason || '' }),
        ]);
      case 'complex-final':
        return el('div', { class: 'event-row kind-conclusion' }, [
          el('span', { class: 'event-kind', text: 'Complex report' }),
          el('p', { class: 'event-text', text: `Decision: ${(ev.report && ev.report.decision) || '—'}${ev.report && ev.report.stopped_by ? ' (stopped by ' + ev.report.stopped_by + ')' : ''}` }),
        ]);
      default:
        return el('div', { class: 'event-row', text: ev.text || ev.kind });
    }
  }

  /* ========================= Evaluation Complex ========================= */
  /** The Evaluation Complex: three stewards that watch the swarm in parallel and vote continue or stop. Shown
   *  like the swarm: one circle per steward, click to read its reasoning, with the votes streamed below. */
  function renderComplex(run, tab) {
    const body = el('div', { class: 'modal-body cluster-body', 'data-scroll-key': 'modal-body:' + tab });
    const cx = run.complex;
    if (!cx || !(cx.agents || []).length) {
      body.appendChild(el('div', { class: 'empty-state small' }, [
        el('p', { class: 'muted', text: 'The Evaluation Complex is not running for this evaluation.' }),
      ]));
      return body;
    }
    const cxEvents = run.events.filter((ev) => String(ev.kind || '').startsWith('complex-'));
    const elapsed = ((run.finishedAt || Date.now()) - run.startedAt) / 1000;
    body.appendChild(el('div', { class: 'cluster-status-bar' }, [
      el('span', { class: 'muted small', text: 'Three stewards watch the swarm in parallel and vote continue or stop. Click one to read its reasoning.' }),
      el('span', { class: 'muted small', text: `${cxEvents.length} events · ${formatDuration(elapsed)}` }),
    ]));
    body.appendChild(renderComplexBanner(run, cx));
    body.appendChild(renderComplexGraph(run, cx, cxEvents));
    if (run.status === 'running') {
      body.appendChild(el('div', { class: 'complex-actions' }, [
        el('button', { class: 'btn small', title: 'Stop the swarm now and write the final verdict', text: 'Force stop & finalize', onclick: () => actions.forceFinalize(run.id) }),
      ]));
    }
    const log = el('div', { class: 'thinking-log', 'data-scroll-key': 'complex-log' });
    if (!cxEvents.length) {
      log.appendChild(el('div', { class: 'event-row kind-muted', text: run.status === 'running' ? 'The stewards have not assessed yet.' : 'The stewards produced no output.' }));
    }
    cxEvents.forEach((ev) => log.appendChild(renderEvent(run, ev)));
    if (run.status === 'running') {
      log.appendChild(el('div', { class: 'event-row kind-live' }, [
        el('span', { class: 'spinner small' }),
        el('span', { text: 'The stewards are watching the swarm…' }),
      ]));
    }
    body.appendChild(log);
    return body;
  }

  function renderComplexBanner(run, cx) {
    const d = cx.decision;
    const cls = d === 'stop' ? 'stopped' : d === 'continue' ? 'extra' : 'hold';
    const label = d === 'stop' ? 'Stop' : d === 'continue' ? 'Continue' : (run.status === 'running' ? 'Watching…' : 'No decision');
    const note = cx.stoppedBy ? `stopped by ${cx.stoppedBy}` : (run.status === 'running' ? 'the swarm is still running' : '');
    const stewards = (cx.report && cx.report.stewards) || cx.agents;
    return el('div', { class: 'decision-banner ' + cls }, [
      el('div', { class: 'decision-head' }, [
        el('span', { class: 'decision-label', text: 'Evaluation Complex' }),
        el('span', { class: 'decision-value', text: label }),
        note ? el('span', { class: 'decision-confidence', text: note }) : null,
      ]),
      el('div', { class: 'complex-votes' }, stewards.map((s) => el('div', { class: 'complex-vote-row' }, [
        el('span', { class: 'complex-vote-name', text: s.name }),
        el('span', { class: 'complex-vote ' + (s.decision === 'stop' ? 'stop' : s.decision === 'continue' ? 'go' : ''), text: s.decision || '—' }),
        el('span', { class: 'muted small', text: s.reason || s.objective || '' }),
      ]))),
    ]);
  }

  function renderComplexGraph(run, cx, cxEvents) {
    const bucket = { events: cxEvents, byAgent: {} };
    cxEvents.forEach((ev) => { if (ev.agent_id) (bucket.byAgent[ev.agent_id] = bucket.byAgent[ev.agent_id] || []).push(ev); });
    const group = { id: 'complex', name: 'Evaluation Complex', agents: cx.agents };
    const selectedId = selectedAgentByGroup['complex'] || (cx.agents[0] && cx.agents[0].id);
    const selected = cx.agents.find((a) => a.id === selectedId) || cx.agents[0] || null;
    const lastTurn = [...cxEvents].reverse().find((ev) => ev.kind === 'complex-turn');
    const liveId = run.status === 'running' && lastTurn ? lastTurn.agent_id : '';
    return el('div', { class: 'cluster-group-block' }, [
      el('div', { class: 'cluster-group-head' }, [
        el('span', { class: 'cluster-group-name', text: 'Evaluation Complex' }),
        el('span', { class: 'cluster-style', text: 'parallel' }),
        el('span', { class: 'muted small', text: `${cx.agents.length} stewards` }),
      ]),
      el('div', { class: 'cluster-graph-wrap' }, [
        renderGroupGraph(run, group, bucket, selectedId, liveId),
        renderComplexStream(run, selected, selected ? (bucket.byAgent[selected.id] || []) : []),
      ]),
    ]);
  }

  function renderComplexStream(run, agent, agentEvents) {
    if (!agent) return el('div', { class: 'agent-stream empty-state small' }, [el('p', { class: 'muted', text: 'No stewards.' })]);
    const items = agentEvents.filter((ev) => ev.kind === 'complex-turn');
    const chars = items.reduce((n, ev) => n + ((ev.text || '').length), 0);
    const head = el('div', { class: 'agent-stream-head' }, [
      el('div', { class: 'agent-stream-name', text: agent.name }),
      el('div', { class: 'agent-stream-model', text: agent.model || '' }),
      el('div', { class: 'agent-stream-stats muted small', text: `${items.length} assessment${items.length === 1 ? '' : 's'} · ${formatCount(chars)} chars` }),
    ]);
    const about = el('div', { class: 'agent-stream-about' }, [
      agent.objective ? el('p', { class: 'cluster-agent-q', text: agent.objective }) : null,
    ]);
    const body = el('div', { class: 'agent-stream-body', 'data-scroll-key': 'complex-stream:' + agent.id });
    if (!items.length) {
      body.appendChild(el('p', { class: 'muted small', text: run.status === 'running' ? 'Nothing yet — this steward has not voted.' : 'This steward produced no output.' }));
    } else {
      items.forEach((ev) => body.appendChild(renderComplexTurn(run, ev)));
    }
    return el('div', { class: 'agent-stream' }, [head, about, body]);
  }

  function renderComplexTurn(run, ev) {
    return el('div', { class: 'stream-item kind-evaluation' }, [
      el('div', { class: 'event-meta' }, [
        el('span', { class: 'event-role', text: `assessment ${ev.round}` }),
        ev.decision ? el('span', { class: 'complex-vote ' + (ev.decision === 'stop' ? 'stop' : 'go'), text: ev.decision }) : null,
        ev.confidence != null ? el('span', { class: 'event-role', text: ev.confidence + '%' }) : null,
        el('span', { class: 'event-time', text: formatTime(ev.ts) }),
      ]),
      ...renderThought(run, ev),
      ev.signals && ev.signals.length ? el('ul', { class: 'complex-signals' }, ev.signals.map((s) => el('li', { text: s }))) : null,
    ]);
  }

  function complexName(run, id) {
    const a = ((run.complex && run.complex.agents) || []).find((x) => x.id === id);
    return a ? a.name : id;
  }

  function renderComplexVerdict(run, ev) {
    return el('div', { class: 'complex-verdict' }, [
      ev.rationale ? el('p', { class: 'event-text', text: ev.rationale }) : null,
      el('div', { class: 'complex-votes' }, Object.keys(ev.stewards || {}).map((id) => {
        const s = ev.stewards[id] || {};
        return el('div', { class: 'complex-vote-row' }, [
          el('span', { class: 'complex-vote-name', text: complexName(run, id) }),
          el('span', { class: 'complex-vote ' + (s.decision === 'stop' ? 'stop' : 'go'), text: s.decision || '—' }),
          el('span', { class: 'muted small', text: s.reason || '' }),
        ]);
      })),
    ]);
  }

  /* ============================== Evaluation ============================== */
  function renderEvaluation(run, tab) {
    const body = el('div', { class: 'modal-body results', 'data-scroll-key': 'modal-body:' + tab });
    const report = run.report;

    if (!report) {
      body.appendChild(el('div', { class: 'empty-state' }, [el('p', { text: 'No report yet.' })]));
      return body;
    }

    if (run.status === 'running') {
      body.appendChild(el('div', { class: 'empty-state small' }, [
        el('div', { class: 'spinner' }),
        el('p', { text: 'Deliberation in progress.' }),
        el('p', { class: 'muted', text: 'The evaluation report appears here when the run finishes. Switch to “Evaluation Swarm” to watch it live.' }),
      ]));
      return body;
    }

    // Run header.
    body.appendChild(renderRunMeta(report.run, report.pipeline));

    // Reality check (ran before the groups: does the idea make sense at all?).
    if (report.reality_check) body.appendChild(renderRealityCheck(report.reality_check));

    // Stop-or-go banner.
    if (report.stop_go) body.appendChild(renderStopGoBanner(report.stop_go));

    // Evaluation Complex (three stewards that watched the swarm in parallel).
    if (report.complex) body.appendChild(renderComplexReport(report.complex));

    // Final report (the comprehensive verdict written for the submitter).
    if (report.verdict) body.appendChild(renderFinalReport(report.verdict));
    if (report.sources && (report.sources.papers || []).length) body.appendChild(renderSources(report.sources));

    // Cross-group.
    if (report.cross_group) body.appendChild(renderCrossGroupBlock(report.cross_group));

    // Per-group cards.
    (report.groups || []).forEach((g) => body.appendChild(renderGroupCard(g)));

    // AGNTCY + analysis.
    if (report.agntcy) body.appendChild(renderAgntcy(report.agntcy));
    if (report.analysis) body.appendChild(renderAnalysis(report.analysis));

    // Raw JSON.
    body.appendChild(el('details', { class: 'raw-json' }, [
      el('summary', { text: 'Raw JSON (evaluation-report.schema.json)' }),
      el('pre', { class: 'raw-json-pre', text: JSON.stringify(report, null, 2) }),
    ]));

    return body;
  }

  function renderRunMeta(run, pipeline) {
    const rows = [
      ['Run id', run.id],
      ['Idea', run.idea],
      ['Status', run.status],
      ['Duration', run.duration_seconds != null ? run.duration_seconds + 's' : '—'],
      ['Cost', run.cost_usd != null ? '$' + run.cost_usd : '—'],
      ['LLM calls', run.llm_calls != null ? String(run.llm_calls) : '—'],
      ['Max cost', run.max_cost_usd != null ? '$' + run.max_cost_usd : '—'],
      ['Pipeline', pipeline ? `${pipeline.rounds} rounds · extra round ${pipeline.extra_round ? 'yes' : 'no'} · stop-or-go ${pipeline.stop_go_decision || '—'}` : '—'],
    ];
    return el('div', { class: 'meta-table' }, rows.map(([k, v]) =>
      el('div', { class: 'meta-row' }, [
        el('span', { class: 'meta-key', text: k }),
        el('span', { class: 'meta-val', text: String(v) }),
      ])
    ));
  }

  /* Stop-or-go is about the deliberation (keep talking or not), not about the idea: the idea's verdict is
   * the "Final verdict" block. Neutral colours so STOP doesn't read as "rejected". */
  function deliberationOutcome(sg) {
    if (!sg) return null;
    if (!sg.consensus_feasible && sg.decision === 'go') return { cls: 'kept', value: 'Extra round, disagreement kept', note: 'Ran one more round; the groups still cannot converge, so a person should decide.' };
    if (!sg.consensus_feasible) return { cls: 'kept', value: 'Disagreement kept', note: 'The groups cannot converge, so a person should decide.' };
    if (sg.decision === 'go') return { cls: 'extra', value: 'Extra round', note: 'Ran one more round to settle an open question, then finished.' };
    return { cls: 'stopped', value: 'Stopped', note: 'The evidence was enough to conclude.' };
  }
  Hack.deliberationOutcome = deliberationOutcome;

  /* The reality check runs before the groups: does the idea make sense in the real world at all? */
  function renderRealityCheck(rc) {
    const cls = rc.verdict === 'nonsense' ? 'nonsense' : rc.verdict === 'questionable' ? 'questionable' : 'grounded';
    const label = rc.verdict === 'nonsense' ? 'Does not make sense' : rc.verdict === 'questionable' ? 'Questionable' : 'Makes sense';
    const meta = [
      rc.category && rc.category !== 'none' ? rc.category.replace(/_/g, ' ') : '',
      rc.confidence != null ? rc.confidence + '% confident' : '',
    ].filter(Boolean).join(' · ');
    const blockers = rc.blockers || [];
    const assumptions = rc.assumptions || [];
    return el('div', { class: 'reality-banner ' + cls }, [
      el('div', { class: 'decision-head' }, [
        el('span', { class: 'decision-label', text: 'Reality check' }),
        el('span', { class: 'decision-value', text: label }),
        meta ? el('span', { class: 'decision-confidence', text: meta }) : null,
      ]),
      rc.summary ? el('p', { class: 'decision-rationale', text: rc.summary }) : null,
      blockers.length || assumptions.length ? el('div', { class: 'decision-cols' }, [
        el('div', { class: 'decision-col' }, [el('h4', { text: 'Real-world blockers' }), el('ul', {}, blockers.map((b) => el('li', { text: b })))]),
        el('div', { class: 'decision-col' }, [el('h4', { text: 'Assumptions that may be false' }), el('ul', {}, assumptions.map((a) => el('li', { text: a })))]),
      ]) : null,
    ]);
  }

  function renderStopGoBanner(sg) {
    const o = deliberationOutcome(sg);
    return el('div', { class: 'decision-banner ' + o.cls }, [
      el('div', { class: 'decision-head' }, [
        el('span', { class: 'decision-label', text: 'Deliberation' }),
        el('span', { class: 'decision-value', text: o.value }),
        el('span', { class: 'decision-confidence', text: o.note }),
      ]),
      sg.rationale ? el('p', { class: 'decision-rationale', text: sg.rationale }) : null,
      el('div', { class: 'decision-cols' }, [
        el('div', { class: 'decision-col' }, [el('h4', { text: 'Pros' }), el('ul', {}, (sg.pros || []).map((p) => el('li', { text: p })))]),
        el('div', { class: 'decision-col' }, [el('h4', { text: 'Cons' }), el('ul', {}, (sg.cons || []).map((c) => el('li', { text: c })))]),
      ]),
      sg.resolve_next ? el('p', { class: 'muted small', text: 'Extra round had to settle: ' + sg.resolve_next }) : null,
    ]);
  }

  /* The Evaluation Complex: three stewards that watched the swarm in parallel and voted continue or stop. */
  function renderComplexReport(cx) {
    if (!cx) return null;
    const d = cx.decision;
    const cls = d === 'stop' ? 'stopped' : d === 'continue' ? 'extra' : 'hold';
    const label = d === 'stop' ? 'Stop' : d === 'continue' ? 'Continue' : 'No decision';
    return el('div', { class: 'decision-banner ' + cls }, [
      el('div', { class: 'decision-head' }, [
        el('span', { class: 'decision-label', text: 'Evaluation Complex' }),
        el('span', { class: 'decision-value', text: label }),
        el('span', { class: 'decision-confidence', text: `${cx.rounds || 0} assessment(s)${cx.stopped_by ? ' · stopped by ' + cx.stopped_by : ''}` }),
      ]),
      el('div', { class: 'complex-votes' }, (cx.stewards || []).map((s) => el('div', { class: 'complex-vote-row' }, [
        el('span', { class: 'complex-vote-name', text: s.name }),
        el('span', { class: 'complex-vote ' + (s.decision === 'stop' ? 'stop' : s.decision === 'continue' ? 'go' : ''), text: s.decision || '—' }),
        el('span', { class: 'muted small', text: s.reason || '' }),
      ]))),
    ]);
  }

  /* arXiv papers the research and business groups were given; citations were checked against this list. */
  function renderSources(src) {
    const unknown = src.unknown_citations || [];
    return el('div', { class: 'conclusion' }, [
      el('h4', { text: `arXiv sources (${src.papers.length}) · used by ${(src.used_by_groups || []).join(', ')}` }),
      el('ul', {}, src.papers.map((p) => el('li', {}, [
        el('a', { href: p.url, target: '_blank', text: 'arXiv:' + p.id }),
        ` ${p.title} (${p.year})`,
        p.cited_by && p.cited_by.length ? el('span', { class: 'muted small', text: ` · cited by ${p.cited_by.join(', ')}` }) : null,
      ]))),
      unknown.length ? el('p', { class: 'muted small', text: `Citations not in the list (possibly invented): ${unknown.map((u) => u.agent_id + ' → ' + u.id).join(', ')}` }) : null,
    ]);
  }

  function renderVerdictBlock(title, v) {
    return el('div', { class: 'conclusion' }, [
      el('h4', { text: title }),
      v.headline ? el('p', { class: 'verdict-headline', text: v.headline }) : null,
      v.conclusion ? el('p', { text: v.conclusion }) : null,
      v.findings && v.findings.length ? el('div', {}, [
        el('h5', { class: 'sub-head', text: 'Findings' }),
        el('ul', {}, v.findings.map((f) => el('li', { text: f }))),
      ]) : null,
      v.pros && v.pros.length ? el('div', { class: 'pros-cons' }, [
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Pros' }), el('ul', {}, v.pros.map((p) => el('li', { text: p })))]),
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Cons' }), el('ul', {}, (v.cons || []).map((c) => el('li', { text: c })))]),
      ]) : null,
      renderScoreChips(v.scores),
    ]);
  }

  /* The final report: the comprehensive verdict written for the person who submitted the idea. It carries the
   * executive summary, the case for and against, an ordered plan with kill criteria, risks and open questions. */
  function renderFinalReport(v) {
    if (!v) return null;
    const rec = v.recommendation;
    const recCls = rec === 'Go' ? 'go' : rec === 'No-go' ? 'stop' : rec === 'Hold' ? 'hold' : 'extra';
    const paras = String(v.summary || '').split(/\n\s*\n/).map((s) => s.trim()).filter(Boolean);
    const plan = v.plan || [];
    const risks = v.risks || [];
    return el('div', { class: 'final-report' }, [
      el('div', { class: 'decision-head' }, [
        el('span', { class: 'decision-label', text: 'Final report' }),
        rec ? el('span', { class: 'decision-value', text: rec }) : null,
      ]),
      v.headline ? el('p', { class: 'verdict-headline', text: v.headline }) : null,
      v.the_idea ? el('p', { class: 'muted small', text: 'Idea as evaluated: ' + v.the_idea }) : null,
      ...paras.map((p) => el('p', { class: 'report-para', text: p })),
      (v.case_for || []).length || (v.case_against || []).length ? el('div', { class: 'pros-cons' }, [
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Case for' }), el('ul', {}, (v.case_for || []).map((x) => el('li', { text: x })))]),
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Case against' }), el('ul', {}, (v.case_against || []).map((x) => el('li', { text: x })))]),
      ]) : null,
      plan.length ? el('div', {}, [
        el('h5', { class: 'sub-head', text: 'Plan' }),
        el('ol', { class: 'plan-list' }, plan.map((s) => el('li', {}, [
          el('span', { class: 'plan-title', text: s.title || '' }),
          s.detail ? el('p', { class: 'plan-detail', text: s.detail }) : null,
          [s.timeframe, s.cost, s.owner].filter(Boolean).length
            ? el('p', { class: 'muted small', text: [s.timeframe, s.cost, s.owner].filter(Boolean).join(' · ') }) : null,
        ]))),
      ]) : null,
      (v.kill_criteria || []).length ? el('div', {}, [
        el('h5', { class: 'sub-head', text: 'Kill criteria' }),
        el('ul', {}, v.kill_criteria.map((x) => el('li', { text: x }))),
      ]) : null,
      risks.length ? el('div', {}, [
        el('h5', { class: 'sub-head', text: 'Risks' }),
        el('ul', { class: 'risk-list' }, risks.map((r) => el('li', {}, [
          r.severity ? el('span', { class: 'risk-sev ' + r.severity, text: r.severity.toUpperCase() }) : null,
          el('span', { text: (r.severity ? ' ' : '') + (r.risk || '') }),
          r.mitigation ? el('span', { class: 'muted', text: ' Mitigation: ' + r.mitigation }) : null,
        ]))),
      ]) : null,
      (v.open_questions || []).length ? el('div', {}, [
        el('h5', { class: 'sub-head', text: 'Open questions' }),
        el('ul', {}, v.open_questions.map((x) => el('li', { text: x }))),
      ]) : null,
      v.what_would_change_the_verdict ? el('p', { class: 'muted small', text: 'What would change this verdict: ' + v.what_would_change_the_verdict }) : null,
      renderScoreChips(v.scores),
    ]);
  }

  function renderCrossGroupBlock(cg) {
    return el('div', { class: 'result-group' }, [
      el('div', { class: 'result-group-head' }, [el('h4', { text: 'Cross-group' })]),
      el('h5', { class: 'sub-head', text: 'Disagreements' }),
      ...(cg.disagreements || []).map((d) => renderDisagreement(d, true)),
      el('h5', { class: 'sub-head', text: 'Agreements' }),
      ...(cg.agreements || []).map((a) => el('div', { class: 'disagreement' }, [
        el('div', { class: 'disagreement-topic', text: a.topic }),
        el('p', { class: 'muted small', text: 'Groups: ' + (a.group_ids || []).join(', ') }),
        el('p', { class: 'disagreement-resolution', text: a.summary }),
      ])),
    ]);
  }

  function renderGroupCard(g) {
    const scoreKeys = Object.keys(g.scores || {});
    const scores = el('div', { class: 'score-grid' }, scoreKeys.map((k) => {
      const s = g.scores[k];
      return el('div', { class: 'score' }, [
        el('div', { class: 'score-top' }, [
          el('span', { text: k }),
          el('span', { class: 'score-val', text: `${s.median}/10` }),
        ]),
        el('div', { class: 'score-bar' }, [el('div', { class: 'score-fill', style: { width: Math.min(100, s.median * 10) + '%' } })]),
        el('div', { class: 'score-range muted small', text: `min ${s.min} · max ${s.max} · n ${s.n}` }),
      ]);
    }));

    const verdictCounts = Object.keys(g.verdict_counts || {});

    return el('div', { class: 'result-group' }, [
      el('div', { class: 'result-group-head' }, [
        el('h4', { text: g.name }),
        el('span', { class: 'cluster-style', text: g.style }),
        el('span', { class: 'muted small', text: g.id }),
      ]),

      // Agent final positions.
      el('h5', { class: 'sub-head', text: 'Agents' }),
      el('div', { class: 'agent-verdicts' }, (g.agents || []).map((a) => renderAgentFinal(a))),

      // Scores + verdict counts.
      scoreKeys.length ? el('h5', { class: 'sub-head', text: 'Scores' }) : null,
      scores,
      verdictCounts.length ? el('div', { class: 'verdict-counts' }, verdictCounts.map((v) =>
        el('span', { class: 'verdict-count' }, [el('span', { class: 'verdict-count-tag', text: v }), el('span', { text: String(g.verdict_counts[v]) })])
      )) : null,

      // Within-group disagreements.
      (g.disagreements || []).length ? el('h5', { class: 'sub-head', text: 'Disagreements' }) : null,
      ...(g.disagreements || []).map((d) => renderDisagreement(d, false)),

      // Group stop-go + verdict.
      g.stop_go ? el('div', { class: 'group-stopgo' }, [
        el('h5', { class: 'sub-head', text: 'Group stop-or-go' }),
        g.stop_go.rationale ? el('p', { class: 'muted small', text: g.stop_go.rationale }) : null,
        el('div', { class: 'pros-cons' }, [
          el('div', { class: 'pc-col' }, [el('h5', { text: 'Pros' }), el('ul', {}, (g.stop_go.pros || []).map((p) => el('li', { text: p })))]),
          el('div', { class: 'pc-col' }, [el('h5', { text: 'Cons' }), el('ul', {}, (g.stop_go.cons || []).map((c) => el('li', { text: c })))]),
        ]),
      ]) : null,
      g.verdict ? renderVerdictBlock('Group verdict', g.verdict) : null,
    ]);
  }

  function renderAgentFinal(a) {
    const fp = a.final_position || {};
    const verdict = fp.template_verdict;
    const cls = verdict === 'Go' ? 'support' : verdict === 'No-go' ? 'oppose' : verdict ? 'conditional' : '';
    return el('div', { class: 'verdict ' + cls }, [
      el('div', { class: 'verdict-head' }, [
        el('span', { class: 'verdict-name', text: a.name }),
        el('span', { class: 'verdict-tag', text: a.model }),
        verdict ? el('span', { class: 'verdict-tag', text: verdict }) : null,
      ]),
      a.question ? el('p', { class: 'muted small', text: a.question }) : null,
      fp.role_verdict ? el('p', { class: 'verdict-quote', text: `${fp.role_verdict.label}: ${fp.role_verdict.value}` }) : null,
      renderScoreChips(fp.template_scores),
    ]);
  }

  function renderDisagreement(d, cross) {
    return el('div', { class: 'disagreement' }, [
      el('div', { class: 'disagreement-topic' }, [
        el('span', { text: d.topic }),
        el('span', { class: 'disagreement-status ' + (d.status || ''), text: d.status || '' }),
      ]),
      el('div', { class: 'disagreement-sides' }, (d.sides || []).map((s) => el('div', { class: 'disagreement-side' }, [
        el('span', { class: 'disagreement-who', text: cross ? (s.group_id || '') : (s.agent_ids || []).join(', ') }),
        el('span', { class: 'disagreement-pos', text: s.position }),
      ]))),
      (d.evidence || []).length ? el('div', { class: 'disagreement-evidence' }, d.evidence.map((e) =>
        el('p', { class: 'evidence-quote', text: `“${e.quote}” — ${e.agent_id}${e.group_id ? ' (' + e.group_id + ')' : ''}` })
      )) : null,
      d.resolution ? el('p', { class: 'disagreement-resolution', text: 'Resolution: ' + d.resolution }) : null,
    ]);
  }

  function renderAgntcy(a) {
    return el('div', { class: 'result-group' }, [
      el('div', { class: 'result-group-head' }, [el('h4', { text: 'AGNTCY transport' })]),
      el('div', { class: 'meta-table' }, [
        el('div', { class: 'meta-row' }, [el('span', { class: 'meta-key', text: 'Transport' }), el('span', { class: 'meta-val', text: a.transport })]),
        el('div', { class: 'meta-row' }, [el('span', { class: 'meta-key', text: 'Protocol' }), el('span', { class: 'meta-val', text: a.protocol })]),
        el('div', { class: 'meta-row' }, [el('span', { class: 'meta-key', text: 'SLIM groups opened' }), el('span', { class: 'meta-val', text: String(a.slim_groups_opened) })]),
      ]),
      el('h5', { class: 'sub-head', text: 'Endpoints' }),
      el('ul', { class: 'endpoint-list' }, (a.endpoints || []).map((e) => el('li', { text: e }))),
    ]);
  }

  function renderAnalysis(a) {
    return el('div', { class: 'result-group' }, [
      el('div', { class: 'result-group-head' }, [el('h4', { text: 'Disagreement analysis' })]),
      el('div', { class: 'meta-table' }, [
        el('div', { class: 'meta-row' }, [el('span', { class: 'meta-key', text: 'Model' }), el('span', { class: 'meta-val', text: a.model })]),
        el('div', { class: 'meta-row' }, [el('span', { class: 'meta-key', text: 'Verified quotes' }), el('span', { class: 'meta-val', text: String(a.verified_quotes) })]),
        el('div', { class: 'meta-row' }, [el('span', { class: 'meta-key', text: 'Dropped quotes' }), el('span', { class: 'meta-val', text: String(a.dropped_quotes) })]),
        el('div', { class: 'meta-row' }, [el('span', { class: 'meta-key', text: 'Dropped items' }), el('span', { class: 'meta-val', text: String(a.dropped_items) })]),
      ]),
    ]);
  }

  /* ---------------------------- small pieces ---------------------------- */
  function renderVerdictLine(ev) {
    const parts = [];
    if (ev.template_verdict) parts.push(el('span', { class: 'chip', text: ev.template_verdict }));
    if (ev.role_verdict) parts.push(el('span', { class: 'chip', text: `${ev.role_verdict.label}: ${ev.role_verdict.value}` }));
    return parts.length ? el('div', { class: 'chip-row' }, parts) : null;
  }

  function renderScoreChips(scores) {
    const keys = Object.keys(scores || {});
    if (!keys.length) return null;
    return el('div', { class: 'chip-row' }, keys.map((k) =>
      el('span', { class: 'chip' }, [el('span', { class: 'chip-key', text: k }), el('span', { text: ' ' + scores[k] })])
    ));
  }

  function renderRoleScores(roleScores) {
    if (!roleScores || !roleScores.length) return null;
    return el('div', { class: 'chip-row' }, roleScores.map((s) =>
      el('span', { class: 'chip' }, [el('span', { class: 'chip-key', text: s.label }), el('span', { text: ` ${s.value}/${s.max}` })])
    ));
  }

  function renderSummary(summary) {
    if (!summary) return null;
    return el('div', { class: 'summary-block' }, [
      summary.text ? el('p', { class: 'event-text', text: summary.text }) : null,
      (summary.pros || []).length ? el('div', { class: 'pros-cons' }, [
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Pros' }), el('ul', {}, summary.pros.map((p) => el('li', { text: p })))]),
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Cons' }), el('ul', {}, (summary.cons || []).map((c) => el('li', { text: c })))]),
      ]) : null,
      (summary.open_questions || []).length ? el('div', {}, [
        el('h5', { class: 'sub-head', text: 'Open questions' }),
        el('ul', {}, summary.open_questions.map((q) => el('li', { text: q }))),
      ]) : null,
      summary.complete === false ? el('p', { class: 'muted small', text: 'Summary was cut off.' }) : null,
    ]);
  }

  function renderStopGo(sg) {
    if (!sg) return null;
    return el('div', { class: 'summary-block' }, [
      el('p', { class: 'event-text', text: `${deliberationOutcome(sg).value}: ${deliberationOutcome(sg).note}` }),
      sg.rationale ? el('p', { class: 'event-text', text: sg.rationale }) : null,
      el('div', { class: 'pros-cons' }, [
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Pros' }), el('ul', {}, (sg.pros || []).map((p) => el('li', { text: p })))]),
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Cons' }), el('ul', {}, (sg.cons || []).map((c) => el('li', { text: c })))]),
      ]),
    ]);
  }

  function renderVerdict(v) {
    if (!v) return null;
    return el('div', { class: 'summary-block' }, [
      v.headline ? el('p', { class: 'verdict-headline', text: v.headline }) : null,
      v.conclusion ? el('p', { class: 'event-text', text: v.conclusion }) : null,
    ]);
  }

  function renderCrossGroup(cg) {
    if (!cg) return null;
    return el('div', { class: 'summary-block' }, [
      el('p', { class: 'event-text', text: `${(cg.disagreements || []).length} cross-group disagreements · ${(cg.agreements || []).length} agreements` }),
      ...(cg.disagreements || []).map((d) => renderDisagreement(d, true)),
    ]);
  }

  /* ------------------------------ lookups ------------------------------ */
  function agentName(run, agentId) {
    for (const g of run.cluster || []) {
      const a = g.agents.find((x) => x.id === agentId);
      if (a) return a.name;
    }
    return agentId || 'Agent';
  }

  Hack.components.modal = { mount, render };
})();