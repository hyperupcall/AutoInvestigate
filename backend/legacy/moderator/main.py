"""Moderator: creates the SLIM group, invites members, starts the round, logs.
It never decides anything (no-central-decision-maker requirement)."""
import asyncio
import json
import os
import logging
import sys
from uuid import uuid4

from a2a.types import Message, MessageSendParams, Part, Role, SendMessageRequest, TextPart
from agntcy_app_sdk import get_agent_identifier
from agntcy_app_sdk.semantic.a2a import ClientConfig, SlimTransportConfig
from agntcy_app_sdk.semantic.a2a.client.factory import A2AClientFactory

from agents.common.cards import build_card
from agents.common.config import GROUP, NAMESPACE, SLIM_SERVER, SLIM_SHARED_SECRET
from agents.common.events import log_event
from agents.common.schema import AGENT_NAMES, EXPERT_NAMES, CouncilMessage, parse_council_message

logger = logging.getLogger("council.moderator")


async def _client():
    cards = {n: build_card(n, "") for n in AGENT_NAMES}
    factory = A2AClientFactory(ClientConfig(slim_config=SlimTransportConfig(
        endpoint=f"http://{SLIM_SERVER}",
        name=f"{NAMESPACE}/{GROUP}/{os.getenv('MODERATOR_NAME', 'moderator')}",
        shared_secret_identity=SLIM_SHARED_SECRET,
    )))
    client = await factory.create(cards[AGENT_NAMES[0]])
    return client, [get_agent_identifier(c) for c in cards.values()]


async def run_command(client, participants, cmd: dict, expect, timeout: float = 150, who=AGENT_NAMES):
    expect = (expect,) if isinstance(expect, str) else tuple(expect)
    """Open a SLIM group, post one command, collect one `expect` reply per agent,
    log them, close the group. The moderator only relays and records."""
    request = SendMessageRequest(id=str(uuid4()), params=MessageSendParams(
        message=Message(messageId=str(uuid4()), role=Role.user,
                        parts=[Part(TextPart(text=json.dumps(cmd)))])))
    log_event("moderator", CouncilMessage(
        round=cmd.get("round", 0), agent="moderator", action="start_round",
        reason=f"{cmd['kind']}", expert=cmd.get("expert")).model_dump())
    got: dict[str, CouncilMessage] = {}
    channel = str(uuid4())
    log_event("slim_group", {"status": "open", "channel": channel, "command": cmd["kind"],
                             "round": cmd.get("round", 0), "members": participants,
                             "slim": SLIM_SERVER, "agent": "moderator", "action": "start_round"})
    stream = client.start_streaming_groupchat(
        init_message=request, group_channel=channel, participants=participants,
        end_message="__never__", timeout=timeout)
    try:
        async for resp in stream:
            try:
                parts = resp.root.result.parts
            except Exception:
                continue
            for p in parts:
                msg = parse_council_message(getattr(p.root, "text", ""))
                if msg and msg.agent in who and msg.action in expect \
                        and msg.agent not in got:
                    got[msg.agent] = msg
                    log_event("agent_message", msg.model_dump())
            if len(got) == len(who):
                break
    finally:
        await stream.aclose()  # closes the SLIM group session
        log_event("slim_group", {"status": "closed", "channel": channel, "command": cmd["kind"],
                                 "round": cmd.get("round", 0), "replies": len(got),
                                 "agent": "moderator", "action": "start_round"})
    return got


async def hello() -> int:
    client, parts = await _client()
    got = await run_command(client, parts, {"kind": "hello", "round": 0}, "hello")
    for a, m in got.items():
        print(f"  heard {a}: {m.reason}")
    ok = len(got) == len(AGENT_NAMES)
    print("HELLO COUNCIL OK" if ok else f"MISSING: {sorted(set(AGENT_NAMES) - set(got))}")
    return 0 if ok else 1


TURN_ACTIONS = ("propose", "accept", "support", "object", "offer_trade", "consult")
LAST: dict = {}  # result of the most recent negotiate() call (used by eval/)
DEFAULT_INFO = ("A competitor has just open-sourced a production-ready agent identity wallet "
                "(idea_01). Buyers are likely to treat that capability as free.")


def _commits_agree(commits: dict) -> tuple[bool, list]:
    out = {a: tuple(m.idea_ids) for a, m in commits.items()}
    agree = len(commits) == len(AGENT_NAMES) and len(set(out.values())) == 1
    return agree, list(next(iter(out.values()), ())) if agree else []


