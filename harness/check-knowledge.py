#!/usr/bin/env python3
"""check-knowledge.py — PASS/FAIL structural check of this repo's knowledge files.

Proves that what the daily-dev-agentic connector (and hand edits) wrote still
has the shape every reader relies on:

  knowledge.md   the exact connector H1, then only `## YYYY-MM-DD` sections
                 (real calendar dates, no repeats, no other H2s) newest first; every top-level
                 bullet in a section is a bold lesson with a non-empty
                 "Why it matters here:", a non-empty "Do:", and a "Source:"
                 line carrying a link and a 0-100 confidence; a bullet
                 outside every day section is a FAIL (readers never see it)
  lessons/       one regular (non-symlink) YYYY-MM-DD.md per day section in
                 knowledge.md, headed `# Lessons — <that date>`, no orphans,
                 no `## ` headings of its own, and lesson content identical
                 (title, why, do, source — continuation lines included) to
                 that day's section in knowledge.md, in the same order
  verified/      only regular files named YYYY-MM-DD_topic_vN.md (real dates)
                 whose first visible non-blank line is a real H1 (not indented 4+)
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

CODE_SPAN_RE = re.compile(r"(?<!\\)(`+)(?!`)(?:.+?)(?<!`)\1(?!`)")   # CommonMark-ish: matching, unescaped backtick runs
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SECTION_RE = re.compile(r"^ {0,3}## (\d{4}-\d{2}-\d{2})\s*$")
LESSON_RE = re.compile(r"^ {0,3}-([ \t]+)\*\*(.+?)\*\*\s*$")     # bold lesson bullet: `-`, 1-4 columns of whitespace (checked after), **title**
TOP_BULLET_RE = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:[ \t]+\S|\s*$)")   # any top-level list item incl. an EMPTY one; ordered markers are 1-9 digits (CommonMark)
FIELD_LABEL_RE = re.compile(r"^\s*-[ \t](Why it matters here|Do|Source):(.*)$")   # label first, value validated after (nesting checked by indent)
# Blocks that interrupt a paragraph (CommonMark): an ATX heading, a block quote, a thematic break.
# A line like this at top level is never lazy continuation of the lesson above it.
THEMATIC_BREAK = r"(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$"   # 3+ of the SAME character (`- * -` is not a break)
INTERRUPT_RE = re.compile(r"^ {0,3}(?:#{1,6}(?:\s|$)|>|" + THEMATIC_BREAK + ")")
LINK_LABEL = r"\[(?:\\.|[^\]\\])+\]"                                          # allows escaped \] inside the label
LINK_OPEN_RE = re.compile(r"^" + LINK_LABEL + r"\(")                       # `[label](` — the destination is scanned by hand
CONFIDENCE_RE = re.compile(r"confidence (\d{1,3})%")
ASCII_PUNCT = set(r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""")   # a backslash escapes exactly these (CommonMark)


def parse_source(text: str) -> tuple[str, int] | None:
    """(destination, confidence) for `[label](https://…) … confidence N%`, else None.

    The destination is read the CommonMark way: no whitespace, and parentheses must
    balance — `https://x.y/(broken)` never closes, so it is not a link at all.
    """
    text = text.strip()
    m = LINK_OPEN_RE.match(text)
    if not m:
        return None
    i, depth = m.end(), 0
    while i < len(text):
        c = text[i]
        if c.isspace() or c in "<>":
            return None                              # a bare destination has no whitespace and no unescaped < >
        if c == "\\" and i + 1 < len(text) and text[i + 1] in ASCII_PUNCT:
            i += 2                                   # `\(` is destination text, not a delimiter
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            if depth == 0:
                break
            depth -= 1
        i += 1
    else:
        return None                              # ran off the end without closing the destination
    dest = text[m.end():i]
    if not re.match(r"https?://\S+$", dest):
        return None
    cm = CONFIDENCE_RE.search(text[i + 1:])
    return (dest, int(cm.group(1))) if cm else None
