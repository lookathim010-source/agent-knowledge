# Verified: Claude surfaces — cloud sessions from the chat/Cowork tab vs the Code tab (2026-09-26, corrected and renamed 2026-09-27)

Source: live tool runs in cloud session <https://claude.ai/code/session_01T7N2VsxDrRZPwWM7zdFnuK> — opened from the **chat/Cowork tab**, not the Code tab (T's correction, 2026-09-27; v1 of this sheet mislabelled it) — plus the current Claude Code docs (claude-code-on-the-web, routines, claude-projects, remote-control) and the Cowork scheduled-tasks help article. Not a daily.dev lesson — a session-verified fact sheet.

## Core finding

"Chat/Cowork is file-out, Code tab is repo-in/repo-out" is false. It is one cloud harness (Claude Code Remote) with many front doors: the chat/Cowork tab, claude.ai/code, mobile Code tab, desktop app "Cloud", `claude --cloud`, routines, Claude Tag. Pick the door by what the session must be handed at birth: GitHub push credential + PR tooling → cloud session; a folder on the PC → Cowork/desktop. Routines, connectors, sub-agents and artifacts travel with all of them.

## Verified live (cloud session opened from the chat/Cowork tab)

- `add_repo(push)` → shallow clone → signed commit → `git push`: native. Credentials never enter the VM; Anthropic's GitHub proxy injects them.
- PR creation via `POST api.github.com/repos/<o>/<r>/pulls` works with the injected credential but REQUIRES `Content-Type: application/json` (proxy returns HTTP 415 without it). `gh` CLI is not installed in the cloud VM.
- Opening a PR auto-subscribes the session (`subscription.created` ~1 s later) under a drive-to-green contract: CI red, merge conflicts and non-optional review findings are work now; never skip/disable a test to get green; re-request reviewers after pushing.
- Scheduled tasks: create / list / delete from a cloud session work. Run-once tasks don't count against the daily routine cap. `send_later` re-arms same-session check-ins.
- Parallel sub-agents run concurrently (two agents, overlapping timestamps).
- A cloud session reaches the linked PC through the device bridge (get_device_info → win32 "my-damn-pc", desktop app 2.9939.2; local MCP servers Filesystem, memory, local-kb-search, sequential-thinking, Windows-MCP).
- The Cowork-created scheduled task (2026-08-24) is listed from this session → one routine store.
- Native push from the chat side: VERIFIED — every push, PR and scheduled-task call in this sheet came from a session opened in the chat/Cowork tab (tab per T's statement; the git/PR/task results are tool-verified). The Cowork session of 2026-08-24 had used a pushbot workaround (this repo, cfd032a; daily-dev-connector with CI); the workaround is not required.

## From the docs (fetched 2026-09-26)

- Remote Control connects claude.ai to a session running on your machine — a local feature viewed remotely. Teleport pulls a cloud session into a local terminal (clean git state, same repo checkout).
- Routines: created from web, desktop app or CLI, all into one cloud account. Desktop "Local" routine = Desktop scheduled task on the machine. Cowork scheduled tasks "can't be tied to a folder on your computer".
- Code-tab Projects (parallel-thread coordinator): public beta on Pro/Max, rolling out first to accounts with cloud-session history and no existing chat/Cowork projects → eligibility for this account UNVERIFIED.
- Auto-fix PRs requires the Claude GitHub App installed on the repo.

## Gotchas

1. After a shallow `add_repo` clone, a pushed branch has no `origin/<branch>` ref (single-branch fetch refspec); the stop-hook falsely reports "unpushed commits / no remote branch". Fix: `git config --add remote.origin.fetch '+refs/heads/X:refs/remotes/origin/X' && git fetch origin X && git branch -u origin/X`.
2. The PC's `memory` knowledge-graph MCP fails from the cloud side (outputSchema declares JSON-Schema draft-07; the cloud validator supports 2020-12 only) — read and write both blocked as of 2026-09-26.
3. The daily-dev-agentic routine reports SUCCEEDED every day, yet this repo has no lesson commits after 2026-08-24: the run exits cleanly on the "connector not attached" branch of its prompt. Green run status ≠ task success.

## Bots seen on the repos

GitGuardian Security Checks · Kilo Code Review (glm-5.3) · Sourcery (no access on private repos; upsell comment only).

## Correction trail

- v1 (commit `ef0c3ac`) labelled the session "Code tab" because T tapped **Code** on the where-does-this-chat-live tile by accident. He corrected it on 2026-09-27; v1 is kept with a superseded banner, this v2 carries the fix. The core finding is unchanged and now stronger: the chat/Cowork-tab session did everything natively.

- v3 (2026-09-27): the proof repository was renamed to `cloud-launch-pad` at T's request; only the Proof artifact line changed.

## Proof artifact

lookathim010-source/cloud-launch-pad (named Claude-Code-Android-App-FULL-ACCESS-ENV-Anthropic-cloud until 2026-09-27; GitHub redirects the old URL) — branch `claude-chat-capability-proof`, commit 9ee5237, PR #1 (merged by T).
