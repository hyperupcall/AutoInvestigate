"""Default settings: three group perspectives, each an object with an `agents` array.
Models are restricted to the cheap set in ../CHEAP_MODELS.md (OpenRouter ids).

Each agent also carries `mcp_servers`: ids from MCP_CATALOG (curated from Smithery,
https://smithery.ai/servers). The agent host connects to those servers and offers
their tools to the agent's model (see deliberation/mcp.py). The frontend shows the same
catalog in the "Configure Agent Groups" popup (website/frontend/js/mcp-servers.js)."""
import copy
import glob
import os

from deliberation.prompts import ROOT, role_name


def _agent(slug: str, prompt: str, model: str, effort: str | None = None,
           mcp_servers: list[str] | None = None) -> dict:
    return {"id": slug, "name": role_name(prompt), "prompt": prompt, "model": model,
            "api_key": "", "reasoning_effort": effort,  # None = use the stage default
            "mcp_servers": mcp_servers or []}


# MCP servers an agent can use, grouped into three categories. `url` is the MCP
# endpoint the agent host connects to; `docs` is the Smithery page.
MCP_CATALOG = [
    # ------------------------------ Academic Research ------------------------------
    {"id": "arxiv", "name": "arXiv", "category": "academic_research",
     "description": "Search and retrieve papers from arXiv by title, author, abstract or category, with full metadata and PDF links.",
     "url": "https://server.smithery.ai/arxiv/mcp", "docs": "https://smithery.ai/server/arxiv"},
    {"id": "semantic-scholar", "name": "Semantic Scholar", "category": "academic_research",
     "description": "Search millions of papers, follow citation graphs, look up authors and fetch open-access PDF links.",
     "url": "https://server.smithery.ai/sigyakuova/semanticscholar/mcp", "docs": "https://smithery.ai/server/sigyakuova/semanticscholar"},
    {"id": "openalex", "name": "OpenAlex", "category": "academic_research",
     "description": "Access the OpenAlex catalog of 270M+ publications: search works, authors and institutions.",
     "url": "https://server.smithery.ai/cyanheads/openalex-mcp-server/mcp", "docs": "https://smithery.ai/server/cyanheads/openalex-mcp-server"},
    {"id": "crossref", "name": "Crossref", "category": "academic_research",
     "description": "Resolve DOIs, search ~155M scholarly works and fetch references via the Crossref REST API.",
     "url": "https://server.smithery.ai/cyanheads/crossref-mcp-server/mcp", "docs": "https://smithery.ai/server/cyanheads/crossref-mcp-server"},
    {"id": "pubmed", "name": "PubMed", "category": "academic_research",
     "description": "Search biomedical literature across 36M citations; find papers, abstracts and related articles.",
     "url": "https://server.smithery.ai/pubmed/mcp", "docs": "https://smithery.ai/server/pubmed"},
    {"id": "paper-search", "name": "Paper Search", "category": "academic_research",
     "description": "Search and download papers from arXiv, PubMed, bioRxiv, medRxiv, Google Scholar, Semantic Scholar and IACR.",
     "url": "https://server.smithery.ai/adamamer20/paper-search-mcp-openai/mcp", "docs": "https://smithery.ai/server/adamamer20/paper-search-mcp-openai"},
    {"id": "citation-checker", "name": "Citation Checker", "category": "academic_research",
     "description": "Check whether references are real: looks each one up in Crossref, doi.org and OpenAlex and gives a verdict.",
     "url": "https://server.smithery.ai/nguyenhieuec/citations/mcp", "docs": "https://smithery.ai/server/nguyenhieuec/citations"},
    {"id": "citeme", "name": "CiteMe", "category": "academic_research",
     "description": "Find scholarly sources, format verified citations in 60+ styles and check pasted bibliographies.",
     "url": "https://server.smithery.ai/citeme/citeme/mcp", "docs": "https://smithery.ai/server/citeme/citeme"},
    {"id": "scholar-sidekick", "name": "Scholar Sidekick", "category": "academic_research",
     "description": "Turn identifiers (DOI, PMID, arXiv, ISBN) into clean citations and bibliography files, with trust signals.",
     "url": "https://server.smithery.ai/scholar-sidekick/remote/mcp", "docs": "https://smithery.ai/server/scholar-sidekick/remote"},
    {"id": "consensus", "name": "Consensus", "category": "academic_research",
     "description": "Search papers with AI-powered analysis: find studies, extract key findings and get evidence-based answers.",
     "url": "https://server.smithery.ai/consensus/mcp", "docs": "https://smithery.ai/server/consensus"},
    {"id": "academic-research", "name": "Academic Research MCP", "category": "academic_research",
     "description": "Literature-review automation: find papers by topic, pull citation counts and trace citation chains (ArXiv + Scholar).",
     "url": "https://server.smithery.ai/nexgendata-apify/academic-research-mcp-server/mcp", "docs": "https://smithery.ai/server/nexgendata-apify/academic-research-mcp-server"},
    {"id": "scholar-feed", "name": "Scholar Feed", "category": "academic_research",
     "description": "Search 600k+ CS/AI/ML papers with novelty analysis; trace citations, pull full text and export BibTeX.",
     "url": "https://server.smithery.ai/yangg40/scholar-feed/mcp", "docs": "https://smithery.ai/server/yangg40/scholar-feed"},
    {"id": "datacite", "name": "DataCite", "category": "academic_research",
     "description": "Search datasets and software, fetch DOI metadata, trace relations and format citations.",
     "url": "https://server.smithery.ai/cyanheads/datacite-mcp-server/mcp", "docs": "https://smithery.ai/server/cyanheads/datacite-mcp-server"},

    # ---------------------------------- Finance ----------------------------------
    {"id": "finance-mcp", "name": "Finance MCP", "category": "finance",
     "description": "Real-time quotes, crypto prices, FX rates and portfolio P&L (Yahoo Finance, CoinGecko, FinViz).",
     "url": "https://server.smithery.ai/nexgendata-apify/finance-mcp-server/mcp", "docs": "https://smithery.ai/server/nexgendata-apify/finance-mcp-server"},
    {"id": "flatland", "name": "Flatland", "category": "finance",
     "description": "Financial reasoning infrastructure: typed models, deterministic compilation and cryptographic receipts.",
     "url": "https://server.smithery.ai/flatlandfi/flatland/mcp", "docs": "https://smithery.ai/server/flatlandfi/flatland"},
    {"id": "prereason", "name": "PreReason", "category": "finance",
     "description": "Market context an agent can reason with: signal, trend, regime, confidence and a plain-language narrative.",
     "url": "https://server.smithery.ai/prereason/briefings/mcp", "docs": "https://smithery.ai/server/prereason/briefings"},
    {"id": "everycalc", "name": "EveryCalc", "category": "finance",
     "description": "Free finance calculators: mortgage, refinance, loan, tax, retirement and 40+ more.",
     "url": "https://server.smithery.ai/xusmanshahx/everycalc/mcp", "docs": "https://smithery.ai/server/xusmanshahx/everycalc"},
    {"id": "monsitools", "name": "MonsiTools Calculators", "category": "finance",
     "description": "Look up and run business, finance and SaaS calculators (runway, break-even, ROAS) instead of doing the math.",
     "url": "https://server.smithery.ai/monsibdtheadventurer/monsitools/mcp", "docs": "https://smithery.ai/server/monsibdtheadventurer/monsitools"},
    {"id": "securelend", "name": "SecureLend Market", "category": "finance",
     "description": "Compare loans, mortgages, credit cards and financing options for individuals and businesses.",
     "url": "https://server.smithery.ai/securelend/market/mcp", "docs": "https://smithery.ai/server/securelend/market"},
    {"id": "wealthtools", "name": "WealthTools MCP", "category": "finance",
     "description": "Budgeting and financial calculations: budgets, expenses, investments, mortgage and net worth.",
     "url": "https://server.smithery.ai/wealthtools/wt-personal-finance-mcp/mcp", "docs": "https://smithery.ai/server/wealthtools/wt-personal-finance-mcp"},
    {"id": "arcadia", "name": "Arcadia", "category": "finance",
     "description": "Read protocol data and build transactions for Uniswap/Aerodrome liquidity positions and yield.",
     "url": "https://server.smithery.ai/arcadia-finance/mcp-server/mcp", "docs": "https://smithery.ai/server/arcadia-finance/mcp-server"},
    {"id": "senaro", "name": "Senaro Personal Finance", "category": "finance",
     "description": "Credit-card payoff, mortgages, refinancing, 401(k) and rent-vs-buy; every rule and default is cited.",
     "url": "https://server.smithery.ai/senaro/personal-finance/mcp", "docs": "https://smithery.ai/server/senaro/personal-finance"},
    {"id": "moltline-business", "name": "Moltline Business", "category": "finance",
     "description": "Finance, bookkeeping, legal-ops and SMB operations tools from the Moltline Studio suite.",
     "url": "https://server.smithery.ai/techdpr/moltline-business/mcp", "docs": "https://smithery.ai/server/techdpr/moltline-business"},

    # --------------------------------- Reasoning ---------------------------------
    {"id": "thoughtbox", "name": "Thoughtbox", "category": "reasoning",
     "description": "Structured reasoning and multi-agent collaboration: mental models, cognitive loops and shared workspaces.",
     "url": "https://server.smithery.ai/Kastalien-Research/thoughtbox/mcp", "docs": "https://smithery.ai/server/Kastalien-Research/thoughtbox"},
    {"id": "clear-thought", "name": "Clear Thought", "category": "reasoning",
     "description": "Structured thinking tools: mental models and sequential thinking for hard problems.",
     "url": "https://server.smithery.ai/waldzellai/clear-thought/mcp", "docs": "https://smithery.ai/server/waldzellai/clear-thought"},
    {"id": "logic-verifier", "name": "Logic Verifier", "category": "reasoning",
     "description": "Verify reasoning chains before an agent acts.",
     "url": "https://server.smithery.ai/mifactory-bot/logic-verifier/mcp", "docs": "https://smithery.ai/server/mifactory-bot/logic-verifier"},
    {"id": "invinoveritas", "name": "Invinoveritas", "category": "reasoning",
     "description": "A neutral second opinion before an irreversible action: approve / approve-with-concerns / reject, with ranked issues.",
     "url": "https://server.smithery.ai/babyblueviper1/invinoveritas/mcp", "docs": "https://smithery.ai/server/babyblueviper1/invinoveritas"},
    {"id": "decide-runtime", "name": "Decide Runtime", "category": "reasoning",
     "description": "Deterministic decision runtime: yes / no / review with a reason code and a saved decision record.",
     "url": "https://server.smithery.ai/decidefyi/decision-runtime/mcp", "docs": "https://smithery.ai/server/decidefyi/decision-runtime"},
    {"id": "quorum", "name": "Quorum", "category": "reasoning",
     "description": "A voting primitive for multi-agent decisions, with state and provenance.",
     "url": "https://server.smithery.ai/wolfendentheo/quorum-mcp/mcp", "docs": "https://smithery.ai/server/wolfendentheo/quorum-mcp"},
    {"id": "mumo", "name": "mumo", "category": "reasoning",
     "description": "Multi-model deliberation: models from different labs answer a question and react to each other.",
     "url": "https://server.smithery.ai/mumo-chat/mumo/mcp", "docs": "https://smithery.ai/server/mumo-chat/mumo"},
    {"id": "math-logic", "name": "Math & Logic", "category": "reasoning",
     "description": "Solve algebra and calculus, verify propositional logic and run safe arithmetic evaluations.",
     "url": "https://server.smithery.ai/ikra/math-logic/mcp", "docs": "https://smithery.ai/server/ikra/math-logic"},
    {"id": "lotus-wisdom", "name": "Lotus Wisdom", "category": "reasoning",
     "description": "Contemplative reasoning for multi-perspective problems and contradictions that logic alone cannot settle.",
     "url": "https://server.smithery.ai/linxule/lotus-wisdom-mcp/mcp", "docs": "https://smithery.ai/server/linxule/lotus-wisdom-mcp"},
    {"id": "rct7-thinking", "name": "RCT7 Thinking", "category": "reasoning",
     "description": "Seven-stage reverse-component thinking to reduce hallucination and align causal intent.",
     "url": "https://server.smithery.ai/delentia/rct7-thinking/mcp", "docs": "https://smithery.ai/server/delentia/rct7-thinking"},
    {"id": "topolift-negotiation", "name": "TopoLift Negotiation", "category": "reasoning",
     "description": "Atom-grounded negotiation reasoning with a citation-grounding audit for every claim.",
     "url": "https://server.smithery.ai/joseph-geraci/topolift-negotiation/mcp", "docs": "https://smithery.ai/server/joseph-geraci/topolift-negotiation"},
    {"id": "ai-rete-rag", "name": "ai·rete·rag", "category": "reasoning",
     "description": "A deterministic rule engine decides; the LLM only explains, grounded in your policy documents.",
     "url": "https://server.smithery.ai/zaharajabeen13/ai-rete-rag/mcp", "docs": "https://smithery.ai/server/zaharajabeen13/ai-rete-rag"},
    {"id": "unl", "name": "Unl", "category": "reasoning",
     "description": "Keeps what you decided and why, and gives each agent the part that bears on its task before it acts.",
     "url": "https://server.smithery.ai/unlimitless/Unl/mcp", "docs": "https://smithery.ai/server/unlimitless/Unl"},
    {"id": "deepseek", "name": "DeepSeek", "category": "reasoning",
     "description": "DeepSeek Chat + Reasoner models with thinking mode, function calling and JSON output.",
     "url": "https://server.smithery.ai/arikusi/deepseek-mcp-server/mcp", "docs": "https://smithery.ai/server/arikusi/deepseek-mcp-server"},
    {"id": "promptarch", "name": "PromptArch", "category": "reasoning",
     "description": "Lint and generate agent context files from ~30 research-backed rules.",
     "url": "https://server.smithery.ai/rlopezlacuague/promptarch/mcp", "docs": "https://smithery.ai/server/rlopezlacuague/promptarch"},
    {"id": "hive-consult", "name": "Hive Consult", "category": "reasoning",
     "description": "Post-quantum signed receipts and settlement for autonomous agent actions.",
     "url": "https://server.smithery.ai/srotzin-adqm/hiveconsult/mcp", "docs": "https://smithery.ai/server/srotzin-adqm/hiveconsult"},
    {"id": "gitwhy", "name": "gitwhy", "category": "reasoning",
     "description": "The shared AI context engine for git: save, search and share the reasoning behind code changes.",
     "url": "https://server.smithery.ai/gitwhy-cli/gitwhy/mcp", "docs": "https://smithery.ai/server/gitwhy-cli/gitwhy"},
    {"id": "agent-dilemma", "name": "AgentDilemma", "category": "reasoning",
     "description": "Vote on open dilemmas and get a calibration block with your running alignment rate.",
     "url": "https://server.smithery.ai/AgentDilemma/Free-decision-audit/mcp", "docs": "https://smithery.ai/server/AgentDilemma/Free-decision-audit"},
    {"id": "zobr-script", "name": "Zobr Script", "category": "reasoning",
     "description": "A cognitive scripting language for structured reasoning with LLMs.",
     "url": "https://server.smithery.ai/zobr-script/zobr-script/mcp", "docs": "https://smithery.ai/server/zobr-script/zobr-script"},
]

