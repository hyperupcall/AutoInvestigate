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
      // One entry per prototype; several build at the same time.
      //   { id, ideaId, ideaText, title, evaluationRunId, createdAt,
      //     plan, job, artifacts, pending, building, error }
      // plan: { id, title, idea_text, status, artifact_specs, steps, artifacts }
      // job:  { id, status, artifact_ids, error }
      items: [],
    },

    /* Settings (popup) */
    settings: {
      generationModel: 'meta-llama/llama-3.1-8b-instruct',
      evaluationModel: 'openai/gpt-oss-120b',
      summarizerModel: 'google/gemma-3-4b-it',
      deliberationSeconds: 15,
      mode: 'quick', // 'quick' (about a minute) | 'deep' (about 7 minutes)
      promptSet: 'default',
      groupPerspectives: JSON.parse(JSON.stringify(Hack.mockData.GROUP_PERSPECTIVES)),
    },

    /* Transient UI */
    ui: {
      modal: { open: false, runId: null, tab: 'cluster', agentSelection: {} },
      settingsOpen: false,
      infoOpen: false,
      // Per-run group selection, opened from "Start Deeper Research".
      //   { open, queueId, selectedGroupIds: [] }
      runConfig: { open: false, queueId: null, selectedGroupIds: [] },
      // "Create variations" popup (opened from an idea, a level or the seed).
      //   { open, target, resolved, count, loading, error,
      //     items: [{ id, text, selected }], meta, nonce }
      variations: { open: false, target: null, resolved: null, count: 3, loading: false, error: null, items: [], meta: null, nonce: 0 },
      // Artifact popup (opened by clicking a finished prototype in column 3).
      //   { open, itemId }
      artifactModal: { open: false, itemId: null },
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
