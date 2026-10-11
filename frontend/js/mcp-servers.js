/* mcp-servers.js — the MCP servers an agent can use, and which agent gets which.
 *
 * Curated from Smithery (https://smithery.ai/servers) across three categories:
 * Academic Research, Finance and Reasoning. Each agent carries `mcp_servers`
 * (ids from this catalog); the backend connects to those servers and offers
 * their tools to the agent's model (see backend/council/mcp.py). This file is
 * the display source of truth; when the backend is live it serves the same
 * catalog in /api/settings (see api-backend.js).
 *
 * `docs` is the Smithery page (safe to open); `url` is the MCP endpoint the
 * backend connects to. */
(function () {
  const Hack = (window.Hack = window.Hack || {});

  const CATEGORIES = {
    academic_research: { id: 'academic_research', name: 'Academic Research', blurb: 'Papers, citations and scholarly search.' },
    finance: { id: 'finance', name: 'Finance', blurb: 'Market data, financial reasoning and calculators.' },
    reasoning: { id: 'reasoning', name: 'Reasoning', blurb: 'Structured thinking, verification and deliberation.' },
  };

  const SERVERS = [
    /* ---------------------------- Academic Research ---------------------------- */
    { id: 'arxiv', name: 'arXiv', category: 'academic_research',
      description: 'Search and retrieve papers from arXiv by title, author, abstract or category, with full metadata and PDF links.',
      docs: 'https://smithery.ai/server/arxiv', url: 'https://server.smithery.ai/arxiv/mcp' },
    { id: 'semantic-scholar', name: 'Semantic Scholar', category: 'academic_research',
      description: 'Search millions of papers, follow citation graphs, look up authors and fetch open-access PDF links.',
      docs: 'https://smithery.ai/server/sigyakuova/semanticscholar', url: 'https://server.smithery.ai/sigyakuova/semanticscholar/mcp' },
    { id: 'openalex', name: 'OpenAlex', category: 'academic_research',
      description: 'Access the OpenAlex catalog of 270M+ publications: search works, authors and institutions.',
      docs: 'https://smithery.ai/server/cyanheads/openalex-mcp-server', url: 'https://server.smithery.ai/cyanheads/openalex-mcp-server/mcp' },
    { id: 'crossref', name: 'Crossref', category: 'academic_research',
      description: 'Resolve DOIs, search ~155M scholarly works and fetch references via the Crossref REST API.',
      docs: 'https://smithery.ai/server/cyanheads/crossref-mcp-server', url: 'https://server.smithery.ai/cyanheads/crossref-mcp-server/mcp' },
    { id: 'pubmed', name: 'PubMed', category: 'academic_research',
      description: 'Search biomedical literature across 36M citations; find papers, abstracts and related articles.',
      docs: 'https://smithery.ai/server/pubmed', url: 'https://server.smithery.ai/pubmed/mcp' },
    { id: 'paper-search', name: 'Paper Search', category: 'academic_research',
      description: 'Search and download papers from arXiv, PubMed, bioRxiv, medRxiv, Google Scholar, Semantic Scholar and IACR.',
      docs: 'https://smithery.ai/server/adamamer20/paper-search-mcp-openai', url: 'https://server.smithery.ai/adamamer20/paper-search-mcp-openai/mcp' },
    { id: 'citation-checker', name: 'Citation Checker', category: 'academic_research',
      description: 'Check whether references are real: looks each one up in Crossref, doi.org and OpenAlex and gives a verdict.',
      docs: 'https://smithery.ai/server/nguyenhieuec/citations', url: 'https://server.smithery.ai/nguyenhieuec/citations/mcp' },
    { id: 'citeme', name: 'CiteMe', category: 'academic_research',
      description: 'Find scholarly sources, format verified citations in 60+ styles and check pasted bibliographies.',
      docs: 'https://smithery.ai/server/citeme/citeme', url: 'https://server.smithery.ai/citeme/citeme/mcp' },
    { id: 'scholar-sidekick', name: 'Scholar Sidekick', category: 'academic_research',
      description: 'Turn identifiers (DOI, PMID, arXiv, ISBN) into clean citations and bibliography files, with trust signals.',
      docs: 'https://smithery.ai/server/scholar-sidekick/remote', url: 'https://server.smithery.ai/scholar-sidekick/remote/mcp' },
    { id: 'consensus', name: 'Consensus', category: 'academic_research',
      description: 'Search papers with AI-powered analysis: find studies, extract key findings and get evidence-based answers.',
      docs: 'https://smithery.ai/server/consensus', url: 'https://server.smithery.ai/consensus/mcp' },
    { id: 'academic-research', name: 'Academic Research MCP', category: 'academic_research',
      description: 'Literature-review automation: find papers by topic, pull citation counts and trace citation chains (ArXiv + Scholar).',
      docs: 'https://smithery.ai/server/nexgendata-apify/academic-research-mcp-server', url: 'https://server.smithery.ai/nexgendata-apify/academic-research-mcp-server/mcp' },
    { id: 'scholar-feed', name: 'Scholar Feed', category: 'academic_research',
      description: 'Search 600k+ CS/AI/ML papers with novelty analysis; trace citations, pull full text and export BibTeX.',
      docs: 'https://smithery.ai/server/yangg40/scholar-feed', url: 'https://server.smithery.ai/yangg40/scholar-feed/mcp' },
    { id: 'datacite', name: 'DataCite', category: 'academic_research',
      description: 'Search datasets and software, fetch DOI metadata, trace relations and format citations.',
      docs: 'https://smithery.ai/server/cyanheads/datacite-mcp-server', url: 'https://server.smithery.ai/cyanheads/datacite-mcp-server/mcp' },

    /* --------------------------------- Finance --------------------------------- */
    { id: 'finance-mcp', name: 'Finance MCP', category: 'finance',
      description: 'Real-time quotes, crypto prices, FX rates and portfolio P&L (Yahoo Finance, CoinGecko, FinViz).',
      docs: 'https://smithery.ai/server/nexgendata-apify/finance-mcp-server', url: 'https://server.smithery.ai/nexgendata-apify/finance-mcp-server/mcp' },
    { id: 'flatland', name: 'Flatland', category: 'finance',
      description: 'Financial reasoning infrastructure: typed models, deterministic compilation and cryptographic receipts.',
      docs: 'https://smithery.ai/server/flatlandfi/flatland', url: 'https://server.smithery.ai/flatlandfi/flatland/mcp' },
    { id: 'prereason', name: 'PreReason', category: 'finance',
      description: 'Market context an agent can reason with: signal, trend, regime, confidence and a plain-language narrative.',
      docs: 'https://smithery.ai/server/prereason/briefings', url: 'https://server.smithery.ai/prereason/briefings/mcp' },
    { id: 'everycalc', name: 'EveryCalc', category: 'finance',
      description: 'Free finance calculators: mortgage, refinance, loan, tax, retirement and 40+ more.',
      docs: 'https://smithery.ai/server/xusmanshahx/everycalc', url: 'https://server.smithery.ai/xusmanshahx/everycalc/mcp' },
    { id: 'monsitools', name: 'MonsiTools Calculators', category: 'finance',
      description: 'Look up and run business, finance and SaaS calculators (runway, break-even, ROAS) instead of doing the math.',
      docs: 'https://smithery.ai/server/monsibdtheadventurer/monsitools', url: 'https://server.smithery.ai/monsibdtheadventurer/monsitools/mcp' },
    { id: 'securelend', name: 'SecureLend Market', category: 'finance',
      description: 'Compare loans, mortgages, credit cards and financing options for individuals and businesses.',
      docs: 'https://smithery.ai/server/securelend/market', url: 'https://server.smithery.ai/securelend/market/mcp' },
    { id: 'wealthtools', name: 'WealthTools MCP', category: 'finance',
      description: 'Budgeting and financial calculations: budgets, expenses, investments, mortgage and net worth.',
      docs: 'https://smithery.ai/server/wealthtools/wt-personal-finance-mcp', url: 'https://server.smithery.ai/wealthtools/wt-personal-finance-mcp/mcp' },
    { id: 'arcadia', name: 'Arcadia', category: 'finance',
      description: 'Read protocol data and build transactions for Uniswap/Aerodrome liquidity positions and yield.',
      docs: 'https://smithery.ai/server/arcadia-finance/mcp-server', url: 'https://server.smithery.ai/arcadia-finance/mcp-server/mcp' },
    { id: 'senaro', name: 'Senaro Personal Finance', category: 'finance',
      description: 'Credit-card payoff, mortgages, refinancing, 401(k) and rent-vs-buy; every rule and default is cited.',
      docs: 'https://smithery.ai/server/senaro/personal-finance', url: 'https://server.smithery.ai/senaro/personal-finance/mcp' },
    { id: 'moltline-business', name: 'Moltline Business', category: 'finance',
      description: 'Finance, bookkeeping, legal-ops and SMB operations tools from the Moltline Studio suite.',
      docs: 'https://smithery.ai/server/techdpr/moltline-business', url: 'https://server.smithery.ai/techdpr/moltline-business/mcp' },

    /* -------------------------------- Reasoning -------------------------------- */
    { id: 'thoughtbox', name: 'Thoughtbox', category: 'reasoning',
      description: 'Structured reasoning and multi-agent collaboration: mental models, cognitive loops and shared workspaces.',
      docs: 'https://smithery.ai/server/Kastalien-Research/thoughtbox', url: 'https://server.smithery.ai/Kastalien-Research/thoughtbox/mcp' },
    { id: 'clear-thought', name: 'Clear Thought', category: 'reasoning',
      description: 'Structured thinking tools: mental models and sequential thinking for hard problems.',
      docs: 'https://smithery.ai/server/waldzellai/clear-thought', url: 'https://server.smithery.ai/waldzellai/clear-thought/mcp' },
    { id: 'logic-verifier', name: 'Logic Verifier', category: 'reasoning',
      description: 'Verify reasoning chains before an agent acts.',
      docs: 'https://smithery.ai/server/mifactory-bot/logic-verifier', url: 'https://server.smithery.ai/mifactory-bot/logic-verifier/mcp' },
    { id: 'invinoveritas', name: 'Invinoveritas', category: 'reasoning',
      description: 'A neutral second opinion before an irreversible action: approve / approve-with-concerns / reject, with ranked issues.',
      docs: 'https://smithery.ai/server/babyblueviper1/invinoveritas', url: 'https://server.smithery.ai/babyblueviper1/invinoveritas/mcp' },
    { id: 'decide-runtime', name: 'Decide Runtime', category: 'reasoning',
      description: 'Deterministic decision runtime: yes / no / review with a reason code and a saved decision record.',
      docs: 'https://smithery.ai/server/decidefyi/decision-runtime', url: 'https://server.smithery.ai/decidefyi/decision-runtime/mcp' },
    { id: 'quorum', name: 'Quorum', category: 'reasoning',
      description: 'A voting primitive for multi-agent decisions, with state and provenance.',
      docs: 'https://smithery.ai/server/wolfendentheo/quorum-mcp', url: 'https://server.smithery.ai/wolfendentheo/quorum-mcp/mcp' },
    { id: 'mumo', name: 'mumo', category: 'reasoning',
      description: 'Multi-model deliberation: models from different labs answer a question and react to each other.',
      docs: 'https://smithery.ai/server/mumo-chat/mumo', url: 'https://server.smithery.ai/mumo-chat/mumo/mcp' },
    { id: 'math-logic', name: 'Math & Logic', category: 'reasoning',
      description: 'Solve algebra and calculus, verify propositional logic and run safe arithmetic evaluations.',
      docs: 'https://smithery.ai/server/ikra/math-logic', url: 'https://server.smithery.ai/ikra/math-logic/mcp' },
    { id: 'lotus-wisdom', name: 'Lotus Wisdom', category: 'reasoning',
      description: 'Contemplative reasoning for multi-perspective problems and contradictions that logic alone cannot settle.',
      docs: 'https://smithery.ai/server/linxule/lotus-wisdom-mcp', url: 'https://server.smithery.ai/linxule/lotus-wisdom-mcp/mcp' },
    { id: 'rct7-thinking', name: 'RCT7 Thinking', category: 'reasoning',
      description: 'Seven-stage reverse-component thinking to reduce hallucination and align causal intent.',
      docs: 'https://smithery.ai/server/delentia/rct7-thinking', url: 'https://server.smithery.ai/delentia/rct7-thinking/mcp' },
    { id: 'topolift-negotiation', name: 'TopoLift Negotiation', category: 'reasoning',
      description: 'Atom-grounded negotiation reasoning with a citation-grounding audit for every claim.',
      docs: 'https://smithery.ai/server/joseph-geraci/topolift-negotiation', url: 'https://server.smithery.ai/joseph-geraci/topolift-negotiation/mcp' },
    { id: 'ai-rete-rag', name: 'ai·rete·rag', category: 'reasoning',
      description: 'A deterministic rule engine decides; the LLM only explains, grounded in your policy documents.',
      docs: 'https://smithery.ai/server/zaharajabeen13/ai-rete-rag', url: 'https://server.smithery.ai/zaharajabeen13/ai-rete-rag/mcp' },
    { id: 'unl', name: 'Unl', category: 'reasoning',
      description: 'Keeps what you decided and why, and gives each agent the part that bears on its task before it acts.',
      docs: 'https://smithery.ai/server/unlimitless/Unl', url: 'https://server.smithery.ai/unlimitless/Unl/mcp' },
    { id: 'deepseek', name: 'DeepSeek', category: 'reasoning',
      description: 'DeepSeek Chat + Reasoner models with thinking mode, function calling and JSON output.',
      docs: 'https://smithery.ai/server/arikusi/deepseek-mcp-server', url: 'https://server.smithery.ai/arikusi/deepseek-mcp-server/mcp' },
    { id: 'promptarch', name: 'PromptArch', category: 'reasoning',
      description: 'Lint and generate agent context files from ~30 research-backed rules.',
      docs: 'https://smithery.ai/server/rlopezlacuague/promptarch', url: 'https://server.smithery.ai/rlopezlacuague/promptarch/mcp' },
    { id: 'hive-consult', name: 'Hive Consult', category: 'reasoning',
      description: 'Post-quantum signed receipts and settlement for autonomous agent actions.',
      docs: 'https://smithery.ai/server/srotzin-adqm/hiveconsult', url: 'https://server.smithery.ai/srotzin-adqm/hiveconsult/mcp' },
    { id: 'gitwhy', name: 'gitwhy', category: 'reasoning',
      description: 'The shared AI context engine for git: save, search and share the reasoning behind code changes.',
      docs: 'https://smithery.ai/server/gitwhy-cli/gitwhy', url: 'https://server.smithery.ai/gitwhy-cli/gitwhy/mcp' },
    { id: 'agent-dilemma', name: 'AgentDilemma', category: 'reasoning',
      description: 'Vote on open dilemmas and get a calibration block with your running alignment rate.',
      docs: 'https://smithery.ai/server/AgentDilemma/Free-decision-audit', url: 'https://server.smithery.ai/AgentDilemma/Free-decision-audit/mcp' },
    { id: 'zobr-script', name: 'Zobr Script', category: 'reasoning',
      description: 'A cognitive scripting language for structured reasoning with LLMs.',
      docs: 'https://smithery.ai/server/zobr-script/zobr-script', url: 'https://server.smithery.ai/zobr-script/zobr-script/mcp' },
  ];

  const byId = {};
  SERVERS.forEach((s) => { byId[s.id] = s; });

  /** Replace the catalog (the backend serves the same list in /api/settings). */
  function setCatalog(list) {
    if (!Array.isArray(list) || !list.length) return;
    SERVERS.length = 0;
    Object.keys(byId).forEach((k) => delete byId[k]);
    list.forEach((s) => { SERVERS.push(s); byId[s.id] = s; });
  }

  /** The catalog entries an agent can access (from its `mcp_servers` ids). */
  function forAgent(agent) {
    const ids = (agent && agent.mcp_servers) || [];
    return ids.map((id) => byId[id]).filter(Boolean);
  }

  /** The catalog entries in one category, in catalog order. */
  function byCategory(category) {
    return SERVERS.filter((s) => s.category === category);
  }

  Hack.mcpServers = { CATEGORIES, SERVERS, byId, forAgent, byCategory, setCatalog };
})();
