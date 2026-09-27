#!/usr/bin/env python3
"""check-knowledge.py — PASS/FAIL structural check of this repo's knowledge files.

Proves that what the daily-dev-agentic connector (and hand edits) wrote still
has the shape every reader relies on:

  knowledge.md   H1, then `## YYYY-MM-DD` sections newest first; every lesson
                 is a bold bullet with "Why it matters here", "Do:", and a
                 "Source:" line carrying a link and a confidence percentage
  lessons/       one YYYY-MM-DD.md per day section in knowledge.md, and the
                 same lesson count per day
  verified/      files named YYYY-MM-DD_topic_vN.md that start with an H1

Contract: one line per check (PASS|WARN|FAIL name evidence), final RESULT
line, exit 0 only when nothing FAILed. `--json` prints one JSON object.

Run:  python3 harness/check-knowledge.py [--json]
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS: list[dict] = []

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECTION_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
LESSON_RE = re.compile(r"^- \*\*.+\*\*\s*$")
SOURCE_RE = re.compile(r"^\s+- Source: \[[^\]]+\]\(https?://[^)]+\).*confidence \d{1,3}%")
VERIFIED_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9-]+_v\d+\.md$")


def record(status: str, name: str, detail: str) -> None:
    RESULTS.append({"status": status, "name": name, "detail": detail})


def ok(name: str, detail: str) -> None:
    record("PASS", name, detail)


def warn(name: str, detail: str) -> None:
    record("WARN", name, detail)


def fail(name: str, detail: str) -> None:
    record("FAIL", name, detail)


def parse_lessons(lines: list[str]) -> dict[str, list[dict]]:
    """Return {date: [lesson dicts]} for a knowledge-style file."""
    sections: dict[str, list[dict]] = {}
    current: str | None = None
    lesson: dict | None = None
    for ln in lines:
        m = SECTION_RE.match(ln)
        if m:
            current = m.group(1)
            sections[current] = []
            lesson = None
            continue
        if current is None:
            continue
        if LESSON_RE.match(ln):
            lesson = {"why": False, "do": False, "source": False, "title": ln.strip("- *\n")[:60]}
            sections[current].append(lesson)
            continue
        if lesson is not None and ln.startswith("  - "):
            if "Why it matters here:" in ln:
                lesson["why"] = True
            elif ln.strip().startswith("- Do:"):
                lesson["do"] = True
            elif SOURCE_RE.match(ln):
                lesson["source"] = True
    return sections


# --- knowledge.md ----------------------------------------------------------
kpath = ROOT / "knowledge.md"
if not kpath.is_file():
    fail("knowledge.md", "missing")
    sections: dict[str, list[dict]] = {}
else:
    lines = kpath.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].startswith("# "):
        ok("knowledge:h1", lines[0][:70])
    else:
        fail("knowledge:h1", "first line is not an H1")
    sections = parse_lessons(lines)
    dates = list(sections)
    if not dates:
        fail("knowledge:sections", "no `## YYYY-MM-DD` sections")
    else:
        ok("knowledge:sections", f"{len(dates)} day section(s), {sum(len(v) for v in sections.values())} lesson(s)")
        if dates == sorted(dates, reverse=True):
            ok("knowledge:order", "newest first")
        else:
            fail("knowledge:order", f"sections not newest-first: {dates}")
        if len(set(dates)) != len(dates):
            fail("knowledge:unique-dates", "duplicate day sections")
    bad = [(d, i, k) for d, ls in sections.items() for i, l in enumerate(ls, 1) for k in ("why", "do", "source") if not l[k]]
    if bad:
        fail("knowledge:lesson-shape", f"{len(bad)} missing field(s): " + ", ".join(f"{d}#{i}:{k}" for d, i, k in bad[:6]))
    elif sections:
        ok("knowledge:lesson-shape", "every lesson has why / do / source+confidence")
    empty = [d for d, ls in sections.items() if not ls]
    if empty:
        warn("knowledge:empty-days", f"day sections with no lessons: {empty}")

# --- lessons/ --------------------------------------------------------------
ldir = ROOT / "lessons"
if not ldir.is_dir():
    warn("lessons/", "directory missing")
else:
    files = sorted(p.name for p in ldir.glob("*.md"))
    stray = [f for f in files if not DATE_RE.match(f[:-3])]
    if stray:
        fail("lessons:names", f"not YYYY-MM-DD.md: {stray}")
    else:
        ok("lessons:names", f"{len(files)} file(s), all dated")
    missing = [d for d in sections if f"{d}.md" not in files]
    extra = [f[:-3] for f in files if f[:-3] not in sections]
    if missing:
        fail("lessons:coverage", f"days in knowledge.md without a lessons file: {missing}")
    elif sections:
        ok("lessons:coverage", "every day section has a lessons file")
    if extra:
        warn("lessons:orphans", f"lessons files with no knowledge.md section: {extra}")
    for d in sections:
        p = ldir / f"{d}.md"
        if p.is_file():
            n_day = sum(1 for ln in p.read_text(encoding="utf-8").splitlines() if LESSON_RE.match(ln))
            n_k = len(sections[d])
            if n_day == n_k:
                ok(f"lessons:{d}", f"{n_day} lesson(s) match knowledge.md")
            else:
                fail(f"lessons:{d}", f"{n_day} lesson(s) here vs {n_k} in knowledge.md")

# --- verified/ -------------------------------------------------------------
vdir = ROOT / "verified"
if not vdir.is_dir():
    warn("verified/", "directory missing")
else:
    vfiles = sorted(p for p in vdir.glob("*.md"))
    badnames = [p.name for p in vfiles if not VERIFIED_NAME_RE.match(p.name)]
    if badnames:
        fail("verified:names", f"not YYYY-MM-DD_topic_vN.md: {badnames}")
    else:
        ok("verified:names", f"{len(vfiles)} sheet(s), all dated and versioned")
    noh1 = [p.name for p in vfiles if not p.read_text(encoding="utf-8").lstrip().startswith("# ")]
    if noh1:
        fail("verified:h1", f"no H1: {noh1}")
    elif vfiles:
        ok("verified:h1", "every sheet starts with an H1")

# --- summary ---------------------------------------------------------------
counts = {s: sum(r["status"] == s for r in RESULTS) for s in ("PASS", "WARN", "FAIL")}
passed = counts["FAIL"] == 0
if "--json" in sys.argv:
    print(json.dumps({"ok": passed, **{k.lower(): v for k, v in counts.items()}, "checks": RESULTS}))
else:
    for r in RESULTS:
        print(f"{r['status']:<4} {r['name']:<24} {r['detail']}")
    print("----")
    print(f"RESULT: {'PASS' if passed else 'FAIL'} — {counts['PASS']} pass, {counts['WARN']} warn, {counts['FAIL']} fail")
sys.exit(0 if passed else 1)
