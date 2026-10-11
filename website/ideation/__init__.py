"""The ideation collective — a long-running daemon that watches the internet for
signals related to a tagged watchlist of topics and turns them into ideas.

Unlike the deliberation collective (one idea in, one report out, driven by a
click), ideation runs unattended: it polls sources on a schedule, a small team of
agents works *together* to refine what it finds into ideas, and the ideas land in
the same store the frontend's Idea Generation column renders.

Reuses `deliberation/` as its shared library (the OpenRouter client, the prompt
loader, settings), exactly as `orchestrator/` and `agent_host/` do.
"""
