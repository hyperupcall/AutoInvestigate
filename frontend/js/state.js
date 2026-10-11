/* state.js — single source of truth + tiny pub/sub. Attaches to window.Hack.store */
(function () {
  const Hack = (window.Hack = window.Hack || {});

  const listeners = new Set();

  const state = {
    /* Left column — level 0 seed */
    seed: {
      text: '',
      iterationType: 'refinement', // refinement | variation | consolidation | freeform
      variationCount: 2,
      freeformPrompt: '',
      submitting: false,
    },
    levels: [], // [{ level, ideas, iteration, pending, error }] — one list per level
    selectedIdeaIds: [],

    /* Middle column */
    evaluation: {
      // queue: ideas copied over from column 1, waiting to be evaluated
      //   { id, text, level, sourceIdeaId, addedAt }
      queue: [],
      // run: { id, ideaId, ideaText, model, status, events, report, cluster,
      //        startedAt, finishedAt, currentPhase, currentAgent }
      runs: [],
      activeRunId: null,
    },

    /* Right column */
    execution: {
      // The idea chosen to turn into artifacts (sent from column 2 or column 1).
      ideaId: null,
      ideaText: '',
      title: '',
      // plan: { id, title, idea_text, status, artifact_specs, steps, artifacts }
      // job:  { id, status, artifact_ids, error }
      plan: null,
      job: null,
      artifacts: [],
      pending: false,   // creating the plan
      building: false,  // implementing the plan
      error: null,
    },

    /* Settings (popup) */
    settings: {
      generationModel: 'openai/gpt-4o-mini',
      evaluationModel: 'anthropic/claude-3.5-sonnet',
      summarizerModel: 'google/gemini-2.0-flash',
      deliberationSeconds: 15,
      mode: 'quick', // 'quick' (about a minute) | 'deep' (about 7 minutes)
      promptSet: 'default',
      groupPerspectives: JSON.parse(JSON.stringify(Hack.mockData.GROUP_PERSPECTIVES)),
    },

    /* Transient UI */
    ui: {
      modal: { open: false, runId: null, tab: 'cluster', agentSelection: {} },
      settingsOpen: false,
      toast: null,
    },
  };

  function subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  function notify() {
    for (const fn of listeners) fn(state);
  }

  /* ---------------------------- selectors ---------------------------- */
  function allIdeas() {
    const out = [];
    for (const lvl of state.levels) {
      for (const idea of lvl.ideas) out.push({ ...idea, level: lvl.level });
    }
    return out;
  }

  function ideaById(id) {
    return allIdeas().find((i) => i.id === id) || null;
  }

  function selectedIdeas() {
    return state.selectedIdeaIds.map(ideaById).filter(Boolean);
  }

  function runById(id) {
    return state.evaluation.runs.find((r) => r.id === id) || null;
  }

  Hack.store = { state, subscribe, notify, allIdeas, ideaById, selectedIdeas, runById };
})();
