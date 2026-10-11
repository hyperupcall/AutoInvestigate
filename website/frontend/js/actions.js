/* actions.js — all state mutations + orchestration of the mocked backend. */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const { uid } = Hack.util;
  const store = Hack.store;
  const backend = Hack.mockBackend;
  const execBackend = Hack.mockExecution;
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
          subject: res.subject,
          lineage: res.lineage,
          label: res.label,
          level: targetLevel,
          parentIdeaIds: parentIdeaIds || [],
          index,
        });
      });
      showToast(res.ideas.length === 1 ? 'Added 1 idea.' : `Added ${res.ideas.length} ideas.`, 'ok');
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

  /** Level N → level N+1, from the selected ideas in a level (or the whole level). */
  async function generateFromLevel(level, ideaIds) {
    const lvl = state.levels.find((l) => l.level === level);
    if (!lvl) return;

    let ids = ideaIds || state.selectedIdeaIds.filter((id) => lvl.ideas.some((i) => i.id === id));
    if (!ids.length) ids = lvl.ideas.map((i) => i.id); // no selection → iterate the whole level
    if (!ids.length) {
      showToast('No ideas in this level.', 'warn');
      return;
    }
    if (lvl.iteration.type === 'consolidation' && ids.length < 2) {
      showToast('Consolidation needs at least two ideas.', 'warn');
      return;
    }

    const sourceIdeas = ids
      .map((id) => lvl.ideas.find((i) => i.id === id))
      .filter(Boolean)
      .map((i) => ({ text: i.text, lineage: i.lineage, subject: i.subject }));

    await runGeneration({
      sourceIdeas,
      targetLevel: level + 1,
      iteration: lvl.iteration,
      seedText: '',
      parentIdeaIds: ids,
    });
  }

  /* --------------------------- evaluation --------------------------- */

  /** Add one idea to the evaluation queue. Returns false if it is already there. */
  function enqueueIdea(idea) {
    if (!idea) return false;
    if (state.evaluation.queue.some((q) => q.text === idea.text)) return false;
    state.evaluation.queue.push({
      id: uid('queue'),
      text: idea.text,
      level: idea.level,
      sourceIdeaId: idea.id,
      addedAt: Date.now(),
    });
    return true;
  }

  /** Copy an idea from column 1 into the evaluation queue (column 2). */
  function queueIdeaForEvaluation(ideaId) {
    const idea = store.ideaById(ideaId);
    if (!idea) return;
    if (!enqueueIdea(idea)) {
      showToast('Already in the evaluation queue.', 'warn');
      return;
    }
    store.notify();
    showToast('Copied to Idea Evaluation.', 'ok');
  }

  /** Copy the selected ideas in a level (or the whole level) into the queue. */
  function queueLevelForEvaluation(level) {
    const lvl = state.levels.find((l) => l.level === level);
    if (!lvl || !lvl.ideas.length) return;
    let ids = state.selectedIdeaIds.filter((id) => lvl.ideas.some((i) => i.id === id));
    if (!ids.length) ids = lvl.ideas.map((i) => i.id);
    let added = 0;
    for (const id of ids) {
      if (enqueueIdea(lvl.ideas.find((i) => i.id === id))) added += 1;
    }
    store.notify();
    if (added) showToast(added === 1 ? 'Copied 1 idea to Idea Evaluation.' : `Copied ${added} ideas to Idea Evaluation.`, 'ok');
    else showToast('Already in the evaluation queue.', 'warn');
  }

  function removeQueuedIdea(queueId) {
    state.evaluation.queue = state.evaluation.queue.filter((q) => q.id !== queueId);
    store.notify();
  }

  function clearEvaluationQueue() {
    state.evaluation.queue = [];
    store.notify();
  }

  /** Start the deeper research for a queued idea; it moves to the runs list.
   *  `groupIds` (optional) limits the run to those agent groups. */
  function startQueuedEvaluation(queueId, groupIds) {
    const item = state.evaluation.queue.find((q) => q.id === queueId);
    if (!item) return;
    state.evaluation.queue = state.evaluation.queue.filter((q) => q.id !== queueId);
    startEvaluation({ ideaId: item.sourceIdeaId, ideaText: item.text, groupIds });
  }

  function startEvaluation({ ideaId, ideaText, groupIds }) {
    const text = ideaText != null ? ideaText : (store.ideaById(ideaId) || {}).text;
    if (!text) return;
    const selectedGroupIds = Array.isArray(groupIds) && groupIds.length ? groupIds.slice() : null;

    // Build the report up front so the agent cluster is visible immediately;
    // the events then stream in and the report is delivered again on done.
    const report = backend.buildReport(text, selectedGroupIds);

    const run = {
      id: uid('run'),
      ideaId: ideaId || null,
      ideaText: text,
      model: state.settings.evaluationModel,
      status: 'running',
      events: [],
      report,
      cluster: report.groups.map((g) => ({
        id: g.id, name: g.name, style: g.style,
        agents: g.agents.map((a) => ({ id: a.id, name: a.name, model: a.model, question: a.question, who_they_are: a.who_they_are })),
      })),
      // The Evaluation Complex: three stewards watching the swarm in parallel (see modal.js).
      complex: report.complex ? {
        agents: (report.complex.stewards || []).map((s) => ({ id: s.id, name: s.name, model: s.model, objective: s.objective })),
        decision: null, stoppedBy: null, report: null,
      } : null,
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
      ideaText: text,
      groupIds: selectedGroupIds,
      settings: state.settings,
      onEvent(ev) {
        run.events.push(ev);
        run.currentPhase = ev.phase;
        run.currentAgent = ev.agent_id || '';
        if (run.complex) {
          if (ev.kind === 'complex-verdict') run.complex.decision = ev.decision;
          if (ev.kind === 'complex-stop') run.complex.stoppedBy = ev.by;
          if (ev.kind === 'complex-final') {
            run.complex.report = ev.report;
            run.complex.decision = ev.report.decision;
            run.complex.stoppedBy = ev.report.stopped_by;
          }
        }
        store.notify();
      },
      onDone(finalReport) {
        run.status = 'done';
        run.report = finalReport;
        run.finishedAt = Date.now();
        run.currentPhase = 'Complete';
        run.currentAgent = '';
        store.notify();
        showToast('Deeper research complete.', 'ok');
      },
    });

    openModal(run.id, 'cluster');
  }

  function cancelEvaluation(runId) {
    const run = store.runById(runId);
    if (!run || run.status !== 'running') return;
    if (run._handle) run._handle.cancel();
    run.status = 'cancelled';
    run.finishedAt = Date.now();
    store.notify();
    showToast('Research run cancelled.', 'warn');
  }

  /** Force stop: stop the swarm now and write the final verdict from what exists (not a cancel). */
  function forceFinalize(runId) {
    const run = store.runById(runId);
    if (!run || run.status !== 'running') return;
    if (run._handle && run._handle.finalize) run._handle.finalize();
    else if (run.backendRunId && Hack.apiBackend) Hack.apiBackend.forceFinalize(run.backendRunId);
    showToast('Stopping the swarm and writing the verdict…', 'warn');
  }

  /** Hide a run: stop it if it is still running, then drop it from the list. */
  function removeRun(runId) {
    const run = store.runById(runId);
    if (!run) return;
    if (run.status === 'running' && run._handle) run._handle.cancel();
    state.evaluation.runs = state.evaluation.runs.filter((r) => r.id !== runId);
    if (state.evaluation.activeRunId === runId) state.evaluation.activeRunId = null;
    if (state.ui.modal.open && state.ui.modal.runId === runId) state.ui.modal.open = false;
    store.notify();
  }

  /** Hide every finished run, keeping the ones still in progress. */
  function clearFinishedRuns() {
    const finished = state.evaluation.runs.filter((r) => r.status !== 'running');
    if (!finished.length) return;
    const openId = state.ui.modal.open ? state.ui.modal.runId : null;
    state.evaluation.runs = state.evaluation.runs.filter((r) => r.status === 'running');
    if (openId && !state.evaluation.runs.some((r) => r.id === openId)) state.ui.modal.open = false;
    store.notify();
    showToast(finished.length === 1 ? 'Hid 1 finished run.' : `Hid ${finished.length} finished runs.`, 'ok');
  }

  /* ------------------------------ modal ------------------------------ */
  function openModal(runId, tab) {
    state.ui.modal = { open: true, runId, tab: tab || 'cluster', agentSelection: {} };
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

  /** Select which agent's output to show in a group's graph panel. */
  function selectModalAgent(groupId, agentId) {
    if (!state.ui.modal.agentSelection) state.ui.modal.agentSelection = {};
    state.ui.modal.agentSelection[groupId] = agentId;
    store.notify();
  }

  /* --------------------------- execution --------------------------- */

  /** Copy an idea into column 3 (from an evaluation run or an idea row). */
  function sendToExecution({ ideaId, ideaText, title, evaluationRunId }) {
    const text = ideaText != null ? ideaText : (store.ideaById(ideaId) || {}).text;
    if (!text) return;
    state.execution = {
      ideaId: ideaId || null, ideaText: text, title: title || '',
      evaluationRunId: evaluationRunId || null, // lets the factory build from the real evaluation report
      plan: null, job: null, artifacts: [], pending: false, building: false, error: null,
    };
    store.notify();
    showToast('Sent to Idea Execution.', 'ok');
  }

  function clearExecution() {
    state.execution = {
      ideaId: null, ideaText: '', title: '',
      plan: null, job: null, artifacts: [], pending: false, building: false, error: null,
    };
    store.notify();
  }

  /** Create the plan for the chosen idea, then implement it and poll the job. */
  async function buildArtifacts() {
    const ex = state.execution;
    if (!ex.ideaText || ex.pending || ex.building) return;
    ex.pending = true;
    ex.error = null;
    store.notify();
    try {
      const { idea, plan } = await execBackend.createIdea({
        text: ex.ideaText, title: ex.title,
        metadata: ex.evaluationRunId ? { evaluation_run_id: ex.evaluationRunId } : undefined,
        options: { artifacts: ['mvp_prototype'] }, // Execute builds one clickable prototype of the idea
      });
      if (state.execution !== ex) return; // the column was reset while we waited
      ex.plan = plan;
      ex.ideaId = ex.ideaId || idea.id;
      ex.pending = false;
      ex.building = true;
      store.notify();

      const { job } = await execBackend.implementPlan(plan.id);
      if (state.execution !== ex) return;
      ex.job = job;
      store.notify();
      pollJob(ex, plan.id, job.id);
    } catch (err) {
      ex.pending = false;
      ex.building = false;
      ex.error = String((err && err.message) || err);
      store.notify();
      showToast('Could not start the build.', 'error');
    }
  }

  function pollJob(ex, planId, jobId) {
    const tick = async () => {
      if (state.execution !== ex) return; // reset since
      try {
        const job = await execBackend.getJob(jobId);
        if (!job) return;
        ex.job = job;
        if (job.status === 'succeeded' || job.status === 'failed') {
          const plan = await execBackend.getPlan(planId).catch(() => null);
          if (plan) { ex.plan = plan; ex.artifacts = plan.artifacts || []; }
          ex.building = false;
          if (job.status === 'failed') ex.error = job.error || 'Build failed.';
          store.notify();
          showToast(job.status === 'succeeded' ? 'Artifacts built.' : 'Build failed.',
                    job.status === 'succeeded' ? 'ok' : 'error');
          return;
        }
        store.notify();
      } catch (e) { /* transient: keep polling */ }
      setTimeout(tick, 700);
    };
    setTimeout(tick, 400);
  }

  /** Download URL for a built artifact (a data: URL in mock mode). */
  function artifactDownloadUrl(artifactId) {
    return execBackend.artifactUrl(artifactId);
  }

  function artifactViewUrl(artifactId) {
    return execBackend.viewUrl ? execBackend.viewUrl(artifactId) : null;
  }

  /* --------------------------- settings popup --------------------------- */
  function openSettings() {
    state.ui.settingsOpen = true;
    store.notify();
    // Pull the latest backend settings so the popup shows what is actually saved.
    if (Hack.apiBackend && Hack.apiBackend.refreshSettings) Hack.apiBackend.refreshSettings().catch(() => {});
  }

  function closeSettings() {
    state.ui.settingsOpen = false;
    store.notify();
  }

  /* --------------------------- information popup --------------------------- */
  function openInfo() {
    state.ui.infoOpen = true;
    store.notify();
  }

  function closeInfo() {
    state.ui.infoOpen = false;
    store.notify();
  }

  /* --------------------------- run config popup --------------------------- */
  /** Open the per-run group picker for a queued idea (all groups selected by default). */
  function openRunConfig(queueId) {
    const groups = state.settings.groupPerspectives || [];
    state.ui.runConfig = { open: true, queueId, selectedGroupIds: groups.map((g) => g.id) };
    store.notify();
  }

  function closeRunConfig() {
    state.ui.runConfig.open = false;
    store.notify();
  }

  function toggleRunConfigGroup(groupId) {
    const rc = state.ui.runConfig;
    const set = new Set(rc.selectedGroupIds);
    if (set.has(groupId)) set.delete(groupId);
    else set.add(groupId);
    rc.selectedGroupIds = [...set];
    store.notify();
  }

  function setAllRunConfigGroups(selected) {
    const groups = state.settings.groupPerspectives || [];
    state.ui.runConfig.selectedGroupIds = selected ? groups.map((g) => g.id) : [];
    store.notify();
  }

  /** Start the queued run with the groups chosen in the popup. */
  function confirmRunConfig() {
    const rc = state.ui.runConfig;
    if (!rc.open) return;
    const queueId = rc.queueId;
    const groupIds = rc.selectedGroupIds.slice();
    if (!groupIds.length) return; // the popup keeps Start disabled in this case
    rc.open = false;
    store.notify();
    startQueuedEvaluation(queueId, groupIds);
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
    selectLevelIdeas,
    submitSeed,
    generateFromLevel,
    queueIdeaForEvaluation,
    queueLevelForEvaluation,
    removeQueuedIdea,
    clearEvaluationQueue,
    startQueuedEvaluation,
    startEvaluation,
    cancelEvaluation,
    forceFinalize,
    removeRun,
    clearFinishedRuns,
    sendToExecution,
    clearExecution,
    buildArtifacts,
    artifactDownloadUrl,
    artifactViewUrl,
    openModal,
    closeModal,
    setModalTab,
    selectModalAgent,
    openSettings,
    closeSettings,
    openInfo,
    closeInfo,
    openRunConfig,
    closeRunConfig,
    toggleRunConfigGroup,
    setAllRunConfigGroups,
    confirmRunConfig,
    updateSettings,
    addGroupPerspective,
    removeGroupPerspective,
    addAgent,
    removeAgent,
    updateAgent,
    updateGroup,
  };
})();