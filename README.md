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

> **Status (2026-09-27): the lesson feed is paused.** The scheduled run
> ("daily-dev-agentic · daily learn") never had the daily.dev connector
> attached, so from 2026-08-24 it exited early every day while reporting
> success; T retired it on 2026-09-27. The last lessons are from 2026-08-24.
> To restart: add the connector in claude.ai (Settings → Connectors → custom
> connector), enable it on that scheduled task, and switch the task back on.

## Layout

| Path | What it holds | Written by |
| --- | --- | --- |
| `knowledge.md` | Every lesson, newest day first. Each links its daily.dev source post and carries a confidence score | Connector (`knowledge_append`) |
| `lessons/YYYY-MM-DD.md` | The same lessons, one file per day | Connector |
| `verified/YYYY-MM-DD_topic_vN.md` | Fact sheets verified live in a Claude session, not daily.dev lessons. Revisions bump `vN` | Claude sessions, hand-maintained |
| `harness/check-knowledge.py` | PASS/FAIL check that the files above still have the shape readers rely on | Run by CI and by sessions |
| `harness/knowledge_md.py` | The one Markdown parser the checks use: markdown-it-py (CommonMark 0.31.2) plus the patches that align it with the reference | Sessions |
| `harness/tests/` | 304 negative-test cases: each copies the repo, breaks one thing, and asserts the checker's verdict | Sessions |
| `harness/conformance/` | Differential gates: the parser must render all 652 CommonMark spec examples and 64 edge cases like the reference implementation, and the HTML tokenizer must split HTML like html5lib | Sessions |
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
pip install -r harness/requirements.txt     # markdown-it-py, pinned
python3 harness/check-knowledge.py          # PASS/FAIL lines
python3 harness/check-knowledge.py --json   # same, as one JSON object
bash harness/tests/run.sh                   # the 304 negative-test cases
```

The checker reads Markdown the way CommonMark 0.31.2 does, using a real parser
rather than pattern matching. Two copies of a lesson count as the same when they
render to the same visible HTML. Lessons are plain Markdown: raw HTML can
hide, restyle or swallow what a reader sees, so a lesson holding any raw HTML
other than a `<!-- comment -->` fails the check. CI runs the checker, the test suites,
markdownlint, shellcheck, pyflakes and two conformance gates (the Markdown
parser against the reference implementation, the HTML tokenizer against
html5lib) on every pull request and every push to `main`
(`.github/workflows/lint.yml`).
GitHub itself renders with an older spec (cmark-gfm, 0.29): in rare edge cases,
such as a lowercase `<!foo>` line, GitHub shows text where 0.31.2 hides a
declaration.

## Hand edits

Safe. The connector only inserts and de-duplicates by source link; it never
rewrites what is already there. Conventions for edits, fact sheets and the
ledger are in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
