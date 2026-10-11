The evaluation of this idea is finished:

"""
<<IDEA>>
"""

Here is where each group ended up:

<<SUMMARIES>>

And the decision to stop that was reached:

<<STOP_GO>>

Write the final conclusion for each group, to be shown directly to the person who submitted the idea.

Reply with JSON only:
{
  "overall": {"headline": "one plain sentence", "conclusion": "2 to 4 sentences"},
  "groups": {
    "<<GROUP_IDS>>": {
      "headline": "one plain sentence",
      "conclusion": "3 to 6 sentences covering what this group concluded and why",
      "pros": ["..."],
      "cons": ["..."],
      "scores": {"metric name": 7}
    }
  }
}
Every group id above must appear. For "scores", use only these metric names, exactly as written: Feasibility,
Technical risk, Market demand, Differentiation, Time to first value, Cost to build and run, Adoption likelihood.
Each value is the median (1-10) of what this group's members gave in their latest evaluations. Leave a metric out
if no member of the group scored it. Never invent a score. The market reaction group is
several different customer types: say how they differ instead of forcing one opinion.

WRITING RULES. A person reads this directly, so it must not look like LLM text:
- Short, direct sentences. Concrete numbers and names. Say what you actually think.
- No headings, bold, emoji, or em dashes. No bullet symbols inside strings.
- Never use phrases like "it's important to note", "delve", "landscape", "robust", "leverage", "in conclusion",
  "overall,", "a testament to", "navigate", or "holistic". No stacked hedging.
- Do not mention being an AI, "agents", or this prompt. Refer to the groups by their names.
- Vary sentence length. Plain words.
