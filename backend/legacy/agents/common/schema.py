"""Council message schema. Every agent reply is JSON validated against this."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Action = Literal[
    "hello",  # plumbing milestone only
    "start_round",  # moderator only
    "propose", "support", "object", "offer_trade", "accept",
    "new_info", "escalate", "invite",  # moderator records only
    "consult", "advise",  # council agent asks an outside expert; expert answers
    "commit",  # each agent's independently computed outcome (decentralized tally)
]
AGENT_NAMES = ("tech_risk", "market", "cisco_fit", "horizon")  # the voting council
EXPERT_NAMES = ("security_expert", "customer_voice", "specialist_on_demand")  # guests: advise, never vote


class Trade(BaseModel):
    give: str
    want: str


class CouncilMessage(BaseModel):
    round: int
    agent: str
    action: Action
    idea_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    trade: Optional[Trade] = None
    expert: Optional[str] = None  # consult: which expert is being asked
    role: Optional[str] = None    # consult of specialist_on_demand: the kind of expert needed
    target: Optional[str] = None  # object/support: the agent being challenged or backed
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_json(self) -> str:
        return self.model_dump_json(exclude_none=True)


def parse_council_message(text: str) -> Optional[CouncilMessage]:
    """Return a validated message, or None if text is not a council message."""
    try:
        return CouncilMessage.model_validate_json(text)
    except Exception:
        return None
