/* components/modal.js — large popup for one research run.
 *
 * Two tabs:
 *   Cluster Status — what is in the agent cluster and what the agents are
 *                    saying, streamed live as the backend emits events.
 *   Evaluation     — the finished evaluation report, shaped exactly like
 *                    evaluation-report.schema.json (plus a raw-JSON view).
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, truncate, formatTime } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  let stickToBottom = true;
  let savedScrollTop = 0;

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
      modal.tab === 'cluster' ? renderCluster(run) : renderEvaluation(run),
    ]);

    const overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeModal() }, [dialog]);
    clear(root);
    root.appendChild(overlay);

    // Restore / advance the cluster log scroll after it is in the DOM.
    const log = dialog.querySelector('[data-scroll-key="cluster-log"]');
    if (log) {
      log.addEventListener('scroll', () => {
        stickToBottom = (log.scrollHeight - log.scrollTop - log.clientHeight) < 48;
        savedScrollTop = log.scrollTop;
      });
      requestAnimationFrame(() => {
        log.scrollTop = stickToBottom ? log.scrollHeight : savedScrollTop;
      });
    }
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
      el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeModal() }),
    ]);
  }

  function renderTabs(active) {
    const tabs = [
      { id: 'cluster', label: 'Cluster Status' },
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

  /* ============================ Cluster Status ============================ */
  function renderCluster(run) {
    const body = el('div', { class: 'modal-body cluster-body' });

    body.appendChild(el('div', { class: 'cluster-status-bar' }, [
      el('span', { class: 'muted small', text: run.status === 'running' ? 'Live backend activity' : 'Run finished' }),
      el('span', { class: 'muted small', text: `${run.events.length} events` }),
    ]));

    // The agent cluster roster — what is in the cluster right now.
    body.appendChild(renderRoster(run));

    // The streamed activity log.
    const log = el('div', { class: 'thinking-log', 'data-scroll-key': 'cluster-log' });
    let lastPhase = null;
    run.events.forEach((ev) => {
      if (ev.phase !== lastPhase) {
        lastPhase = ev.phase;
        log.appendChild(el('div', { class: 'phase-divider' }, [el('span', { text: ev.phase })]));
      }
      log.appendChild(renderEvent(run, ev));
    });

    if (run.status === 'running') {
      log.appendChild(el('div', { class: 'event-row kind-live' }, [
        el('span', { class: 'spinner small' }),
        el('span', { text: `${run.currentPhase}${run.currentAgent ? ' · ' + agentName(run, run.currentAgent) + ' is working…' : '…'}` }),
      ]));
    }

    body.appendChild(log);
    return body;
  }

  function renderRoster(run) {
    const groups = run.cluster || [];
    if (!groups.length) {
      return el('div', { class: 'empty-state small' }, [el('p', { class: 'muted', text: 'No cluster yet.' })]);
    }
    return el('div', { class: 'cluster-roster' }, [
      el('div', { class: 'cluster-roster-title', text: 'Agent cluster' }),
      ...groups.map((g) => el('div', { class: 'cluster-group' }, [
        el('div', { class: 'cluster-group-head' }, [
          el('span', { class: 'cluster-group-name', text: g.name }),
          el('span', { class: 'cluster-style', text: g.style }),
          el('span', { class: 'muted small', text: `${g.agents.length} agents` }),
        ]),
        el('div', { class: 'cluster-agents' }, g.agents.map((a) => el('div', { class: 'cluster-agent' }, [
          el('div', { class: 'cluster-agent-head' }, [
            el('span', { class: 'cluster-agent-name', text: a.name }),
            el('span', { class: 'cluster-agent-model', text: a.model }),
          ]),
          a.question ? el('p', { class: 'cluster-agent-q', text: a.question }) : null,
          a.who_they_are ? el('p', { class: 'cluster-agent-who muted small', text: a.who_they_are }) : null,
        ]))),
      ])),
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
          el('p', { class: 'event-text', text: ev.text }),
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
          el('p', { class: 'event-text', text: ev.text }),
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
      default:
        return el('div', { class: 'event-row', text: ev.text || ev.kind });
    }
  }

  /* ============================== Evaluation ============================== */
  function renderEvaluation(run) {
    const body = el('div', { class: 'modal-body results' });
    const report = run.report;

    if (!report) {
      body.appendChild(el('div', { class: 'empty-state' }, [el('p', { text: 'No report yet.' })]));
      return body;
    }

    if (run.status === 'running') {
      body.appendChild(el('div', { class: 'empty-state small' }, [
        el('div', { class: 'spinner' }),
        el('p', { text: 'Deliberation in progress.' }),
        el('p', { class: 'muted', text: 'The evaluation report appears here when the run finishes. Switch to “Cluster Status” to watch it live.' }),
      ]));
      return body;
    }

    // Run header.
    body.appendChild(renderRunMeta(report.run, report.pipeline));

    // Stop-or-go banner.
    if (report.stop_go) body.appendChild(renderStopGoBanner(report.stop_go));

    // Final verdict.
    if (report.verdict) body.appendChild(renderVerdictBlock('Final verdict', report.verdict));
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
    if (!sg.consensus_feasible) return { cls: 'kept', value: 'Disagreement kept', note: 'The groups cannot converge, so a person should decide.' };
    if (sg.decision === 'go') return { cls: 'extra', value: 'Extra round', note: 'Ran one more round to settle an open question, then finished.' };
    return { cls: 'stopped', value: 'Stopped', note: 'The evidence was enough to conclude.' };
  }
  Hack.deliberationOutcome = deliberationOutcome;

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
      v.pros && v.pros.length ? el('div', { class: 'pros-cons' }, [
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Pros' }), el('ul', {}, v.pros.map((p) => el('li', { text: p })))]),
        el('div', { class: 'pc-col' }, [el('h5', { text: 'Cons' }), el('ul', {}, (v.cons || []).map((c) => el('li', { text: c })))]),
      ]) : null,
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