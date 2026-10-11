"""Single-agent baseline: ONE decision-maker that sees every idea and all of the
private information at once (all four agents' notes plus both experts' knowledge).
This is deliberately a strong baseline."""
import json

from agents.common.data import load_ideas, load_notes
from agents.common.llm import ask_json
from agents.common.schema import AGENT_NAMES, EXPERT_NAMES
from agents.common.tally import BUDGET_HOURS, SLOTS

GOALS = {"tech_risk": "avoid ideas likely to fail technically", "market": "pick ideas with clear buyers",
         "cisco_fit": "pick ideas that build on Cisco/Outshift areas",
         "horizon": "balance near-term payoff vs long-term bets"}


async def decide() -> dict:
    ideas = load_ideas()
    hours = {i["id"]: i["est_hours"] for i in ideas}
    notes = "\n\n".join(f"## {a} (goal: {GOALS[a]})\n{load_notes(a)}" for a in AGENT_NAMES)
    know = "\n\n".join(f"## {e}\n{load_notes(e)}" for e in EXPERT_NAMES if e != "specialist_on_demand")
    system = ("You are the single decision-maker for Cisco Outshift's research council. You can see every "
              "stakeholder's goal and private notes, plus two outside experts' knowledge. Choose the "
              f"{SLOTS} ideas to build, together within {BUDGET_HOURS} engineer-hours, that are best for "
              "Outshift overall, weighing all four stakeholders fairly.")
    user = (f"Ideas:\n{json.dumps(ideas)}\n\nStakeholders:\n{notes}\n\nExperts:\n{know}\n\n"
            'Reply JSON only: {"top3": ["idea_xx","idea_yy","idea_zz"], "reason": "1-2 sentences"}')

    def validate(o):
        ids = o.get("top3")
        if not isinstance(ids, list) or len(set(ids)) != SLOTS or any(i not in hours for i in ids):
            return f"top3 must be {SLOTS} distinct valid idea ids"
        return None if sum(hours[i] for i in ids) <= BUDGET_HOURS else "over budget"

    o = await ask_json(system, user, validate)
    return {"idea_ids": sorted(o["top3"]), "reason": o.get("reason", "")}