MCP_CATEGORIES = {
    "academic_research": {"id": "academic_research", "name": "Academic Research", "blurb": "Papers, citations and scholarly search."},
    "finance": {"id": "finance", "name": "Finance", "blurb": "Market data, financial reasoning and calculators."},
    "reasoning": {"id": "reasoning", "name": "Reasoning", "blurb": "Structured thinking, verification and deliberation."},
}


def _groups() -> list[dict]:
    return [
        {"id": "research", "name": "Professional Research Group",
         "description": "Researchers judging feasibility, architecture, whether an LLM is needed, and prior art.",
         "consensus": "converge", "use_sources": True,
         "agents": [
             _agent("feasibility_scientist", "prompts/research/feasibility_scientist.md", "meta-llama/llama-3.1-8b-instruct",
                    mcp_servers=["arxiv", "semantic-scholar", "thoughtbox"]),
             _agent("systems_architect", "prompts/research/systems_architect.md", "openai/gpt-oss-120b",
                    mcp_servers=["arxiv", "crossref", "math-logic"]),
             _agent("ai_systems_researcher", "prompts/research/ai_systems_researcher.md", "google/gemma-3-4b-it",
                    mcp_servers=["arxiv", "paper-search", "scholar-feed", "thoughtbox"]),
             _agent("critical_reviewer", "prompts/research/critical_reviewer.md", "meta-llama/llama-3.1-8b-instruct:online",
                    mcp_servers=["citation-checker", "citeme", "crossref", "logic-verifier", "invinoveritas"]),
         ]},
        {"id": "private_equity", "name": "Private Equity and Business",
         "description": "Four partners judging technical risk, market size, competitive position, and returns.",
         "consensus": "converge", "use_sources": True,
         "agents": [
             _agent("technical_risk_partner", "prompts/private_equity/technical_risk_partner.md", "openai/gpt-oss-120b",
                    mcp_servers=["arxiv", "crossref", "logic-verifier", "invinoveritas"]),
             _agent("market_revenue_partner", "prompts/private_equity/market_revenue_partner.md", "google/gemma-3-4b-it:online",
                    mcp_servers=["finance-mcp", "flatland", "prereason", "openalex"]),
             _agent("competitive_strategy_partner", "prompts/private_equity/competitive_strategy_partner.md", "meta-llama/llama-3.1-8b-instruct",
                    mcp_servers=["finance-mcp", "flatland", "semantic-scholar"]),
             _agent("horizon_returns_partner", "prompts/private_equity/horizon_returns_partner.md", "openai/gpt-oss-120b",
                    mcp_servers=["finance-mcp", "prereason", "quorum"]),
         ]},
        {"id": "market", "name": "Market Reaction",
         "description": "Customer archetypes reacting to the idea. They are not expected to agree.",
         "consensus": "diverge", "use_sources": False,
         "agents": [
             _agent("power_user", "prompts/market/power_user.md", "meta-llama/llama-3.1-8b-instruct",
                    mcp_servers=["thoughtbox", "clear-thought"]),
             _agent("enterprise_decision_maker", "prompts/market/enterprise_decision_maker.md", "google/gemma-3-4b-it",
                    mcp_servers=["invinoveritas", "decide-runtime", "securelend"]),
             _agent("skeptical_technical_critic", "prompts/market/skeptical_technical_critic.md", "openai/gpt-oss-120b",
                    mcp_servers=["citation-checker", "crossref", "logic-verifier"]),
             _agent("startup_builder", "prompts/market/startup_builder.md", "meta-llama/llama-3.1-8b-instruct",
                    mcp_servers=["finance-mcp", "everycalc", "thoughtbox"]),
             _agent("free_tier_maximizer", "prompts/market/free_tier_maximizer.md", "google/gemma-3-4b-it",
                    mcp_servers=["everycalc", "monsitools", "clear-thought"]),
         ]},
    ]


