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
  Text inside HTML comments, fenced code blocks or indented code blocks never
  counts as content; a copy that turns prose into code (or back) is a difference.

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

# CommonMark whitespace is space and tab only: a NBSP (U+00A0) or any other Unicode space is
# CONTENT — `## 2026-08-24<NBSP>` is not the date heading, a NBSP-only line is not blank, `-<NBSP>x`
# is not a list item. Structural checks therefore never use `\s`, `\S` or bare `.strip()`.
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
SECTION_RE = re.compile(r"^ {0,3}## ([0-9]{4}-[0-9]{2}-[0-9]{2})[ \t]*$")
LESSON_RE = re.compile(r"^ {0,3}-([ \t]+)\*\*(.+?)\*\*[ \t]*$")     # bold lesson bullet: `-`, 1-4 columns of whitespace (checked after), **title**
TOP_BULLET_RE = re.compile(r"^ {0,3}(?:[-*+]|[0-9]{1,9}[.)])(?:[ \t]+[^ \t]|[ \t]*$)")   # any top-level list item incl. an EMPTY one; ordered markers are 1-9 digits (CommonMark)
FIELD_LABEL_RE = re.compile(r"^( *)-([ \t]+)(Why it matters here|Do|Source):(.*)$")   # label first; 1-4 columns after `-` (5+ = code), nesting checked by indent
# Blocks that interrupt a paragraph (CommonMark): an ATX heading, a block quote, a thematic break.
# A line like this at top level is never lazy continuation of the lesson above it.
THEMATIC_BREAK = r"(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,})$"   # 3+ of the SAME character (`- * -` is not a break)
INTERRUPT_RE = re.compile(r"^ {0,3}(?:#{1,6}(?:[ \t]|$)|>|" + THEMATIC_BREAK + ")")
ATX_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")                                   # any ATX heading
_REF_TITLE = r"""(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\((?:[^()\\]|\\.)*\))"""
REF_TITLE_RE = re.compile(r"^[ \t]*" + _REF_TITLE + r"[ \t]*$")   # a ref def's title alone on the next line
_REF_LABEL_RE = re.compile(r"^ {0,3}\[((?:\\.|[^\[\]\\])+)\]:[ \t]*")   # `[label]:` — no unescaped brackets inside the label
_REF_TITLE_TAIL_RE = re.compile(r"^(?:[ \t]+(?P<title>" + _REF_TITLE + r"))?[ \t]*$")


def indent_of(ln: str) -> int:
    return len(ln) - len(ln.lstrip(" "))


def blank(ln: str) -> bool:
    """A blank line the CommonMark way: nothing but spaces and tabs (a NBSP-only line is a paragraph)."""
    return ln.strip(" \t") == ""


def scan_destination(text: str, i: int) -> int | None:
    """Index just past a bare link destination starting at `text[i]`, or None when there is none.

    CommonMark: no spaces or ASCII control characters, no unescaped `<` or `>`, and unescaped
    parentheses must balance — `https://x.y/(oops` never closes, so it is not a destination.
    """
    depth = 0
    while i < len(text):
        c = text[i]
        if c == " " or c == "\t" or ord(c) < 32 or c == "\x7f" or c in "<>":
            break
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
    if i < len(text) and text[i] in "<>":
        return None
    return i if depth == 0 else None


def link_ref_def(ln: str) -> bool | None:
    """None unless `ln` is a COMPLETE link reference definition `[label]: destination ["title"]`;
    otherwise True when it carries a title, False when a title may still follow on the next line.
    The label needs a non-whitespace character and no unescaped brackets; the destination is
    `<…>` (no `<`, `>` inside) or a bare one with balanced parentheses; anything else after it
    makes the line prose."""
    lm = _REF_LABEL_RE.match(ln)
    if not lm or not lm.group(1).strip(" \t"):
        return None
    i = lm.end()
    if i < len(ln) and ln[i] == "<":
        j = ln.find(">", i + 1)
        if j < 0 or "<" in ln[i + 1:j]:
            return None
        end = j + 1
    else:
        end = scan_destination(ln, i)
        if end is None or end == i:
            return None
    tm = _REF_TITLE_TAIL_RE.match(ln[end:])
    if not tm:
        return None
    return tm.group("title") is not None


def first_visible(lines: list[str]) -> str:
    """The first line a reader sees as content: blank lines, block marks, link reference
    definitions (and, for a definition that has no title yet, its title on the following
    line — a quoted line after a definition that already carries one is a paragraph) are
    skipped. A continuation line (the prose after a multi-line inline comment's `-->`)
    counts as visible only when it carries text."""
    k = 0
    while k < len(lines):
        ln = lines[k]
        if ln.startswith(CONT_MARK):
            tail = ln[len(CONT_MARK):]
            if not blank(tail):
                return tail
            k += 1
            continue
        if blank(ln) or is_mark(ln):
            k += 1
            continue
        rd = link_ref_def(ln)
        if rd is not None:
            k += 1
            if rd is False and k < len(lines) and REF_TITLE_RE.match(lines[k]):
                k += 1
            continue
        return ln
    return ""
