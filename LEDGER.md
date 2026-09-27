# Ledger

One row per hand-made or session-made change. Newest first. Connector runs are
not logged here; `git log -- knowledge.md` is their trail.

Columns: **Date** is UTC. **Session** is the claude.ai/code link or `hand`.
**Outcome** is one of `merged`, `closed`, `open`, `direct` (committed to main).
**Evidence** is the commit, PR, or harness result that proves it.

| Date | Session | Branch | PR | Outcome | Evidence |
| --- | --- | --- | --- | --- | --- |
| 2026-09-27 | [session_01T7N2VsxDrRZPwWM7zdFnuK](https://claude.ai/code/session_01T7N2VsxDrRZPwWM7zdFnuK) | `claude/face-lift-v1` | #1 | open | correction: `verified/2026-09-26_claude-surfaces_v2.md` (session ran in the chat/Cowork tab, not the Code tab — T's correction 2026-09-27); v1 banner-marked superseded |
| 2026-09-27 | [session_01T7N2VsxDrRZPwWM7zdFnuK](https://claude.ai/code/session_01T7N2VsxDrRZPwWM7zdFnuK) | `claude/face-lift-v1` | #1 | open | README restructure, CONTRIBUTING, ledger, `harness/check-knowledge.py` (RESULT: PASS — 12 pass, 0 warn, 0 fail after review fixes), lint CI, description + topics set via `gh` on the linked PC; follow-up pushes fix 3 Sourcery + 107 Codex findings (23 rounds; rounds 22-23 also rewrote 5 earlier suite cases that CommonMark, checked against commonmark.js 0.31.2, had the other way) |
| 2026-09-26 | [session_01T7N2VsxDrRZPwWM7zdFnuK](https://claude.ai/code/session_01T7N2VsxDrRZPwWM7zdFnuK) | `main` | — | direct | commit `ef0c3ac`: `verified/2026-09-26_claude-surfaces_v1.md` |
| 2026-08-24 | Cowork session | `main` | — | direct | commits `27aa529`…`0763bf4`: repo bootstrap, first 5 lessons (`cfd032a`), README |
