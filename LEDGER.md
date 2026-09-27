# Ledger

One row per hand-made or session-made change. Newest first. Connector runs are
not logged here; `git log -- knowledge.md` is their trail.

Columns: **Date** is UTC. **Session** is the claude.ai/code link or `hand`.
**Outcome** is one of `merged`, `closed`, `open`, `direct` (committed to main).
**Evidence** is the commit, PR, or harness result that proves it.

| Date | Session | Branch | PR | Outcome | Evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-09-27 | [session_01T7N2VsxDrRZPwWM7zdFnuK](https://claude.ai/code/session_01T7N2VsxDrRZPwWM7zdFnuK) | `claude/harness-v2` | #2 | open | harness v2: `check-knowledge.py` rebuilt on markdown-it-py (1,345 → 597 lines + 52-line `knowledge_md.py`), 201 negative-test cases moved into `harness/tests/` and CI, CommonMark conformance gate (652/652 spec examples, 42 edge cases vs commonmark.js 0.31.2), 4 old test assertions corrected with reference evidence, `verified/…_v3.md` for the launch-pad rename, lesson feed documented as paused, PR #1 rows flipped to merged (merge `7946224`); 2nd push fixes 5 Codex findings on `78d12a9` (offsets after `<pre>`, invisible-only fields, comments in labels, `--json` without deps, code splitting the confidence word) with round-28 suite (17 cases, 218 total) and a shellcheck + pyflakes CI job |
| 2026-09-27 | [session_01T7N2VsxDrRZPwWM7zdFnuK](https://claude.ai/code/session_01T7N2VsxDrRZPwWM7zdFnuK) | `claude/face-lift-v1` | #1 | merged | correction: `verified/2026-09-26_claude-surfaces_v2.md` (session ran in the chat/Cowork tab, not the Code tab — T's correction 2026-09-27); v1 banner-marked superseded |
| 2026-09-27 | [session_01T7N2VsxDrRZPwWM7zdFnuK](https://claude.ai/code/session_01T7N2VsxDrRZPwWM7zdFnuK) | `claude/face-lift-v1` | #1 | merged | README restructure, CONTRIBUTING, ledger, `harness/check-knowledge.py` (RESULT: PASS — 12 pass, 0 warn, 0 fail after review fixes), lint CI, description + topics set via `gh` on the linked PC; follow-up pushes fix 3 Sourcery + 129 Codex findings, 1 pushed back with evidence (27 rounds; rounds 22-25 also rewrote 14 earlier suite cases whose vehicle or CommonMark reading no longer held, each checked against commonmark.js 0.31.2 or by mutation) |
| 2026-09-26 | [session_01T7N2VsxDrRZPwWM7zdFnuK](https://claude.ai/code/session_01T7N2VsxDrRZPwWM7zdFnuK) | `main` | — | direct | commit `ef0c3ac`: `verified/2026-09-26_claude-surfaces_v1.md` |
| 2026-08-24 | Cowork session | `main` | — | direct | commits `27aa529`…`0763bf4`: repo bootstrap, first 5 lessons (`cfd032a`), README |
