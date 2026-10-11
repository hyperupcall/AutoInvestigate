/* mock-backend.js — MOCKED backend for BACKEND Code B.
 *
 * Every function here returns fake data after a simulated delay so the UI can be
 * built and demoed without a server. To wire the real backend, replace the bodies
 * of `generateIdeas` and `startEvaluation` with `fetch()` calls to the routes
 * documented by the backend team. The shapes returned here are the contract the
 * UI expects.
 *
 *   generateIdeas(...)   -> Part 1: Idea generation
 *   startEvaluation(...) -> Part 2: Idea evaluation (streams events, then results)
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const { sleep, truncate, makeRng } = Hack.util;
  const D = Hack.mockData;

  /* ================================================================== *
   * Lineage: a standard, human-readable description of how an idea was
   * derived. This is what produces labels like:
   *   "Idea after 1 refinement"
   *   "Idea after 3 variations"
   *   "Idea after combining 2 ideas"
   *   "Idea after 2 variations and 1 combination"
   * ================================================================== */

  function joinClauses(clauses) {
    if (clauses.length === 1) return clauses[0];
    if (clauses.length === 2) return `${clauses[0]} and ${clauses[1]}`;
    return `${clauses.slice(0, -1).join(', ')}, and ${clauses[clauses.length - 1]}`;
  }

  function describeOp(op, lineageLength) {
    switch (op.type) {
      case 'refinement':
        return `${op.count} refinement${op.count > 1 ? 's' : ''}`;
      case 'variation':
        return `${op.count} variation${op.count > 1 ? 's' : ''}`;
      case 'combination':
        // Standalone consolidation reads "combining 2 ideas"; in a chain it
        // reads "1 combination" (matching the spec's examples).
        return lineageLength === 1
          ? `combining ${op.ideaCount || 2} ideas`
          : `${op.count} combination${op.count > 1 ? 's' : ''}`;
      case 'freeform':
        return 'free-form modification';
      default:
        return op.type;
    }
  }

  function describeLineage(lineage) {
    if (!lineage || !lineage.length) return 'Initial idea';
    return 'Idea after ' + joinClauses(lineage.map((op) => describeOp(op, lineage.length)));
  }

  /** Use the deepest source lineage as the base so we don't double-count. */
  function pickBaseLineage(lineages) {
    let best = [];
    for (const lin of lineages) {
      if ((lin || []).length > best.length) best = lin;
    }
    return best.map((op) => ({ ...op }));
  }

  function makeOp(iterationType, sourceIdeas, variationCount) {
    switch (iterationType) {
      case 'variation':
        return { type: 'variation', count: Math.max(1, variationCount || 2) };
      case 'consolidation':
        return { type: 'combination', count: 1, ideaCount: Math.max(2, sourceIdeas.length) };
      case 'freeform':
        return { type: 'freeform', count: 1 };
      case 'refinement':
      default:
        return { type: 'refinement', count: Math.max(1, sourceIdeas.length) };
    }
  }

  function fill(template, vars) {
    return template.replace(/\{(\w+)\}/g, (_, key) => (vars[key] != null ? vars[key] : `{${key}}`));
  }

  function buildIdeaTexts({ iterationType, sourceIdeas, variationCount, freeformPrompt, seedText, rng }) {
    const templates = D.IDEA_TEMPLATES[iterationType] || D.IDEA_TEMPLATES.refinement;
    const sources = sourceIdeas.length ? sourceIdeas : [{ text: seedText || 'the seed idea', lineage: [] }];
    const ideaList = sources.map((s) => truncate(s.text, 90));

    if (iterationType === 'variation') {
      const out = [];
      for (let n = 1; n <= variationCount; n += 1) {
        out.push(fill(rng.pick(templates), {
          n,
          idea: ideaList[0] || ideaList.join('; '),
          market: rng.pick(D.MARKETS),
          twist: rng.pick(D.TWISTS),
        }));
      }
      return out;
    }
    if (iterationType === 'consolidation') {
      return [fill(rng.pick(templates), { ideas: ideaList.join(' + '), bridge: rng.pick(D.BRIDGES) })];
    }
    if (iterationType === 'freeform') {
      return [fill(rng.pick(templates), {
        idea: ideaList.join('; '),
        prompt: freeformPrompt || 'apply the requested modification',
      })];
    }
    return [fill(rng.pick(templates), { idea: ideaList.join('; ') })];
  }

  /* ================================================================== *
   * Part 1 — Idea generation
   * ================================================================== */
  async function generateIdeas({ sourceIdeas = [], iterationType = 'refinement', variationCount = 2, freeformPrompt = '', model, seedText = '' }) {
    // Simulated network + model latency.
    await sleep(900 + Math.random() * 900);

    const seed = seedText || sourceIdeas.map((i) => i.text).join('|') || 'seed';
    const rng = makeRng(seed + '|' + iterationType + '|' + variationCount);
    const baseLineage = pickBaseLineage(sourceIdeas.map((i) => i.lineage || []));
    const op = makeOp(iterationType, sourceIdeas, variationCount);
    const lineage = [...baseLineage, op];
    const texts = buildIdeaTexts({ iterationType, sourceIdeas, variationCount, freeformPrompt, seedText, rng });

    return {
      label: describeLineage(lineage),
      lineage,
      operation: op,
      model: model || 'mock/model',
      ideas: texts.map((text) => ({ text })),
    };
  }

  /* ================================================================== *
   * Part 2 — Idea evaluation (streaming)
   * ================================================================== */

  const REACTIONS = [
    'Reacting to the other groups: I still hold my position, but the market objection is fair.',
    'The research group is being too generous. My concern stands.',
    'I am updating slightly — the strategic-fit argument is stronger than I first credited.',
    'I disagree with the consensus framing. This should stay unresolved.',
    'I can live with a bounded pilot, but only with the guardrails I named.',
    'New information changes things: if the trust boundary is fixed, my objection mostly dissolves.',
  ];

  function pickThought(lens, rng) {
    const pool = D.THOUGHTS[lens];
    return pool ? rng.pick(pool) : 'Considering the idea against my group’s criteria.';
  }

  function buildScript(ideaText, settings) {
    const groups = settings.groupPerspectives;
    const rng = makeRng(ideaText + '|eval');
    const events = [];
    const push = (e) => events.push(Object.assign({ gap: 450 }, e));

    push({ phase: 'Round 1 · Deliberation', kind: 'phase', text: 'Each group forms an independent position. No cross-talk yet.' });
    for (const g of groups) {
      push({ phase: 'Round 1 · Deliberation', kind: 'group-start', group: g.name, text: `${g.name} enters deliberation.` });
      for (const a of g.agents) {
        push({ phase: 'Round 1 · Deliberation', kind: 'thought', group: g.name, agent: a.name, role: a.role, text: pickThought(a.lens, rng), gap: 520 });
      }
    }

    push({ phase: 'Summarization · Pass 1', kind: 'phase', text: 'Condensing each group into pros, cons and scores.' });
    for (const g of groups) {
      push({ phase: 'Summarization · Pass 1', kind: 'summary', group: g.name, text: D.SUMMARIES[g.id] || 'Summary generated.', gap: 600 });
    }

    push({ phase: 'Round 2 · Deliberation', kind: 'phase', text: 'Groups now see each other’s summaries and react.' });
    for (const g of groups) {
      for (const a of g.agents) {
        push({ phase: 'Round 2 · Deliberation', kind: 'thought', group: g.name, agent: a.name, role: a.role, text: rng.pick(REACTIONS), gap: 420 });
      }
    }

    push({ phase: 'Summarization · Pass 2', kind: 'phase', text: 'Second-pass summaries, now informed by cross-group reaction.' });
    for (const g of groups) {
      push({ phase: 'Summarization · Pass 2', kind: 'summary', group: g.name, text: 'Revised — ' + (D.SUMMARIES[g.id] || 'Summary generated.'), gap: 550 });
    }

    push({ phase: 'Stop-or-Go Decision', kind: 'decision', text: 'Deciding whether consensus is even the right outcome.', gap: 900 });
    push({ phase: 'Final Conclusions', kind: 'conclusion', text: 'Writing the final conclusions for each group.', gap: 900 });
    return events;
  }

  const GROUP_METRICS = {
    research: ['Feasibility', 'Scalability', 'Evidence', 'Horizon'],
    pe: ['Tech risk', 'Market', 'Strategic fit', 'Horizon'],
    market: ['Enthusiasm', 'Willingness to pay', 'Trust', 'Adoption'],
  };

  const PROS = {
    research: [
      'Core mechanism is grounded in existing literature',
      'Clear path to a prototype within a quarter',
      'Evaluation harness is buildable with current tooling',
    ],
    pe: [
      'Strong strategic fit with the existing agent runtime',
      'Identifiable enterprise buyer with budget authority',
      'Defensible if the data plane becomes the moat',
    ],
    market: [
      'Power users would adopt it immediately',
      'Founders see it as a viable wedge',
      'Low switching cost for early adopters',
    ],
  };

  const CONS = {
    research: [
      'Evaluation story is thin; claims are hard to falsify',
      'Scale-up cost curve is unfavourable past pilot size',
      'Timeline assumes clean data that does not exist yet',
    ],
    pe: [
      'No clear budget holder identified',
      'Market demand is latent, not urgent',
      'Moat is thin without distribution',
    ],
    market: [
      'Security sign-off blocked by an unclear trust boundary',
      'Procurement cannot forecast the bill',
      'Enterprise needs SSO, audit logs and data residency',
    ],
  };

  function pickN(rng, arr, n) {
    const copy = arr.slice();
    const out = [];
    while (out.length < n && copy.length) out.push(copy.splice(rng.int(0, copy.length - 1), 1)[0]);
    return out;
  }

  function buildResults(ideaText, settings) {
    const rng = makeRng(ideaText + '|results');
    const groups = settings.groupPerspectives.map((g) => {
      const metricKeys = GROUP_METRICS[g.id] || ['Feasibility', 'Market', 'Fit', 'Horizon'];
      const scores = {};
      metricKeys.forEach((k) => { scores[k] = rng.int(3, 9); });
      return {
        id: g.id,
        name: g.name,
        summary: D.SUMMARIES[g.id] || 'Summary generated.',
        pros: pickN(rng, PROS[g.id] || PROS.research, 2 + rng.int(0, 1)),
        cons: pickN(rng, CONS[g.id] || CONS.research, 2 + rng.int(0, 1)),
        scores,
        agents: g.agents.map((a) => ({
          name: a.name,
          role: a.role,
          verdict: rng.pick(['support', 'conditional', 'oppose']),
          quote: pickThought(a.lens, rng),
        })),
      };
    });

    const decision = rng.pick(D.DECISIONS);
    const stopOrGo = {
      decision: decision.decision,
      confidence: rng.int(45, 88) / 100,
      rationale: decision.rationale,
      pros: pickN(rng, [
        'The objections are addressable with scope changes',
        'At least one group sees a credible path to value',
        'The disagreement itself is informative, not noise',
      ], 2),
      cons: pickN(rng, [
        'Groups do not converge on a single recommendation',
        'Key risks remain unresolved without more information',
        'A human decision is required before committing budget',
      ], 2),
    };

    const conclusion =
      `Across ${groups.length} group perspectives the idea "${truncate(ideaText, 70)}" drew a ` +
      `${stopOrGo.decision.toLowerCase()} verdict at ${Math.round(stopOrGo.confidence * 100)}% confidence. ` +
      'The strongest support came from the research and business perspectives; the sharpest resistance came from ' +
      'the market perspective, where security and procurement concerns were not fully answered. ' +
      'Recommended next step: a bounded pilot with the guardrails named during deliberation.';

    return { groups, stopOrGo, conclusion, generatedAt: Date.now() };
  }

  /**
   * startEvaluation — streams agent activity, then delivers final results.
   * Returns a handle with `cancel()` and `durationMs`.
   */
  function startEvaluation({ ideaText, settings, onEvent, onDone }) {
    const events = buildScript(ideaText, settings);
    const totalGap = events.reduce((sum, e) => sum + e.gap, 0);
    const targetMs = Math.min(Math.max(settings.deliberationSeconds || 15, 6), 60) * 1000;
    const scale = targetMs / totalGap;

    const timers = [];
    let cancelled = false;
    let t = 0;
    for (const ev of events) {
      t += ev.gap * scale;
      const delay = t;
      timers.push(setTimeout(() => {
        if (!cancelled) onEvent({ ...ev, ts: Date.now() });
      }, delay));
    }
    const doneDelay = t + 700;
    timers.push(setTimeout(() => {
      if (!cancelled) onDone(buildResults(ideaText, settings));
    }, doneDelay));

    return {
      cancel() { cancelled = true; timers.forEach(clearTimeout); },
      durationMs: doneDelay,
    };
  }

  Hack.mockBackend = {
    generateIdeas,
    startEvaluation,
    describeLineage,
    describeOp,
    buildResults,
  };
})();
