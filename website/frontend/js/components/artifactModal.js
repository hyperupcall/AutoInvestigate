/* components/artifactModal.js — the popup opened by clicking a finished prototype
 * in column 3 (Idea Execution).
 *
 * It explains what the artifact is and how to download or interact with it: the
 * interactive prototype is shown in a sandboxed frame (scripts only: no network, no
 * forms, no navigation), with links to open it full screen and to download it. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;

  let root = null;
  let overlay = null;
  let bodyEl = null;
  let lastSignature = null;

  const DESCRIPTIONS = {
    source_repository: 'A source repository scaffold: a README describing the experiment the panel asked for and a starter script where the real systems plug in.',
    literature_review: "A literature review: the papers the agents were given, every group's verdict, scores and pros and cons, and a short related-work synthesis.",
    npm_package: 'An NPM package scaffold (package.json, index.js, README, .npmignore).',
    docker_image: 'A Docker image manifest (Dockerfile, manifest.json, placeholder image.tar).',
    tarball: 'A tarball packaging every artifact built for this idea.',
  };

  function describe(a, view) {
    if (a.type === 'mvp_prototype') {
      return view
        ? "An interactive prototype: a clickable product screen for this idea's narrow first version, with demo data and the evaluation panel's concerns built in. Try it below, open it full screen, or download the HTML to run it yourself."
        : "An interactive prototype: a clickable product screen for this idea's narrow first version. Download it to run it yourself.";
    }
    return DESCRIPTIONS[a.type] || `A ${a.type} artifact.`;
  }

  /* The prototype is fetched and shown through srcdoc in a sandboxed frame (scripts only: no network, no forms,
   * no navigation, no access to this page). Loading it by URL from another port renders blank in some browsers.
   * The HTML is cached per artifact so re-renders do not refetch; if the fetch fails, the frame loads the URL. */
  const previewCache = new Map();
  function previewFrame(id, view) {
    const frame = el('iframe', { class: 'artifact-preview', sandbox: 'allow-scripts', title: 'Prototype preview' });
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
    return el('div', { class: 'artifact-block' }, [
      el('div', { class: 'artifact-block-head' }, [
        el('div', {}, [
          el('span', { class: 'exec-artifact-type', text: a.type }),
          el('span', { class: 'exec-artifact-name', text: a.name }),
        ]),
        el('div', { class: 'artifact-block-actions' }, [
          view ? el('a', { class: 'mini-btn', href: view, target: '_blank', rel: 'noopener', text: 'Open full screen' }) : null,
          url ? el('a', { class: 'mini-btn', href: url, download: '', text: 'Download' }) : null,
        ]),
      ]),
      el('p', { class: 'artifact-desc', text: describe(a, view) }),
      view ? previewFrame(a.id, view) : null,
      (a.files || []).length
        ? el('details', { class: 'artifact-files' }, [
            el('summary', { text: `${a.files.length} file${a.files.length === 1 ? '' : 's'}` }),
            el('ul', {}, a.files.map((f) => el('li', { text: f }))),
          ])
        : null,
    ]);
  }

  function renderBody() {
    const am = store.state.ui.artifactModal;
    const item = store.state.execution.items.find((x) => x.id === am.itemId);
    if (!item) return el('p', { class: 'muted', text: 'This prototype is no longer available.' });

    const status = item.error ? 'Failed' : item.pending ? 'Creating plan…' : item.building ? 'Building…' : 'Done generating';
    return el('div', {}, [
      el('div', { class: 'artifact-meta' }, [
        el('span', { class: 'muted small', text: status }),
        item.plan ? el('span', { class: 'muted small', text: item.plan.title || '' }) : null,
      ]),
      el('div', { class: 'artifact-idea' }, [
        el('div', { class: 'exec-section-label', text: 'Idea' }),
        el('p', { class: 'artifact-idea-text', text: item.ideaText }),
      ]),
      item.error ? el('div', { class: 'section-error', text: item.error }) : null,
      item.artifacts.length
        ? el('div', { class: 'artifact-list' }, item.artifacts.map(renderArtifact))
        : el('p', { class: 'muted small', text: 'No artifacts yet.' }),
    ]);
  }

  function mount(container) {
    root = container;

    bodyEl = el('div', { class: 'modal-body' });
    const dialog = el('div', { class: 'modal artifact-modal', onclick: (e) => e.stopPropagation() }, [
      el('div', { class: 'modal-head' }, [
        el('div', { class: 'modal-head-main' }, [
          el('h3', { class: 'modal-title', text: 'Artifact' }),
          el('p', { class: 'muted small', text: 'What this prototype is, and how to download or interact with it.' }),
        ]),
        el('button', { class: 'icon-btn', title: 'Close', text: '✕', onclick: () => actions.closeArtifactModal() }),
      ]),
      bodyEl,
    ]);

    overlay = el('div', { class: 'modal-overlay', onclick: () => actions.closeArtifactModal() }, [dialog]);
    overlay.style.display = 'none';

    clear(root);
    root.appendChild(overlay);

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && store.state.ui.artifactModal.open) actions.closeArtifactModal();
    });

    render();
  }

  function render() {
    if (!overlay) return;
    const am = store.state.ui.artifactModal;
    overlay.style.display = am.open ? '' : 'none';
    if (!am.open) { lastSignature = null; return; }
    // Only rebuild when the shown item changes: rebuilding recreates the preview frame,
    // which would reload the prototype and throw away whatever the viewer just clicked.
    const item = store.state.execution.items.find((x) => x.id === am.itemId);
    const sig = JSON.stringify([am.itemId, item ? [item.pending, item.building, item.error, item.artifacts.map((a) => a.id)] : null]);
    if (sig === lastSignature) return;
    lastSignature = sig;
    clear(bodyEl);
    bodyEl.appendChild(renderBody());
  }

  Hack.components.artifactModal = { mount, render };
})();