# Skills

Third-party agent skills used by this project, installed with the **manual**
method (raw files fetched from each source repo) rather than a CLI/plugin
installer. Each skill lives in its own directory with a `SKILL.md` (YAML
frontmatter + instructions) plus any `references/` or `examples/` files the
skill depends on.

These are curated from [agenticskills.io](https://agenticskills.io/). They are
vendored here so the project has a stable, reviewable copy; re-fetch from the
source repos to update.

## Installed skills

| Directory | Skill | Source repo | Path in repo | License |
| --- | --- | --- | --- | --- |
| `brainstorming/` | Brainstorming | [obra/superpowers](https://github.com/obra/superpowers) | `skills/brainstorming` | MIT |
| `internal-comms/` | Internal Comms | [anthropics/skills](https://github.com/anthropics/skills) | `skills/internal-comms` | Apache-2.0 |
| `humanizer/` | Humanizer | [blader/humanizer](https://github.com/blader/humanizer) | repo root | MIT |
| `copy-editing/` | Copy Editing | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | `skills/copy-editing` | MIT |
| `marketing-ideas/` | Marketing Ideas | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | `skills/marketing-ideas` | MIT |
| `launch-strategy/` | Launch Strategy | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | `skills/launch` | MIT |

## What each skill is for

- **brainstorming** — Socratic design refinement: turns rough ideas into
  structured designs and specs before any implementation work.
- **internal-comms** — Writes status reports, newsletters, FAQs, 3P updates and
  incident reports for internal teams.
- **humanizer** — Rewrites AI-sounding prose to remove the tells (not-X-but-Y
  contrasts, one-line closers, forced triads, dash overuse, inflated claims).
- **copy-editing** — Seven-sweep copy editing for marketing and conversion copy,
  plus an AI-tell check.
- **marketing-ideas** — A library of 139 marketing/growth ideas, matched to
  stage, budget and timeline.
- **launch-strategy** — Product launch planning: the ORB channel framework,
  readiness gate, five-phase launch, Product Hunt strategy and checklists.

## Manual install method

The manual method creates the skill directory and downloads the raw
`SKILL.md` (and any referenced files) from the source repo, e.g.:

```sh
mkdir -p website/skills/brainstorming
curl -o website/skills/brainstorming/SKILL.md \
  https://raw.githubusercontent.com/obra/superpowers/main/skills/brainstorming/SKILL.md
```

Files were fetched from the `main` branch of each source repo. The
`launch-strategy` directory is named after the skill's display name; the source
path is `skills/launch` and its frontmatter `name` is `launch`.
