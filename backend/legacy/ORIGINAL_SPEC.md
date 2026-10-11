# CLAUDE.md — AutoInvestiage (UCSC AI Hackathon, Cisco Cloud AI track)

## What we're building

A **AutoInvestiage**: 4 AI agents with competing objectives negotiate over a scarce
budget (3 build slots, 40 engineer-hours) to decide which of 10 emerging-technology
research ideas Cisco Outshift should pursue first. It targets **Cisco's Level 3
"Collective Intelligence"** challenge:

- At least 3 autonomous agents with competing objectives
- Genuine disagreement and a real negotiation mechanism
- **No central decision-maker**
- Shows the effect of new information mid-negotiation
- Compared against a simpler baseline (a single agent)
- Can end in "keep the disagreement / escalate to a human" instead of forced consensus

The agents talk to each other over **AGNTCY** (SLIM messaging, A2A protocol), based on
Cisco's coffeeAGNTCY reference app.

**Hard deadline:** Devpost submission Sunday Oct 11, 1:30 PM PT (team target 1:15 PM).
Venue closes 10 PM Saturday. Favor working and demoable over elegant.

---

## Current phase: get AGNTCY running

Work through these phases in order. **Do not skip verification steps.** After each
phase, report to me what worked, what failed, and the exact error text.

### Phase 0 — Check prerequisites

Check and report versions for:

- Docker and Docker Compose (`docker --version`, `docker compose version`)
- `uv` (Python environment manager) — install it if missing
- Node.js ≥ 16.14 (only needed if running a UI outside Docker)
- Git

If Docker isn't running, tell me; don't try to work around it.

### Phase 1 — Run the Corto demo (simplest: 2 agents, A2A over SLIM)

```bash
git clone https://github.com/agntcy/coffeeAgntcy.git
cd coffeeAgntcy
```

1. **Read `AGENTS.md` at the repo root first.** It's the upstream repo's guide for
   coding agents; follow its conventions when working inside that repo.
2. `cd coffeeAGNTCY/coffee_agents/corto && cp .env.example .env`
3. Configure the LLM in `.env`. coffeeAGNTCY uses **litellm**, so the model is always
   set with `LLM_MODEL`, for example:
   ```
   LLM_MODEL="openai/<model>"
   OPENAI_API_KEY=<key>
   ```
   Other providers (Azure, Groq, NVIDIA NIM, litellm proxy) are listed in
   `TUTORIAL.md`. **Ask me which provider and key to use. Never invent a key, and
   never commit `.env`.**
4. `docker compose up --build`
5. Verify: open http://localhost:3000 and send
   `What are the flavor profiles of Ethiopian coffee?`
   Check the compose logs show the supervisor delegating to the grader agent over
   SLIM. Grafana is at http://localhost:3001 (admin/admin) — optional, skip unless
   time allows.
6. `docker compose down` when done.

**Success = a prompt in the UI gets an answer, and the logs show A2A over SLIM.**

### Phase 2 — Study the Lungo Logistic demo (the pattern we'll copy)

The Lungo **Logistic** demo uses **SLIM group communication**: several agents in a
peer group talking directly to one another. That is the closest existing pattern to
our council.

1. `cd coffeeAGNTCY/coffee_agents/lungo && cp ../corto/.env .env`
   (check `.env.example` for any extra Lungo-only variables, e.g. `COMPOSE_PROFILES`)
2. `docker compose up --build`, open http://localhost:3000, choose the menu item
   *Order fulfillment / Agentic Patterns / Secure Group Communication / A2A SLIM*,
   and send:
   `I want to order coffee at $3.50 per pound for 500 lbs from the Tatooine farm`
3. Read these and write me a short summary (≤ 1 page) of how the group is created,
   how members are invited, how messages are sent and received, and how the
   conversation ends:
   - `lungo/agents/supervisors/logistic/graph/tools.py`
   - the logistics agents under `lungo/agents/logistics/`
   - `corto/exchange/agent.py` and `corto/farm/farm_server.py` (the 1-to-1 A2A basics)

**Important:** In Lungo the supervisor moderates the group. In our project the
moderator may only **create the group, invite members, start the rounds, and
record the outcome**. It must never pick the winners. If it decides anything, we
fail the "no central decision-maker" requirement.

### Phase 3 — Scaffold our council