LINK_LABEL = r"\[(?:\\.|[^\]\\])+\]"                                          # allows escaped \] inside the label
LINK_OPEN_RE = re.compile(r"^" + LINK_LABEL + r"\(")                       # `[label](` — the destination is scanned by hand
CONFIDENCE_RE = re.compile(r"(?<![A-Za-z0-9_])confidence ([0-9]{1,3})%(?![0-9%])")   # a standalone label: `overconfidence 80%` is not one
ASCII_PUNCT = set(r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""")   # a backslash escapes exactly these (CommonMark)


def parse_source(text: str) -> tuple[str, int] | None:
    """(destination, confidence) for `[label](https://…) … confidence N%`, else None.

    The destination is read the CommonMark way: no whitespace, and parentheses must
    balance — `https://x.y/(broken)` never closes, so it is not a link at all.
    """
    text = text.strip(" \t")
    if not text.startswith("["):
        return None
    j, bdepth = 1, 0                                 # the label: balanced, unescaped brackets are allowed inside
    while j < len(text):
        c = text[j]
        if c == "\\" and j + 1 < len(text) and text[j + 1] in ASCII_PUNCT:
            j += 2
            continue
        if c == "[":
            bdepth += 1
        elif c == "]":
            if bdepth == 0:
                break
            bdepth -= 1
        j += 1
    if j >= len(text) or j == 1 or j + 1 >= len(text) or text[j + 1] != "(":
        return None
    i = scan_destination(text, j + 2)
    if i is None or i >= len(text) or text[i] != ")":
        return None                              # no whitespace, no unescaped < >, parentheses balance, `)` closes
    dest = text[j + 2:i]
    if not re.match(r"https?://[^ \t]+$", dest):
        return None
    cm = CONFIDENCE_RE.search(text[i + 1:])
    return (dest, int(cm.group(1))) if cm else None
DAY_H1_RE = re.compile(r"^# Lessons — ([0-9]{4}-[0-9]{2}-[0-9]{2})[ \t]*$")
VERIFIED_NAME_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}_[a-z0-9-]+_v[0-9]+\.md$")
H1_LINE_RE = re.compile(r"^ {0,3}#[ \t]+[^ \t]")   # a real ATX H1 with text: ≤3 leading spaces (4 = code), space or tab after `#`
FIELDS = ("why", "do", "source")
H2_RE = re.compile(r"^ {0,3}##(?:[ \t]|$)")   # any ATX H2 (≤3-space indent), including a bare `##`; NBSP is not a separator
bad_headings: list[str] = []   # filled by parse_lessons: H2s that are not valid day headings
SETEXT_H2_RE = re.compile(r"^ {0,3}-+[ \t]*$")   # a dash underline directly under a top-level paragraph line makes it an H2
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
    """Collapse runs of spaces/tabs in prose (a NBSP is content and stays), but keep inline code
    verbatim (`printf 'a  b'` means two spaces)."""
    spans: list[str] = []
    parts: list[str] = []
    i = 0
    for a, b in code_spans(s):
        parts.append(s[i:a])
        spans.append(s[a:b])
        parts.append(f"\x02{len(spans) - 1}\x02")
        i = b
    parts.append(s[i:])
    out = " ".join(t for t in re.split(r"[ \t]+", "".join(parts).strip(" \t")) if t)
    return re.sub(r"\x02(\d+)\x02", lambda m: spans[int(m.group(1))], out)


HARD_BREAK = "⏎"   # joins two lines of a field when the first ends in a hard line break (2+ spaces or an odd backslash)
PARA_BREAK = "¶"   # joins two paragraphs of the same field (a blank line between the field and its continuation)


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
CONT_MARK = "\x00cont"         # prefix: this line is paragraph continuation text (it began inside an inline comment)
LIST_ITEM_RE = re.compile(r"^( *)([-*+]|[0-9]{1,9}[.)])([ \t]+)[^ \t]")   # marker + whitespace + content (for content-column tracking)
THEMATIC_RE = re.compile(r"^ {0,3}" + THEMATIC_BREAK)                 # `---`, `- - -`, `***`: a thematic break outranks a list item
_HTML6 = ("address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|"
          "fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|"
          "menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul")
HTML_MARK = "\x00html"         # left by sanitize() where an HTML block other than a comment (types 1, 3-7) opened
MARKS = (FENCE_MARK, COMMENT_MARK, HTML_MARK)
PAYLOAD_SEP = "\x01"          # a fence/HTML mark may carry the block's text after this: `<indent>MARK\x01line⏎line`
BLOCK_SEP = "⏎"
_HTML_TYPE1 = re.compile(r"^ {0,3}<(script|pre|style|textarea)(?:[ \t]|>|$)", re.IGNORECASE)   # tag whitespace is space/tab only
_HTML_TYPE7 = re.compile(   # a complete open or close tag alone on the line (cannot interrupt a paragraph)
    r"^ {0,3}(?:<[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*(?:[ \t]*=[ \t]*(?:[^ \t\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*[ \t]*/?>"
    r"|</[A-Za-z][A-Za-z0-9-]*[ \t]*>)[ \t]*$")


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
    if re.match(r"^ {0,3}<![A-Z]", rel):         # uppercase only (CommonMark type 4); `<!foo>` is text
        return HTML_MARK, ">"
    if re.match(r"^ {0,3}</?(?:" + _HTML6 + r")(?:[ \t]|/?>|$)", rel, re.IGNORECASE):
        return HTML_MARK, None
    if not in_paragraph and _HTML_TYPE7.match(rel):
        return HTML_MARK, None
    return None


def has_inner_strong(s: str) -> bool:
    """True when `s` (a would-be title, code spans masked) holds a live `**`: one whose run of
    preceding backslashes is EVEN (`\\**` is an escaped backslash and then a real delimiter,
    `\**` is an escaped star). Every position is tested, so `\***` — an escaped star followed
    by a live `**` — is caught too. A live `**` inside the title means it is not ONE strong span."""
    for a in range(len(s) - 1):
        if s[a] == "*" and s[a + 1] == "*" and (a - len(s[:a].rstrip("\\"))) % 2 == 0:
            return True
    return False


def interrupts_paragraph(ln: str, eff: int) -> bool:
    """CommonMark: can `ln` (leading tabs expanded), read inside the list item whose content
    column is `eff`, interrupt a paragraph? An ATX heading, a thematic break, a block quote,
    a fence, an HTML block of types 1-6 and a non-empty list item (an ordered one only when it
    starts at 1) can; anything indented 4+ columns past `eff` cannot — indented code never
    interrupts a paragraph, it is lazy continuation text there."""
    rel = ln[eff:]
    if len(rel) - len(rel.lstrip(" ")) > 3:
        return False
    li = LIST_ITEM_RE.match(rel)
    fm = FENCE_RE.match(rel)
    return bool(THEMATIC_RE.match(rel) or ATX_RE.match(rel) or rel.lstrip(" ").startswith(">")
                or (li and can_interrupt(li))
                or (fm and not (fm.group(1)[0] == "`" and "`" in fm.group(2)))
                or html_block_start(rel, True))
unclosed: list[str] = []   # filled by sanitize: a fence or comment still open at end of file


QUOTE_RE = re.compile(r"^ {0,3}> ?")


def quote_depth(ln: str) -> tuple[int, str]:
    """(number of leading block-quote markers, the text inside them) — CommonMark parses the
    quoted text as blocks, so `> ## x` holds a real H2 and `> Foo` / `> ---` a Setext one."""
    depth = 0
    while True:
        m = QUOTE_RE.match(ln)
        if not m:
            return depth, ln
        depth += 1
        ln = ln[m.end():]


def unquote(ln: str) -> str:
    return quote_depth(ln)[1]


def is_h2(ln: str) -> bool:
    """An ATX H2 on this line, inside block quotes or not."""
    return bool(H2_RE.match(unquote(ln)))


def mark_kind(ln: str) -> str | None:
    """Which block mark this sanitized line is (its payload ignored), or None for ordinary text."""
    head = ln.lstrip(" ").split(PAYLOAD_SEP, 1)[0]
    return head if head in MARKS else None


def mark_token(ln: str) -> str:
    """A comparison token for a fence/HTML mark: what readers see of the block, spaces made visible
    so prose normalisation cannot collapse them (`⟨code⟩print(1)`, `⟨html⟩<div>x</div>`)."""
    kind = mark_kind(ln)
    payload = ln.split(PAYLOAD_SEP, 1)[1] if PAYLOAD_SEP in ln else ""
    return ("⟨code⟩" if kind == FENCE_MARK else "⟨html⟩") + payload.replace(" ", "␣").replace("\t", "⇥")


def is_mark(ln: str) -> bool:
    return mark_kind(ln) is not None


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


def can_interrupt(li: re.Match) -> bool:
    """CommonMark: a list item may interrupt a paragraph only if it is non-empty and, when
    ordered, starts at 1 (`2. more` under a paragraph is lazy continuation text)."""
    marker = li.group(2)
    return not marker[0].isdigit() or int(marker[:-1]) == 1


def content_col(li: re.Match) -> int:
    """Content column of a list item (CommonMark): marker end, then the whitespace
    after it expanded at 4-column tab stops; 5+ columns of it counts as 1 (the rest
    is code inside the item)."""
    col = len(li.group(1)) + len(li.group(2))
    gap = gap_cols(col, li.group(3))
    return col + (1 if gap >= 5 else gap)


BACKTICK_RUN_RE = re.compile(r"`+")


def backtick_runs(ln: str) -> list[tuple[int, int]]:
    """(start, end) of every backtick run that can delimit code. A backtick preceded by an ODD
    number of backslashes is an escaped literal and drops out of its run; an even number
    (`\\\\``) is an escaped backslash followed by a live backtick."""
    runs: list[tuple[int, int]] = []
    for m in BACKTICK_RUN_RE.finditer(ln):
        a, b = m.start(), m.end()
        if (a - len(ln[:a].rstrip("\\"))) % 2 == 1:
            a += 1
        if a < b:
            runs.append((a, b))
    return runs


def code_spans(s: str) -> list[tuple[int, int]]:
    """Extents (delimiters included) of the code spans that open AND close within `s`, paired the
    CommonMark way: a run pairs with the next run of the same length; a run with no partner is
    literal text and scanning continues after it."""
    runs = backtick_runs(s)
    out: list[tuple[int, int]] = []
    k = 0
    while k < len(runs):
        a, b = runs[k]
        j = next((idx for idx in range(k + 1, len(runs)) if runs[idx][1] - runs[idx][0] == b - a), None)
        if j is None:
            k += 1
            continue
        out.append((a, runs[j][1]))
        k = j + 1
    return out


def mask_spans(s: str) -> str:
    """`s` with each closed code span replaced by `x`s of the same length (delimiters included)."""
    out = list(s)
    for a, b in code_spans(s):
        out[a:b] = "x" * (b - a)
    return "".join(out)


def mask_code(ln: str, open_run: int) -> tuple[str, int]:
    """Mask inline code with backticks for delimiter scanning; return (masked, open_run_after).

    A backtick run with no same-length closer on its line opens a span that continues
    on the following lines of the paragraph (CommonMark treats the newline as a space),
    so `<!--` on the next line inside that span is code, not a comment. `open_run` is
    the length of such a run carried over from the previous line (0 = none).
    """
    runs = backtick_runs(ln)
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


def closes_in_paragraph(rest: list[str], containers: list[int] = ()) -> bool:
    """True when `-->` arrives on a later line of the SAME paragraph. CommonMark settles block
    structure before inline HTML, so the paragraph ends at a blank line or at any line that
    starts a block able to interrupt it — a heading, thematic break, block quote, fence, HTML
    block, or a list item (a sibling `- Do:` included), judged against the deepest open list
    item the line's indent satisfies. An opener whose closer lies beyond that is literal text."""
    for nxt in rest:
        nxt = expand_lead(nxt)
        if blank(nxt):
            return False
        indent = len(nxt) - len(nxt.lstrip(" "))
        eff = next((c for c in reversed(containers) if c <= indent), 0)
        if interrupts_paragraph(nxt, eff):
            return False
        if "-->" in nxt:
            return True
    return False


def strip_inline_comments(ln: str, scan: str, rest: list[str] = (), containers: list[int] = ()) -> str:
    """Remove `<!-- … -->` spans from one prose line (`scan` is `ln` with code masked), carrying
    an unterminated comment into the module-level `_in_comment` flag when — and only when — its
    closer arrives later in the same paragraph (`rest` = the lines that follow, `containers` =
    the content columns of the list items open at this line)."""
    global _in_comment
    buf: list[str] = []
    i = 0
    comment_here = False
    while i < len(scan):
        if _in_comment:
            j = scan.find("-->", i)
            if j < 0:
                i = len(scan)
            else:
                _in_comment = False
                i = j + 3
        else:
            j = scan.find("<!--", i)
            if j < 0:
                buf.append(ln[i:])
                i = len(scan)
            elif "-->" not in scan[j + 4:] and not closes_in_paragraph(rest, containers):
                buf.append(ln[i:])                   # opener with no closer in this paragraph: literal text
                i = len(scan)
            else:
                buf.append(ln[i:j])
                _in_comment = comment_here = True
                i = j + 4
    prose = "".join(buf)
    # Spaces that sat before a comment which ran to the end of the line (`text  <!-- c -->`
    # or a comment that continues onto the next line) were never line-ending spaces, so
    # they must not read as a hard break once the comment is gone. Spaces AFTER `-->` stay.
    if comment_here and (_in_comment or scan.endswith("-->")):
        prose = prose.rstrip()
    return prose


_in_comment = False   # an inline `<!-- …` still open at the end of the previous prose line (sanitize state)


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
    global _in_comment
    _in_comment = False          # an INLINE `<!-- …` (mid-paragraph) still open from a previous line
    html_end: str | None = None  # inside an HTML block: the string that closes it, or None = closes at a blank line
    in_html = False
    in_paragraph = False         # the previous line was prose (a type-7 HTML block cannot start here)
    open_run = 0                 # length of an inline-code backtick run still open from the previous line
    containers: list[int] = []   # content columns of the open list items, innermost last
    block_at = -1                # index in `out` of the open fence/HTML block's mark line
    block_base = 0               # content column of the list item that block lives in
    block_text: list[str] = []   # the block's lines, container indentation removed (its payload)
    unclosed.clear()

    def close_block() -> None:
        nonlocal block_at
        if block_at >= 0:
            out[block_at] += PAYLOAD_SEP + BLOCK_SEP.join(block_text)
        block_at = -1
        block_text.clear()

    for k, ln in enumerate(lines):
        ln = expand_lead(ln)
        indent = len(ln) - len(ln.lstrip(" "))
        if blank(ln):
            open_run = 0             # a code span cannot cross a blank line (the paragraph ends)
            _in_comment = False      # nor can an inline comment: an unclosed `<!--` was literal text
            in_paragraph = False
        # A fence or HTML block inside a list item ends with that item (CommonMark: the block runs
        # "until the end of the containing block"): a non-blank line shallower than the item's
        # content column closes both, and is then read as an ordinary line.
        if (fence_char is not None or in_html) and not blank(ln) and indent < block_base:
            fence_char = None
            in_html = False
            close_block()
        if fence_char is not None:
            m = fence_match(ln, fence_base)
            if m and m.group(1)[0] == fence_char and len(m.group(1)) >= fence_len and m.group(2).strip(" \t") == "":   # NBSP etc. is content
                fence_char = None
                close_block()                    # the closing fence is not content
            else:
                block_text.append(ln[min(indent, block_base):])
            out.append("")
            continue
        if in_html:
            # Types 1-5 end WITH the line holding their terminator; types 6-7 end at a blank
            # line, which is itself not part of the block.
            if html_end is None:
                if blank(ln):
                    in_html = False
                    close_block()
                else:
                    block_text.append(ln[min(indent, block_base):])
            else:
                block_text.append(ln[min(indent, block_base):])
                if html_end in ln.lower():       # `</PRE>` closes a `<pre>` block too
                    in_html = False
                    close_block()
            out.append("")
            continue
        cont = False
        if _in_comment:
            j = ln.find("-->")
            if j < 0:
                out.append(CONT_MARK)    # wholly inside the inline comment: no text, but the paragraph is still open
                continue
            _in_comment = False
            ln = ln[j + 3:]          # the rest of the line is prose again — but it did not BEGIN the
            cont = True              # line, so it can never start a block: it stays in the paragraph
        # Track which list items are still open: a non-blank line shallower than an
        # item's content column closes that item (and everything nested in it).
        lazy = False
        if not blank(ln) and not cont:
            # Judge "does this line start a block?" relative to the deepest container the
            # line's indent still satisfies (a `<!--` at column 0 under a column-4 field is a
            # top-level HTML block, not paragraph text). A lazy continuation (paragraph text
            # that is none of the block starts) stays inside the open list item however
            # shallow it is, so it must not pop the containers.
            eff = next((c for c in reversed(containers) if c <= indent), 0)
            lazy = in_paragraph and not interrupts_paragraph(ln, eff)
            if not lazy:
                open_run = 0         # a new block began: a backtick run left open in the previous paragraph was literal
                while containers and indent < containers[-1]:
                    containers.pop()
                base = containers[-1] if containers else 0
                li = LIST_ITEM_RE.match(ln[base:])   # a marker 4+ columns past the container is code, not a list item
                if li and len(li.group(1)) <= 3 and not THEMATIC_RE.match(ln[base:]):
                    containers.append(base + content_col(li))
        base = containers[-1] if containers else 0
        if cont:
            scan, open_run = mask_code(ln, open_run)
            out.append(CONT_MARK + strip_inline_comments(ln, scan, lines[k + 1:], containers))
            in_paragraph = True
            continue
        # An HTML block (`<!--`, `<pre>`, `<div>`, … first on the line, relative to the open
        # item) is a block like a fence: it leaves a boundary mark and its lines are raw HTML,
        # never Markdown — a `## date` or `- Do:` inside it is not a heading or a field.
        hb = html_block_start(ln[base:], in_paragraph) if indent >= base else None
        if hb:
            mark, html_end = hb
            out.append(" " * indent + mark)
            open_run = 0
            in_paragraph = False
            rel = ln[base:].lstrip(" ")
            if html_end is None:
                in_html = True                       # until a blank line
            elif html_end == ">":
                in_html = ">" not in rel[2:]         # `<!X … >` may close on its own line
            else:
                in_html = html_end not in rel.lower()[len(html_end) - 1:]   # e.g. `<!-- x -->` closes on its own line
            if mark == HTML_MARK:                    # a comment renders nothing: no payload to compare
                block_at, block_base = len(out) - 1, base
                block_text.append(ln[base:])
                if not in_html:
                    close_block()
            continue
        m = fence_match(ln, base)
        # CommonMark: a backtick fence cannot open when its info string contains a
        # backtick (that line is an inline code span, not a fence); tilde fences may.
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence_char, fence_len, fence_base = m.group(1)[0], len(m.group(1)), base
            open_run = 0
            in_paragraph = False
            out.append(" " * indent + FENCE_MARK)
            block_at, block_base = len(out) - 1, base
            block_text.append(m.group(2).strip(" \t"))   # what readers see of the opener: its info string
            continue
        # Inline code spans are opaque: a <!-- inside `…` is code, not a comment opener.
        # Mask them (same length, harmless chars) for delimiter scanning; restore text after.
        scan, open_run = mask_code(ln, open_run)
        prose = strip_inline_comments(ln, scan, lines[k + 1:], containers)
        # Prose that continues the paragraph keeps it open; otherwise the line opens one only if,
        # read inside its container, it is neither a heading, a thematic break nor indented code.
        rel = prose[base:]
        in_paragraph = lazy or (not blank(prose) and len(rel) - len(rel.lstrip(" ")) <= 3
                                and not ATX_RE.match(rel) and not THEMATIC_RE.match(rel))
        out.append(prose)
    if fence_char is not None:   # implicitly closed at end of file, but a hand editor forgot the closer
        unclosed.append(f"fenced code block opened with {fence_char * fence_len} never closes")
    if _in_comment or (in_html and html_end == "-->"):
        unclosed.append("HTML comment never closes")
    elif in_html and html_end is not None:
        unclosed.append(f"HTML block never closes (no {html_end!r})")
    close_block()                # a block still open at end of file keeps its text
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
        # col   content column of the lesson item; fcol  that of the open field item (None = none open)
        # last  the open field's key; para  a paragraph is open (lazy continuation may follow);
        # pcol  the content column of the container that paragraph lives in (a Setext underline
        #       must sit there); tail  lesson-level prose after the fields — visible, so compared
        return {"title": norm(title), "why": "", "do": "", "source": "", "source_raw": "", "tail": "",
                "col": 2, "fcol": None, "last": None, "hard": False, "para": False, "pcol": 0, "pq": 0,
                "seen": {"why": False, "do": False, "source": False},
                "problems": (["not-a-bold-lesson-bullet"] if malformed else [])}

    def absorb(lesson: dict, ln: str, para: bool = False) -> None:
        """Prose belongs to the open field — or to the title when no field has started, or to
        the lesson's tail when the fields are done. A hard line break on the previous line is
        kept as HARD_BREAK, and a new paragraph inside the item as PARA_BREAK, so two copies
        that render differently never compare equal."""
        text = ln.strip(" \t")
        if not text:
            return
        sep = f" {PARA_BREAK} " if para else (f" {HARD_BREAK} " if lesson["hard"] else " ")
        if lesson["last"] is not None:
            key = lesson["last"]
            if key == "source":
                lesson["source_raw"] = norm(lesson["source_raw"] + sep + text)
            else:
                lesson[key] = norm(lesson[key] + sep + text)
        elif not any(lesson["seen"].values()):
            lesson["title"] = norm(lesson["title"] + sep + text)
        else:
            lesson["tail"] = norm(lesson["tail"] + sep + text)
        lesson["hard"] = ends_hard(ln)

    def open_para(lesson: dict, col: int, qdepth: int = 0) -> None:
        lesson["para"], lesson["pcol"], lesson["pq"] = True, col, qdepth

    def close_para(lesson: dict) -> None:
        lesson["para"], lesson["hard"] = False, False

    top_para: str | None = None   # the previous line, when it was a top-level paragraph line (a Setext underline may follow)
    quote_para: tuple[int, str] | None = None   # same, for a paragraph line inside a top-level block quote (depth, text)
    ref_title_next = False        # the previous line was a reference definition without a title: its title may follow
    for idx, ln in enumerate(lines):
        prev_blank = blank(ln)
        prev_top_para, top_para = top_para, None
        prev_quote_para, quote_para = quote_para, None
        title_may_follow, ref_title_next = ref_title_next, False
        if prev_blank:
            if lesson is not None:
                close_para(lesson)                # a blank line ends any paragraph (the list item stays open)
            continue
        # A dash underline right under a top-level paragraph line turns that line into an H2
        # (Setext). It is never a day heading, so it is a bad heading that ends the section.
        # The same holds inside a block quote when both lines sit at the same quote depth.
        qd, qtext = quote_depth(ln)
        if (prev_top_para is not None and SETEXT_H2_RE.match(ln)) or (
                prev_quote_para is not None and qd == prev_quote_para[0] and SETEXT_H2_RE.match(qtext)):
            para_text = prev_top_para if prev_top_para is not None else prev_quote_para[1]
            bad_headings.append(para_text.strip()[:60] + " / " + ln.strip()[:20])
            current = None
            lesson = None
            continue
        if qd and not blank(qtext) and not INTERRUPT_RE.match(qtext) and not TOP_BULLET_RE.match(qtext) and not FENCE_RE.match(qtext) \
                and (lesson is None or indent_of(ln) < lesson["col"]):
            quote_para = (qd, qtext)              # a paragraph line inside a top-level block quote
        if ln.startswith(CONT_MARK):              # paragraph text that began inside an inline comment
            if lesson is not None and current is not None and lesson["para"]:
                absorb(lesson, ln[len(CONT_MARK):])
            continue
        indent = len(ln) - len(ln.lstrip(" "))
        # CommonMark: a line indented at or past the open lesson's content column is INSIDE that
        # list item. Blocks there are read relative to the innermost item the line sits in: the
        # open field's content column when the line reaches it, else the lesson's.
        nested = lesson is not None and current is not None and indent >= lesson["col"]
        if nested:
            in_field = lesson["fcol"] is not None and indent >= lesson["fcol"]
            eff = lesson["fcol"] if in_field else lesson["col"]
            rel = ln[eff:]
            # An ATX heading inside the item — even `  ## 2026-08-23`, or `  > ## x` inside a block
            # quote — can never open a day section (and a heading interrupts any paragraph). An H2
            # there is a problem; other levels are recorded as text so copies that differ in them differ.
            if ATX_RE.match(unquote(rel)):
                if not in_field and lesson["fcol"] is not None:
                    lesson["last"] = lesson["fcol"] = None
                if is_h2(rel):
                    lesson["problems"].append(f"heading {ln.strip()[:30]!r} nested inside the lesson (indent {indent})")
                else:
                    absorb(lesson, ln, para=True)
                close_para(lesson)
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
        if is_h2(ln):                             # an H2 that is not `## YYYY-MM-DD` (block-quoted ones included)
            bad_headings.append(ln.strip(" \t"))    # keep a trailing NBSP visible in the report
            current = None                        # nothing after it belongs to a day
            lesson = None
            continue
        if current is None:
            # Nothing visible belongs outside a day section except the file's H1 on its first line
            # and link reference definitions (with a title on the next line when the definition has
            # none): a bullet, a paragraph, a thematic break, a code block — readers see it, no day file has it.
            if title_may_follow and REF_TITLE_RE.match(ln):
                continue
            rd = link_ref_def(ln)
            if rd is not None:
                ref_title_next = rd is False
                continue
            if not is_mark(ln) and not (idx == 0 and H1_LINE_RE.match(ln)):
                misplaced.append(ln.strip()[:60])
            if mark_kind(ln) in (FENCE_MARK, HTML_MARK):   # a comment renders nothing and is allowed metadata
                misplaced.append("<code block or raw HTML>")
            if not TOP_BULLET_RE.match(ln) and not INTERRUPT_RE.match(ln) and not is_mark(ln) and (indent <= 3 or prev_top_para is not None):
                top_para = ln
            continue
        if not nested:
            # A line shallower than the lesson's content column is a sibling or a block that closes the list.
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
                    and m.group(2)[0] != "*"                                      # `***foo**` → `*` + strong
                    and not (m.group(2).endswith("*") and (len(m.group(2)) - 1 - len(m.group(2)[:-1].rstrip("\\"))) % 2 == 0)   # `**foo***` → strong + `*`
                    and not has_inner_strong(mask_spans(m.group(2)))                  # `**` inside a code span is opaque
                    and gap_cols(indent + 1, m.group(1)) <= 4):
                lesson = new_lesson(m.group(2), malformed=False)
                lesson["col"] = content_col(li)
                lesson["hard"] = ends_hard(ln)
                open_para(lesson, lesson["col"])
                sections[current].append(lesson)
                continue
            if TOP_BULLET_RE.match(ln) and not (lesson is not None and lesson["para"]
                                                and (li is None or not can_interrupt(li))):
                # (a `2.` item or an empty item directly under a paragraph cannot start a list: it
                # is lazy continuation text and is handled below)
                parts = ln.strip().split(None, 1)
                lesson = new_lesson("MALFORMED: " + (parts[1].strip() if len(parts) > 1 else "(empty list item)"), malformed=True)
                lesson["col"] = content_col(li) if li else indent + 2
                lesson["hard"] = ends_hard(ln)
                open_para(lesson, lesson["col"])
                sections[current].append(lesson)
                continue
            if not is_mark(ln) and not INTERRUPT_RE.match(ln) and (lesson is None or not lesson["para"]) and (
                    indent <= 3 or prev_top_para is not None):
                top_para = ln                          # a top-level paragraph line: a `---` next would make it an H2
            if lesson is not None:
                if lesson["para"] and not INTERRUPT_RE.match(ln) and not is_mark(ln):
                    # Lazy continuation (CommonMark): a non-blank, non-list line directly
                    # under a paragraph — even at indent 0 — is still that paragraph's text.
                    absorb(lesson, ln)
                else:
                    # A heading, thematic break, block quote, fenced code block, HTML block
                    # (`<div>`, `<!--`, …), or a paragraph after a blank line closes the list:
                    # fields that follow render as a NEW list, not this lesson's, so they must not reconnect.
                    lesson = None
            continue
        # ---- nested line: inside the open lesson item ----
        if is_mark(ln):
            # A fenced code block, comment block or HTML block inside the item ends the paragraph;
            # sitting beside the field items (shallower than the open field's content) it closes that
            # item. Code and raw HTML are visible, so their text joins the comparison as a token.
            if not in_field and lesson["fcol"] is not None:
                lesson["last"] = lesson["fcol"] = None
            if mark_kind(ln) != COMMENT_MARK:
                absorb(lesson, mark_token(ln), para=True)
            close_para(lesson)
            continue
        # A dash underline directly under a paragraph inside the item, at that paragraph's
        # container column, makes it a Setext H2 (CommonMark) — a heading hidden in a lesson.
        if lesson["para"] and indent >= lesson["pcol"]:
            uq, utext = quote_depth(ln[lesson["pcol"]:])
            if uq == lesson["pq"] and SETEXT_H2_RE.match(utext):
                lesson["problems"].append(f"Setext H2 (underline {ln.strip()[:12]!r}) nested inside the lesson")
                close_para(lesson)
                continue
        if lesson["para"] and not interrupts_paragraph(ln, eff):
            absorb(lesson, ln)                    # lazy continuation of the open paragraph, wherever the line sits
            continue
        if not in_field and lesson["fcol"] is not None:
            lesson["last"] = lesson["fcol"] = None   # shallower than the open field's content: that item is closed
        rel_indent = len(rel) - len(rel.lstrip(" "))
        if rel_indent >= 4:
            close_para(lesson)                    # an indented code block inside the item: code, never prose
            continue
        fm = FIELD_LABEL_RE.match(ln)
        if fm and not in_field:
            gap = gap_cols(indent + 1, fm.group(2))
            if gap > 4:
                lesson["problems"].append(f"field '{fm.group(3)}' has {gap} columns after `-`: its text renders as code, not a field")
                lesson["last"], lesson["fcol"] = None, indent + 2
                close_para(lesson)
                continue
            label, value = fm.group(3), fm.group(4)
            key = {"Why it matters here": "why", "Do": "do", "Source": "source"}[label]
            lesson["last"], lesson["fcol"] = key, indent + 1 + gap
            open_para(lesson, lesson["fcol"])
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
            continue
        if THEMATIC_RE.match(rel):                # a thematic break inside the item: a block, not text
            close_para(lesson)
            continue
        # Anything else opens a new paragraph inside the item: a list item that is not a lesson
        # field (a sub-bullet, an ordered item, a `- Do:` nested inside another field), a block
        # quote, or plain text after a blank line, a block or code. Its text is recorded.
        li = LIST_ITEM_RE.match(rel)
        absorb(lesson, ln, para=True)
        open_para(lesson, eff + content_col(li) if li else eff, quote_depth(rel)[0])

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


KEY_FIELDS = ("title",) + FIELDS + ("tail",)   # what two copies of a lesson are compared on


def lesson_key(l: dict) -> tuple[str, str, str, str, str]:
    return (l["title"], l["why"], l["do"], l["source"], l["tail"])


# --- knowledge.md ----------------------------------------------------------
kpath = ROOT / "knowledge.md"
sections: dict[str, list[dict]] = {}
if kpath.is_symlink():
    fail("knowledge.md", "is a symlink — the managed file must be a real file inside the repo (connector writes would go to the target)")
elif not kpath.is_file():
    fail("knowledge.md", "missing")
else:
    lines = read_lines(kpath) or []
    if lines and lines[0] == KNOWLEDGE_H1:            # exact: trailing whitespace would break the connector's anchor too
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
        fail("knowledge:misplaced", f"{len(k_misplaced)} visible block(s) outside any `## YYYY-MM-DD` section: {k_misplaced[:3]}")
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
        first = first_visible(day_lines)   # comments, code and reference definitions are skipped, not counted
        hm = DAY_H1_RE.match(first)
        if not hm:
            problems.append(f"first visible line must be `# Lessons — {d}`, got {first[:40]!r}")
        elif hm.group(1) != d:
            problems.append(f"H1 date {hm.group(1)} does not match filename {d}")
        stray_headings = [ln.strip() for ln in day_lines if is_h2(ln)]
        if stray_headings:
            problems.append(f"contains H2 heading(s) {stray_headings[:4]} — a per-day file has no `## ` headings")
        # A per-day file carries no `## ` heading of its own: parse it as that day's section.
        day_sections, _ = parse_lessons([f"## {d}"] + [ln for ln in day_lines if not is_h2(ln)])
        if bad_headings:
            problems.append(f"contains Setext H2 heading(s) {bad_headings[:4]} — a per-day file has no `## ` headings")
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
                    diff_fields.append(a[0][:30] + ": " + ",".join(f for f, x, y in zip(KEY_FIELDS, a, b) if x != y))
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
        return first_visible(sanitize(lines))
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
