/* mock-data.js — static fixtures for the mocked backend.
 * Everything here is fake data used to make the UI feel alive without a server.
 * When wiring the real backend, this file is only needed for defaults. */
(function () {
  const Hack = (window.Hack = window.Hack || {});

  /* ------------------------------------------------------------------ *
   * Group perspectives (BACKEND Code B · Part 2 defaults)
   * ------------------------------------------------------------------ */
  const GROUP_PERSPECTIVES = [
    {
      id: 'research',
      name: 'Professional Research Group',
      blurb: 'Research professionals assessing stage, feasibility and scale-up path.',
      agents: [
        { id: 'r1', name: 'Dr. Ada Reyes', role: 'Research Stage Analyst', lens: 'stage', model: 'anthropic/claude-3.5-sonnet' },
        { id: 'r2', name: 'Prof. Kenji Nakamura', role: 'Scalability Assessor', lens: 'scale', model: 'anthropic/claude-3.5-sonnet' },
        { id: 'r3', name: 'Dr. Priya Anand', role: 'Feasibility & Timeline Lead', lens: 'feasibility', model: 'openai/gpt-4o' },
        { id: 'r4', name: 'Dr. Marcus Webb', role: 'Long-horizon Impact Analyst', lens: 'horizon', model: 'openai/gpt-4o' },
      ],
    },
    {
      id: 'pe',
      name: 'Private Equity / Business',
      blurb: 'Partners positioning the idea to maximise returns.',
      agents: [
        { id: 'p1', name: 'Elena Voss', role: 'Tech Risk Partner', lens: 'techRisk', model: 'anthropic/claude-3.5-sonnet' },
        { id: 'p2', name: 'David Okafor', role: 'Market Partner', lens: 'market', model: 'openai/gpt-4o' },
        { id: 'p3', name: 'Sofia Marchetti', role: 'Strategic Fit Partner', lens: 'strategicFit', model: 'openai/gpt-4o' },
        { id: 'p4', name: 'James Whitfield', role: 'Horizon Partner', lens: 'horizon', model: 'anthropic/claude-3.5-sonnet' },
      ],
    },
    {
      id: 'market',
      name: 'Market Reaction',
      blurb: 'The people you are trying to serve. They rarely agree.',
      agents: [
        { id: 'm1', name: 'Priya · Power User', role: 'Senior SRE', lens: 'powerUser', model: 'openai/gpt-4o-mini' },
        { id: 'm2', name: 'Tom · Free-tier', role: 'Hobbyist Developer', lens: 'freeTier', model: 'openai/gpt-4o-mini' },
        { id: 'm3', name: 'Karen · Enterprise Buyer', role: 'VP Engineering', lens: 'enterprise', model: 'openai/gpt-4o' },
        { id: 'm4', name: 'Ahmed · Security Lead', role: 'CISO Office', lens: 'security', model: 'anthropic/claude-3.5-sonnet' },
        { id: 'm5', name: 'Lena · Founder', role: 'Seed-stage Founder', lens: 'founder', model: 'openai/gpt-4o-mini' },
      ],
    },
  ];

  /* Extra archetypes the settings page can pull from. */
  const CUSTOMER_ARCHETYPES = [
    { id: 'powerUser', name: 'Priya · Power User', role: 'Senior SRE', lens: 'powerUser' },
    { id: 'freeTier', name: 'Tom · Free-tier', role: 'Hobbyist Developer', lens: 'freeTier' },
    { id: 'enterprise', name: 'Karen · Enterprise Buyer', role: 'VP Engineering', lens: 'enterprise' },
    { id: 'security', name: 'Ahmed · Security Lead', role: 'CISO Office', lens: 'security' },
    { id: 'founder', name: 'Lena · Founder', role: 'Seed-stage Founder', lens: 'founder' },
    { id: 'platform', name: 'Marco · Platform Engineer', role: 'Cloud Platform Team', lens: 'platform' },
    { id: 'procurement', name: 'Grace · Procurement', role: 'IT Procurement', lens: 'procurement' },
    { id: 'compliance', name: 'Yusuf · Compliance', role: 'Regulatory Affairs', lens: 'compliance' },
    { id: 'student', name: 'Nia · Student', role: 'CS Undergrad', lens: 'student' },
    { id: 'researcher', name: 'Dr. Hana · Researcher', role: 'Applied ML Researcher', lens: 'researcher' },
  ];

  /* ------------------------------------------------------------------ *
   * Prompt presets (BACKEND Code B: prompts live on the filesystem)
   * ------------------------------------------------------------------ */
  const PROMPT_PRESETS = [
    { id: 'default', name: 'default.md', description: 'Balanced deliberation + pros/cons + feasibility scores.' },
    { id: 'aggressive', name: 'aggressive-skeptic.md', description: 'Adversarial: agents actively try to falsify the idea.' },
    { id: 'optimistic', name: 'optimistic-builder.md', description: 'Constructive: agents assume the idea works and find the best path.' },
    { id: 'strategic', name: 'strategic-fit.md', description: 'Weighted toward strategic fit.' },
    { id: 'investor', name: 'investor-memo.md', description: 'Output shaped like an investment memo with a clear recommendation.' },
  ];

  /* ------------------------------------------------------------------ *
   * Idea text templates, keyed by iteration type.
   * ------------------------------------------------------------------ */
  const MARKETS = [
    'regulated EU enterprise', 'US federal / public sector', 'developer tooling',
    'mid-market SaaS', 'edge / telco', 'defence & critical infrastructure',
    'healthcare compliance', 'open-source community',
  ];
  const TWISTS = [
    'trading breadth for a single sharp use-case',
    'moving the heavy compute to the edge',
    'wrapping it as a managed service with a usage-based price',
    'shipping it as an open-core library first',
    'making the audit trail the headline feature',
    'collapsing three steps into one opinionated workflow',
  ];
  const BRIDGES = [
    'the first idea supplies the data plane and the second supplies the policy engine',
    'the shared substrate is a single agent runtime that both ideas can plug into',
    'the combined system turns a one-off tool into a continuous feedback loop',
    'one idea becomes the ingestion layer and the other becomes the reasoning layer',
  ];

  const IDEA_TEMPLATES = {
    refinement: [
      'Refined concept: {idea} — narrowed to a concrete MVP with a defined technical milestone, validated against existing open-source prior art and near-term demand.',
      'Sharpened: {idea}. Scope reduced to a single deployable component; success measured as a measurable reduction in operator toil.',
      'Hardened: {idea}. The vague ambition is replaced with a specific buyer, a specific workflow, and a specific first deliverable.',
    ],
    variation: [
      'Variation {n}: {idea} — repositioned for the {market} market, {twist}.',
      'Variation {n}: {idea} — same core mechanism, but {twist} to serve {market}.',
      'Variation {n}: {idea} — a narrower cut aimed at {market}, {twist}.',
    ],
    combination: [
      'Consolidated: {ideas} — a unified system where {bridge}.',
      'Merged: {ideas} — the combined idea keeps the strongest part of each and drops the overlap.',
    ],
    freeform: [
      'Modified: {idea} — {prompt}',
      'Adjusted: {idea} — {prompt} (applied as a free-form constraint).',
    ],
  };

  /* ------------------------------------------------------------------ *
   * Agent "thinking" templates, keyed by lens.
   * ------------------------------------------------------------------ */
  const THOUGHTS = {
    stage: [
      'Stage check: this reads as applied research, not a product yet. The core mechanism is plausible but unproven at scale.',
      'I would place this at TRL 3–4. There is a path to a prototype, but the evaluation story is thin.',
      'The idea conflates a research question with an engineering deliverable. Split them before funding.',
    ],
    scale: [
      'Scale-up is the real risk: it works in a lab, but the cost curve turns unfavourable past roughly 10k concurrent users.',
      'Nothing here blocks horizontal scaling, but the data plane will need re-architecting before it is multi-tenant.',
      'I can see a path to scale only if the dependency on a single upstream vendor is removed.',
    ],
    feasibility: [
      'A credible prototype is 6–8 weeks with two engineers. A production-grade version is a different conversation.',
      'The hard part is not the model, it is the evaluation harness. Budget for that explicitly.',
      'Feasible, but the timeline assumes clean data. Real customer data will add a quarter.',
    ],
    horizon: [
      'Near-term payoff is weak, but this compounds: every deployment generates the training signal for the next one.',
      'This is a 3–5 year bet dressed up as a quarterly deliverable. Be honest about that.',
      'The long-term option value is high even if the first version is unremarkable.',
    ],
    techRisk: [
      'Technical risk is moderate: the mechanism is proven in adjacent systems, but integration risk is high.',
      'I would avoid this as-is. The failure mode is silent and expensive to detect.',
      'The risk is acceptable only if we can fall back to a deterministic path when the model is wrong.',
    ],
    market: [
      'There is a clear buyer here, but the budget line is unclear. Who signs the cheque?',
      'Demand is real but latent. This needs a wedge that creates urgency.',
      'The market is crowded at the top and empty at the bottom. The bottom is where this wins.',
    ],
    strategicFit: [
      'This builds naturally on the existing agent runtime and the existing telemetry surface.',
      'Weak fit as stated. Reframe it around the network data plane and it becomes strategic.',
      'Strong fit: it extends an existing control point rather than creating a new silo.',
    ],
    powerUser: [
      'I would try this once. I would not pay for it unless it saves me more than two hours a week.',
      'Give me a CLI and an API and I am in. Give me a dashboard and I am out.',
      'The defaults matter more than the features. If the defaults are wrong I will never get to the features.',
    ],
    freeTier: [
      'If the free tier is generous I will use it forever and never convert. That is a feature, not a bug.',
      'I will absolutely abuse this. Rate limits need to be honest or I will find the edge.',
      'I like it, but I will not put a credit card in until I have hit the wall at least twice.',
    ],
    enterprise: [
      'I cannot deploy this without SSO, audit logs and a data-residency story. Those are table stakes.',
      'The value is obvious; the procurement path is not. I need a security questionnaire answered.',
      'I would pilot this with one team, but I will not standardise on it for a year.',
    ],
    security: [
      'Threat model first. What happens when the agent is prompt-injected with hostile data?',
      'I am not signing off until the data flow is documented and the blast radius is bounded.',
      'The idea is fine; the trust boundary is not. Fix that and I stop objecting.',
    ],
    founder: [
      'This is a great wedge but a bad company on its own. It is a feature inside something bigger.',
      'I would build this in a weekend and see if anyone asks for more. Cheap to test.',
      'The moat is thin. Whoever has the distribution wins, and that is probably not us.',
    ],
    platform: [
      'Operationally this is another thing to run. Show me the SLO and the on-call story.',
      'If it does not fit the existing deployment pipeline it will not get adopted internally.',
      'I like it if it is a library. I dislike it if it is a service I have to babysit.',
    ],
    procurement: [
      'What is the unit of pricing? If I cannot forecast the bill I cannot approve it.',
      'We already have three tools that overlap with this. Consolidation is the only way in.',
      'The licensing model matters more than the technology here.',
    ],
    compliance: [
      'Data residency and retention are the blockers. Everything else is negotiable.',
      'If personal data touches this, we need a DPIA before any pilot.',
      'The audit trail is the product as far as I am concerned.',
    ],
    student: [
      'This is genuinely cool and I would use it for coursework immediately.',
      'I do not have budget, but I have time and I will tell everyone if it is good.',
      'The docs are the whole experience for me. If they are bad I bounce.',
    ],
    researcher: [
      'The interesting question is buried. Surface it and this becomes publishable.',
      'I would want a baseline comparison before believing any of the claims.',
      'The method is sound but the evaluation is not. That is fixable.',
    ],
  };

  const SUMMARIES = {
    research: 'The group is cautiously positive on the core mechanism but split on readiness. Two agents see a credible prototype path; two argue the evaluation story is too thin to fund at scale.',
    pe: 'The partners see a real but narrow opportunity. Tech risk is acceptable, market demand is latent rather than urgent, and strategic fit is strong only if reframed around the network data plane.',
    market: 'Reaction is genuinely mixed and does not converge. Power users and founders are enthusiastic; enterprise, security and procurement raise hard blockers that the idea does not yet answer.',
  };

  const DECISIONS = [
    {
      decision: 'GO',
      rationale: 'The disagreement is productive rather than fatal: the objections are all addressable with scope changes, and the strategic fit is strong enough to justify a bounded pilot.',
    },
    {
      decision: 'KEEP DISAGREEMENT',
      rationale: 'The groups are not converging, and forcing consensus would hide the real signal. The market and security objections are legitimate and unresolved; keep the disagreement and hand it to a human.',
    },
    {
      decision: 'STOP',
      rationale: 'The technical risk and the absence of a clear budget holder outweigh the upside. The idea is interesting but not investable in its current form.',
    },
  ];

  Hack.mockData = {
    GROUP_PERSPECTIVES,
    CUSTOMER_ARCHETYPES,
    PROMPT_PRESETS,
    IDEA_TEMPLATES,
    THOUGHTS,
    SUMMARIES,
    DECISIONS,
    MARKETS,
    TWISTS,
    BRIDGES,
  };
})();
