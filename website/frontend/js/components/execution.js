/* components/execution.js — RIGHT column: Idea Execution.
 *
 * Turns chosen ideas into tangible prototypes via the Artifact Factory backend
 * (the repo's artifactfactory/). Ideas arrive here with "Execute →" from a research
 * run in column 2; each one builds on its own, so several build at the same time.
 * The column lists each prototype with its status; clicking a finished one opens a
 * popup (artifactModal) that explains the artifact and how to download or interact
 * with it. The prototype is not shown inline here.
 */
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
        el('span', { class: 'column-index', text: '3' }),
        el('h2', { text: 'Idea Execution' }),
      ]),
      el('p', { class: 'column-sub', text: 'Turn chosen ideas into tangible prototypes. Several build at the same time.' }),
    ]);

    const body = el('div', { class: 'column-body', 'data-scroll-key': 'exec-body' });
    container.appendChild(header);
    container.appendChild(body);

    refs = { body };
    render();
  }

  function render() {
    if (!refs.body) return;
    const ex = store.state.execution;
    preserveView(refs.body, () => {
      clear(refs.body);
      refs.body.appendChild(renderStatus());

      if (!ex.items.length) {
        refs.body.appendChild(el('div', { class: 'empty-state' }, [
          el('img', { class: 'empty-mark', src: 'favicon.svg', alt: '', width: 20, height: 20 }),
          el('p', { text: 'No prototypes yet.' }),
          el('p', { class: 'muted', text: 'Open a research run in Idea Evaluation and press Execute → to build its idea here.' }),
        ]));
        return;
      }

      const building = ex.items.filter((it) => it.pending || it.building).length;
      refs.body.appendChild(el('div', { class: 'queue-head' }, [
        el('span', {
          class: 'muted small',
          text: ex.items.length + (ex.items.length === 1 ? ' prototype' : ' prototypes') + (building ? ` · ${building} building` : ''),
        }),
        el('div', { class: 'level-head-actions' }, [
          el('button', { class: 'link-btn', text: 'Clear all', title: 'Remove every prototype', onclick: () => actions.clearExecution() }),
        ]),
      ]));
      ex.items.forEach((item) => refs.body.appendChild(renderItem(item)));
    });
  }

  function renderStatus() {
    const live = Hack.artifactFactoryInfo && Hack.artifactFactoryInfo.live;
    return el('div', { class: 'exec-status' }, [
      el('span', { text: 'Artifact Factory: ' }),
      el('span', { class: live ? 'live' : 'muted', text: live ? 'live' : 'mock' }),
    ]);
  }

  function itemStatus(item) {
    if (item.error) return { cls: 'failed', text: 'Failed' };
    if (item.pending) return { cls: 'building', text: 'Creating plan…' };
    if (item.building) return { cls: 'building', text: 'Building prototype…' };
    if (item.artifacts.length) return { cls: 'done', text: 'Done generating' };
    return { cls: '', text: 'Queued' };
  }

  function renderItem(item) {
    const status = itemStatus(item);
    const ready = !item.pending && !item.building && (item.artifacts.length > 0 || !!item.error);
    return el('div', {
      class: 'exec-item ' + status.cls + (ready ? ' clickable' : ''),
      title: ready ? 'Open the artifact' : '',
      onclick: ready ? () => actions.openArtifactModal(item.id) : null,
    }, [
      el('div', { class: 'exec-item-head' }, [
        el('span', { class: 'exec-item-status ' + status.cls }, [
          (item.pending || item.building) ? el('span', { class: 'dot-pulse' }) : null,
          status.text,
        ]),
        el('div', { class: 'exec-item-head-right' }, [
          el('span', { class: 'muted small', text: timeAgo(item.createdAt) }),
          el('button', {
            class: 'mini-btn', text: '✕', title: 'Remove this prototype',
            onclick: (e) => { e.stopPropagation(); actions.removeExecutionItem(item.id); },
          }),
        ]),
      ]),
      el('p', { class: 'exec-item-idea', text: truncate(item.ideaText, 160) }),
      item.plan ? el('p', { class: 'muted small', text: item.plan.title || 'Plan' }) : null,
      item.error ? el('div', { class: 'section-error', text: item.error }) : null,
      el('div', { class: 'exec-item-foot' }, [
        el('span', { class: 'muted small', text: item.artifacts.length ? `${item.artifacts.length} artifact${item.artifacts.length === 1 ? '' : 's'}` : '' }),
        el('div', { class: 'exec-item-actions' }, [
          item.error
            ? el('button', { class: 'mini-btn', text: 'Retry', onclick: (e) => { e.stopPropagation(); actions.buildArtifacts(item.id); } })
            : null,
          ready ? el('span', { class: 'link-btn', text: 'Open →' }) : null,
        ]),
      ]),
    ]);
  }

  Hack.components.execution = { mount, render };
})();