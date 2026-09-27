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
                 headed `# Lessons — <that date>`, no orphans, no `## `
                 headings of its own, and lesson
                 content identical (title, why, do, source) to that day's
                 section in knowledge.md, in the same order
  verified/      only readable files named YYYY-MM-DD_topic_vN.md (real dates)
                 whose first non-blank line is a real H1 (not indented 4+)
  Text inside HTML comments or fenced code blocks never counts as content.

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
SECTION_RE = re.compile(r"^ {0,3}## (\d{4}-\d{2}-\d{2})\s*$")
LESSON_RE = re.compile(r"^ {0,3}- \*\*(.+?)\*\*\s*$")           # well-formed bold lesson bullet (≤3-space indent is still top level)
TOP_BULLET_RE = re.compile(r"^ {0,3}(?:[-*+]|\d+[.)])(?: +\S|\s*$)")   # any top-level list item incl. an EMPTY one, any marker, ≤3-space indent
FIELD_LABEL_RE = re.compile(r"^\s*- (Why it matters here|Do|Source):(.*)$")   # label first, value validated after (nesting checked by indent)
LINK_LABEL = r"\[(?:\\.|[^\]\\])+\]"                                          # allows escaped \] inside the label
SOURCE_VALUE_RE = re.compile(r"^ " + LINK_LABEL + r"\(https?://[^)\s]+\).*confidence (\d{1,3})%")
DAY_H1_RE = re.compile(r"^# Lessons — (\d{4}-\d{2}-\d{2})\s*$")
VERIFIED_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9-]+_v\d+\.md$")
H1_LINE_RE = re.compile(r"^ {0,3}# \S")   # a real ATX H1: at most 3 leading spaces (4 = code block)
FIELDS = ("why", "do", "source")
H2_RE = re.compile(r"^ {0,3}##(?:\s|$)")   # any ATX H2 (≤3-space indent), including a bare `##`
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


def read_lines(p: pathlib.Path) -> list[str] | None:
    """Lines of a UTF-8 text file, or None (with a FAIL recorded) when it is not valid UTF-8."""
    try:
        return p.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        fail(f"utf8:{p.name}", f"not valid UTF-8 at byte {exc.start}: {exc.reason}")
        return None


FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CODE_SPAN_RE = re.compile(r"(`+)(?!`)(?:.+?)(?<!`)\1(?!`)")   # CommonMark-ish: matching backtick runs
unclosed: list[str] = []   # filled by sanitize: a fence or comment still open at end of file


