/* mock-execution.js — MOCKED Artifact Factory backend (column 3 · Idea Execution).
 *
 * Mirrors the real REST API in ../artifactfactory (see its README):
 *
 *   createIdea({ text, title, options }) -> { idea, plan }
 *   implementPlan(planId)                -> { job }   (starts an async build)
 *   getJob(jobId)                        -> job
 *   getPlan(planId)                      -> plan (with joined `artifacts`)
 *   listPlans()                          -> [plan]
 *   artifactUrl(artifactId)              -> a download URL (a data: URL here)
 *
 * api-execution.js swaps these bodies for fetch() calls when the factory is
 * reachable; the shapes returned here are the contract the UI expects. Output is
 * deterministic per idea (seeded PRNG), so the same idea always builds the same
 * artifacts.
 */
(function () {
  const Hack = (window.Hack = window.Hack || {});
  const { sleep, makeRng, uid } = Hack.util;

  const DEFAULT_ARTIFACTS = [
    { type: 'source_repository', params: { language: 'python' } },
    { type: 'npm_package', params: {} },
    { type: 'docker_image', params: {} },
    { type: 'literature_review', params: {} },
    { type: 'tarball', params: {} },
  ];

  const STEP_LABELS = {
    source_repository: 'Scaffold source repository',
    npm_package: 'Scaffold NPM package',
    docker_image: 'Build Docker image manifest',
    literature_review: 'Write literature review',
    tarball: 'Package all artifacts into a tarball',
  };

  const ideas = {};      // id -> idea
  const plans = {};      // id -> plan
  const jobs = {};       // id -> job
  const artifacts = {};  // id -> artifact

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const nowIso = () => new Date().toISOString();

  function slugify(text) {
    const s = String(text || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60);
    return s.replace(/^-+|-+$/g, '') || 'artifact';
  }

  function deriveTitle(idea) {
    const title = (idea.title || '').trim();
    if (title) return title;
    const text = (idea.text || '').trim();
    if (!text) return 'Untitled Idea';
    const first = text.split('.')[0].trim();
    return (first || text).slice(0, 80);
  }

  function buildPlan(idea, options) {
    const title = deriveTitle(idea);
    const name = slugify(title);
    const raw = options && options.artifacts;
    const specs = raw && raw.length
      ? raw.map((r) => (typeof r === 'string' ? { type: r, params: {} } : { type: r.type, params: Object.assign({}, r.params) }))
      : DEFAULT_ARTIFACTS.map((a) => ({ type: a.type, params: Object.assign({}, a.params) }));

    const artifact_specs = specs.map((s) => ({ type: s.type, name, params: s.params, status: 'pending' }));
    const steps = artifact_specs.map((s) => {
      let label = STEP_LABELS[s.type] || `Build ${s.type}`;
      if (s.type === 'source_repository') label += ` (${s.params.language || 'python'})`;
      return label;
    });

    const now = nowIso();
    return {
      id: uid('plan'), idea_id: idea.id, idea_text: idea.text, title,
      status: 'planned', artifact_specs, artifact_ids: [], steps,
      created_at: now, updated_at: now,
    };
  }

  /* File lists per artifact type, mirroring artifactfactory/artifacts.py. */
  function filesFor(type, base, name) {
    switch (type) {
      case 'source_repository': {
        const module = slugify(name).replace(/-/g, '_');
        return [`${base}/README.md`, `${base}/pyproject.toml`, `${base}/src/${module}/__init__.py`,
                `${base}/src/${module}/main.py`, `${base}/tests/test_main.py`];
      }
      case 'npm_package':
        return [`${base}/package.json`, `${base}/index.js`, `${base}/README.md`, `${base}/.npmignore`];
      case 'docker_image':
        return [`${base}/Dockerfile`, `${base}/manifest.json`, `${base}/image.tar`];
      case 'literature_review':
        return [`${base}/literature_review.md`];
      case 'tarball':
        return [`${base}/${name}.tar.gz`];
      default:
        return [`${base}/README.md`];
    }
  }

  function buildArtifact(plan, job, spec) {
    const name = spec.name || slugify(plan.title);
    const base = `plans/${plan.id}/${spec.type}/${name}`;
    return {
      id: uid('artifact'), plan_id: plan.id, job_id: job.id,
      type: spec.type, name, key: base, uri: 'mock://' + base,
      files: filesFor(spec.type, base, name), created_at: nowIso(),
    };
  }

  async function createIdea({ text, title = '', options } = {}) {
    await sleep(400 + Math.random() * 400);
    const idea = {
      id: uid('idea'), text, title, validated: true, metadata: {},
      created_at: nowIso(), plan_id: null,
    };
    const plan = buildPlan(idea, options);
    idea.plan_id = plan.id;
    ideas[idea.id] = idea;
    plans[plan.id] = plan;
    return { idea: clone(idea), plan: clone(plan) };
  }

  async function implementPlan(planId) {
    const plan = plans[planId];
    if (!plan) throw new Error('plan not found');
    const job = {
      id: uid('job'), plan_id: planId, status: 'queued', artifact_ids: [],
      error: null, created_at: nowIso(), started_at: null, finished_at: null,
    };
    jobs[job.id] = job;
    plan.status = 'implementing';
    simulate(job, plan);
    return { job: clone(job) };
  }

  /** Walk the plan's specs, emitting one artifact at a time. */
  function simulate(job, plan) {
    job.status = 'running';
    job.started_at = nowIso();
    const rng = makeRng(plan.idea_text);
    let i = 0;
    const step = () => {
      if (i >= plan.artifact_specs.length) {
        plan.status = 'implemented';
        job.status = 'succeeded';
        job.finished_at = nowIso();
        return;
      }
      const spec = plan.artifact_specs[i];
      const artifact = buildArtifact(plan, job, spec);
      artifacts[artifact.id] = artifact;
      job.artifact_ids.push(artifact.id);
      plan.artifact_ids.push(artifact.id);
      spec.status = 'built';
      spec.artifact_id = artifact.id;
      i += 1;
      setTimeout(step, 300 + rng.int(0, 400));
    };
    setTimeout(step, 300);
  }

  async function getJob(jobId) {
    await sleep(60);
    return jobs[jobId] ? clone(jobs[jobId]) : null;
  }

  async function getPlan(planId) {
    await sleep(60);
    const plan = plans[planId];
    if (!plan) return null;
    const out = clone(plan);
    out.artifacts = plan.artifact_ids.map((id) => artifacts[id]).filter(Boolean).map(clone);
    return out;
  }

  async function listPlans() {
    return Object.values(plans).map(clone);
  }

  /** A data: URL so the download button works offline too. */
  function artifactUrl(artifactId) {
    const a = artifacts[artifactId];
    if (!a) return null;
    const manifest = [
      `Artifact: ${a.name}`,
      `Type: ${a.type}`,
      `Plan: ${a.plan_id}`,
      `Job: ${a.job_id}`,
      '',
      'Files:',
      ...a.files.map((f) => `  - ${f}`),
      '',
      '(Mock artifact — the real Artifact Factory returns the built files.)',
    ].join('\n');
    return 'data:text/plain;charset=utf-8,' + encodeURIComponent(manifest);
  }

  Hack.mockExecution = {
    createIdea, implementPlan, getJob, getPlan, listPlans, artifactUrl,
    DEFAULT_ARTIFACTS,
  };
})();