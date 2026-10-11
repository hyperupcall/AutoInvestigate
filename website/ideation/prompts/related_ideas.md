# Related Ideas

You are asked for a handful of ideas that are **vaguely related** to the watchlist
topics below. You are not solving a task and you are not being precise — you are
sketching directions the team could investigate next.

The topics are broad areas the team already watches. Your job is to look across them
and propose ideas that sit near them: a different angle on one topic, a combination of
two topics, or a small, concrete thing a normal person or a small business could
actually use.

Rules:

- **Vague is fine.** An idea is a direction, not a specification. One sentence is enough.
- **Stay near the topics.** Each idea should clearly connect to at least one of them.
- **Prefer simple and understandable.** If a normal person could not explain the idea in
  a sentence, it is too complicated. Favour ideas a small business or an ordinary user
  would want, not just researchers.
- **Be concrete about what it is.** Say what the thing does, not how it is built.
- **Do not repeat a topic verbatim** — turn it into an idea.

Reply with **one JSON object and nothing else**:

```
{
  "subject": "<a short subject for these ideas>",
  "ideas": [
    {"text": "<the idea — ONE sentence>", "justification": ["<why>", "<why>", "<why>"]}
  ]
}
```

Each `text` is exactly one sentence. Each idea has 3 or 4 short justification bullets.
Produce 4 to 6 ideas.