# Only these models may be used (see ../CHEAP_MODELS.md). OpenRouter ids.
LIBRARY_MODELS = ["meta-llama/llama-3.1-8b-instruct", "google/gemma-3-4b-it", "openai/gpt-oss-120b"]


def _steward(slug: str, name: str, objective: str, prompt: str, model: str, effort: str = "low") -> dict:
    return {"id": slug, "name": name, "objective": objective, "prompt": prompt, "model": model,
            "api_key": "", "reasoning_effort": effort}


def _stewards() -> list[dict]:
    """The three Evaluation Complex stewards. They share one goal (continue or stop the swarm) but optimize for
    different things, so they genuinely disagree (see orchestrator/complex.py)."""
    return [
        _steward("usefulness", "Usefulness Steward",
                 "Is there a useful or implementable result in what the collectives produced?",
                 "prompts/system/complex_usefulness.md", "openai/gpt-oss-120b"),
        _steward("convergence", "Convergence Steward",
                 "Would another round actually change anything (information gain)?",
                 "prompts/system/complex_convergence.md", "openai/gpt-oss-120b"),
        _steward("roi", "ROI Steward",
                 "Is another round worth its cost in time and money?",
                 "prompts/system/complex_roi.md", "openai/gpt-oss-120b"),
    ]


