# Conventions

Two kinds of writer share this repository: the daily-dev-agentic connector,
which appends lessons on a schedule, and Claude sessions or humans, who add
verified fact sheets and fix things. These rules keep them from colliding.

## What the connector owns

- `knowledge.md` and `lessons/*.md` are connector-managed. Edit them only to
  fix a factual or formatting error in an existing lesson; do not add lessons
  by hand (they would not carry a seen-post watermark and could be duplicated
  on the next run).
- The connector commits straight to `main`. Do not move these files, rename
  the H1, or change the `## YYYY-MM-DD` section format; the connector and
  `harness/check-knowledge.py` both depend on it.

## What sessions and humans own

- `verified/YYYY-MM-DD_topic_vN.md`: a fact sheet proven in a session with
  tool output, not read in an article. Start with an H1, say where the
  evidence came from, mark anything unverified as such. A revision is a new
  `vN`, never an overwrite.
- `README.md`, `CONTRIBUTING.md`, `LEDGER.md`, `harness/`, `.github/`.

## Branches and pull requests

- Hand or session changes go on `claude/<topic>` and land through a pull
  request. Connector commits are the one exception.
- The PR body says what changed, pastes the `check-knowledge.py` result, and
  names the risk. A change under `harness/` also pastes `bash harness/tests/run.sh`;
  a change to `harness/knowledge_md.py` or the markdown-it-py pin must keep the
  conformance gate green (see the `conformance` job in `.github/workflows/lint.yml`).
- Found a Markdown shape the checker gets wrong? Render it with the reference
  implementation (commonmark.js 0.31.2) first, then add it to
  `harness/conformance/cases.json` and a failing case to `harness/tests/` before fixing.
- Merge only on green CI.

## Ledger

Every hand or session change adds one row to `LEDGER.md` (newest first).
A row written inside its own pull request says `open`; the next ledger change
flips it to `merged` or `closed` with the merge commit.
Connector runs are not logged there; their trail is the git history of
`knowledge.md`.

## Lint

`.markdownlint.yml` is lenient on purpose (no line-length rule, inline HTML
allowed) so connector output passes unchanged. Run
`npx markdownlint-cli2@0.23.3 "**/*.md"` (the version CI pins) before opening a PR.
