/* components/evaluation.js — MIDDLE column: idea evaluation + research runs. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, truncate, timeAgo, preserveView } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let refs = {};
  let queueSig = null;
  // One cached card per run, reused across renders so its buttons (the ✕, Cancel, …)
  // are not destroyed while a streamed event triggers a re-render mid-click.
  const runCards = new Map();

  function mount(container) {
    clear(container);
    const header = el('div', { class: 'column-head' }, [
      el('div', { class: 'column-title' }, [
        el('span', { class: 'column-index', text: '2' }),
        el('h2', { text: 'Idea Evaluation' }),
      ]),
      el('p', { class: 'column-sub', text: 'Ideas you copy over with Evaluate appear here. Start deeper research to run the multi-agent deliberation.' }),
    ]);

    const list = el('div', { class: 'eval-list' });
    const head = el('div', { class: 'queue-head' });
    const queueBox = el('div', { class: 'eval-queue' });
    const runsBox = el('div', { class: 'eval-runs' });
    const empty = el('div', { class: 'empty-state small' }, [
      el('p', { class: 'muted', text: 'Click Evaluate on an idea in the left column to copy it here.' }),
    ]);
    list.append(head, queueBox, runsBox, empty);

    container.appendChild(header);
    container.appendChild(el('div', { class: 'column-body', 'data-scroll-key': 'eval-body' }, [list]));

    refs = { list, head, queueBox, runsBox, empty };
    queueSig = null;
    runCards.clear();
    render();
  }

  function render() {
    const s = store.state;
    const queue = s.evaluation.queue;
    const runs = s.evaluation.runs;
    const total = queue.length + runs.length;
    const finishedCount = runs.filter((r) => r.status !== 'running').length;

    preserveView(refs.list, () => {
      refs.empty.style.display = total ? 'none' : '';
      refs.head.style.display = total ? '' : 'none';
      refs.queueBox.style.display = total ? '' : 'none';
      refs.runsBox.style.display = total ? '' : 'none';

      // Head — cheap, rebuilt every render.
      clear(refs.head);
      if (total) {
        refs.head.appendChild(el('span', { class: 'muted small', text: total + (total === 1 ? ' idea' : ' ideas') }));
        refs.head.appendChild(el('div', { class: 'level-head-actions' }, [
          queue.length
            ? el('button', { class: 'link-btn', text: 'Clear queued', onclick: () => actions.clearEvaluationQueue() })
            : null,
          finishedCount
            ? el('button', { class: 'link-btn', text: 'Hide finished', title: 'Hide all completed and cancelled runs', onclick: () => actions.clearFinishedRuns() })
            : null,
        ]));
      }

      // Queue — rebuilt only when the queue itself changes. A streamed run re-renders
      // the column constantly; rebuilding the queue then would destroy the ✕ button
      // between mousedown and mouseup, and the click would be lost.
      const sig = queue.map((q) => q.id).join('|');
      if (sig !== queueSig) {
        queueSig = sig;
        clear(refs.queueBox);
        queue.forEach((item) => refs.queueBox.appendChild(renderQueued(item)));
      }

      // Runs — each card is reused and updated in place (never detached while it is
      // already in the right position), so its buttons stay clickable during a run.
      const liveIds = new Set(runs.map((r) => r.id));
      for (const [id, entry] of runCards) {
        if (!liveIds.has(id)) { entry.card.remove(); runCards.delete(id); }
      }
      runs.forEach((run, i) => {
        const card = renderRun(run);
        const current = refs.runsBox.children[i];
        if (current !== card) refs.runsBox.insertBefore(card, current || null);
      });
    });
  }

  function renderQueued(item) {
    return el('div', { class: 'eval-target' }, [
      el('p', { class: 'eval-target-text', text: truncate(item.text, 180) }),
      el('div', { class: 'eval-target-foot' }, [
        el('div', { class: 'eval-target-actions' }, [
          el('button', { class: 'mini-btn', title: 'Remove from queue', text: '✕', onclick: () => actions.removeQueuedIdea(item.id) }),
          el('button', { class: 'btn small primary', text: 'Start Deeper Research', onclick: () => actions.openRunConfig(item.id) }),
        ]),
      ]),
    ]);
  }

  /* ------------------------------- runs ------------------------------- */

  /** Build a run card once; `updateRunCard` then refreshes it in place. */
  function buildRunCard(run) {
    const status = el('span', { class: 'run-status' });
    const time = el('span', { class: 'muted small' });
    const head = el('div', { class: 'run-head' }, [
      status,
      el('div', { class: 'run-head-right' }, [
        time,
        el('button', {
          class: 'mini-btn', text: '✕', title: 'Hide this run',
          onclick: (e) => { e.stopPropagation(); actions.removeRun(run.id); },
        }),
      ]),
    ]);
    const idea = el('p', { class: 'run-idea' });
    const progressBar = el('div', { class: 'run-progress-bar' });
    const progress = el('div', { class: 'run-progress' }, [progressBar]);
    const footLeft = el('span', { class: 'muted small' });
    const chips = el('div', { class: 'run-foot-actions' });
    const foot = el('div', { class: 'run-foot' }, [footLeft, chips]);
    const card = el('div', {
      class: 'run-card',
      onclick: () => actions.openModal(run.id, run.status === 'done' ? 'evaluation' : 'cluster'),
    }, [head, idea, progress, foot]);
    return { card, status, time, idea, progress, progressBar, footLeft, chips };
  }

  function updateRunCard(c, run) {
    const statusText = run.status === 'running' ? 'Running' : run.status === 'done' ? 'Complete' : 'Cancelled';
    c.card.className = 'run-card ' + run.status;

    c.status.className = 'run-status ' + run.status;
    clear(c.status);
    if (run.status === 'running') c.status.appendChild(el('span', { class: 'dot-pulse' }));
    c.status.appendChild(document.createTextNode(statusText));

    c.time.textContent = timeAgo(run.startedAt);
    c.idea.textContent = truncate(run.ideaText, 150);

    const progress = run.status === 'running' ? Math.min(95, 6 + run.events.length * 3) : 100;
    c.progress.style.display = run.status === 'running' ? '' : 'none';
    c.progressBar.style.width = progress + '%';

    const report = run.report;
    const agentCount = (run.cluster || []).reduce((n, g) => n + g.agents.length, 0);
    const decision = report && report.stop_go ? report.stop_go.decision : null;
    c.footLeft.textContent = run.status === 'running'
      ? (run.currentPhase || '')
      : `${run.cluster ? run.cluster.length : 0} groups · ${agentCount} agents`;

    clear(c.chips);
    if (decision && Hack.deliberationOutcome) {
      const outcome = Hack.deliberationOutcome(report.stop_go);
      c.chips.appendChild(el('span', { class: 'run-decision ' + outcome.cls, text: outcome.value }));
    }
    if (run.complex && run.complex.decision) {
      c.chips.appendChild(el('span', { class: 'run-decision ' + (run.complex.decision === 'stop' ? 'kept' : 'extra'), text: 'Complex: ' + run.complex.decision }));
    }
    if (run.status === 'running') {
      c.chips.appendChild(el('button', {
        class: 'mini-btn', text: 'Force stop', title: 'Stop the swarm now and write the final verdict',
        onclick: (e) => { e.stopPropagation(); actions.forceFinalize(run.id); },
      }));
      c.chips.appendChild(el('button', {
        class: 'mini-btn', text: 'Cancel', title: 'Stop this run',
        onclick: (e) => { e.stopPropagation(); actions.cancelEvaluation(run.id); },
      }));
    }
    c.chips.appendChild(el('button', {
      class: 'mini-btn', text: 'Execute →', title: 'Send this idea to Idea Execution',
      onclick: (e) => { e.stopPropagation(); actions.sendToExecution({ ideaId: run.ideaId, ideaText: run.ideaText, evaluationRunId: run.backendRunId || null }); },
    }));
    if (run.backendRunId) {
      c.chips.appendChild(el('a', {
        class: 'link-btn', href: Hack.agentViewUrl(run.backendRunId),
        title: 'Open this run in the full Agent View', text: 'Agent View →',
        onclick: (e) => e.stopPropagation(),
      }));
    }
    c.chips.appendChild(el('span', { class: 'link-btn', text: 'Open →' }));
  }

  function renderRun(run) {
    let c = runCards.get(run.id);
    if (!c) { c = buildRunCard(run); runCards.set(run.id, c); }
    updateRunCard(c, run);
    return c.card;
  }

  Hack.components.evaluation = { mount, render };
})();