async def negotiate(rounds: int = 4, info_round: int | None = 2, info: str = DEFAULT_INFO,
                    stop_early: bool = True, pace: float = 0) -> int:
    """Round 0 proposals, then up to `rounds` turns. The moderator only opens
    groups, relays commands, and records what the agents commit."""
    client, parts = await _client()
    allmsgs: list[CouncilMessage] = []

    async def step(cmd, expect):
        got = await run_command(client, parts, cmd, expect)
        allmsgs.extend(got.values())
        return got

    props = await step({"kind": "round0", "round": 0}, "propose")
    print("ROUND 0")
    for a in AGENT_NAMES:
        m = props.get(a)
        print(f"  {a:10s} propose {m.idea_ids if m else 'MISSING'}")
    final = None
    for r in range(0, rounds + 1):
        if r > 0:
            await asyncio.sleep(pace)  # pause so a human can read the last round
            cmd = {"kind": "turn", "round": r, "last_round": rounds}
            if info_round == r and info:
                cmd["new_info"] = info
                log_event("new_info", CouncilMessage(
                    round=r, agent="moderator", action="new_info", reason=info).model_dump())
                print(f"  ** NEW INFO before round {r}: {info}")
            got = await step(cmd, TURN_ACTIONS)
            print(f"ROUND {r}")
            for a in AGENT_NAMES:
                m = got.get(a)
                if m:
                    t = f" {m.trade.give}->{m.trade.want}" if m.trade else ""
                    print(f"  {a:10s} {m.action:11s} {m.idea_ids}{t}  {m.reason[:90]}")
                else:
                    print(f"  {a:10s} MISSING")
            for a in AGENT_NAMES:  # moderator only invites; the asker chose the expert
                m = got.get(a)
                if m and m.action == "consult" and m.expert in EXPERT_NAMES:
                    log_event("invite", CouncilMessage(
                        round=r, agent="moderator", action="invite", expert=m.expert,
                        reason=f"{a} asked {m.expert}: {m.reason}"[:300]).model_dump() | {"requested_by": a, "role": m.role})
                    eid = get_agent_identifier(build_card(m.expert, ""))
                    adv = await run_command(client, parts + [eid], {
                        "kind": "consult", "round": r, "expert": m.expert, "asker": a,
                        "question": m.reason, "idea_ids": m.idea_ids, "role": m.role}, "advise", who=(m.expert,))
                    allmsgs.extend(adv.values())
                    for am in adv.values():
                        print(f"  EXPERT {am.agent}: {am.reason[:110]}")
        await asyncio.sleep(1.5 + pace)  # let every agent receive every peer message
        commits = await run_command(client, parts, {"kind": "tally", "round": r}, "commit")
        agree, winner = _commits_agree(commits)
        print(f"  commits r{r}: {'MATCH' if agree else 'MISMATCH'} -> {winner or 'no winner'}")
        log_event("round_summary", {"round": r, "agreed": agree, "outcome": winner or None})
        if not agree and len(commits) == len(AGENT_NAMES):
            final = ("escalate", [], "agents' independent tallies disagree")
            break
        if winner and stop_early:
            final = ("consensus", winner, f"3+ of 4 agents back {', '.join(winner)} (round {r})")
            break
    if final is None:
        final = ("escalate", [], _disagreement_summary(allmsgs))
    status, ideas_, summary = final
    log_event("final", {"round": r, "agent": "moderator", "action": "escalate" if status == "escalate" else "commit",
                        "status": status, "idea_ids": ideas_, "reason": summary})
    print(f"\nFINAL: {status.upper()} {ideas_ or ''}\n  {summary}")
    LAST.clear()
    LAST.update({"status": status, "idea_ids": ideas_, "summary": summary, "rounds": r, "msgs": allmsgs})
    return 0


def _disagreement_summary(msgs: list[CouncilMessage]) -> str:
    """Mechanical record of where each agent ended up (no judgment by the moderator)."""
    backing, objections = {}, {}
    for m in sorted(msgs, key=lambda m: m.timestamp):
        if m.action in ("propose", "accept") and len(m.idea_ids) == 3:
            backing[m.agent] = m.idea_ids
        if m.action == "object":
            for i in m.idea_ids:
                objections.setdefault(i, set()).add(m.agent)
    pos = "; ".join(f"{a} backs {','.join(sorted(v))}" for a, v in sorted(backing.items()))
    ob = ("; objected to: " + ", ".join(f"{i} by {'/'.join(sorted(a))}" for i, a in sorted(objections.items()))) if objections else ""
    return f"No set reached 3 of 4 backers. Final positions: {pos}{ob}"


LOGDIR = os.path.dirname(os.getenv("EVENTS_LOG", "logs/events.jsonl")) or "."
TRIGGER = os.path.join(LOGDIR, "trigger.json")
CANCEL = os.path.join(LOGDIR, "cancel")
STATUS = os.path.join(LOGDIR, "status.json")


def _set_status(state: str) -> None:
    with open(STATUS, "w") as f:
        json.dump({"state": state}, f)


async def serve() -> None:
    """Always-on runner: the UI's button drops logs/trigger.json; we wipe the log
    and run a fresh negotiation. Agents reset themselves at round 0."""
    os.makedirs(LOGDIR, exist_ok=True)
    _set_status("idle")
    print("runner ready: waiting for the UI to start a negotiation", flush=True)
    while True:
        if os.path.exists(TRIGGER):
            try:
                cfg = json.load(open(TRIGGER))
            except Exception:
                cfg = {}
            os.remove(TRIGGER)
            if os.path.exists(CANCEL):
                os.remove(CANCEL)
            open(os.getenv("EVENTS_LOG", "logs/events.jsonl"), "w").close()
            _set_status("running")
            task = asyncio.create_task(negotiate(
                pace=float(cfg.get("pace", 4)),
                info_round=2 if cfg.get("news", True) else None))
            while not task.done():
                if os.path.exists(CANCEL):
                    os.remove(CANCEL)
                    task.cancel()
                    break
                await asyncio.sleep(0.4)
            try:
                await task
            except asyncio.CancelledError:
                log_event("final", {"round": 0, "agent": "moderator", "action": "escalate",
                                    "status": "cancelled", "idea_ids": [], "reason": "Stopped by the user."})
            except Exception as e:  # keep the runner alive for the next run
                log_event("final", {"round": 0, "agent": "moderator", "action": "escalate",
                                    "status": "error", "idea_ids": [], "reason": f"Run failed: {e}"[:300]})
            _set_status("idle")
        await asyncio.sleep(0.4)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(asyncio.run(serve()) if "serve" in sys.argv else asyncio.run(negotiate(pace=float(os.getenv("PACE", "0"))) if "negotiate" in sys.argv else negotiate(rounds=0) if "round0" in sys.argv else hello()))
