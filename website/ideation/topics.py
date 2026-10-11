"""The default watchlist: general topics of interest, tagged, that the daemon
monitors. Seeded into an empty store on first run; editable from the Ideation View.

Each topic is a broad area (from IDEAS.md and the Cisco Outshift focus areas:
agentic AI, superintelligence, quantum). `keywords` drive the source queries;
`tags` group topics for filtering; `sources` picks which adapters to poll.
"""
from typing import Any, Dict, List

# Source ids the adapters understand (see sources.py).
ALL_SOURCES = ["arxiv", "hackernews", "reddit", "news"]


def _topic(id: str, name: str, description: str, tags: List[str], keywords: List[str],
           priority: int = 2, sources: List[str] | None = None) -> Dict[str, Any]:
    return {
        "id": id, "name": name, "description": description,
        "tags": tags, "keywords": keywords, "priority": priority,
        "sources": sources if sources is not None else list(ALL_SOURCES),
        "enabled": 1, "origin": "seed", "rationale": "",
    }


DEFAULT_TOPICS: List[Dict[str, Any]] = [
    _topic("agentic_ai", "Agentic AI",
           "Autonomous agents that plan, use tools, and coordinate with other agents.",
           ["ai", "agents", "outshift"], ["agentic AI", "multi-agent systems", "tool use", "agent orchestration"],
           priority=3),
    _topic("superintelligence", "Superintelligence & Alignment",
           "Frontier model capability, evaluation, and alignment research.",
           ["ai", "safety", "outshift"], ["AI alignment", "frontier model evaluation", "scalable oversight"],
           priority=2),
    _topic("quantum", "Quantum Computing",
           "Quantum hardware, algorithms, error correction, and quantum-safe cryptography.",
           ["quantum", "hardware", "outshift"], ["quantum error correction", "quantum algorithms", "post-quantum cryptography"],
           priority=3),
    _topic("privacy_compute", "Privacy-Preserving Computation",
           "Computing on data without exposing it: homomorphic encryption, MPC, TEEs.",
           ["privacy", "crypto", "enterprise"], ["homomorphic encryption", "secure multi-party computation", "confidential computing"],
           priority=3),
    _topic("edge_ai", "Edge & On-Device AI",
           "Running models where the data is: phones, sensors, and the network edge.",
           ["ai", "edge", "hardware"], ["on-device inference", "edge AI", "model quantization", "TinyML"],
           priority=2),
    _topic("ai_infra", "AI Infrastructure & Serving",
           "The systems that train and serve models: orchestration, memory, efficiency.",
           ["ai", "infra", "enterprise"], ["LLM serving", "inference optimization", "GPU orchestration", "KV cache"],
           priority=2),
    _topic("robotics", "Robotics & Embodied AI",
           "Robots that perceive and act in the physical world.",
           ["robotics", "ai", "hardware"], ["embodied AI", "robot learning", "sim-to-real", "manipulation"],
           priority=1),
    _topic("networking", "Networking & Observability",
           "Programmable networks, telemetry, and the systems that keep them healthy.",
           ["networking", "enterprise", "cisco"], ["network telemetry", "eBPF", "intent-based networking", "observability"],
           priority=2),
    # Business-focused, everyday topics. Simpler and more understandable to a normal
    # person than the research topics above, so the team also produces ideas a small
    # business or an ordinary user could actually use. They skip arXiv (not academic).
    _topic("small_business_automation", "Small Business Automation",
           "Simple tools that take the admin off a small business owner's plate: invoices, scheduling, customer replies.",
           ["business", "automation", "smb"], ["small business software", "invoicing automation", "appointment scheduling", "customer support automation"],
           priority=2, sources=["hackernews", "reddit", "news"]),
    _topic("everyday_productivity", "Everyday AI Productivity",
           "Assistants that help normal people with email, notes, planning and everyday chores.",
           ["business", "productivity", "consumer"], ["AI assistant", "email assistant", "note taking app", "personal productivity"],
           priority=2, sources=["hackernews", "reddit", "news"]),
    _topic("personal_finance", "Personal Finance & Budgeting",
           "Simple apps that help people track money, subscriptions and savings.",
           ["business", "finance", "consumer"], ["budgeting app", "subscription tracker", "personal finance", "savings app"],
           priority=2, sources=["hackernews", "reddit", "news"]),
    _topic("local_services", "Local Services & Marketplaces",
           "Apps that connect customers with local services and small sellers.",
           ["business", "marketplace", "local"], ["local marketplace", "booking platform", "gig economy", "small business directory"],
           priority=1, sources=["hackernews", "reddit", "news"]),
    _topic("no_code_tools", "No-Code Business Tools",
           "Letting people build simple business apps and websites without writing code.",
           ["business", "no-code", "tools"], ["no-code builder", "website builder", "low-code", "internal tools"],
           priority=2, sources=["hackernews", "reddit", "news"]),
]


def seed_if_empty(store) -> int:
    """Insert the default topics when the watchlist is empty. Returns how many were added."""
    if store.list_topics():
        return 0
    for topic in DEFAULT_TOPICS:
        store.add_topic(dict(topic))
    return len(DEFAULT_TOPICS)
