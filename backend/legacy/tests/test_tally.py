from agents.common.schema import CouncilMessage as M
from agents.common.tally import tally

H = {f"idea_{i:02d}": 14 for i in range(1, 11)}
A, B = ["idea_01", "idea_02", "idea_03"], ["idea_04", "idea_05", "idea_06"]
def m(agent, action, ids, ts): return M(round=1, agent=agent, action=action, idea_ids=ids, timestamp=ts)

# 3 of 4 back A, but 3*14=42h > 40h budget -> no winner
assert tally([m(a, "propose", A, "1") for a in ("tech_risk", "market", "cisco_fit")], H).winner is None
H2 = {k: 12 for k in H}
assert tally([m(a, "propose", A, "1") for a in ("tech_risk", "market", "cisco_fit")], H2).winner == A
# two sets, 2 backers each -> no winner
r = tally([m("tech_risk", "propose", A, "1"), m("market", "propose", A, "1"),
           m("cisco_fit", "propose", B, "1"), m("horizon", "propose", B, "1")], H2)
assert r.winner is None, r
# later accept overrides earlier propose; reaching 3 backers wins
msgs = [m("tech_risk", "propose", A, "1"), m("market", "propose", B, "1"),
        m("cisco_fit", "propose", A, "1"), m("horizon", "propose", B, "1"),
        m("market", "accept", A, "2")]
assert tally(msgs, H2).winner == A
# order of arrival does not matter (determinism)
assert tally(list(reversed(msgs)), H2).winner == tally(msgs, H2).winner
print("tally tests passed")
