#!/usr/bin/env python3
"""check-knowledge.py — PASS/FAIL structural check of this repo's knowledge files.

Proves that what the daily-dev-agentic connector (and hand edits) wrote still
has the shape every reader relies on:

  knowledge.md   the exact connector H1, then only `## YYYY-MM-DD` sections
                 (real calendar dates, no repeats, no other H2s) newest first; every top-level
                 bullet in a section is a bold lesson with a non-empty
                 "Why it matters here:", a non-empty "Do:", and a "Source:"
                 line carrying a link and a 0-100 confidence
  lessons/       one readable YYYY-MM-DD.md per day section in knowledge.md,
                 no orphans, no `## ` headings of its own, and lesson
                 content identical (title, why, do, source) to that day's
                 section in knowledge.md, in the same order
  verified/      readable files named YYYY-MM-DD_topic_vN.md (real dates)
                 whose first non-blank line is a real H1 (not indented 4+)

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

KNOWLEDGE_H1 = "# daily-dev-agentic knowledge — T agent"   # the connector depends on this exact line

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECTION_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
LESSON_RE = re.compile(r"^- \*\*(.+?)\*\*\s*$")                 # well-formed bold lesson bullet
TOP_BULLET_RE = re.compile(r"^(?:[-*+]|\d+[.)]) +\S")           # any top-level list item, any marker
WHY_RE = re.compile(r"^  - Why it matters here: (\S.*)$")
DO_RE = re.compile(r"^  - Do: (\S.*)$")
SOURCE_RE = re.compile(r"^  - Source: \[[^\]]+\]\(https?://[^)\s]+\).*confidence (\d{1,3})%")
VERIFIED_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9-]+_v\d+\.md$")
H1_LINE_RE = re.compile(r"^ {0,3}# \S")   # a real ATX H1: at most 3 leading spaces (4 = code block)
FIELDS = ("why", "do", "source")
H2_RE = re.compile(r"^##(?:\s|$)")   # any ATX H2, including a bare `##`
bad_headings: list[str] = []   # filled by parse_lessons: H2s that are not valid day headings


def record(status: str, name: str, detail: str) -> None:
    RESULTS.append({"status": status, "name": name, "detail": detail})


def ok(name: str, detail: str) -> None:
    record("PASS", name, detail)


def warn(name: str, detail: str) -> None:
    record("WARN", name, detail)


def fail(name: str, detail: str) -> None:
    record("FAIL", name, detail)


def valid_date(s: str) -> bool:
    """True only for a real ISO calendar date (rejects 2026-99-99)."""
    try:
        datetime.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def norm(s: str) -> str:
    return " ".join(s.split())


def parse_lessons(lines: list[str]) -> tuple[dict[str, list[dict]], list[str]]:
    """Return ({date: [lesson]}, [duplicate dates]) for a knowledge-style file.

    A lesson is {"title", "why", "do", "source", "problems"} with the field
    TEXT (normalized) so two copies can be compared, and a list of problems:
    missing or empty fields, a confidence outside 0-100, or a top-level bullet
    that is not a well-formed bold lesson (recorded, never dropped, so a
    malformed lesson can't vanish from the count). A repeated `## date`
    heading is recorded as a duplicate; its lessons join the first occurrence.
    """
    sections: dict[str, list[dict]] = {}
    duplicates: list[str] = []
    current: str | None = None
    lesson: dict | None = None
    bad_headings.clear()

    def new_lesson(title: str, malformed: bool) -> dict:
        return {"title": norm(title), "why": "", "do": "", "source": "",
                "problems": (["not-a-bold-lesson-bullet"] if malformed else [])}

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
        if H2_RE.match(ln):                       # an H2 that is not `## YYYY-MM-DD`
            bad_headings.append(ln.strip())
            current = None                        # nothing after it belongs to a day
            lesson = None
            continue
        if current is None:
            continue
        m = LESSON_RE.match(ln)
        if m:
            lesson = new_lesson(m.group(1), malformed=False)
            sections[current].append(lesson)
            continue
        if TOP_BULLET_RE.match(ln):
            lesson = new_lesson("MALFORMED: " + ln.split(None, 1)[1].strip(), malformed=True)
            sections[current].append(lesson)
            continue
        if lesson is None:
            continue
        if (m := WHY_RE.match(ln)):
            lesson["why"] = norm(m.group(1))
        elif (m := DO_RE.match(ln)):
            lesson["do"] = norm(m.group(1))
        elif (m := SOURCE_RE.match(ln)):
            conf = int(m.group(1))
            if 0 <= conf <= 100:
                lesson["source"] = norm(ln.strip()[2:])
            else:
                lesson["problems"].append(f"confidence {conf}% out of 0-100")

    for ls in sections.values():
        for l in ls:
            if "not-a-bold-lesson-bullet" in l["problems"]:
                continue
            for k in FIELDS:
                if not l[k] and not (k == "source" and any(p.startswith("confidence") for p in l["problems"])):
                    l["problems"].append(f"missing or empty {k}")
    return sections, duplicates


def shape_errors(sections: dict[str, list[dict]]) -> list[str]:
    """Problems as 'date#n: problem'."""
    return [f"{d}#{i}: {p}" for d, ls in sections.items() for i, l in enumerate(ls, 1) for p in l["problems"]]


def lesson_key(l: dict) -> tuple[str, str, str, str]:
    return (l["title"], l["why"], l["do"], l["source"])


# --- knowledge.md ----------------------------------------------------------
kpath = ROOT / "knowledge.md"
sections: dict[str, list[dict]] = {}
if not kpath.is_file():
    fail("knowledge.md", "missing")
else:
    lines = kpath.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].rstrip() == KNOWLEDGE_H1:
        ok("knowledge:h1", "exact connector heading present")
    else:
        fail("knowledge:h1", f"first line must be {KNOWLEDGE_H1!r}, got {(lines[0] if lines else '')[:70]!r}")
    sections, dup_dates = parse_lessons(lines)
    k_bad_headings = list(bad_headings)
    dates = list(sections)
    if k_bad_headings:
        fail("knowledge:headings", f"H2 headings that are not `## YYYY-MM-DD`: {k_bad_headings[:4]}")
    else:
        ok("knowledge:headings", "every H2 is a day heading")
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
        fail("knowledge:lesson-shape", f"{len(bad)} problem(s): " + "; ".join(bad[:6]))
    elif sections:
        ok("knowledge:lesson-shape", "every lesson is a bold bullet with non-empty why / do / source (confidence 0-100)")
    empty = [d for d, ls in sections.items() if not ls]
    if empty:
        fail("knowledge:empty-days", f"day sections with no recognizable lessons: {empty}")

# --- lessons/ --------------------------------------------------------------
ldir = ROOT / "lessons"
if not ldir.is_dir():
    if sections:
        fail("lessons/", f"directory missing but knowledge.md has {len(sections)} day section(s)")
    else:
        warn("lessons/", "directory missing (no day sections to cover)")
else:
    entries = sorted(ldir.glob("*.md"))
    unreadable = [p.name for p in entries if not p.is_file()]   # dangling symlinks, directories
    if unreadable:
        fail("lessons:readable", f"not readable regular files: {unreadable}")
    files = [p.name for p in entries if p.is_file()]
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
        problems: list[str] = []
        stray_headings = [ln.strip() for ln in day_lines if H2_RE.match(ln)]
        if stray_headings:
            problems.append(f"contains H2 heading(s) {stray_headings[:4]} — a per-day file has no `## ` headings")
        # A per-day file carries no `## ` heading of its own: parse it as that day's section.
        day_sections, _ = parse_lessons([f"## {d}"] + [ln for ln in day_lines if not H2_RE.match(ln)])
        day_lessons = day_sections.get(d, [])
        bad_day = shape_errors({d: day_lessons})
        if bad_day:
            problems.append(f"shape: {bad_day[:4]}")
        keys_k = [lesson_key(l) for l in sections[d]]
        keys_d = [lesson_key(l) for l in day_lessons]
        if keys_d != keys_k:
            titles_k = {k[0] for k in keys_k}
            titles_d = {k[0] for k in keys_d}
            only_k = [k[0][:40] for k in keys_k if k[0] not in titles_d]   # title absent from the day file
            only_d = [k[0][:40] for k in keys_d if k[0] not in titles_k]   # title absent from knowledge.md
            diff_fields: list[str] = []
            for a, b in zip(keys_k, keys_d):
                if a != b and a[0] == b[0]:
                    diff_fields.append(a[0][:30] + ": " + ",".join(f for f, x, y in zip(("title",) + FIELDS, a, b) if x != y))
            detail = f"{len(keys_d)} lesson(s) here vs {len(keys_k)} in knowledge.md"
            if diff_fields:
                detail += f"; same title, different content: {diff_fields[:3]}"
            if only_k:
                detail += f"; only in knowledge.md: {only_k[:3]}"
            if only_d:
                detail += f"; only here: {only_d[:3]}"
            if not diff_fields and not only_k and not only_d:
                detail += "; same set, different order" if len(keys_d) == len(keys_k) else "; a lesson repeats"
            problems.append(detail)
        if problems:
            fail(f"lessons:{d}", "; ".join(problems))
        else:
            ok(f"lessons:{d}", f"{len(day_lessons)} lesson(s), identical content and order to knowledge.md")

# --- verified/ -------------------------------------------------------------
vdir = ROOT / "verified"
if not vdir.is_dir():
    warn("verified/", "directory missing")
else:
    ventries = sorted(vdir.glob("*.md"))
    vunreadable = [p.name for p in ventries if not p.is_file()]
    if vunreadable:
        fail("verified:readable", f"not readable regular files: {vunreadable}")
    vfiles = [p for p in ventries if p.is_file()]
    badnames = [p.name for p in vfiles if not VERIFIED_NAME_RE.match(p.name) or not valid_date(p.name[:10])]
    if badnames:
        fail("verified:names", f"not a real YYYY-MM-DD_topic_vN.md: {badnames}")
    else:
        ok("verified:names", f"{len(vfiles)} sheet(s), all dated and versioned")
    def first_nonblank(p: pathlib.Path) -> str:
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                return ln
        return ""
    noh1 = [p.name for p in vfiles if not H1_LINE_RE.match(first_nonblank(p))]
    if noh1:
        fail("verified:h1", f"first non-blank line is not an H1 (indent ≤3, `# `): {noh1}")
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
