# agent-knowledge

[![Lint](https://github.com/lookathim010-source/agent-knowledge/actions/workflows/lint.yml/badge.svg)](https://github.com/lookathim010-source/agent-knowledge/actions/workflows/lint.yml)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Written by: daily-dev-agentic connector](https://img.shields.io/badge/written%20by-daily--dev--agentic%20connector-blue)
![Lessons carry a confidence score](https://img.shields.io/badge/lessons-confidence--scored-orange)

The readable memory of T's **daily-dev-agentic** loop: what the agent learned
from daily.dev, distilled into lessons that name why each one matters for the
stack (Claude Code, MCP, multi-agent systems, LangGraph, Firebase, Python,
Rust, local LLMs, fintech infrastructure) and what to do about it.

Written mostly by a machine. The daily.dev MCP connector (Cloudflare Worker
`dailydevplugd`) appends lessons after each scheduled run; Claude sessions
add verified fact sheets; humans fix typos. Run state (seen-post watermark,
counters) lives in Cloudflare KV, not here.

## Layout

| Path | What it holds | Written by |
| --- | --- | --- |
| `knowledge.md` | Every lesson, newest day first. Each links its daily.dev source post and carries a confidence score | Connector (`knowledge_append`) |
| `lessons/YYYY-MM-DD.md` | The same lessons, one file per day | Connector |
| `verified/YYYY-MM-DD_topic_vN.md` | Fact sheets verified live in a Claude session, not daily.dev lessons. Revisions bump `vN` | Claude sessions, hand-maintained |
| `harness/check-knowledge.py` | PASS/FAIL check that the files above still have the shape readers rely on | Run by CI and by sessions |
| `LEDGER.md` | One row per hand-made or session-made change (connector runs are not logged here) | Sessions and hand edits |

## How a lesson is shaped

```markdown
## 2026-08-24

- **One actionable sentence, supported by the article.**
  - Why it matters here: the link to T's stack or a live project.
  - Do: the concrete next action, or "None now".
  - Source: [Title](https://...) — Author (⬆️ upvotes · 💬 comments) · tags: a, b · confidence 80%
```

Confidence follows the connector's scale: official docs or maintainer posts
around 80–95, well-upvoted practitioner posts 60–80, single opinions 30–55.
Zero lessons on a quiet day is a valid result; the loop is told never to pad.

## Reading it

- Newest first: open `knowledge.md` and read from the top.
- One day: open `lessons/<date>.md`.
- Something proven rather than read: `verified/`.
- Programmatically: the connector's `knowledge_read` tool (`days: N`) returns
  the same content without cloning.

## Checking it

```bash
python3 harness/check-knowledge.py          # PASS/FAIL lines
python3 harness/check-knowledge.py --json   # same, as one JSON object
```

CI runs this plus markdownlint on every pull request and on every push to
`main` (`.github/workflows/lint.yml`). Run it locally before pushing a branch.

## Hand edits

Safe. The connector only inserts and de-duplicates by source link; it never
rewrites what is already there. Conventions for edits, fact sheets and the
ledger are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
