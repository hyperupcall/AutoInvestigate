/* mock-backend.js — MOCKED backend for BACKEND Code B.
 *
 * Every function here returns fake data after a simulated delay so the UI can be
 * built and demoed without a server. To wire the real backend, replace the bodies
 * of `generateIdeas` and `startEvaluation` with `fetch()` calls to the routes
 * documented by the backend team. The shapes returned here are the contract the
 * UI expects.
 *
 *   generateIdeas(...)   -> Part 1: Idea generation
 *   buildReport(...)     -> Part 2: the evaluation report (evaluation-report.schema.json)
 *   startEvaluation(...) -> Part 2: streams cluster events, then delivers the report
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const { sleep, truncate, makeRng, uid } = Hack.util;
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
   * Part 2 — Idea evaluation
   *
   * The report shape is exactly evaluation-report.schema.json. The sample
   * report (js/mock-report.js) is used as the fixture; only the run header is
   * adapted to the idea being evaluated.
   * ================================================================== */

  function cloneReport() {
    return JSON.parse(JSON.stringify(Hack.mockReport));
  }

  /** Build the full evaluation report for an idea. Synchronous so the UI can
   *  show the agent cluster immediately, before any events stream in. */
  function buildReport(ideaText) {
    const report = cloneReport();
    report.generated_at = new Date().toISOString();
    report.run = Object.assign({}, report.run, {
      id: uid('run'),
      idea: ideaText,
      status: 'done',
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    });
    return report;
  }

  /** Flatten the report into the ordered stream of cluster events the UI shows. */
  function buildScript(report) {
    const events = [];
    const push = (e, gap) => events.push(Object.assign({ gap: gap || 320 }, e));

    push({ phase: 'Setup', kind: 'phase', text: 'Opening SLIM groups and registering agents over A2A.' }, 500);
    push({
      phase: 'Setup',
      kind: 'cluster',
      text: `${report.agntcy.slim_groups_opened} SLIM groups opened · transport ${report.agntcy.transport} · protocol ${report.agntcy.protocol}`,
      groups: report.groups.map((g) => ({
        id: g.id, name: g.name, style: g.style,
        agents: g.agents.map((a) => ({ id: a.id, name: a.name, model: a.model, question: a.question, who_they_are: a.who_they_are })),
      })),
    }, 700);

    for (const g of report.groups) {
      push({
        phase: 'Deliberation',
        kind: 'group-start',
        group: g.name,
        groupId: g.id,
        style: g.style,
        text: `${g.name} enters deliberation (${g.style}).`,
      }, 420);

      for (const r of g.rounds) {
        const phase = `Round ${r.round}`;
        push({
          phase, kind: 'round-start', group: g.name, groupId: g.id, round: r.round,
          label: r.label, shared_summaries_before: r.shared_summaries_before,
          text: `${r.label}${r.shared_summaries_before ? ' · all group summaries were shared first' : ''}`,
        }, 360);

        for (const t of r.discussion) {
          push({
            phase, kind: 'turn', group: g.name, groupId: g.id, round: r.round,
            agent_id: t.agent_id, model: t.model, text: t.text,
            turn: t.turn, elapsed_seconds: t.elapsed_seconds,
          }, 380);
        }
        for (const t of r.missed_turns || []) {
          push({ phase, kind: 'missed', group: g.name, groupId: g.id, round: r.round, agent_id: t.agent_id, reason: t.reason }, 220);
        }
        for (const ev of r.evaluations) {
          push({
            phase, kind: 'evaluation', group: g.name, groupId: g.id, round: r.round,
            agent_id: ev.agent_id, model: ev.model, text: ev.text,
            role_verdict: ev.role_verdict, role_scores: ev.role_scores,
            template_verdict: ev.template_verdict, template_scores: ev.template_scores,
            complete: ev.complete,
          }, 420);
        }
        for (const f of r.failed_evaluations || []) {
          push({ phase, kind: 'failed', group: g.name, groupId: g.id, round: r.round, agent_id: f.agent_id, reason: f.reason }, 220);
        }
        if (r.summary) {
          push({ phase, kind: 'summary', group: g.name, groupId: g.id, round: r.round, summary: r.summary }, 560);
        }
      }
    }

    push({ phase: 'Cross-group', kind: 'phase', text: 'Comparing positions across groups.' }, 520);
    push({ phase: 'Cross-group', kind: 'cross-group', cross_group: report.cross_group }, 560);
    push({ phase: 'Stop-or-Go', kind: 'stop-go', stop_go: report.stop_go }, 760);
    push({ phase: 'Verdict', kind: 'verdict', verdict: report.verdict }, 760);
    return events;
  }

  /**
   * startEvaluation — streams cluster activity, then delivers the final report.
   * Returns a handle with `cancel()` and `durationMs`.
   */
  function startEvaluation({ ideaText, settings, onEvent, onDone }) {
    const report = buildReport(ideaText);
    const events = buildScript(report);
    const totalGap = events.reduce((sum, e) => sum + e.gap, 0);
    const targetMs = Math.min(Math.max((settings && settings.deliberationSeconds) || 15, 6), 60) * 1000;
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
      if (!cancelled) onDone(report);
    }, doneDelay));

    return {
      cancel() { cancelled = true; timers.forEach(clearTimeout); },
      durationMs: doneDelay,
    };
  }

  Hack.mockBackend = {
    generateIdeas,
    buildReport,
    startEvaluation,
    describeLineage,
    describeOp,
  };
})();