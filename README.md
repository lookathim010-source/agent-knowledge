# agent-knowledge

The readable memory of T's daily-dev-agentic loop. Written by the daily.dev MCP connector (Cloudflare Worker `dailydevplugd`).

- `knowledge.md` — all lessons, newest day first; every lesson links its daily.dev source post.
- `lessons/YYYY-MM-DD.md` — the same lessons as one file per day.
- `verified/YYYY-MM-DD_topic_vN.md` — session-verified fact sheets written by Claude sessions (not daily.dev lessons); hand-maintained.

Each lesson is distilled by the agent from community-vetted daily.dev posts on T's stack (Claude Code, MCP, multi-agent systems, LangGraph, Firebase, Python, Rust, local LLMs, fintech infra) and carries a confidence score. Run state (seen-post watermark, counters) lives in Cloudflare KV, not here. Hand edits are safe — the connector only ever inserts and de-duplicates by source link.