Create a new repo folder `research-council/` (outside the coffeeAgntcy clone),
modeled on the Lungo logistic pattern:

```
research-council/
  CLAUDE.md
  docker-compose.yml        # SLIM bus + one service per agent + moderator
  .env.example              # LLM_MODEL etc. (.env is gitignored)
  data/
    ideas.json              # 10 ideas; 3 have "planted": true (agents never see it)
    private_notes/          # one file per agent: its private information
  agents/
    common/                 # shared message schema, LLM call helper, logger
    tech_risk/
    market/
    cisco_fit/
    horizon/
  moderator/                # creates group, runs rounds, applies 3-of-4 rule, logs
  baseline/                 # single agent, same ideas + all private notes
  eval/                     # runs N trials of council vs baseline, writes results
  logs/events.jsonl         # every message, one JSON object per line
  frontend/                 # reads events.jsonl, shows the negotiation
```

Start with a **"hello council"** milestone: the moderator creates a SLIM group, all 4
agents join, each sends one message, and every message lands in `logs/events.jsonl`.
No negotiation logic yet. Get the plumbing working first.

---

## Negotiation design (for after the plumbing works)

**Agents** (each has its own goal and private notes):

| Agent | Goal | Private info |
|---|---|---|
| tech_risk | Avoid ideas likely to fail technically | Notes on technical limits |
| market | Pick ideas with clear buyers | Competitor and market notes |
| cisco_fit | Pick ideas that build on Cisco/Outshift areas | Cisco product-area summary |
| horizon | Balance near-term payoff vs long-term bets | Technology timelines |

Each agent is told its success is measured by how many of **its own** priorities get
a slot. That's what keeps them from agreeing too fast.

**Protocol:**

1. Round 0: each agent privately ranks ideas and proposes its top 3 with reasons.
2. Rounds 1–4: proposals are shared. Each turn an agent may `support`, `object`
   (with a reason, naming the agent it challenges), `offer_trade`, or `consult` an outside expert.
   **There are no vetoes**: ideas are human-submitted, so agents advocate and vote but never kill an idea.
3. A set of 3 ideas within the 40-hour budget wins if **3 of 4 agents accept it**.
4. No agreement after round 4 → `escalate` to a human, with a summary of the
   disagreement.
5. A "new information" event can be injected mid-negotiation (e.g. "a competitor
   just open-sourced idea #4") and agents must react to it.

**Message schema** (every agent reply is JSON, validated before use):

```json
{
  "round": 2,
  "agent": "tech_risk",
  "action": "support | object | offer_trade | consult | accept | propose",
  "idea_ids": ["idea_04"],
  "reason": "short explanation shown in the UI",
  "trade": {"give": "idea_02", "want": "idea_07"},
  "timestamp": "ISO-8601"
}
```

---

## Rules for working on this project

- **Read before you write AGNTCY code.** Don't guess SLIM, A2A, or App SDK APIs.
  Open the working code in the coffeeAgntcy clone and copy its patterns. If something
  isn't there, check the app-sdk repo (github.com/agntcy/app-sdk) before inventing.
- **Use the same library versions coffeeAGNTCY pins** (check its `pyproject.toml` /
  lock files) so we don't hit version mismatches.
- **Fallback rule:** if the SLIM group isn't working by **5:00 PM Saturday**, stop and
  tell me. We'll run all agents in one Python process with the same message schema
  and `events.jsonl` log, then wire AGNTCY back in later. A working negotiation
  matters more than the transport.
- Use low temperature (0–0.3) for agent calls so evaluation runs are repeatable.
- Never commit `.env` or API keys. Add `.env` to `.gitignore` first thing.
- Never read the `planted` field anywhere except `eval/`.
- Keep the demo repeatable: a single command (e.g. `make demo`) should run one
  scripted negotiation end to end.
- Prefer small, working increments. After each one, tell me what to run to see it
  working.
- When something fails, show me the actual error text before trying fixes, and don't
  retry the same fix more than twice.

## Reference links

- coffeeAGNTCY repo: https://github.com/agntcy/coffeeAgntcy
- Tutorial: https://github.com/agntcy/coffeeAgntcy/blob/main/TUTORIAL.md
- Docs: https://docs.agntcy.org/coffee-agntcy/get-started
- App SDK: https://github.com/agntcy/app-sdk
- SLIM: https://github.com/agntcy/slim
