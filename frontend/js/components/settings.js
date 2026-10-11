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

  const MODELS = [
    'openai/gpt-4o',
    'openai/gpt-4o-mini',
    'anthropic/claude-3.5-sonnet',
    'google/gemini-2.0-flash',
    'meta-llama/llama-3.1-70b-instruct',
    'jev/typesafe-eval',
    'openrouter/auto',
  ];

  /** Real model list when the backend is connected: the configured models, the Jev router, then the cheapest. */
  function modelOptions() {
    const info = Hack.backendInfo;
    if (!info || !info.live || !info.settings) return MODELS.slice();
    const s = info.settings;
    const configured = s.groups.flatMap((g) => g.agents.map((a) => a.model)).concat([s.stages.summarizer.model, s.stages.judge.model]);
    const cheap = (info.models || []).filter((m) => !m.variable_price && !m.expires).slice(0, 40).map((m) => m.id);
    return [...new Set([...configured, 'typesafe/jev-router', ...cheap])];
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
      }, options.map((m) => el('option', { value: m, text: m, selected: m === value }))),
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
        modelOptions().map((m) => el('option', { value: m, text: m, selected: m === agent.model }))),
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

    wrap.appendChild(section('Models', [
      modelField('Generation model', 'generationModel', s.generationModel),
      modelField('Evaluation model', 'evaluationModel', s.evaluationModel),
      modelField('Summarizer model', 'summarizerModel', s.summarizerModel),
      el('div', { class: 'field inline' }, [
        el('label', { text: 'Deliberation (seconds)' }),
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