DAY_H1_RE = re.compile(r"^# Lessons — (\d{4}-\d{2}-\d{2})\s*$")
VERIFIED_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9-]+_v\d+\.md$")
H1_LINE_RE = re.compile(r"^ {0,3}#[ \t]+\S")   # a real ATX H1 with text: ≤3 leading spaces (4 = code), space or tab after `#`
FIELDS = ("why", "do", "source")
H2_RE = re.compile(r"^ {0,3}##(?:\s|$)")   # any ATX H2 (≤3-space indent), including a bare `##`
bad_headings: list[str] = []   # filled by parse_lessons: H2s that are not valid day headings
misplaced: list[str] = []      # filled by parse_lessons: top-level bullets that sit under no `## YYYY-MM-DD`


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
    """Collapse prose whitespace, but keep inline code verbatim (`printf 'a  b'` means two spaces)."""
    spans: list[str] = []
    masked = CODE_SPAN_RE.sub(lambda m: (spans.append(m.group(0)), f"\x02{len(spans) - 1}\x02")[1], s)
    out = " ".join(masked.split())
    return re.sub(r"\x02(\d+)\x02", lambda m: spans[int(m.group(1))], out)


HARD_BREAK = "⏎"   # joins two lines of a field when the first ends in a hard line break (2+ spaces or an odd backslash)


def ends_hard(ln: str) -> bool:
    """True when a following line would render after a hard line break, not a soft one."""
    if ln.endswith("  "):
        return True
    if not ln.endswith("\\"):
        return False                                  # `text\ ` — the space, not the backslash, ends the line
    return (len(ln) - len(ln.rstrip("\\"))) % 2 == 1


def regular_file(p: pathlib.Path) -> bool:
    """True only for a plain file: symlinks (live or dangling) and directories are rejected.

    `is_file()` follows a symlink, so a link pointing outside the repo would be read
    and checked as if it were repo content; `lstat()` looks at the entry itself.
    """
    try:
        return not p.is_symlink() and p.is_file()
    except OSError:
        return False


def read_lines(p: pathlib.Path) -> list[str] | None:
    """Lines of a UTF-8 text file (a leading BOM is encoding metadata, not content, and is
    dropped), or None (with a FAIL recorded) when it is not valid UTF-8."""
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        fail(f"utf8:{p.name}", f"not valid UTF-8 at byte {exc.start}: {exc.reason}")
        return None
    # CommonMark line endings are CR, LF and CRLF only; U+2028, U+000C etc. stay inside a line.
    lines = re.split(r"\r\n|\r|\n", text)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FENCE_MARK = "\x00fence"       # left by sanitize() where a fenced block opened, at its indent: a block boundary, never text
COMMENT_MARK = "\x00comment"   # same, where an HTML comment BLOCK (`<!--` at line start) opened
LIST_ITEM_RE = re.compile(r"^( *)([-*+]|\d{1,9}[.)])([ \t]+)\S")   # marker + whitespace + content (for content-column tracking)
THEMATIC_RE = re.compile(r"^ {0,3}" + THEMATIC_BREAK)                 # `---`, `- - -`, `***`: a thematic break outranks a list item
_HTML6 = ("address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|"
          "fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|"
          "menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul")
HTML_BLOCK_RE = re.compile(   # CommonMark HTML block starts that CAN interrupt a paragraph (types 1-6); type 7 cannot
    r"^ {0,3}(?:<(?:script|pre|style|textarea)(?:\s|>|$)|<!--|<\?|<![A-Za-z]|<!\[CDATA\[|</?(?:" + _HTML6 + r")(?:\s|/?>|$))",
    re.IGNORECASE)
HTML_MARK = "\x00html"         # left by sanitize() where an HTML block other than a comment (types 1, 3-7) opened
MARKS = (FENCE_MARK, COMMENT_MARK, HTML_MARK)
_HTML_TYPE1 = re.compile(r"^ {0,3}<(script|pre|style|textarea)(?:\s|>|$)", re.IGNORECASE)
_HTML_TYPE7 = re.compile(   # a complete open or close tag alone on the line (cannot interrupt a paragraph)
    r"^ {0,3}(?:<[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z_:][A-Za-z0-9_.:-]*(?:\s*=\s*(?:[^\s\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*\s*/?>"
    r"|</[A-Za-z][A-Za-z0-9-]*\s*>)\s*$")


