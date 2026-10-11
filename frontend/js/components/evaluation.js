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
      el('p', { class: 'column-sub', text: 'Selected ideas appear here. Start deeper research to run the multi-agent deliberation.' }),
    ]);

    const targets = el('div', { class: 'eval-targets' });
    const runs = el('div', { class: 'eval-runs' });

    container.appendChild(header);
    container.appendChild(el('div', { class: 'column-body', 'data-scroll-key': 'eval-body' }, [
      el('div', { class: 'eval-section-label', text: 'Selected for evaluation' }),
      targets,
      el('div', { class: 'eval-section-label', text: 'Research runs' }),
      runs,
    ]));

    refs = { targets, runs };
    render();
  }

  function render() {
    const s = store.state;
    const selected = store.selectedIdeas();

    preserveView(refs.targets, () => {
      clear(refs.targets);
      if (!selected.length) {
        refs.targets.appendChild(el('div', { class: 'empty-state small' }, [
          el('p', { class: 'muted', text: 'Select an idea in the left column to evaluate it.' }),
        ]));
        return;
      }
      selected.forEach((idea) => {
        refs.targets.appendChild(el('div', { class: 'eval-target' }, [
          el('p', { class: 'eval-target-text', text: truncate(idea.text, 180) }),
          el('div', { class: 'eval-target-foot' }, [
            el('span', { class: 'muted small', text: 'Level ' + idea.level }),
            el('button', { class: 'btn small primary', text: 'Start Deeper Research', onclick: () => actions.startEvaluation(idea.id) }),
          ]),
        ]));
      });
    });

    preserveView(refs.runs, () => {
      clear(refs.runs);
      if (!s.evaluation.runs.length) {
        refs.runs.appendChild(el('div', { class: 'empty-state small' }, [
          el('p', { class: 'muted', text: 'No research runs yet.' }),
        ]));
        return;
      }
      s.evaluation.runs.forEach((run) => refs.runs.appendChild(renderRun(run)));
    });
  }

  function renderRun(run) {
    const statusText = run.status === 'running' ? 'Running' : run.status === 'done' ? 'Complete' : 'Cancelled';
    const progress = run.status === 'running' ? Math.min(95, 6 + run.events.length * 3) : 100;

    return el('div', {
      class: 'run-card ' + run.status,
      onclick: () => actions.openModal(run.id, run.status === 'done' ? 'results' : 'thinking'),
    }, [
      el('div', { class: 'run-head' }, [
        el('span', { class: 'run-status ' + run.status }, [
          run.status === 'running' ? el('span', { class: 'dot-pulse' }) : null,
          statusText,
        ]),
        el('span', { class: 'muted small', text: timeAgo(run.startedAt) }),
      ]),
      el('p', { class: 'run-idea', text: truncate(run.ideaText, 150) }),
      run.status === 'running'
        ? el('div', { class: 'run-progress' }, [el('div', { class: 'run-progress-bar', style: { width: progress + '%' } })])
        : null,
      el('div', { class: 'run-foot' }, [
        el('span', { class: 'muted small', text: run.status === 'running' ? (run.currentPhase || '') : `${run.events.length} events` }),
        el('span', { class: 'link-btn', text: 'Open →' }),
      ]),
    ]);
  }

  Hack.components.evaluation = { mount, render };
})();