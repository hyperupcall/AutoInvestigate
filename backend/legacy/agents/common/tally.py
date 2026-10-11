"""Deterministic, decentralized tally. Every agent runs this on the messages it
saw; the moderator never does. Same messages in => same outcome out.

Rules: a set of 3 ideas wins if >=3 of 4 agents back it (their latest propose or
accept) and it fits the hour budget. A tie between winning sets means no decision.
Agents cannot veto: ideas are human-submitted, so agents advocate and vote but never kill an idea."""
from collections import Counter
from dataclasses import dataclass, field

from agents.common.schema import AGENT_NAMES, CouncilMessage

BUDGET_HOURS, NEEDED, SLOTS = 40, 3, 3


@dataclass
class TallyResult:
    winner: list[str] | None
    support: dict[str, int] = field(default_factory=dict)  # "id,id,id" -> backers
    basis: int = 0  # number of agent messages considered
    reason: str = ""


def tally(msgs: list[CouncilMessage], hours: dict[str, int]) -> TallyResult:
    msgs = sorted((m for m in msgs if m.agent in AGENT_NAMES),
                  key=lambda m: (m.timestamp, m.agent, m.action))
    backing: dict[str, frozenset] = {}
    for m in msgs:
        if m.action in ("propose", "accept") and len(set(m.idea_ids)) == SLOTS:
            backing[m.agent] = frozenset(m.idea_ids)
    counts = Counter(backing.values())
    support = {",".join(sorted(s)): c for s, c in counts.items()}
    ok = [(s, c) for s, c in counts.items()
          if c >= NEEDED and sum(hours.get(i, 999) for i in s) <= BUDGET_HOURS]
    res = TallyResult(None, support, len(msgs))
    if not ok:
        best = max(counts.values(), default=0)
        res.reason = f"no set has {NEEDED} of 4 backers (best has {best}); basis={len(msgs)}"
        return res
    top = max(c for _, c in ok)
    leaders = [s for s, c in ok if c == top]
    if len(leaders) > 1:
        res.reason = f"tie between {len(leaders)} sets with {top} backers; basis={len(msgs)}"
        return res
    res.winner = sorted(leaders[0])
    res.reason = f"{top} of 4 back {','.join(res.winner)}; basis={len(msgs)}"
    return res