def html_block_start(rel: str, in_paragraph: bool) -> tuple[str, str | None] | None:
    """(mark, end) when `rel` (a line with its container indent stripped) opens a CommonMark
    HTML block: `end` is the substring that closes it (on this or a later line, that line
    included), or None for a block that ends at the next blank line. Type 7 never starts
    inside a paragraph."""
    m = _HTML_TYPE1.match(rel)
    if m:
        return HTML_MARK, "</" + m.group(1).lower() + ">"
    if re.match(r"^ {0,3}<!--", rel):
        return COMMENT_MARK, "-->"
    if re.match(r"^ {0,3}<\?", rel):
        return HTML_MARK, "?>"
    if re.match(r"^ {0,3}<!\[CDATA\[", rel):
        return HTML_MARK, "]]>"
    if re.match(r"^ {0,3}<![A-Za-z]", rel):
        return HTML_MARK, ">"
    if re.match(r"^ {0,3}</?(?:" + _HTML6 + r")(?:\s|/?>|$)", rel, re.IGNORECASE):
        return HTML_MARK, None
    if not in_paragraph and _HTML_TYPE7.match(rel):
        return HTML_MARK, None
    return None
INNER_STRONG_RE = re.compile(r"(?<!\\)\*\*")                        # an unescaped ** inside a title: not ONE strong span
unclosed: list[str] = []   # filled by sanitize: a fence or comment still open at end of file


def is_mark(ln: str) -> bool:
    return ln.strip() in MARKS


def expand_lead(ln: str) -> str:
    """Leading tabs expanded to spaces at 4-column tab stops (CommonMark), rest untouched."""
    col = 0
    i = 0
    while i < len(ln) and ln[i] in " \t":
        col = col + 1 if ln[i] == " " else col + 4 - col % 4
        i += 1
    return " " * col + ln[i:]


def gap_cols(start: int, ws: str) -> int:
    """Width in columns of whitespace `ws` beginning at column `start` (tabs to 4-column stops)."""
    end = start
    for ch in ws:
        end = end + 1 if ch == " " else end + 4 - end % 4
    return end - start


def content_col(li: re.Match) -> int:
    """Content column of a list item (CommonMark): marker end, then the whitespace
    after it expanded at 4-column tab stops; 5+ columns of it counts as 1 (the rest
    is code inside the item)."""
    col = len(li.group(1)) + len(li.group(2))
    gap = gap_cols(col, li.group(3))
    return col + (1 if gap >= 5 else gap)


BACKTICK_RUN_RE = re.compile(r"`+")


def mask_code(ln: str, open_run: int) -> tuple[str, int]:
    """Mask inline code with backticks for delimiter scanning; return (masked, open_run_after).

    A backtick run with no same-length closer on its line opens a span that continues
    on the following lines of the paragraph (CommonMark treats the newline as a space),
    so `<!--` on the next line inside that span is code, not a comment. `open_run` is
    the length of such a run carried over from the previous line (0 = none).
    """
    runs: list[tuple[int, int]] = []
    for m in BACKTICK_RUN_RE.finditer(ln):
        a, b = m.start(), m.end()
        if (a - len(ln[:a].rstrip("\\"))) % 2 == 1:   # `\`` — the first backtick is a literal, not part of the run
            a += 1
        if a < b:
            runs.append((a, b))
    out: list[str] = []
    i = k = 0
    if open_run:
        j = next((idx for idx, (a, b) in enumerate(runs) if b - a == open_run), None)
        if j is None:
            return "`" * len(ln), open_run           # the whole line is still code
        out.append("`" * runs[j][1])
        i, k, open_run = runs[j][1], j + 1, 0
    while k < len(runs):
        a, b = runs[k]
        j = next((idx for idx in range(k + 1, len(runs)) if runs[idx][1] - runs[idx][0] == b - a), None)
        if j is None:                                 # opens a span that may close on a later line
            out.append(ln[i:a])
            out.append("`" * (len(ln) - a))
            return "".join(out), b - a
        out.append(ln[i:a])
        out.append("`" * (runs[j][1] - a))
        i, k = runs[j][1], j + 1
    out.append(ln[i:])
    return "".join(out), 0


