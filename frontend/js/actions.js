/* actions.js — all state mutations + orchestration of the mocked backend. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const { uid } = Hack.util;
  const store = Hack.store;
  const backend = Hack.mockBackend;
  const state = store.state;

  /* ------------------------------ helpers ------------------------------ */
  let toastTimer = null;
  function showToast(message, kind) {
    state.ui.toast = { message, kind: kind || 'info', id: uid('toast') };
    store.notify();
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      state.ui.toast = null;
      store.notify();
    }, 3200);
  }

  /* -------------------------------- seed -------------------------------- */
  function setSeed(patch) {
    Object.assign(state.seed, patch);
    store.notify();
  }

  /* ---------------------------- selection ---------------------------- */
  function toggleIdeaSelection(id) {
    const idx = state.selectedIdeaIds.indexOf(id);
    if (idx === -1) state.selectedIdeaIds.push(id);
    else state.selectedIdeaIds.splice(idx, 1);
    store.notify();
  }

  function clearSelection() {
    state.selectedIdeaIds = [];
    store.notify();
  }

  function selectOnly(id) {
    state.selectedIdeaIds = [id];
    store.notify();
  }

  function selectLevelIdeas(level) {
    const lvl = state.levels.find((l) => l.level === level);
    if (!lvl) return;
    const ids = lvl.ideas.map((i) => i.id);
    const allSelected = ids.every((id) => state.selectedIdeaIds.includes(id));
    if (allSelected) {
      state.selectedIdeaIds = state.selectedIdeaIds.filter((id) => !ids.includes(id));
    } else {
      for (const id of ids) if (!state.selectedIdeaIds.includes(id)) state.selectedIdeaIds.push(id);
    }
    store.notify();
  }

  /* ---------------------------- generation ---------------------------- */
  function ensureLevel(level) {
    let lvl = state.levels.find((l) => l.level === level);
    if (!lvl) {
      lvl = {
        level,
        ideas: [],
        iteration: { type: 'refinement', variationCount: 2, freeformPrompt: '' },
        pending: 0,
        error: null,
      };
      state.levels.push(lvl);
      state.levels.sort((a, b) => a.level - b.level);
    }
    return lvl;
  }

  function setLevelIteration(level, patch) {
    const lvl = ensureLevel(level);
    Object.assign(lvl.iteration, patch);
    store.notify();
  }

  /** Shared generation routine. Appends results to the target level's list. */
  async function runGeneration({ sourceIdeas, targetLevel, iteration, seedText, parentIdeaIds }) {
    const lvl = ensureLevel(targetLevel);
    lvl.pending += 1;
    lvl.error = null;
    store.notify();

    try {
      const res = await backend.generateIdeas({
        sourceIdeas,
        iterationType: iteration.type,
        variationCount: iteration.variationCount,
        freeformPrompt: iteration.freeformPrompt,
        model: state.settings.generationModel,
        seedText: seedText || '',
      });

      res.ideas.forEach((idea, index) => {
        lvl.ideas.push({
          id: uid('idea'),
          text: idea.text,
          lineage: res.lineage,
          label: res.label,
          level: targetLevel,
          parentIdeaIds: parentIdeaIds || [],
          index,
        });
      });
      showToast(`Added: ${res.label}`, 'ok');
    } catch (err) {
      lvl.error = String((err && err.message) || err);
      showToast('Generation failed (mock).', 'error');
    } finally {
      lvl.pending -= 1;
      store.notify();
    }
  }

  /** Level 0 → level 1, from the seed box. */
  async function submitSeed() {
    if (state.seed.submitting) return;
    const text = state.seed.text.trim();
    if (!text) {
      showToast('Enter a seed idea first.', 'warn');
      return;
    }
    state.seed.submitting = true;
    store.notify();
    try {
      await runGeneration({
        sourceIdeas: [],
        targetLevel: 1,
        iteration: {
          type: state.seed.iterationType,
          variationCount: state.seed.variationCount,
          freeformPrompt: state.seed.freeformPrompt,
        },
        seedText: text,
        parentIdeaIds: [],
      });
    } finally {
      state.seed.submitting = false;
      store.notify();
    }
  }

  /** Level N → level N+1, from the selected (or given) ideas in a level. */
  async function generateFromLevel(level, ideaIds) {
    const lvl = state.levels.find((l) => l.level === level);
    if (!lvl) return;

    const ids = ideaIds || state.selectedIdeaIds.filter((id) => lvl.ideas.some((i) => i.id === id));
    if (!ids.length) {
      showToast('Select at least one idea in this level.', 'warn');
      return;
    }
    if (lvl.iteration.type === 'consolidation' && ids.length < 2) {
      showToast('Consolidation needs at least two ideas.', 'warn');
      return;
    }

    const sourceIdeas = ids
      .map((id) => lvl.ideas.find((i) => i.id === id))
      .filter(Boolean)
      .map((i) => ({ text: i.text, lineage: i.lineage }));

    await runGeneration({
      sourceIdeas,
      targetLevel: level + 1,
      iteration: lvl.iteration,
      seedText: '',
      parentIdeaIds: ids,
    });
  }

  /** Iterate a single idea on its own, using the level's iteration type. */
  async function iterateIdea(level, ideaId) {
    const lvl = state.levels.find((l) => l.level === level);
    if (!lvl) return;
    if (lvl.iteration.type === 'consolidation') {
      showToast('Consolidation needs multiple ideas — select them and use Generate.', 'warn');
      return;
    }
    await generateFromLevel(level, [ideaId]);
  }

  /* --------------------------- evaluation --------------------------- */
  function startEvaluation(ideaId) {
    const idea = store.ideaById(ideaId);
    if (!idea) return;

    const run = {
      id: uid('run'),
      ideaId,
      ideaText: idea.text,
      model: state.settings.evaluationModel,
      status: 'running',
      events: [],
      results: null,
      startedAt: Date.now(),
      finishedAt: null,
      currentPhase: 'Starting…',
      currentAgent: '',
      _handle: null,
    };
    state.evaluation.runs.unshift(run);
    state.evaluation.activeRunId = run.id;
    store.notify();

    run._handle = backend.startEvaluation({
      ideaText: idea.text,
      settings: state.settings,
      onEvent(ev) {
        run.events.push(ev);
        run.currentPhase = ev.phase;
        run.currentAgent = ev.agent || '';
        store.notify();
      },
      onDone(results) {
        run.status = 'done';
        run.results = results;
        run.finishedAt = Date.now();
        run.currentPhase = 'Complete';
        run.currentAgent = '';
        store.notify();
        showToast('Deeper research complete.', 'ok');
      },
    });

    openModal(run.id, 'thinking');
  }

  function cancelEvaluation(runId) {
    const run = store.runById(runId);
    if (!run || run.status !== 'running') return;
    if (run._handle) run._handle.cancel();
    run.status = 'cancelled';
    run.finishedAt = Date.now();
    store.notify();
  }

  /* ------------------------------ modal ------------------------------ */
  function openModal(runId, tab) {
    state.ui.modal = { open: true, runId, tab: tab || 'thinking' };
    store.notify();
  }

  function closeModal() {
    state.ui.modal.open = false;
    store.notify();
  }

  function setModalTab(tab) {
    state.ui.modal.tab = tab;
    store.notify();
  }

  /* --------------------------- settings popup --------------------------- */
  function openSettings() {
    state.ui.settingsOpen = true;
    store.notify();
  }

  function closeSettings() {
    state.ui.settingsOpen = false;
    store.notify();
  }

  /* ----------------------------- settings ----------------------------- */
  function updateSettings(patch) {
    Object.assign(state.settings, patch);
    store.notify();
  }

  function addGroupPerspective() {
    state.settings.groupPerspectives.push({
      id: uid('group'),
      name: 'New Group Perspective',
      blurb: 'Describe who these agents are and what they care about.',
      agents: [{ id: uid('agent'), name: 'Agent 1', role: 'Analyst', lens: 'stage', model: state.settings.evaluationModel }],
    });
    store.notify();
  }

  function removeGroupPerspective(groupId) {
    state.settings.groupPerspectives = state.settings.groupPerspectives.filter((g) => g.id !== groupId);
    store.notify();
  }

  function addAgent(groupId) {
    const group = state.settings.groupPerspectives.find((g) => g.id === groupId);
    if (!group) return;
    group.agents.push({ id: uid('agent'), name: `Agent ${group.agents.length + 1}`, role: 'Analyst', lens: 'stage', model: state.settings.evaluationModel });
    store.notify();
  }

  function removeAgent(groupId, agentId) {
    const group = state.settings.groupPerspectives.find((g) => g.id === groupId);
    if (!group) return;
    group.agents = group.agents.filter((a) => a.id !== agentId);
    store.notify();
  }

  function updateAgent(groupId, agentId, patch) {
    const group = state.settings.groupPerspectives.find((g) => g.id === groupId);
    if (!group) return;
    const agent = group.agents.find((a) => a.id === agentId);
    if (!agent) return;
    Object.assign(agent, patch);
    store.notify();
  }

  function updateGroup(groupId, patch) {
    const group = state.settings.groupPerspectives.find((g) => g.id === groupId);
    if (!group) return;
    Object.assign(group, patch);
    store.notify();
  }

  Hack.actions = {
    showToast,
    setSeed,
    toggleIdeaSelection,
    clearSelection,
    selectOnly,
    selectLevelIdeas,
    setLevelIteration,
    submitSeed,
    generateFromLevel,
    iterateIdea,
    startEvaluation,
    cancelEvaluation,
    openModal,
    closeModal,
    setModalTab,
    openSettings,
    closeSettings,
    updateSettings,
    addGroupPerspective,
    removeGroupPerspective,
    addAgent,
    removeAgent,
    updateAgent,
    updateGroup,
  };
})();