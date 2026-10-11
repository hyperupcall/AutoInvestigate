# Research Council

Four AI agents with competing goals negotiate over a scarce budget (3 build slots, 40 engineer-hours)
to decide which of 10 emerging-technology ideas Cisco Outshift should pursue first. There is no
central decision-maker. Agents talk to each other over **AGNTCY** (A2A messages on **SLIM** groups).

## Run it

```bash
cd ~/Documents/research-council
make up          # starts SLIM, 4 council agents, 3 expert agents, the runner and the UI
```

Open http://localhost:8090 and press **Reset and run**. (Needs Docker running and the root `.env`
(`../../.env`) with `OPENROUTER_API_KEY`; the model is set with `LLM_MODEL` and routed through
OpenRouter. See `../../.env.example`.)

Other commands:

| Command | What it does |
|---|---|
| `make demo` | one paced negotiation from the terminal (`make demo PACE=8` for slower) |
| `make test` | unit tests for the deterministic tally |
| `make down` | stop everything |
| `docker compose --profile run run --rm eval python -m eval.run_eval --council 10 --baseline 20` | council vs single-agent eval (writes `eval/results.json`; don't use the UI button meanwhile) |
| `docker compose logs -f slim` | raw SLIM bus traffic |

## How it works

- **Round 0:** each agent privately ranks the ideas from its own notes and proposes its top 3.
- **Rounds 1-4:** each agent makes one move per round: `propose`, `accept`, `support`, `object` (naming
  the agent it challenges), `offer_trade` or `consult`. There are no vetoes: ideas are human-submitted, so agents
  advocate and vote but never kill an idea.
- **Consult:** an agent asks an outside expert (`security_expert`, `customer_voice`, or
  `specialist_on_demand` playing any role it names). The moderator only invites the expert into the
  SLIM group. Experts advise and never vote.
- **Decision:** a set of 3 ideas within 40 hours wins when 3 of 4 agents back it. Every agent runs the
  same deterministic tally (`agents/common/tally.py`) on the messages it saw and broadcasts a `commit`;
  the outcome is final only if all four commits match. No agreement after round 4 escalates to a human.
- **New information** (default: a competitor open-sources idea 01) is injected before round 2.
- **The moderator** (`moderator/main.py`) only opens SLIM groups, relays commands, injects the scripted
  news, and records what the agents committed.

## Layout

```
agents/common/   schema, tally, executor, expert, llm helper, SLIM server glue
agents/<name>/   one entrypoint per agent
moderator/       group creation, rounds, runner service for the UI button
baseline/        single agent that sees all private notes
eval/            council vs baseline (only place allowed to read the `planted` field)
frontend/        stdlib server + single-page UI reading logs/events.jsonl
data/            ideas.json and per-agent private notes
```

## Known limits

- Current Claude models only accept `temperature=1`, so runs vary; the eval reports rates over many runs.
- The council matches but does not beat the single-agent baseline on quality; its value is the visible,
  auditable negotiation and its reaction to new information.
