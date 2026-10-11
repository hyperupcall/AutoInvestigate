You are analysing the record of an idea evaluation. Find where people disagreed and where groups agreed.

The idea: """<<IDEA>>"""

The people, by id (use these ids exactly):
<<ROSTER>>

The record, round by round. Each line is "[agent_id] what they said". Summaries are marked SUMMARY.
<<RECORD>>

Reply with JSON only:
{
  "within_group": {
    "<group_id>": [
      {"topic": "short noun phrase", "round": 1,
       "sides": [{"agent_ids": ["id"], "position": "one sentence"}, {"agent_ids": ["id"], "position": "one sentence"}],
       "status": "resolved" or "open", "resolution": "one sentence, empty if open",
       "evidence": [{"agent_id": "id", "quote": "exact words copied from the record"}]}
    ]
  },
  "cross_group": [
    {"topic": "short noun phrase",
     "sides": [{"group_id": "id", "agent_ids": ["id"], "position": "one sentence"}, {"group_id": "id", "agent_ids": ["id"], "position": "one sentence"}],
     "status": "resolved" or "open",
     "evidence": [{"agent_id": "id", "quote": "exact words copied from the record"}]}
  ],
  "agreements": [{"topic": "short noun phrase", "group_ids": ["id", "id"], "summary": "one sentence"}]
}

Rules:
- Every group id (<<GROUP_IDS>>) must appear under "within_group", with 1 to 5 real disagreements each (an empty list
  only if the group truly agreed on everything).
- 2 to 6 cross-group disagreements: places where one group's position conflicts with another's.
- 1 to 4 agreements shared by at least two groups.
- Each item needs at least two sides, and at least one quote per side.
- Quotes must be copied word for word from the record, 6 to 25 words, from the agent you attribute them to.
  Never paraphrase inside "quote". Quotes that are not found in the record are discarded.
- Only use the ids listed above. Plain sentences, no markdown.
