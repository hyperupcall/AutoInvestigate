/* components/modal.js — popup with two tabs: "Agent Thinking" and "Results". */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, truncate, formatTime } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  let stickToBottom = true;

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

    const dialog = el('div', { class: 'modal', onclick: (e) => e.stopPropagation() }, [
      renderHead(run),
      renderTabs(modal.tab),
      modal.tab === 'thinking' ? renderThinking(run) : renderResults(run),
    ]);

    const overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeModal() }, [dialog]);
    clear(root);
    root.appendChild(overlay);
  }

  function renderHead(run) {
    const statusText = run.status === 'running' ? 'Running' : run.status === 'done' ? 'Complete' : 'Cancelled';
    return el('div', { class: 'modal-head' }, [
      el('div', { class: 'modal-head-main' }, [
        el('div', { class: 'modal-eyebrow' }, [
          el('span', { class: 'run-status ' + run.status }, [run.status === 'running' ? el('span', { class: 'dot-pulse' }) : null, statusText]),
          el('span', { class: 'muted small', text: 'Idea evaluation · ' + (run.model || '') }),
        ]),
        el('h3', { class: 'modal-title', text: truncate(run.ideaText, 160) }),
      ]),
      el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeModal() }),
    ]);
  }

  function renderTabs(active) {
    const tabs = [
      { id: 'thinking', label: 'Agent Thinking' },
      { id: 'results', label: 'Results' },
    ];
    return el('div', { class: 'modal-tabs' }, tabs.map((t) =>
      el('button', {
        class: 'modal-tab' + (active === t.id ? ' active' : ''),
        text: t.label,
        onclick: () => actions.setModalTab(t.id),
      })
    ));
  }

  /* --------------------------- thinking tab --------------------------- */
  function renderThinking(run) {
    const log = el('div', { class: 'thinking-log', 'data-scroll-key': 'thinking-log' });
    log.addEventListener('scroll', () => {
      stickToBottom = (log.scrollHeight - log.scrollTop - log.clientHeight) < 48;
    });

    let lastPhase = null;
    let lastGroup = null;
    run.events.forEach((ev) => {
      if (ev.phase !== lastPhase) {
        lastPhase = ev.phase;
        lastGroup = null;
        log.appendChild(el('div', { class: 'phase-divider' }, [el('span', { text: ev.phase })]));
      }
      if (ev.kind === 'group-start') {
        lastGroup = ev.group;
        log.appendChild(el('div', { class: 'group-divider', text: ev.group }));
        return;
      }
      if (ev.kind === 'phase') {
        log.appendChild(el('div', { class: 'event-row kind-phase', text: ev.text }));
        return;
      }
      if (ev.kind === 'summary') {
        log.appendChild(el('div', { class: 'event-row kind-summary' }, [
          el('span', { class: 'event-group', text: ev.group }),
          el('p', { class: 'event-text', text: ev.text }),
        ]));
        return;
      }
      if (ev.kind === 'decision' || ev.kind === 'conclusion') {
        log.appendChild(el('div', { class: 'event-row kind-' + ev.kind }, [
          el('span', { class: 'event-kind', text: ev.kind === 'decision' ? 'Stop-or-Go' : 'Conclusion' }),
          el('p', { class: 'event-text', text: ev.text }),
        ]));
        return;
      }
      // thought
      log.appendChild(el('div', { class: 'event-row kind-thought' }, [
        el('div', { class: 'event-meta' }, [
          el('span', { class: 'event-agent', text: ev.agent || 'Agent' }),
          el('span', { class: 'event-role', text: ev.role || '' }),
          el('span', { class: 'event-time', text: formatTime(ev.ts) }),
        ]),
        el('p', { class: 'event-text', text: ev.text }),
      ]));
    });

    if (run.status === 'running') {
      log.appendChild(el('div', { class: 'event-row kind-live' }, [
        el('span', { class: 'spinner small' }),
        el('span', { text: `${run.currentPhase}${run.currentAgent ? ' · ' + run.currentAgent + ' is thinking…' : '…'}` }),
      ]));
    }

    if (stickToBottom) requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });

    return el('div', { class: 'modal-body' }, [
      el('div', { class: 'thinking-status' }, [
        el('span', { class: 'muted small', text: run.status === 'running' ? 'Live backend activity' : 'Run finished' }),
        el('span', { class: 'muted small', text: `${run.events.length} events` }),
      ]),
      log,
    ]);
  }

  /* --------------------------- results tab --------------------------- */
  function renderResults(run) {
    if (run.status === 'running') {
      return el('div', { class: 'modal-body' }, [
        el('div', { class: 'empty-state' }, [
          el('div', { class: 'spinner' }),
          el('p', { text: 'Results will appear here when the deliberation finishes.' }),
          el('p', { class: 'muted', text: 'Switch to “Agent Thinking” to watch it live.' }),
        ]),
      ]);
    }
    if (!run.results) {
      return el('div', { class: 'modal-body' }, [el('div', { class: 'empty-state' }, [el('p', { text: 'No results.' })])]);
    }

    const r = run.results;
    const body = el('div', { class: 'modal-body results' });

    // Stop-or-go banner
    const decisionClass = r.stopOrGo.decision === 'GO' ? 'go' : r.stopOrGo.decision === 'STOP' ? 'stop' : 'hold';
    body.appendChild(el('div', { class: 'decision-banner ' + decisionClass }, [
      el('div', { class: 'decision-head' }, [
        el('span', { class: 'decision-label', text: 'Stop-or-Go' }),
        el('span', { class: 'decision-value', text: r.stopOrGo.decision }),
        el('span', { class: 'decision-confidence', text: Math.round(r.stopOrGo.confidence * 100) + '% confidence' }),
      ]),
      el('p', { class: 'decision-rationale', text: r.stopOrGo.rationale }),
      el('div', { class: 'decision-cols' }, [
        el('div', { class: 'decision-col' }, [
          el('h4', { text: 'Pros' }),
          el('ul', {}, r.stopOrGo.pros.map((p) => el('li', { text: p }))),
        ]),
        el('div', { class: 'decision-col' }, [
          el('h4', { text: 'Cons' }),
          el('ul', {}, r.stopOrGo.cons.map((c) => el('li', { text: c }))),
        ]),
      ]),
    ]));

    // Per-group cards
    r.groups.forEach((g) => {
      const scores = el('div', { class: 'score-grid' }, Object.keys(g.scores).map((k) => {
        const v = g.scores[k];
        return el('div', { class: 'score' }, [
          el('div', { class: 'score-top' }, [el('span', { text: k }), el('span', { class: 'score-val', text: v + '/10' })]),
          el('div', { class: 'score-bar' }, [el('div', { class: 'score-fill', style: { width: (v * 10) + '%' } })]),
        ]);
      }));

      body.appendChild(el('div', { class: 'result-group' }, [
        el('div', { class: 'result-group-head' }, [el('h4', { text: g.name })]),
        el('p', { class: 'result-summary', text: g.summary }),
        scores,
        el('div', { class: 'pros-cons' }, [
          el('div', { class: 'pc-col' }, [el('h5', { text: 'Pros' }), el('ul', {}, g.pros.map((p) => el('li', { text: p })))]),
          el('div', { class: 'pc-col' }, [el('h5', { text: 'Cons' }), el('ul', {}, g.cons.map((c) => el('li', { text: c })))]),
        ]),
        el('div', { class: 'agent-verdicts' }, g.agents.map((a) => el('div', { class: 'verdict ' + a.verdict }, [
          el('div', { class: 'verdict-head' }, [
            el('span', { class: 'verdict-name', text: a.name }),
            el('span', { class: 'verdict-tag', text: a.verdict }),
          ]),
          el('p', { class: 'verdict-quote', text: a.quote }),
        ]))),
      ]));
    });

    // Conclusion
    body.appendChild(el('div', { class: 'conclusion' }, [
      el('h4', { text: 'Final conclusion' }),
      el('p', { text: r.conclusion }),
    ]));

    return body;
  }

  Hack.components.modal = { mount, render };
})();