def fence_match(ln: str, base: int) -> re.Match | None:
    """FENCE_RE applied relative to the innermost open list item's content column.

    CommonMark strips a list item's content indentation before block parsing, so a
    fence nested under `  - Do:` (content column 4) is a fence at 4..7 spaces.
    """
    if len(ln) - len(ln.lstrip(" ")) < base:
        return None
    return FENCE_RE.match(ln[base:])


def sanitize(lines: list[str]) -> list[str]:
    """Return what a reader sees as prose: fenced code and HTML comments blanked.

    Single pass, CommonMark-shaped: inside a fence, nothing is interpreted (a
    `<!--` in code cannot open a comment) and the block closes only on a fence
    of the same character at least as long as the opener with nothing but
    spaces after it. Inside a comment, nothing is interpreted (a ``` in a
    comment cannot open a fence) until `-->`. Fences are recognised relative
    to the content column of the innermost open list item, so a code block
    nested under a lesson field is code too. The opener line is replaced by
    FENCE_MARK at the fence's indent so the parser still sees a block boundary
    there (a fence closes an open list item just as a heading does), and an
    HTML comment that starts a line (an HTML block) leaves COMMENT_MARK the
    same way; an inline `<!-- … -->` mid-paragraph leaves nothing, it is just
    raw inline HTML. The rest of each block is blank. Leading tabs are expanded
    to spaces at 4-column stops. Line count is preserved.
    """
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    fence_base = 0
    in_comment = False           # an INLINE `<!-- …` (mid-paragraph) still open from a previous line
    html_end: str | None = None  # inside an HTML block: the string that closes it, or None = closes at a blank line
    in_html = False
    in_paragraph = False         # the previous line was prose (a type-7 HTML block cannot start here)
    open_run = 0                 # length of an inline-code backtick run still open from the previous line
    containers: list[int] = []   # content columns of the open list items, innermost last
    unclosed.clear()
    for ln in lines:
        ln = expand_lead(ln)
        if not ln.strip():
            open_run = 0             # a code span cannot cross a blank line (the paragraph ends)
            in_paragraph = False
        if fence_char is not None:
            m = fence_match(ln, fence_base)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len and m.group(2).strip() == "":
                fence_char = None
            out.append("")
            continue
        if in_html:
            # Types 1-5 end WITH the line holding their terminator; types 6-7 end at a blank
            # line, which is itself not part of the block.
            if html_end is None:
                if not ln.strip():
                    in_html = False
            elif html_end in ln:
                in_html = False
            out.append("")
            continue
        if in_comment:
            j = ln.find("-->")
            if j < 0:
                out.append("")
                continue
            in_comment = False
            ln = ln[j + 3:]          # the rest of the line is prose again
        # Track which list items are still open: a non-blank line shallower than an
        # item's content column closes that item (and everything nested in it).
        if ln.strip():
            indent = len(ln) - len(ln.lstrip(" "))
            while containers and indent < containers[-1]:
                containers.pop()
            li = LIST_ITEM_RE.match(ln)
            if li and not THEMATIC_RE.match(ln):
                containers.append(content_col(li))
        base = containers[-1] if containers else 0
        # An HTML block (`<!--`, `<pre>`, `<div>`, … first on the line, relative to the open
        # item) is a block like a fence: it leaves a boundary mark and its lines are raw HTML,
        # never Markdown — a `## date` or `- Do:` inside it is not a heading or a field.
        hb = html_block_start(ln[base:], in_paragraph) if len(ln) - len(ln.lstrip(" ")) >= base else None
        if hb:
            mark, html_end = hb
            out.append(" " * (len(ln) - len(ln.lstrip(" "))) + mark)
            open_run = 0
            in_paragraph = False
            rel = ln[base:].lstrip(" ")
            if html_end is None:
                in_html = True                       # until a blank line
            elif html_end == ">":
                in_html = ">" not in rel[2:]         # `<!X … >` may close on its own line
            else:
                in_html = html_end not in rel[len(html_end) - 1:]   # e.g. `<!-- x -->` closes on its own line
            continue
        m = fence_match(ln, base)
        # CommonMark: a backtick fence cannot open when its info string contains a
        # backtick (that line is an inline code span, not a fence); tilde fences may.
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence_char, fence_len, fence_base = m.group(1)[0], len(m.group(1)), base
            open_run = 0
            in_paragraph = False
            out.append(" " * (len(ln) - len(ln.lstrip(" "))) + FENCE_MARK)
            continue
        # Inline code spans are opaque: a <!-- inside `…` is code, not a comment opener.
        # Mask them (same length, harmless chars) for delimiter scanning; restore text after.
        scan, open_run = mask_code(ln, open_run)
        buf: list[str] = []
        i = 0
        comment_here = False
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
                    in_comment = comment_here = True
                    i = j + 4
        prose = "".join(buf)
        # Spaces that sat before a comment which ran to the end of the line (`text  <!-- c -->`
        # or a comment that continues onto the next line) were never line-ending spaces, so
        # they must not read as a hard break once the comment is gone. Spaces AFTER `-->` stay.
        if comment_here and (in_comment or scan.endswith("-->")):
            prose = prose.rstrip()
        in_paragraph = bool(prose.strip()) and not H2_RE.match(prose) and not THEMATIC_RE.match(prose)
        out.append(prose)
    if fence_char is not None:
        unclosed.append(f"fenced code block opened with {fence_char * fence_len} never closes")
    if in_comment or (in_html and html_end == "-->"):
        unclosed.append("HTML comment never closes")
    elif in_html and html_end is not None:
        unclosed.append(f"HTML block never closes (no {html_end!r})")
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
    misplaced.clear()
    lines = sanitize(lines)

    def new_lesson(title: str, malformed: bool) -> dict:
        return {"title": norm(title), "why": "", "do": "", "source": "", "source_raw": "", "col": 2, "last": None, "hard": False,
                "seen": {"why": False, "do": False, "source": False},
                "problems": (["not-a-bold-lesson-bullet"] if malformed else [])}

    def absorb(lesson: dict, ln: str) -> None:
        """Continuation text belongs to the field above it — or to the title when no field
        has started. A hard line break on the previous line is kept as HARD_BREAK so two
        copies that render differently never compare equal."""
        text = ln.strip()
        sep = f" {HARD_BREAK} " if lesson["hard"] else " "
        if lesson["last"] is not None:
            key = lesson["last"]
            if key == "source":
                lesson["source_raw"] = norm(lesson["source_raw"] + sep + text)
            else:
                lesson[key] = norm(lesson[key] + sep + text)
        elif not any(lesson["seen"].values()):
            lesson["title"] = norm(lesson["title"] + sep + text)
        lesson["hard"] = ends_hard(ln)

    prev_blank = True
    for ln in lines:
        was_prev_blank, prev_blank = prev_blank, not ln.strip()
        indent = len(ln) - len(ln.lstrip(" "))
        # CommonMark: a line indented at or past the open lesson's content column is INSIDE
        # that list item — even `  ## 2026-08-23` — so it can never open a day section.
        if lesson is not None and current is not None and indent >= lesson["col"] and H2_RE.match(ln):
            lesson["problems"].append(f"heading {ln.strip()[:30]!r} nested inside the lesson (indent {indent})")
            lesson["last"] = None
            continue
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
            if TOP_BULLET_RE.match(ln) and not THEMATIC_RE.match(ln):   # a bullet under no day heading: readers never see it as a lesson
                misplaced.append(ln.strip()[:60])
            continue
        # CommonMark: a line indented at or past the current lesson's content column
        # (marker + the whitespace after it, tabs expanded) belongs to that lesson;
        # anything shallower is a sibling or a block that closes the list.
        nested = lesson is not None and indent >= lesson["col"]
        if not nested:
            if THEMATIC_RE.match(ln):             # `- - -` is a thematic break, never a list item
                lesson = None
                continue
            m = LESSON_RE.match(ln)
            li = LIST_ITEM_RE.match(ln)
            # `- ** **` / `- ** x**` / `- **x **` are not bold (a `**` next to whitespace cannot
            # open or close); `- **a** b **c**` is two strong spans, not one title; 5+ columns
            # after the marker make the title an indented code block, not bold.
            if (m and li and m.group(2).strip() and not m.group(2)[0].isspace() and not m.group(2)[-1].isspace()
                    and (len(m.group(2)) - len(m.group(2).rstrip("\\"))) % 2 == 0   # `\**` escapes the first closing star
                    and not INNER_STRONG_RE.search(CODE_SPAN_RE.sub(lambda c: "x" * len(c.group(0)), m.group(2)))   # `**` in code is opaque
                    and gap_cols(indent + 1, m.group(1)) <= 4):
                lesson = new_lesson(m.group(2), malformed=False)
                lesson["col"] = content_col(li)
                lesson["hard"] = ends_hard(ln)
                sections[current].append(lesson)
                continue
            if TOP_BULLET_RE.match(ln):
                parts = ln.strip().split(None, 1)
                lesson = new_lesson("MALFORMED: " + (parts[1].strip() if len(parts) > 1 else "(empty list item)"), malformed=True)
                lesson["col"] = content_col(li) if li else indent + 2
                lesson["hard"] = ends_hard(ln)
                sections[current].append(lesson)
                continue
            if lesson is not None and ln.strip():
                if not was_prev_blank and not INTERRUPT_RE.match(ln) and not HTML_BLOCK_RE.match(ln) and not is_mark(ln):
                    # Lazy continuation (CommonMark): a non-blank, non-list line directly
                    # under a paragraph — even at indent 0 — is still that paragraph's text.
                    absorb(lesson, ln)
                else:
                    # A heading, thematic break, block quote, fenced code block, HTML block
                    # (`<div>`, `<!--`, …), or a paragraph after a blank line closes the list:
                    # fields that follow render as a NEW list, not this lesson's, so they must not reconnect.
                    lesson = None
            continue
        # Nested line. A child list marker is valid only at indent col .. col+3
        # (CommonMark: ≥ content column + 4 is an indented code block, not a list).
        if is_mark(ln):
            lesson["last"] = None     # a code block or comment block inside the item ends the paragraph; the lesson goes on
            continue
        m = FIELD_LABEL_RE.match(ln)
        if m and indent >= lesson["col"] + 4:
            lesson["problems"].append(f"field '{m.group(1)}' indented {indent} spaces renders as code, not a nested bullet")
            lesson["last"] = None
            continue
        if not m:
            # continuation text (indented) belongs to the field above it — or to the title
            if ln.strip():
                absorb(lesson, ln)
            continue
        label, value = m.group(1), m.group(2)
        key = {"Why it matters here": "why", "Do": "do", "Source": "source"}[label]
        lesson["last"] = key
        lesson["hard"] = ends_hard(ln)
        if lesson["seen"][key]:
            lesson["problems"].append(f"duplicate {key}")
        lesson["seen"][key] = True
        # The value may continue on the next line(s); emptiness and the source shape are
        # judged once the whole field has been assembled (see the finalisation loop).
        if key == "source":
            lesson["source_raw"] = norm(value)
        else:
            lesson[key] = norm(value)

    for ls in sections.values():
        for l in ls:
            if "not-a-bold-lesson-bullet" in l["problems"]:
                continue
            for k in FIELDS:
                if not l["seen"][k]:
                    l["problems"].append(f"missing {k}")
                elif k != "source" and not l[k]:
                    l["problems"].append(f"missing or empty {k}")
            if l["seen"]["source"]:
                parsed = parse_source(l["source_raw"])
                if parsed is None:
                    l["problems"].append("source line is not `[title](https://…) … confidence N%`")
                elif not 0 <= parsed[1] <= 100:
                    l["problems"].append(f"confidence {parsed[1]}% out of 0-100")
                else:
                    l["source"] = l["source_raw"]
    return sections, duplicates


