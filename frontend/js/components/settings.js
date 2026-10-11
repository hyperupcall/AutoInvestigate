/* components/settings.js — settings content (models, prompts, group perspectives).
 * The content is rendered by the settings popup (settingsModal.js) and by the
 * standalone settings.html page. Kept deliberately close to "bare HTML". */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;
  const D = Hack.mockData;

  // Only these models may be used (see CHEAP_MODELS.md). One source of truth: model-info.js.
  const MODELS = Hack.modelInfo.MODELS.map((m) => m.id);

  /** Only the cheap models are offered; a configured backend model is folded in when it is one of them. */
  function modelOptions() {
    const info = Hack.backendInfo;
    if (!info || !info.live || !info.settings) return MODELS.slice();
    const s = info.settings;
    const configured = s.groups.flatMap((g) => g.agents.map((a) => a.model)).concat([s.stages.summarizer.model, s.stages.judge.model]);
    const allowed = (m) => MODELS.includes(m.replace(/:online$/, ''));
    return [...new Set([...MODELS, ...configured.filter(allowed)])];
  }

  /** Provider is the part before the slash in an OpenRouter id (e.g. "google" in google/gemma-3-4b-it). */
  function providerOf(model) {
    const id = String(model || '').replace(/:online$/, '');
    const slash = id.indexOf('/');
    return slash > 0 ? id.slice(0, slash) : 'other';
  }

  /** Sort by provider, then by model id, so long lists are easy to scan. */
  function sortModelsByProvider(models) {
    return models.slice().sort((a, b) => {
      const pa = providerOf(a);
      const pb = providerOf(b);
      if (pa !== pb) return pa.localeCompare(pb);
      return a.localeCompare(b);
    });
  }

  /** <option>s grouped into <optgroup>s by provider, so a large list stays parseable. */
  function modelOptionNodes(models, selected) {
    const groups = new Map();
    sortModelsByProvider(models).forEach((m) => {
      const p = providerOf(m);
      if (!groups.has(p)) groups.set(p, []);
      groups.get(p).push(m);
    });
    return [...groups.entries()].map(([provider, list]) =>
      el('optgroup', { label: provider }, list.map((m) =>
        el('option', { value: m, text: m, selected: m === selected }))));
  }

  function section(title, children) {
    return el('div', { class: 'settings-section' }, [
      el('h3', { class: 'settings-title', text: title }),
      el('div', { class: 'settings-body' }, children),
    ]);
  }

  function modelField(label, key, value) {
    const options = modelOptions();
    if (value && !options.includes(value)) options.unshift(value);
    return el('div', { class: 'field' }, [
      el('label', { text: label }),
      el('select', {
        class: 'select',
        onchange: (e) => { store.state.settings[key] = e.target.value; },
      }, modelOptionNodes(options, value)),
    ]);
  }

  function renderGroup(group) {
    const agents = el('div', { class: 'agents' });
    group.agents.forEach((a) => agents.appendChild(renderAgent(group, a)));

    return el('div', { class: 'group-card' }, [
      el('div', { class: 'group-head' }, [
        el('input', {
          class: 'text-input group-name', value: group.name,
          oninput: (e) => { group.name = e.target.value; },
        }),
        el('button', { class: 'icon-btn danger', title: 'Remove group', text: '✕', onclick: () => actions.removeGroupPerspective(group.id) }),
      ]),
      el('input', {
        class: 'text-input group-blurb', value: group.blurb || '', placeholder: 'What does this group care about?',
        oninput: (e) => { group.blurb = e.target.value; },
      }),
      agents,
      el('button', { class: 'btn small ghost', text: '+ Add agent', onclick: () => actions.addAgent(group.id) }),
    ]);
  }

  function renderAgent(group, agent) {
    return el('div', { class: 'agent-row' }, [
      el('input', { class: 'text-input', value: agent.name, placeholder: 'Name', oninput: (e) => { agent.name = e.target.value; } }),
      el('input', { class: 'text-input', value: agent.role, placeholder: 'Role', oninput: (e) => { agent.role = e.target.value; } }),
      el('select', { class: 'select small', onchange: (e) => { agent.model = e.target.value; } },
        modelOptionNodes(modelOptions(), agent.model)),
      el('button', { class: 'icon-btn danger', title: 'Remove agent', text: '✕', onclick: () => actions.removeAgent(group.id, agent.id) }),
    ]);
  }

  /** The settings form itself. Rebuilt only when the group/agent structure changes. */
  function renderContent() {
    const s = store.state.settings;
    const wrap = el('div', { class: 'settings-content' });
    const info = Hack.backendInfo;
    if (info && info.live) {
      wrap.appendChild(el('p', { class: 'muted small' }, [
        'Connected to the backend. Groups, per-agent models and API keys are saved there: ',
        el('a', { href: info.base + '/settings', target: '_blank', text: 'open backend settings' }),
        '. Here you can change the deliberation time and the summarizer for your next run.',
      ]));
    }

    wrap.appendChild(section('Mode', [
      el('div', { class: 'field' }, [
        el('label', { text: 'Evaluation mode' }),
        el('select', { class: 'select', onchange: (e) => { s.mode = e.target.value; } }, [
          el('option', { value: 'quick', text: 'Quick: about a minute', selected: (s.mode || 'quick') === 'quick' }),
          el('option', { value: 'deep', text: 'Deep: about 7 minutes, full write-ups', selected: s.mode === 'deep' }),
        ]),
      ]),
    ]));

    wrap.appendChild(section('Models', [
      modelField('Generation model', 'generationModel', s.generationModel),
      modelField('Evaluation model', 'evaluationModel', s.evaluationModel),
      modelField('Summarizer model', 'summarizerModel', s.summarizerModel),
      el('div', { class: 'field inline' }, [
        el('label', { text: 'Deliberation (seconds, deep mode)' }),
        el('input', {
          type: 'number', min: 6, max: 60, class: 'num-input', value: s.deliberationSeconds,
          oninput: (e) => { s.deliberationSeconds = Math.max(6, Math.min(60, Number(e.target.value) || 15)); },
        }),
      ]),
    ]));

    const activePrompt = D.PROMPT_PRESETS.find((p) => p.id === s.promptSet);
    wrap.appendChild(section('Prompts', [
      el('div', { class: 'field' }, [
        el('label', { text: 'Prompt set (loaded from filesystem)' }),
        el('select', { class: 'select', onchange: (e) => { s.promptSet = e.target.value; } },
          D.PROMPT_PRESETS.map((p) => el('option', { value: p.id, text: p.name, selected: p.id === s.promptSet }))),
      ]),
      el('p', { class: 'muted small', text: activePrompt ? activePrompt.description : '' }),
    ]));

    const groupsWrap = el('div', { class: 'groups' });
    s.groupPerspectives.forEach((g) => groupsWrap.appendChild(renderGroup(g)));
    wrap.appendChild(section('Group perspectives', [
      groupsWrap,
      el('button', { class: 'btn small', text: '+ Add group perspective', onclick: () => actions.addGroupPerspective() }),
    ]));

    return wrap;
  }

  /* ------------------- standalone page (settings.html) ------------------- */
  let refs = {};
  let lastSignature = null;

  function signature() {
    const g = store.state.settings.groupPerspectives;
    return g.map((x) => x.id + ':' + x.agents.map((a) => a.id).join(',')).join('|');
  }

  function mount(container) {
    clear(container);
    const header = el('div', { class: 'column-head' }, [
      el('div', { class: 'column-title' }, [
        el('span', { class: 'column-index', text: '⚙' }),
        el('h2', { text: 'Settings' }),
      ]),
      el('p', { class: 'column-sub', text: 'Models, prompts and group perspectives. API keys always live on the backend.' }),
    ]);
    const body = el('div', { class: 'column-body', 'data-scroll-key': 'settings-body' });
    container.appendChild(header);
    container.appendChild(body);
    refs = { body };
    lastSignature = null;
    render();
  }

  function render() {
    if (!refs.body) return;
    const sig = signature();
    if (sig === lastSignature && refs.body.childElementCount) return;
    lastSignature = sig;
    clear(refs.body);
    refs.body.appendChild(renderContent());
  }

  Hack.components.settings = { mount, render, renderContent };
})();