/* components/settings.js — the settings form, shown in the Settings popup.
 *
 * When the backend is reachable it renders the backend's real settings (mode,
 * sources, keys, stages, MCP servers, groups and agents) and saves them with
 * PUT /api/settings, so the popup is the one place to configure everything.
 * Without a backend it falls back to the in-memory mock settings (models,
 * prompts, group perspectives). */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  Hack.components = Hack.components || {};
  const { el, clear } = Hack.util;
  const store = Hack.store;
  const actions = Hack.actions;
  const D = Hack.mockData;

  // Only these models may be used (see CHEAP_MODELS.md). One source of truth: model-info.js.
  const MODELS = Hack.modelInfo.MODELS.map((m) => m.id);
  const EFFORTS = [null, 'none', 'minimal', 'low', 'medium', 'high'];
  const STAGES = [
    ['deliberate', 'Discussion turns'],
    ['evaluate', 'Evaluations'],
    ['summarize', 'Summaries'],
    ['judge', 'Stop or go'],
    ['final', 'Final report'],
    ['reality_check', 'Reality check'],
  ];

  /* ------------------------- backend settings draft ------------------------- */
  let draft = null;        // working copy of the backend settings
  let draftSource = null;  // the info.settings object the draft came from
  let draftVersion = 0;    // bumped whenever the draft is rebuilt (so the form re-renders)
  let status = null;       // { ok, text } shown next to Save

  function live() {
    return !!(Hack.backendInfo && Hack.backendInfo.live && Hack.backendInfo.settings);
  }

  function ensureDraft() {
    const S = Hack.backendInfo.settings;
    if (draftSource !== S) {
      draft = JSON.parse(JSON.stringify(S));
      draftSource = S;
      draftVersion += 1;
    }
    return draft;
  }

  /** Called when the popup opens: start from a clean draft and clear the last message. */
  function onOpen() {
    draft = null;
    draftSource = null;
    status = null;
  }

  /* ------------------------------ model options ------------------------------ */
  /** The models offered: the backend's live list when connected, else the cheap set. */
  function modelOptions() {
    const info = Hack.backendInfo;
    const base = info && info.live && info.models && info.models.length
      ? info.models.map((m) => m.id)
      : MODELS.slice();
    if (info && info.live && info.settings) {
      const s = info.settings;
      const configured = s.groups.flatMap((g) => g.agents.map((a) => a.model))
        .concat([s.sources.model, s.stages.summarizer.model, s.stages.judge.model, s.stages.final.model, s.stages.reality_check.model])
        .concat(((s.complex || {}).stewards || []).map((st) => st.model));
      return [...new Set([...base, ...configured.filter(Boolean)])];
    }
    return base;
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

  /* ------------------------------ field builders ------------------------------ */
  function section(title, children) {
    return el('div', { class: 'settings-section' }, [
      el('h3', { class: 'settings-title', text: title }),
      el('div', { class: 'settings-body' }, children),
    ]);
  }

  function field(label, node) {
    return el('div', { class: 'field' }, [el('label', { text: label }), node]);
  }

  function textInput(value, oninput, opts) {
    return el('input', Object.assign({ class: 'text-input', value: value == null ? '' : value, oninput }, opts || {}));
  }

  function numberInput(value, oninput, opts) {
    return el('input', Object.assign({ type: 'number', class: 'num-input', value, oninput }, opts || {}));
  }

  function checkbox(checked, onchange) {
    return el('input', { type: 'checkbox', checked: !!checked, onchange });
  }

  function select(options, value, onchange, cls) {
    return el('select', { class: cls || 'select', onchange },
      options.map((o) => el('option', { value: o.value, text: o.label, selected: o.value === value })));
  }

  function modelSelect(value, onchange, cls) {
    const options = modelOptions();
    if (value && !options.includes(value)) options.unshift(value);
    return el('select', { class: cls || 'select', onchange }, modelOptionNodes(options, value));
  }

  function effortSelect(value, onchange) {
    const options = EFFORTS.map((e) => ({ value: e == null ? '' : e, label: e || 'stage default' }));
    return select(options, value == null ? '' : value, (e) => onchange(e.target.value || null), 'select small');
  }

  function keyInput(value, oninput) {
    return el('input', {
      type: 'password', class: 'text-input', value: value || '', autocomplete: 'off',
      placeholder: value ? 'saved (type to replace)' : 'default key', oninput,
    });
  }

  /* --------------------------- backend settings form --------------------------- */
  function renderGeneral(S) {
    const stages = el('table', { class: 'settings-table' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { text: 'Stage' }), el('th', { text: 'Max tokens per reply' }), el('th', { text: 'Reasoning effort' }),
      ])]),
      el('tbody', {}, STAGES.map(([k, label]) => el('tr', {}, [
        el('td', { text: label }),
        el('td', {}, [numberInput(S.max_tokens[k], (e) => { S.max_tokens[k] = Number(e.target.value); }, { min: 100, max: 16000 })]),
        el('td', {}, [effortSelect(S.reasoning_effort[k], (v) => { S.reasoning_effort[k] = v || 'low'; })]),
      ]))),
    ]);

    return section('General', [
      field('Evaluation mode', select([
        { value: 'quick', label: 'Quick: about a minute (one pass per round, short write-ups)' },
        { value: 'deep', label: 'Deep: about 7 minutes (timed discussions, full write-ups)' },
      ], S.mode, (e) => { S.mode = e.target.value; })),
      el('div', { class: 'field inline' }, [
        el('label', {}, [checkbox(S.sources.enabled, (e) => { S.sources.enabled = e.target.checked; }), ' Give arXiv papers to the groups marked below']),
      ]),
      el('div', { class: 'field-row' }, [
        field('At most (papers)', numberInput(S.sources.max_papers, (e) => { S.sources.max_papers = Number(e.target.value); }, { min: 1, max: 15 })),
        field('Chosen by model', modelSelect(S.sources.model, (e) => { S.sources.model = e.target.value; })),
      ]),
      el('div', { class: 'field-row' }, [
        field('Deliberation seconds (deep mode)', numberInput(S.deliberation_seconds, (e) => { S.deliberation_seconds = Number(e.target.value); }, { min: 5, max: 900 })),
        field('Max cost per evaluation (USD)', numberInput(S.max_cost_usd, (e) => { S.max_cost_usd = Number(e.target.value); }, { min: 0.05, max: 50, step: 0.05 })),
        field('Web search results', numberInput(S.web_search_results, (e) => { S.web_search_results = Number(e.target.value); }, { min: 0, max: 10 })),
      ]),
      stages,
    ]);
  }

  function renderStage(S, key, title) {
    const cfg = S.stages[key];
    return section(title, [
      el('div', { class: 'field-row' }, [
        field('Model', modelSelect(cfg.model, (e) => { cfg.model = e.target.value; })),
        field('API key', keyInput(cfg.api_key, (e) => { cfg.api_key = e.target.value; })),
      ]),
    ]);
  }

  /** The Evaluation Complex: three stewards that watch the swarm in parallel and decide whether it should
   *  continue or stop. They share one goal but optimize for different things (see orchestrator/complex.py). */
  function renderComplex(S) {
    const cx = S.complex || (S.complex = { enabled: true, max_seconds: 300, interval_seconds: 45, stop_votes: 2, stewards: [] });
    const stewards = cx.stewards || (cx.stewards = []);
    return section('Evaluation Complex (three stewards watching the swarm)', [
      el('p', { class: 'muted small', text: 'Three agents run in parallel to the swarm and decide whether it should continue or stop. They share one goal but optimize for different things, so they disagree. When enough vote stop, or the time limit is reached, the swarm stops and writes its verdict.' }),
      el('div', { class: 'field inline' }, [
        el('label', {}, [checkbox(cx.enabled, (e) => { cx.enabled = e.target.checked; }), ' Run the Evaluation Complex alongside the swarm']),
      ]),
      el('div', { class: 'field-row' }, [
        field('Force stop after (seconds)', numberInput(cx.max_seconds, (e) => { cx.max_seconds = Number(e.target.value); }, { min: 30, max: 3600 })),
        field('Re-assess every (seconds)', numberInput(cx.interval_seconds, (e) => { cx.interval_seconds = Number(e.target.value); }, { min: 5, max: 600 })),
        field('Stop votes needed', numberInput(cx.stop_votes, (e) => { cx.stop_votes = Number(e.target.value); }, { min: 1, max: Math.max(1, stewards.length) })),
      ]),
      el('div', { class: 'groups' }, stewards.map((st) => el('div', { class: 'group-card' }, [
        el('div', { class: 'group-head' }, [
          el('span', { class: 'cluster-group-name', text: st.name || st.id }),
          el('span', { class: 'muted small', text: st.objective || '' }),
        ]),
        el('div', { class: 'field-row' }, [
          field('Model', modelSelect(st.model, (e) => { st.model = e.target.value; })),
          field('Reasoning effort', effortSelect(st.reasoning_effort, (v) => { st.reasoning_effort = v || 'low'; })),
          field('API key', keyInput(st.api_key, (e) => { st.api_key = e.target.value; })),
        ]),
        el('p', { class: 'muted small', text: 'Prompt: ' + (st.prompt || '') }),
      ]))),
    ]);
  }

  function renderMcp(S) {
    const m = S.mcp || (S.mcp = { enabled: true, api_key: '', timeout_seconds: 20, max_tool_calls: 2 });
    const keyField = m.api_key_env
      ? field('Smithery API key', el('span', { class: 'muted small', text: 'set in .env (SMITH_API_KEY)' }))
      : field('Smithery API key', keyInput(m.api_key, (e) => { m.api_key = e.target.value; }));
    return section('MCP servers', [
      el('div', { class: 'field inline' }, [
        el('label', {}, [checkbox(m.enabled, (e) => { m.enabled = e.target.checked; }), ' Let agents use their MCP servers (deep mode)']),
      ]),
      el('div', { class: 'field-row' }, [
        keyField,
        field('Timeout (seconds)', numberInput(m.timeout_seconds, (e) => { m.timeout_seconds = Number(e.target.value); }, { min: 1, max: 120 })),
        field('Max tool calls per agent', numberInput(m.max_tool_calls, (e) => { m.max_tool_calls = Number(e.target.value); }, { min: 0, max: 8 })),
      ]),
    ]);
  }

  /** The full MCP server catalog, grouped by category. Moved here from the old
   *  "Configure Agent Groups" popup, which is gone. */
  function renderCatalog() {
    const mcp = Hack.mcpServers || { CATEGORIES: {}, byCategory: () => [] };
    const cats = mcp.CATEGORIES || {};
    const blocks = Object.keys(cats).map((id) => {
      const servers = mcp.byCategory(id);
      if (!servers.length) return null;
      return el('div', { class: 'mcp-cat-block' }, [
        el('h4', { class: 'mcp-cat-title', text: cats[id].name }),
        cats[id].blurb ? el('p', { class: 'muted small', text: cats[id].blurb }) : null,
        el('ul', { class: 'mcp-catalog-list' }, servers.map((s) =>
          el('li', {}, [
            el('a', { href: s.docs, target: '_blank', rel: 'noopener', text: s.name }),
            el('span', { class: 'muted', text: ' — ' + (s.description || '') }),
          ]))),
      ]);
    }).filter(Boolean);
    return section('MCP server catalog', [
      el('p', { class: 'muted small', text: 'Curated from Smithery (Academic Research, Finance, Reasoning). Each agent can use the servers listed under it above; the backend connects to them and offers their tools to the agent.' }),
      el('div', { class: 'mcp-catalog' }, blocks),
    ]);
  }

  function renderAgent(S, g, a) {
    const catalog = S.mcp_catalog || [];
    const have = a.mcp_servers || [];
    const chips = have.map((id) => {
      const srv = catalog.find((x) => x.id === id) || { name: id };
      return el('span', { class: 'chip' }, [
        el('span', { text: srv.name }),
        el('button', {
          class: 'chip-x', type: 'button', title: 'Remove this server', text: '✕',
          onclick: () => { a.mcp_servers = have.filter((x) => x !== id); store.notify(); },
        }),
      ]);
    });
    const addSel = select(catalog.filter((x) => !have.includes(x.id)).map((x) => ({ value: x.id, label: `${x.name} — ${x.category}` })), '', () => {});

    return el('div', { class: 'agent-card' }, [
      el('div', { class: 'agent-card-head' }, [
        textInput(a.name, (e) => { a.name = e.target.value; }),
        modelSelect(a.model, (e) => { a.model = e.target.value; }, 'select small'),
        keyInput(a.api_key, (e) => { a.api_key = e.target.value; }),
        effortSelect(a.reasoning_effort, (v) => { a.reasoning_effort = v; }),
        el('a', {
          class: 'link-btn', target: '_blank', rel: 'noopener', text: (a.prompt || '').split('/').pop(),
          href: (Hack.backendInfo.base || '') + '/api/prompt?path=' + encodeURIComponent(a.prompt),
        }),
        el('button', {
          class: 'icon-btn danger', type: 'button', title: 'Remove agent', text: '✕',
          onclick: () => {
            if (g.agents.length === 1) { status = { ok: false, text: 'A group needs at least one agent.' }; store.notify(); return; }
            g.agents = g.agents.filter((x) => x !== a);
            store.notify();
          },
        }),
      ]),
      el('div', { class: 'agent-mcp' }, [
        el('span', { class: 'mcp-label muted small', text: 'MCP servers' }),
        chips.length ? el('span', { class: 'chips' }, chips) : el('span', { class: 'muted small', text: 'none' }),
        el('span', { class: 'mcp-add-row' }, [
          addSel,
          el('button', {
            class: 'btn small ghost', type: 'button', text: 'Add server',
            onclick: () => { if (addSel.value && !have.includes(addSel.value)) { a.mcp_servers = [...have, addSel.value]; store.notify(); } },
          }),
        ]),
      ]),
    ]);
  }

  function renderGroup(S, g) {
    const used = new Set(S.groups.flatMap((gg) => gg.agents.map((a) => a.id)));
    const lib = (S.archetype_library || []).filter((l) => !used.has(l.id));
    const libSel = lib.length ? select(lib.map((l) => ({ value: l.id, label: l.name })), lib[0].id, () => {}) : null;

    return el('div', { class: 'group-card' }, [
      el('div', { class: 'group-head' }, [
        textInput(g.name, (e) => { g.name = e.target.value; }, { class: 'text-input group-name' }),
        el('span', { class: 'tag', text: `${g.agents.length} agents` }),
      ]),
      el('div', { class: 'field-row' }, [
        field('Discussion style', select([
          { value: 'auto', label: 'automatic (the backend decides per group)' },
          { value: 'converge', label: 'aim for a shared view' },
          { value: 'diverge', label: 'members are not expected to agree' },
        ], g.consensus, (e) => { g.consensus = e.target.value; })),
        el('div', { class: 'field inline' }, [
          el('label', {}, [checkbox(g.use_sources, (e) => { g.use_sources = e.target.checked; }), ' uses arXiv papers']),
        ]),
      ]),
      el('div', { class: 'agents' }, g.agents.map((a) => renderAgent(S, g, a))),
      libSel ? el('div', { class: 'field-row' }, [
        field('Add an agent from the archetype library', libSel),
        el('button', {
          class: 'btn small', type: 'button', text: 'Add',
          onclick: () => {
            const l = lib.find((x) => x.id === libSel.value);
            if (!l) return;
            g.agents.push({ id: l.id, name: l.name, prompt: l.prompt, model: l.model, api_key: '', reasoning_effort: null, mcp_servers: [] });
            store.notify();
          },
        }),
      ]) : null,
    ]);
  }

  async function save(S) {
    try {
      const out = await Hack.apiBackend.saveSettings(S);
      status = out.ok
        ? { ok: true, text: 'Saved. New settings apply to the next evaluation.' }
        : { ok: false, text: 'Not saved: ' + (out.errors || []).join('; ') };
      if (out.ok) await Hack.apiBackend.refreshSettings();
    } catch (e) {
      status = { ok: false, text: 'Could not save: ' + e.message };
    }
    store.notify();
  }

  async function reset() {
    if (!window.confirm('Reset every setting, including saved keys, to the defaults?')) return;
    try {
      await Hack.apiBackend.resetSettings();
      await Hack.apiBackend.refreshSettings();
      status = { ok: true, text: 'Reset to defaults.' };
    } catch (e) {
      status = { ok: false, text: 'Could not reset: ' + e.message };
    }
    store.notify();
  }

  function renderBackend() {
    const S = ensureDraft();
    const wrap = el('div', { class: 'settings-content' });
    wrap.appendChild(el('p', { class: 'muted small' }, [
      'These are the backend settings; Save applies to the next evaluation.',
    ]));
    wrap.appendChild(renderGeneral(S));
    wrap.appendChild(renderStage(S, 'summarizer', 'Summarizer (pros and cons per group)'));
    wrap.appendChild(renderStage(S, 'judge', 'Stop-or-go judge'));
    wrap.appendChild(renderStage(S, 'final', 'Final report writer (the comprehensive verdict)'));
    wrap.appendChild(renderStage(S, 'reality_check', 'Reality check (does the idea make sense, before the groups run)'))
    wrap.appendChild(renderComplex(S));
    wrap.appendChild(renderMcp(S));
    wrap.appendChild(section('Group perspectives', [
      el('div', { class: 'groups' }, S.groups.map((g) => renderGroup(S, g))),
    ]));
    wrap.appendChild(renderCatalog());
    wrap.appendChild(el('div', { class: 'settings-actions' }, [
      el('button', { class: 'btn primary', type: 'button', text: 'Save settings', onclick: () => save(S) }),
      el('button', { class: 'btn ghost', type: 'button', text: 'Reset to defaults', onclick: () => reset() }),
      status ? el('span', { class: 'settings-status ' + (status.ok ? 'ok' : 'err'), text: status.text }) : null,
    ]));
    return wrap;
  }

  /* --------------------------- mock settings form --------------------------- */
  function modelField(label, key, value) {
    const options = modelOptions();
    if (value && !options.includes(value)) options.unshift(value);
    return el('div', { class: 'field' }, [
      el('label', { text: label }),
      el('select', { class: 'select', onchange: (e) => { store.state.settings[key] = e.target.value; } },
        modelOptionNodes(options, value)),
    ]);
  }

  function renderMockGroup(group) {
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
      el('div', { class: 'agents' }, group.agents.map((agent) => el('div', { class: 'agent-row' }, [
        el('input', { class: 'text-input', value: agent.name, placeholder: 'Name', oninput: (e) => { agent.name = e.target.value; } }),
        el('input', { class: 'text-input', value: agent.role, placeholder: 'Role', oninput: (e) => { agent.role = e.target.value; } }),
        el('select', { class: 'select small', onchange: (e) => { agent.model = e.target.value; } },
          modelOptionNodes(modelOptions(), agent.model)),
        el('button', { class: 'icon-btn danger', title: 'Remove agent', text: '✕', onclick: () => actions.removeAgent(group.id, agent.id) }),
      ]))),
      el('button', { class: 'btn small ghost', text: '+ Add agent', onclick: () => actions.addAgent(group.id) }),
    ]);
  }

  function renderMock() {
    const s = store.state.settings;
    const wrap = el('div', { class: 'settings-content' });
    wrap.appendChild(el('p', { class: 'muted small', text: 'No backend connected: these settings are in-memory only. Start the backend to configure models, keys, groups and MCP servers.' }));

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

    wrap.appendChild(section('Group perspectives', [
      el('div', { class: 'groups' }, s.groupPerspectives.map(renderMockGroup)),
      el('button', { class: 'btn small', text: '+ Add group perspective', onclick: () => actions.addGroupPerspective() }),
    ]));

    wrap.appendChild(renderCatalog());

    return wrap;
  }

  /* ------------------------------ entry points ------------------------------ */
  function renderContent() {
    return live() ? renderBackend() : renderMock();
  }

  /** Rebuild the form only when the structure (groups/agents/MCP) or the message changes,
   *  so live evaluation events never steal focus from an input mid-typing. */
  function signature() {
    if (live()) {
      const S = ensureDraft();
      const structure = S.groups.map((g) => g.id + ':' + g.agents.map((a) => a.id + '[' + (a.mcp_servers || []).join(',') + ']').join(',')).join('|');
      return 'live|' + draftVersion + '|' + structure + '|' + (status ? status.text : '');
    }
    const g = store.state.settings.groupPerspectives;
    return 'mock|' + g.map((x) => x.id + ':' + x.agents.map((a) => a.id).join(',')).join('|');
  }

  Hack.components.settings = { renderContent, signature, onOpen };
})();