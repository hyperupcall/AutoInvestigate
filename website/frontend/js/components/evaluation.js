/* components/evaluation.js — MIDDLE column: idea evaluation + research runs. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, truncate, timeAgo, preserveView } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let refs = {};

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

    container.appendChild(header);
    container.appendChild(el('div', { class: 'column-body', 'data-scroll-key': 'eval-body' }, [list]));

    refs = { list };
    render();
  }

  function render() {
    const s = store.state;
    const queue = s.evaluation.queue;
    const runs = s.evaluation.runs;
    const finishedCount = runs.filter((r) => r.status !== 'running').length;

    preserveView(refs.list, () => {
      clear(refs.list);
      if (!queue.length && !runs.length) {
        refs.list.appendChild(el('div', { class: 'empty-state small' }, [
          el('p', { class: 'muted', text: 'Click Evaluate on an idea in the left column to copy it here.' }),
        ]));
        return;
      }
      const total = queue.length + runs.length;
      refs.list.appendChild(el('div', { class: 'queue-head' }, [
        el('span', { class: 'muted small', text: total + (total === 1 ? ' idea' : ' ideas') }),
        el('div', { class: 'level-head-actions' }, [
          queue.length
            ? el('button', { class: 'link-btn', text: 'Clear queued', onclick: () => actions.clearEvaluationQueue() })
            : null,
          finishedCount
            ? el('button', { class: 'link-btn', text: 'Hide finished', title: 'Hide all completed and cancelled runs', onclick: () => actions.clearFinishedRuns() })
            : null,
        ]),
      ]));
      queue.forEach((item) => refs.list.appendChild(renderQueued(item)));
      runs.forEach((run) => refs.list.appendChild(renderRun(run)));
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

  function renderRun(run) {
    const statusText = run.status === 'running' ? 'Running' : run.status === 'done' ? 'Complete' : 'Cancelled';
    const progress = run.status === 'running' ? Math.min(95, 6 + run.events.length * 3) : 100;
    const report = run.report;
    const agentCount = (run.cluster || []).reduce((n, g) => n + g.agents.length, 0);
    const decision = report && report.stop_go ? report.stop_go.decision : null;

    return el('div', {
      class: 'run-card ' + run.status,
      onclick: () => actions.openModal(run.id, run.status === 'done' ? 'evaluation' : 'cluster'),
    }, [
      el('div', { class: 'run-head' }, [
        el('span', { class: 'run-status ' + run.status }, [
          run.status === 'running' ? el('span', { class: 'dot-pulse' }) : null,
          statusText,
        ]),
        el('div', { class: 'run-head-right' }, [
          el('span', { class: 'muted small', text: timeAgo(run.startedAt) }),
          el('button', {
            class: 'mini-btn', text: '✕', title: 'Hide this run',
            onclick: (e) => { e.stopPropagation(); actions.removeRun(run.id); },
          }),
        ]),
      ]),
      el('p', { class: 'run-idea', text: truncate(run.ideaText, 150) }),
      run.status === 'running'
        ? el('div', { class: 'run-progress' }, [el('div', { class: 'run-progress-bar', style: { width: progress + '%' } })])
        : null,
      el('div', { class: 'run-foot' }, [
        el('span', { class: 'muted small', text: run.status === 'running' ? (run.currentPhase || '') : `${run.cluster ? run.cluster.length : 0} groups · ${agentCount} agents` }),
        el('div', { class: 'run-foot-actions' }, [
          decision && Hack.deliberationOutcome ? el('span', { class: 'run-decision ' + Hack.deliberationOutcome(report.stop_go).cls, text: Hack.deliberationOutcome(report.stop_go).value }) : null,
          run.complex && run.complex.decision ? el('span', { class: 'run-decision ' + (run.complex.decision === 'stop' ? 'kept' : 'extra'), text: 'Complex: ' + run.complex.decision }) : null,
          run.status === 'running'
            ? el('button', {
                class: 'mini-btn', text: 'Force stop', title: 'Stop the swarm now and write the final verdict',
                onclick: (e) => { e.stopPropagation(); actions.forceFinalize(run.id); },
              })
            : null,
          run.status === 'running'
            ? el('button', {
                class: 'mini-btn', text: 'Cancel', title: 'Stop this run',
                onclick: (e) => { e.stopPropagation(); actions.cancelEvaluation(run.id); },
              })
            : null,
          el('button', {
            class: 'mini-btn', text: 'Execute →', title: 'Send this idea to Idea Execution',
            onclick: (e) => { e.stopPropagation(); actions.sendToExecution({ ideaId: run.ideaId, ideaText: run.ideaText, evaluationRunId: run.backendRunId || null }); },
          }),
          run.backendRunId
            ? el('a', {
                class: 'link-btn', href: Hack.agentViewUrl(run.backendRunId),
                title: 'Open this run in the full Agent View', text: 'Agent View →',
                onclick: (e) => e.stopPropagation(),
              })
            : null,
          el('span', { class: 'link-btn', text: 'Open →' }),
        ]),
      ]),
    ]);
  }

  Hack.components.evaluation = { mount, render };
})();