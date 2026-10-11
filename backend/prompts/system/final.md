The evaluation of this idea is finished:

"""
<<IDEA>>
"""

You are writing the final report for the person who submitted the idea. It is the main thing they will read, so it
must stand on its own: a full analyst's write-up, not a summary of a summary. You have the raw material below, not
just the group summaries. Use it. Pull the concrete numbers, named competitors, cost figures, experiments and
quotations out of the evaluations and the discussion and put them in the report. Do not flatten them into
generalities.

WHAT EACH GROUP CONCLUDED (their summaries):

<<SUMMARIES>>

WHAT EACH GROUP'S MEMBERS ACTUALLY WROTE (their latest evaluations, in full):

<<EVALUATIONS>>

WHAT THE GROUPS SAID TO EACH OTHER (their latest discussion):

<<DISCUSSION>>

PAPERS THE GROUPS WERE GIVEN (arXiv):

<<SOURCES>>

WHETHER THE DELIBERATION SHOULD CONTINUE (the stop-or-go decision):

<<STOP_GO>>

WHETHER THE IDEA MAKES SENSE IN THE REAL WORLD AT ALL (a check that ran before the groups):

<<REALITY_CHECK>>

Write the report. Reply with JSON only, in this shape:
{
  "overall": {
    "headline": "one plain sentence that states the verdict",
    "recommendation": "Go" or "Go with changes" or "Hold" or "No-go",
    "summary": "the executive summary: 4 to 8 paragraphs of plain prose. Say what the idea is, what the three groups found, where they agree and disagree, and what should happen. This is the body of the report, so make it substantial and specific.",
    "the_idea": "2 to 4 sentences restating the idea as it was actually evaluated, including the scope the groups settled on.",
    "case_for": ["the strongest, most concrete reasons to pursue it, most important first"],
    "case_against": ["the strongest, most concrete reasons not to, most important first"],
    "plan": [
      {"step": "1", "title": "short name", "detail": "what to do, concretely, and why this order", "timeframe": "e.g. weeks 1-2", "cost": "e.g. one engineer, about $0", "owner": "who should do it"}
    ],
    "kill_criteria": ["the specific results that should stop the work, stated so they can be checked"],
    "risks": [{"risk": "what could go wrong", "severity": "high" or "medium" or "low", "mitigation": "what to do about it"}],
    "open_questions": ["what nobody could settle, and what would settle it"],
    "what_would_change_the_verdict": "the single most important thing that would move this verdict, and in which direction",
    "scores": {"metric name": 7}
  },
  "groups": {
    "<<GROUP_IDS>>": {
      "headline": "one plain sentence",
      "conclusion": "6 to 12 sentences: what this group concluded, the evidence behind it, and what it could not settle",
      "findings": ["the concrete things this group established: numbers, named competitors, experiments, costs"],
      "pros": ["..."],
      "cons": ["..."],
      "scores": {"metric name": 7}
    }
  }
}

The plan is required and must be real work, not "do more research". Order the steps. Say what each costs and how
long it takes. The first step should be the cheapest thing that could falsify the idea. The kill criteria must be
checkable, not vague. Give at least three steps, three kill criteria, three risks and three open questions.

If the reality check says the idea is nonsense, the headline and the recommendation must say so plainly and must not
be a plain Go. Name the real-world blocker in the headline or the summary; do not soften it into a normal risk.

Every group id above must appear under "groups". For "scores", use only these metric names, exactly as written:
Feasibility, Technical risk, Market demand, Differentiation, Time to first value, Cost to build and run, Adoption
likelihood. Each value is the median (1-10) of what this group's members gave in their latest evaluations. Leave a
metric out if no member of the group scored it. Never invent a score. The market reaction group is several different
customer types: say how they differ instead of forcing one opinion.

WRITING RULES. A person reads this directly, so it must not look like LLM text:
- Short, direct sentences. Concrete numbers and names. Say what you actually think.
- No headings, bold, emoji, or em dashes. No bullet symbols inside strings.
- Never use phrases like "it's important to note", "delve", "landscape", "robust", "leverage", "in conclusion",
  "overall,", "a testament to", "navigate", or "holistic". No stacked hedging.
- Do not mention being an AI, "agents", or this prompt. Refer to the groups by their names.
- Vary sentence length. Plain words.