def shape_errors(sections: dict[str, list[dict]]) -> list[str]:
    """Problems as 'date#n: problem'."""
    return [f"{d}#{i}: {p}" for d, ls in sections.items() for i, l in enumerate(ls, 1) for p in l["problems"]]


def lesson_key(l: dict) -> tuple[str, str, str, str]:
    return (l["title"], l["why"], l["do"], l["source"])


# --- knowledge.md ----------------------------------------------------------
kpath = ROOT / "knowledge.md"
sections: dict[str, list[dict]] = {}
if kpath.is_symlink():
    fail("knowledge.md", "is a symlink — the managed file must be a real file inside the repo (connector writes would go to the target)")
elif not kpath.is_file():
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
    k_misplaced = list(misplaced)
    dates = list(sections)
    if k_bad_headings:
        fail("knowledge:headings", f"H2 headings that are not `## YYYY-MM-DD`: {k_bad_headings[:4]}")
    else:
        ok("knowledge:headings", "every H2 is a day heading")
    if k_misplaced:
        fail("knowledge:misplaced", f"{len(k_misplaced)} top-level bullet(s) outside any `## YYYY-MM-DD` section: {k_misplaced[:3]}")
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
if ldir.is_symlink():
    fail("lessons/", "is a symlink — the managed directory must be a real directory inside the repo")
