#!/usr/bin/env python3
"""check-knowledge.py — PASS/FAIL structural check of this repo's knowledge files.

Proves that what the daily-dev-agentic connector (and hand edits) wrote still
has the shape every reader relies on:

  knowledge.md   H1, then `## YYYY-MM-DD` sections (real calendar dates, no
                 repeats) newest first; every top-level bullet in a section is
                 a bold lesson with "Why it matters here", "Do:", and a
                 "Source:" line carrying a link and a 0-100 confidence
  lessons/       one YYYY-MM-DD.md per day section in knowledge.md, no
                 orphans, and the same lessons (titles, order, shape) per day
  verified/      files named YYYY-MM-DD_topic_vN.md that start with an H1

Contract: one line per check (PASS|WARN|FAIL name evidence), final RESULT
line, exit 0 only when nothing FAILed. `--json` prints one JSON object.

Run:  python3 harness/check-knowledge.py [--json]
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS: list[dict] = []

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECTION_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
LESSON_RE = re.compile(r"^- \*\*.+\*\*\s*$")
SOURCE_RE = re.compile(r"^\s+- Source: \[[^\]]+\]\(https?://[^)]+\).*confidence (\d{1,3})%")
PLAIN_BULLET_RE = re.compile(r"^- (?!\*\*)\S")   # a top-level bullet that is not a bold lesson


def valid_date(s: str) -> bool:
    """True only for a real ISO calendar date (rejects 2026-99-99)."""
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False
VERIFIED_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9-]+_v\d+\.md$")


def record(status: str, name: str, detail: str) -> None:
    RESULTS.append({"status": status, "name": name, "detail": detail})


def ok(name: str, detail: str) -> None:
    record("PASS", name, detail)


def warn(name: str, detail: str) -> None:
    record("WARN", name, detail)


def fail(name: str, detail: str) -> None:
    record("FAIL", name, detail)


def parse_lessons(lines: list[str]) -> tuple[dict[str, list[dict]], list[str]]:
    """Return ({date: [lesson dicts]}, [duplicate dates]) for a knowledge-style file.

    A repeated `## YYYY-MM-DD` heading is recorded as a duplicate and its
    lessons are appended to the first occurrence, so nothing is silently lost.
    A top-level bullet inside a day section that is not a bold lesson is
    recorded as a malformed lesson (why/do/source all False) so it FAILs the
    shape check instead of vanishing from the count.
    """
    sections: dict[str, list[dict]] = {}
    duplicates: list[str] = []
    current: str | None = None
    lesson: dict | None = None
    for ln in lines:
        m = SECTION_RE.match(ln)
        if m:
            current = m.group(1)
            if current in sections:
                duplicates.append(current)
            else:
                sections[current] = []
            lesson = None
            continue
        if current is None:
            continue
        if LESSON_RE.match(ln):
            lesson = {"why": False, "do": False, "source": False, "title": ln.strip().strip("-").strip().strip("*").strip()}
            sections[current].append(lesson)
            continue
        if PLAIN_BULLET_RE.match(ln):
            lesson = {"why": False, "do": False, "source": False, "malformed": True, "title": "MALFORMED: " + ln[2:].strip()[:50]}
            sections[current].append(lesson)
            continue
        if lesson is not None and ln.startswith("  - "):
            if "Why it matters here:" in ln:
                lesson["why"] = True
            elif ln.strip().startswith("- Do:"):
                lesson["do"] = True
            else:
                sm = SOURCE_RE.match(ln)
                if sm:
                    lesson["source"] = 0 <= int(sm.group(1)) <= 100
                    if not lesson["source"]:
                        lesson["confidence_out_of_range"] = int(sm.group(1))
    return sections, duplicates


def shape_errors(sections: dict[str, list[dict]]) -> list[str]:
    """Names of lesson-shape problems as 'date#n:field'."""
    out: list[str] = []
    for d, ls in sections.items():
        for i, l in enumerate(ls, 1):
            if l.get("malformed"):
                out.append(f"{d}#{i}:not-a-bold-lesson-bullet")
                continue
            for k in ("why", "do", "source"):
                if not l[k]:
                    out.append(f"{d}#{i}:{k}" + (f"(confidence {l['confidence_out_of_range']}% out of 0-100)" if k == "source" and "confidence_out_of_range" in l else ""))
    return out


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
    sections, dup_dates = parse_lessons(lines)
    dates = list(sections)
    if not dates:
        fail("knowledge:sections", "no `## YYYY-MM-DD` sections")
    else:
        ok("knowledge:sections", f"{len(dates)} day section(s), {sum(len(v) for v in sections.values())} lesson(s)")
        if dates == sorted(dates, reverse=True):
            ok("knowledge:order", "newest first")
        else:
            fail("knowledge:order", f"sections not newest-first: {dates}")
        if dup_dates:
            fail("knowledge:unique-dates", f"day section repeated: {sorted(set(dup_dates))}")
        else:
            ok("knowledge:unique-dates", "no repeated day sections")
        impossible = [d for d in dates if not valid_date(d)]
        if impossible:
            fail("knowledge:real-dates", f"not calendar dates: {impossible}")
        else:
            ok("knowledge:real-dates", "every day section is a real calendar date")
    bad = shape_errors(sections)
    if bad:
        fail("knowledge:lesson-shape", f"{len(bad)} missing field(s): " + ", ".join(bad[:6]))
    elif sections:
        ok("knowledge:lesson-shape", "every lesson has why / do / source+confidence")
    empty = [d for d, ls in sections.items() if not ls]
    if empty:
        warn("knowledge:empty-days", f"day sections with no lessons: {empty}")

# --- lessons/ --------------------------------------------------------------
ldir = ROOT / "lessons"
if not ldir.is_dir():
    if sections:
        fail("lessons/", f"directory missing but knowledge.md has {len(sections)} day section(s)")
    else:
        warn("lessons/", "directory missing (no day sections to cover)")
else:
    files = sorted(p.name for p in ldir.glob("*.md"))
    stray = [f for f in files if not DATE_RE.match(f[:-3]) or not valid_date(f[:-3])]
    if stray:
        fail("lessons:names", f"not a real YYYY-MM-DD.md: {stray}")
    else:
        ok("lessons:names", f"{len(files)} file(s), all dated")
    missing = [d for d in sections if f"{d}.md" not in files]
    extra = [f[:-3] for f in files if f[:-3] not in sections]
    if missing:
        fail("lessons:coverage", f"days in knowledge.md without a lessons file: {missing}")
    elif sections:
        ok("lessons:coverage", "every day section has a lessons file")
    if extra:
        fail("lessons:orphans", f"lessons files with no knowledge.md section: {extra}")
    for d in sections:
        p = ldir / f"{d}.md"
        if not p.is_file():
            continue
        day_lines = p.read_text(encoding="utf-8").splitlines()
        # A per-day file has no `## date` heading of its own: parse it as that day's section.
        day_sections, day_dups = parse_lessons([f"## {d}"] + [ln for ln in day_lines if not SECTION_RE.match(ln)])
        day_lessons = day_sections.get(d, [])
        problems: list[str] = []
        bad_day = shape_errors({d: day_lessons})
        if bad_day:
            problems.append(f"missing field(s) {bad_day[:4]}")
        titles_k = [l["title"] for l in sections[d]]
        titles_d = [l["title"] for l in day_lessons]
        if titles_d != titles_k:
            only_k = [t[:40] for t in titles_k if t not in titles_d]
            only_d = [t[:40] for t in titles_d if t not in titles_k]
            problems.append(f"{len(titles_d)} lesson(s) here vs {len(titles_k)} in knowledge.md"
                            + (f"; only in knowledge.md: {only_k}" if only_k else "")
                            + (f"; only here: {only_d}" if only_d else "")
                            + (("; same set, different order" if len(titles_d) == len(titles_k) else "; a title repeats") if not only_k and not only_d else ""))
        if problems:
            fail(f"lessons:{d}", "; ".join(problems))
        else:
            ok(f"lessons:{d}", f"{len(day_lessons)} lesson(s), same titles and shape as knowledge.md")

# --- verified/ -------------------------------------------------------------
vdir = ROOT / "verified"
if not vdir.is_dir():
    warn("verified/", "directory missing")
else:
    vfiles = sorted(p for p in vdir.glob("*.md"))
    badnames = [p.name for p in vfiles if not VERIFIED_NAME_RE.match(p.name) or not valid_date(p.name[:10])]
    if badnames:
        fail("verified:names", f"not a real YYYY-MM-DD_topic_vN.md: {badnames}")
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