def sanitize(lines: list[str]) -> list[str]:
    """Return what a reader sees as prose: fenced code and HTML comments blanked.

    Single pass, CommonMark-shaped: inside a fence, nothing is interpreted (a
    `<!--` in code cannot open a comment) and the block closes only on a fence
    of the same character at least as long as the opener with nothing but
    spaces after it. Inside a comment, nothing is interpreted (a ``` in a
    comment cannot open a fence) until `-->`. Line count is preserved.
    """
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    in_comment = False
    unclosed.clear()
    for ln in lines:
        if fence_char is not None:
            m = FENCE_RE.match(ln)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len and m.group(2).strip() == "":
                fence_char = None
            out.append("")
            continue
        if in_comment:
            j = ln.find("-->")
            if j < 0:
                out.append("")
                continue
            in_comment = False
            ln = ln[j + 3:]          # the rest of the line is prose again
        m = FENCE_RE.match(ln)
        if m:
            fence_char, fence_len = m.group(1)[0], len(m.group(1))
            out.append("")
            continue
        # Inline code spans are opaque: a <!-- inside `…` is code, not a comment opener.
        # Mask them (same length, harmless chars) for delimiter scanning; restore text after.
        scan = CODE_SPAN_RE.sub(lambda m: "`" * len(m.group(0)), ln)
        buf: list[str] = []
        i = 0
        while i < len(scan):
            if in_comment:
                j = scan.find("-->", i)
                if j < 0:
                    i = len(scan)
                else:
                    in_comment = False
                    i = j + 3
            else:
                j = scan.find("<!--", i)
                if j < 0:
                    buf.append(ln[i:])
                    i = len(scan)
                else:
                    buf.append(ln[i:j])
                    in_comment = True
                    i = j + 4
        out.append("".join(buf))
    if fence_char is not None:
        unclosed.append(f"fenced code block opened with {fence_char * fence_len} never closes")
    if in_comment:
        unclosed.append("HTML comment never closes")
    return out


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
    lines = sanitize(lines)

    def new_lesson(title: str, malformed: bool) -> dict:
        return {"title": norm(title), "why": "", "do": "", "source": "", "indent": 0, "last": None,
                "seen": {"why": False, "do": False, "source": False},
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
        indent = len(ln) - len(ln.lstrip(" "))
        # CommonMark: a line indented at or past the current lesson's content column
        # (its own indent + 2 for "- ") belongs to that lesson; anything shallower is a sibling.
        nested = lesson is not None and indent >= lesson["indent"] + 2
        if not nested:
            m = LESSON_RE.match(ln)
            if m:
                lesson = new_lesson(m.group(1), malformed=False)
                lesson["indent"] = indent
                sections[current].append(lesson)
                continue
            if TOP_BULLET_RE.match(ln):
                parts = ln.strip().split(None, 1)
                lesson = new_lesson("MALFORMED: " + (parts[1].strip() if len(parts) > 1 else "(empty list item)"), malformed=True)
                lesson["indent"] = indent
                sections[current].append(lesson)
                continue
            continue
        # Nested line. A child list marker is valid only at indent lesson+2 .. lesson+5
        # (CommonMark: ≥ content column + 4 is an indented code block, not a list).
        m = FIELD_LABEL_RE.match(ln)
        if m and indent >= lesson["indent"] + 6:
            lesson["problems"].append(f"field '{m.group(1)}' indented {indent} spaces renders as code, not a nested bullet")
            lesson["last"] = None
            continue
        if not m:
            # continuation text (lazy or indented) belongs to the field above it — or to the title
            text = ln.strip()
            if text and lesson["last"] is not None:
                key = lesson["last"]
                if key == "source":
                    lesson["source"] = norm(lesson["source"] + " " + text) if lesson["source"] else lesson["source"]
                else:
                    lesson[key] = norm(lesson[key] + " " + text)
            elif text and lesson["last"] is None and not lesson["seen"]["why"] and not lesson["seen"]["do"] and not lesson["seen"]["source"]:
                lesson["title"] = norm(lesson["title"] + " " + text)
            continue
        label, value = m.group(1), m.group(2)
        key = {"Why it matters here": "why", "Do": "do", "Source": "source"}[label]
        lesson["last"] = key
        if lesson["seen"][key]:
            lesson["problems"].append(f"duplicate {key}")
        lesson["seen"][key] = True
        if key == "source":
            sm = SOURCE_VALUE_RE.match(value)
            if not sm:
                lesson["problems"].append("source line is not `[title](https://…) … confidence N%`")
            elif not 0 <= int(sm.group(1)) <= 100:
                lesson["problems"].append(f"confidence {sm.group(1)}% out of 0-100")
            else:
                lesson["source"] = norm(value)
        elif value.strip():
            lesson[key] = norm(value)
        else:
            lesson["problems"].append(f"missing or empty {key}")

    for ls in sections.values():
        for l in ls:
            if "not-a-bold-lesson-bullet" in l["problems"]:
                continue
            for k in FIELDS:
                if not l["seen"][k]:
                    l["problems"].append(f"missing {k}")
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
    lines = read_lines(kpath) or []
    if lines and lines[0].rstrip() == KNOWLEDGE_H1:
        ok("knowledge:h1", "exact connector heading present")
    else:
        fail("knowledge:h1", f"first line must be {KNOWLEDGE_H1!r}, got {(lines[0] if lines else '')[:70]!r}")
    sections, dup_dates = parse_lessons(lines)
    k_unclosed = list(unclosed)
    if k_unclosed:
        fail("knowledge:unclosed", "; ".join(k_unclosed) + " — everything after it is hidden from readers")
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
    entries = sorted(ldir.iterdir())                            # every entry, not only *.md
    unreadable = [p.name for p in entries if not p.is_file()]   # dangling symlinks, directories
    if unreadable:
        fail("lessons:readable", f"not readable regular files: {unreadable}")
    files = [p.name for p in entries if p.is_file()]
    stray = [f for f in files if not f.endswith(".md") or not DATE_RE.match(f[:-3]) or not valid_date(f[:-3])]
    if stray:
        fail("lessons:names", f"not a real YYYY-MM-DD.md: {stray}")
    else:
        ok("lessons:names", f"{len(files)} file(s), all dated")
    missing = [d for d in sections if f"{d}.md" not in files]
    extra = [f[:-3] for f in files if f.endswith(".md") and f[:-3] not in sections]
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
        raw = read_lines(p)
        if raw is None:
            continue
        day_lines = sanitize(raw)
        problems: list[str] = list(unclosed)
        first = next((ln for ln in day_lines if ln.strip()), "")
        hm = DAY_H1_RE.match(first)
        if not hm:
            problems.append(f"first line must be `# Lessons — {d}`, got {first[:40]!r}")
        elif hm.group(1) != d:
            problems.append(f"H1 date {hm.group(1)} does not match filename {d}")
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
    ventries = sorted(vdir.iterdir())                           # every entry, not only *.md
    vunreadable = [p.name for p in ventries if not p.is_file()]
    if vunreadable:
        fail("verified:readable", f"not readable regular files: {vunreadable}")
    vfiles = [p for p in ventries if p.is_file()]
    badnames = [p.name for p in vfiles if not VERIFIED_NAME_RE.match(p.name) or not valid_date(p.name[:10])]
    if badnames:
        fail("verified:names", f"not a real YYYY-MM-DD_topic_vN.md: {badnames}")
    else:
        ok("verified:names", f"{len(vfiles)} sheet(s), all dated and versioned")
    def first_nonblank(p: pathlib.Path) -> str | None:
        lines = read_lines(p)
        if lines is None:
            return None
        for ln in lines:
            if ln.strip():
                return ln
        return ""
    firsts = {p.name: first_nonblank(p) for p in vfiles}
    noh1 = [n for n, f in firsts.items() if f is not None and not H1_LINE_RE.match(f)]
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