def archetype_library() -> list[dict]:
    """Extra customer archetypes that can be added to the market group from the settings popup."""
    out = []
    for i, path in enumerate(sorted(glob.glob(os.path.join(ROOT, "prompts/market/archetypes/*.md")))):
        rel = os.path.relpath(path, ROOT)
        out.append(_agent(os.path.basename(path)[:-3], rel, LIBRARY_MODELS[i % len(LIBRARY_MODELS)]))
    return out


DEFAULT_SETTINGS = {
    "mode": "quick",                     # quick: about a minute (one pass per round, short write-ups) | deep: about 7 minutes
    "sources": {"enabled": True, "max_papers": 8, "model": "google/gemma-3-4b-it"},  # arXiv papers for groups with use_sources
    "deliberation_seconds": 60,          # per deliberation round, per group
    "max_cost_usd": 1.0,                 # a run stops when this is spent
    "web_search_results": 3,             # per search for ":online" models
    # MCP: agents connect to the servers in their `mcp_servers` and may call their tools.
    "mcp": {"enabled": True, "api_key": "", "timeout_seconds": 20, "max_tool_calls": 2},
    "max_tokens": {"deliberate": 500, "evaluate": 4500, "summarize": 5000, "judge": 4000, "final": 9000, "reality_check": 1200},
    "reasoning_effort": {"deliberate": "none", "evaluate": "low", "summarize": "none", "judge": "low", "final": "low", "reality_check": "low"},
    "stages": {
        "summarizer": {"model": "openai/gpt-oss-120b", "api_key": ""},
        "judge": {"model": "openai/gpt-oss-120b", "api_key": ""},
        "final": {"model": "openai/gpt-oss-120b", "api_key": ""},  # the final report writer (see prompts/system/final.md)
        "reality_check": {"model": "openai/gpt-oss-120b", "api_key": ""},
    },
    # The Evaluation Complex: three stewards that watch the swarm in parallel and decide whether it should
    # continue or stop (see orchestrator/complex.py). max_seconds force-stops the swarm and writes the verdict;
    # stop_votes is how many of the three must vote stop to stop the swarm early.
    "complex": {"enabled": True, "max_seconds": 300, "interval_seconds": 45, "stop_votes": 2,
                "stewards": _stewards()},
    "groups": _groups(),
}


def default_settings() -> dict:
    return copy.deepcopy(DEFAULT_SETTINGS)
