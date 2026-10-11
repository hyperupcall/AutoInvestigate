# Backend notes (for Claude Code and humans)

- This folder is the idea-evaluation backend (spec: ../CLAUDE.md section 3, Part 2). Read README.md first.
- AGNTCY: the SDK keeps ONE SLIM connection per process, so each agent runs in its own process
  (agent_host/main.py supervises them). The orchestrator only opens SLIM groups and relays; it decides nothing.
- Never commit `.env`, `data/settings.json`, `logs/` or `results/`. Keys stay on the backend.
- Models: cheap, recent, diverse OpenRouter models picked from the live price list (Oct 2026). Reasoning effort
  is set per stage; cut-off replies are retried once. Check models with `make smoke`.
- Stop-or-go = keep deliberating or not (not a verdict on the idea). The idea's verdict is the final headline.
- The frontend reads the report schema directly; live events are translated in orchestrator/compat.py.
- Tests: `make test`. Pipeline control flow, report parsing, quote verification, compat shapes, OpenRouter client.