elif not ldir.is_dir():
    if sections:
        fail("lessons/", f"directory missing but knowledge.md has {len(sections)} day section(s)")
    else:
        warn("lessons/", "directory missing (no day sections to cover)")
else:
    entries = sorted(ldir.iterdir())                            # every entry, not only *.md
    unreadable = [p.name for p in entries if not regular_file(p)]   # symlinks (live or dangling), directories
    if unreadable:
        fail("lessons:readable", f"not regular files (symlinks and directories are rejected): {unreadable}")
    files = [p.name for p in entries if regular_file(p)]
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
        if not regular_file(p):
            continue
        raw = read_lines(p)
        if raw is None:
            continue
        day_lines = sanitize(raw)
        problems: list[str] = list(unclosed)
        first = next((ln for ln in day_lines if ln.strip() and not is_mark(ln)), "")   # comments and code are skipped, not counted
        hm = DAY_H1_RE.match(first)
        if not hm:
            problems.append(f"first visible line must be `# Lessons — {d}`, got {first[:40]!r}")
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
if vdir.is_symlink():
    fail("verified/", "is a symlink — the managed directory must be a real directory inside the repo")
elif not vdir.is_dir():
    warn("verified/", "directory missing")
else:
    ventries = sorted(vdir.iterdir())                           # every entry, not only *.md
    vunreadable = [p.name for p in ventries if not regular_file(p)]
    if vunreadable:
        fail("verified:readable", f"not regular files (symlinks and directories are rejected): {vunreadable}")
    vfiles = [p for p in ventries if regular_file(p)]
    badnames = [p.name for p in vfiles if not VERIFIED_NAME_RE.match(p.name) or not valid_date(p.name[:10])]
    if badnames:
        fail("verified:names", f"not a real YYYY-MM-DD_topic_vN.md: {badnames}")
    else:
        ok("verified:names", f"{len(vfiles)} sheet(s), all dated and versioned")
    def first_nonblank(p: pathlib.Path) -> str | None:
        """First line a reader sees as prose: comments and fenced code are skipped, not counted."""
        lines = read_lines(p)
        if lines is None:
            return None
        for ln in sanitize(lines):
            if ln.strip() and not is_mark(ln):
                return ln
        return ""
    firsts = {p.name: first_nonblank(p) for p in vfiles}
    noh1 = [n for n, f in firsts.items() if f is not None and not H1_LINE_RE.match(f)]
    if noh1:
        fail("verified:h1", f"first visible non-blank line is not an H1 (indent ≤3, `# `; comments and code ignored): {noh1}")
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
