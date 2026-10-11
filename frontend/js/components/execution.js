/* components/execution.js — RIGHT column: Idea Execution.
 *
 * Turns a chosen idea into tangible artifacts via the Artifact Factory backend
 * (../artifactfactory). An idea arrives here with "Execute →" from a research
 * run in column 2 (or an idea row in column 1). Building creates a plan, then
 * implements it and lists the artifacts with download links.
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear, truncate, preserveView } = Hack.util;
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
      el('p', { class: 'column-sub', text: 'Turn a chosen idea into a tangible artifact.' }),
    ]);

    const body = el('div', { class: 'column-body', 'data-scroll-key': 'exec-body' });
    container.appendChild(header);
    container.appendChild(body);

    refs = { body };
    render();
  }

  /* Only redraw when the execution state actually changes: redrawing recreates the prototype frame, which would
   * reload the prototype and throw away whatever the viewer just clicked in it. */
  let lastSignature = null;
  function signature(ex) {
    const job = ex.job || {};
    const live = !!(Hack.artifactFactoryInfo && Hack.artifactFactoryInfo.live);
    const plan = ex.plan ? [ex.plan.id, ex.plan.status, (ex.plan.artifact_specs || []).map((x) => x.status).join()] : null;
    return JSON.stringify([ex.ideaText, ex.title, ex.pending, ex.building, ex.error, plan, job.id, job.status,
      ex.artifacts.map((a) => a.id), live]);
  }

  function render() {
    if (!refs.body) return;
    const ex = store.state.execution;
    const sig = signature(ex);
    if (sig === lastSignature) return;
    lastSignature = sig;
    preserveView(refs.body, () => {
      clear(refs.body);
      refs.body.appendChild(renderStatus());

      if (!ex.ideaText) {
        refs.body.appendChild(el('div', { class: 'empty-state' }, [
          el('img', { class: 'empty-mark', src: 'favicon.svg', alt: '', width: 20, height: 20 }),
          el('p', { text: 'No idea selected.' }),
          el('p', { class: 'muted', text: 'Open a research run in Idea Evaluation and press Execute → to send its idea here.' }),
        ]));
        return;
      }

      refs.body.appendChild(renderIdea(ex));
      if (ex.pending) {
        refs.body.appendChild(el('div', { class: 'exec-progress' }, [el('div', { class: 'spinner' }), el('span', { text: 'Creating the plan…' })]));
      }
      if (ex.plan) refs.body.appendChild(renderPlan(ex));
      if (ex.building) {
        refs.body.appendChild(el('div', { class: 'exec-progress' }, [el('div', { class: 'spinner' }), el('span', { text: 'Building the prototype (about a minute)…' })]));
      }
      if (ex.artifacts.length) refs.body.appendChild(renderArtifacts(ex));
      if (ex.error) refs.body.appendChild(el('div', { class: 'section-error', text: ex.error }));
    });
  }

  function renderStatus() {
    const live = Hack.artifactFactoryInfo && Hack.artifactFactoryInfo.live;
    return el('div', { class: 'exec-status' }, [
      el('span', { text: 'Artifact Factory: ' }),
      el('span', { class: live ? 'live' : 'muted', text: live ? 'live' : 'mock' }),
    ]);
  }

  function renderIdea(ex) {
    const canBuild = !ex.pending && !ex.building && !(ex.plan && ex.plan.status === 'implemented');
    return el('div', { class: 'exec-idea' }, [
      el('p', { class: 'exec-idea-text', text: truncate(ex.ideaText, 260) }),
      el('div', { class: 'exec-idea-foot' }, [
        el('button', { class: 'link-btn', text: 'Clear', onclick: () => actions.clearExecution() }),
        canBuild
          ? el('button', { class: 'btn small primary', text: ex.plan ? 'Build again' : 'Build prototype', onclick: () => actions.buildArtifacts() })
          : null,
      ]),
    ]);
  }

  function renderPlan(ex) {
    const plan = ex.plan;
    const built = new Set((plan.artifact_ids || []));
    return el('div', { class: 'exec-plan' }, [
      el('div', { class: 'exec-plan-head' }, [
        el('span', { class: 'exec-plan-title', text: plan.title || 'Plan' }),
        el('span', { class: 'exec-plan-status', text: plan.status }),
      ]),
      el('ol', { class: 'exec-steps' }, (plan.steps || []).map((step, i) => {
        const spec = (plan.artifact_specs || [])[i];
        const done = spec && spec.status === 'built';
        return el('li', { class: done ? 'done' : '', text: step });
      })),
    ]);
  }

  function renderArtifacts(ex) {
    return el('div', {}, [
      el('div', { class: 'exec-section-label', text: 'Artifacts' }),
      el('div', { class: 'exec-artifacts' }, ex.artifacts.map(renderArtifact)),
    ]);
  }

  /* The prototype is fetched and shown through srcdoc in a sandboxed frame (scripts only: no network, no forms,
   * no navigation, no access to this page). Loading it by URL from another port renders blank in some browsers.
   * The HTML is cached per artifact so re-renders do not refetch; if the fetch fails, the frame loads the URL. */
  const previewCache = new Map();
  function previewFrame(id, view) {
    const frame = el('iframe', { class: 'exec-preview', sandbox: 'allow-scripts', title: 'Prototype preview' });
    // Set the content only once the frame is in the page (content set on a detached frame can stay blank).
    const show = (html, tries = 0) => {
      if (frame.isConnected) frame.srcdoc = html;
      else if (tries < 50) requestAnimationFrame(() => show(html, tries + 1));
    };
    const html = previewCache.get(id);
    if (html) { show(html); return frame; }
    fetch(view).then((r) => (r.ok ? r.text() : Promise.reject(r.status))).then((text) => {
      previewCache.set(id, text);
      show(text);
    }).catch(() => { frame.src = view; });
    return frame;
  }

  function renderArtifact(a) {
    const url = actions.artifactDownloadUrl(a.id);
    const view = a.type === 'mvp_prototype' ? actions.artifactViewUrl(a.id) : null;
    if (view) {
      // The prototype itself: a sandboxed preview (scripts only: no network, no forms, no navigation).
      return el('div', { class: 'exec-artifact' }, [
        el('div', { class: 'exec-artifact-head' }, [
          el('div', {}, [
            el('span', { class: 'exec-artifact-type', text: 'prototype' }),
            el('span', { class: 'exec-artifact-name', text: a.name }),
          ]),
          el('div', {}, [
            el('a', { class: 'mini-btn', href: view, target: '_blank', rel: 'noopener', text: 'Open full screen' }),
            url ? el('a', { class: 'mini-btn', href: url, download: '', text: 'Download' }) : null,
          ]),
        ]),
        previewFrame(a.id, view),
      ]);
    }
    return el('div', { class: 'exec-artifact' }, [
      el('div', { class: 'exec-artifact-head' }, [
        el('div', {}, [
          el('span', { class: 'exec-artifact-type', text: a.type }),
          el('span', { class: 'exec-artifact-name', text: a.name }),
        ]),
        url
          ? el('a', { class: 'mini-btn', href: url, download: '', text: 'Download' })
          : el('span', { class: 'muted small', text: 'no download' }),
      ]),
      el('ul', { class: 'exec-artifact-files' }, (a.files || []).map((f) => el('li', { text: f }))),
    ]);
  }

  Hack.components.execution = { mount, render };
})();