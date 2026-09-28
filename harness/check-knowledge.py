#!/usr/bin/env python3
"""check-knowledge.py — PASS/FAIL structural check of this repo's knowledge files.

Proves that what the daily-dev-agentic connector (and hand edits) wrote still
has the shape every reader relies on:

  knowledge.md   the exact connector H1, then only `## YYYY-MM-DD` sections
                 (real calendar dates, no repeats, no other H2s) newest first; every top-level
                 bullet in a section is a bold lesson with a non-empty
                 "Why it matters here:", a non-empty "Do:", and a "Source:"
                 line carrying a link and a 0-100 confidence, written in plain
                 Markdown (raw HTML other than <!-- comments --> FAILs); a bullet
                 outside every day section is a FAIL (readers never see it), and so
                 is any other visible top-level block inside a day section (a
                 paragraph, heading, rule, code or raw HTML — no day file carries it)
  lessons/       one regular (non-symlink) YYYY-MM-DD.md per day section in
                 knowledge.md, headed `# Lessons — <that date>`, no orphans,
                 no H2 headings of its own, and every lesson RENDERING identically
                 to that day's section in knowledge.md, in the same order
  verified/      only regular files named YYYY-MM-DD_topic_vN.md (real dates)
                 whose first visible block is an ATX H1 with text (a code block or
                 raw HTML before it is visible, a comment or reference definition is not)

How: Markdown is parsed by markdown-it-py (CommonMark 0.31.2 preset; CI pins it and
checks it against the reference implementation on all 652 spec examples), so block
structure is the parser's, not ours. Two copies of a lesson are the same when they
render to the same HTML once markup a browser never displays (comments, processing
instructions, declarations, CDATA) is removed — found by a browser-faithful HTML
tokenizer that CI checks against html5lib — and text whitespace is collapsed the way a
browser does outside <pre> and <code> (not at all when the lesson holds raw HTML that
shows whitespace as written). Raw HTML can hide, restyle or swallow what a reader
sees, so a lesson holding any raw HTML other than a comment FAILs outright; the
visibility rules that remain (text inside raw HTML never counts as a value) only shape
the extra diagnostics such a lesson gets.

Contract: one line per check (PASS|WARN|FAIL name evidence), final RESULT
line, exit 0 only when nothing FAILed. `--json` prints one JSON object.

Run:  pip install -r harness/requirements.txt && python3 harness/check-knowledge.py [--json]
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from knowledge_md import MD, VOID_TAGS, html_open_at_end, html_segments   # CommonMark + browser-faithful HTML
except Exception as exc:                              # missing, or a release whose internals the patches no longer fit
    _why = ("markdown-it-py is not installed" if isinstance(exc, ImportError) and "markdown_it" in str(exc)
            else f"markdown-it-py failed to load ({type(exc).__name__}: {exc})")
    _detail = f"{_why} — run: pip install -r harness/requirements.txt"
    if "--json" in sys.argv:                          # the contract holds in both modes: one JSON object, or lines
        print(json.dumps({"ok": False, "pass": 0, "warn": 0, "fail": 1,
                          "checks": [{"status": "FAIL", "name": "harness:deps", "detail": _detail}]}))
    else:
        print(f"FAIL harness:deps             {_detail}")
        print("----")
        print("RESULT: FAIL — 0 pass, 0 warn, 1 fail")
    sys.exit(1)

ROOT = pathlib.Path(__file__).resolve().parents[1]
RESULTS: list[dict] = []

KNOWLEDGE_H1 = "# daily-dev-agentic knowledge — T agent"   # the connector depends on this exact line
SECTION_RE = re.compile(r"^ {0,3}## ([0-9]{4}-[0-9]{2}-[0-9]{2})[ \t]*$")   # exact: a NBSP or closing `##` is not the day heading
DAY_H1_RE = re.compile(r"^# Lessons — ([0-9]{4}-[0-9]{2}-[0-9]{2})[ \t]*$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
VERIFIED_NAME_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}_[a-z0-9-]+_v[0-9]+\.md$")
LABELS = {"Why it matters here": "why", "Do": "do", "Source": "source"}
FIELD_RE = re.compile(r"(Why it matters here|Do|Source):")
FIELDS = ("why", "do", "source")
CONFIDENCE_RE = re.compile(r"(?<![A-Za-z0-9_])confidence ([0-9]{1,3})%(?![0-9%])")   # a standalone label only
MARKER_RE = re.compile(r"^[ \t]*(?:[-*+]|[0-9]{1,9}[.)])[ \t]*")
WS = " \t\n\r\f"                                    # HTML/CommonMark whitespace; a NBSP is content
SEP = "\ufffc"    # visible non-text content (code, an image): splits words and counts as a value
SPLIT = "\x00"    # a raw HTML tag, or anything inside a raw HTML element: splits words, never counts as a value
BLOCK_TAGS = frozenset("address article aside blockquote br dd details dialog div dl dt fieldset figcaption figure "
                       "footer form h1 h2 h3 h4 h5 h6 header hgroup hr li main nav ol p pre search section summary "
                       "table tbody td tfoot th thead tr ul".split())      # whitespace next to these is never shown
# Raw HTML that shows whitespace as written (textarea, xmp, listing, plaintext render as pre /
# pre-wrap; checked in Chromium 141) or can make it so (a style element or attribute): a lesson
# holding any of it is compared without whitespace normalization.
WS_KEEP_TAGS = frozenset({"textarea", "xmp", "listing", "plaintext", "style"})
STYLE_ATTR_RE = re.compile(r"[\t\n\f\r \"'/]style[\t\n\f\r ]*=", re.I)
# Raw-HTML blocks that only end at a terminator (CommonMark types 1-5); the parser also ends them
# when their container ends, but the OUTPUT then holds unterminated HTML that a browser reads past.
HTML_ENDS = ((re.compile(r"<(script|pre|style|textarea)(?:[ \t>]|$)", re.I), None),
             (re.compile(r"<!--"), "-->"), (re.compile(r"<\?"), "?>"),
             (re.compile(r"<!\[CDATA\["), "]]>"), (re.compile(r"<![A-Za-z]"), ">"))


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


def regular_file(p: pathlib.Path) -> bool:
    """A plain file only: symlinks (live or dangling) and directories are rejected, because
    `is_file()` follows a link and would check content from outside the repo."""
    try:
        return not p.is_symlink() and p.is_file()
    except OSError:
        return False


def read_text(p: pathlib.Path) -> str | None:
    """A UTF-8 file's text with a leading BOM dropped and CR / CRLF made LF (CommonMark line
    endings), or None with a FAIL recorded when it is not valid UTF-8."""
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        fail(f"utf8:{p.name}", f"not valid UTF-8 at byte {exc.start}: {exc.reason}")
        return None
    return re.sub(r"\r\n?", "\n", text)


# --- parse tree ------------------------------------------------------------------
class Node:
    """One block of the parse: its opening token `t`, child blocks `kids`, and the token
    span [i, j] it covers (a leaf block spans one token)."""
    __slots__ = ("t", "kind", "kids", "i", "j")

    def __init__(self, t, i: int) -> None:
        self.t, self.i, self.j, self.kids = t, i, i, []
        self.kind = t.type[:-5] if t.type.endswith("_open") else t.type


class Doc:
    """A parsed Markdown file: tokens, top-level blocks, reference env, source lines."""

    def __init__(self, text: str) -> None:
        self.env: dict = {}
        self.tokens = MD.parse(text, self.env)
        self.lines = text.split("\n")
        self.n_lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        self.top: list[Node] = []
        stack: list[Node] = []
        for k, t in enumerate(self.tokens):
            if t.nesting == -1:
                stack.pop().j = k
                continue
            n = Node(t, k)
            (stack[-1].kids if stack else self.top).append(n)
            if t.nesting == 1:
                stack.append(n)

    def line(self, n: Node, offset: int = 0) -> str:
        return self.lines[n.t.map[0] + offset] if n.t.map else ""

    def html(self, n: Node) -> str:
        """The block rendered with this file's reference definitions, as a reader sees it."""
        return visible_html(MD.renderer.render(self.tokens[n.i:n.j + 1], MD.options, self.env))

    def unclosed(self) -> list[str]:
        out: list[str] = []
        for t in self.tokens:
            if t.type == "fence" and t.map[1] >= self.n_lines:
                last = self.lines[t.map[1] - 1] if t.map[1] - 1 > t.map[0] else ""
                closer = r"[ \t>]*" + re.escape(t.markup[0]) + "{%d,}[ \t]*" % len(t.markup)
                if not re.fullmatch(closer, last):
                    out.append(f"fenced code block opened with {t.markup} never closes")
            elif t.type == "html_block":
                c, msg = t.content.lstrip(" "), None
                for opener, end in HTML_ENDS:             # CommonMark: the block swallows Markdown until its end marker
                    m = opener.match(c)
                    if m:
                        end = end or f"</{m.group(1).lower()}>"
                        if end not in c.lower():  # CommonMark tests the whole line: `<?>` and `<!-->` close at once
                            msg = "comment" if end == "-->" else f"no {end!r}"
                        break
                msg = msg or html_open_at_end(t.content)  # the browser: still inside a tag, comment or raw-text element
                if msg:
                    out.append("HTML comment never closes" if msg == "comment" else f"HTML block never closes ({msg})")
        return out


def walk(n: Node):
    yield n
    for k in n.kids:
        yield from walk(k)


def visible_html(html: str) -> str:
    """Rendered HTML reduced to what a reader can tell apart. Markup a browser never displays is
    removed by a browser-faithful tokenizer (knowledge_md.html_segments), so tags, attribute values
    and raw text stay byte-exact. Text whitespace is collapsed the way CSS does in normal flow —
    runs become one space, also across inline element boundaries, and none survives next to a block
    boundary — except inside <pre>, <code> and elements that keep whitespace (textarea, xmp,
    listing, plaintext, a style attribute). A <style> element can restyle anything, so a lesson
    holding one is compared with whitespace exactly as written."""
    segs: list[tuple[str, str, str]] = []
    for seg in html_segments(html):
        if seg[0] == "text" and segs and segs[-1][0] == "text":
            segs[-1] = ("text", segs[-1][1] + seg[1], "")    # text that a removed comment split is one text
        elif seg[0] != "hidden":
            segs.append(seg)
    text = [src.replace("<", "&lt;") if kind == "text" else src for kind, src, _ in segs]
    if any(kind == "start" and name == "style" for kind, _, name in segs):
        return "".join(text).strip(WS)
    keep: list[str] = []                                      # open elements whose whitespace is shown as written
    last, space = None, True                                  # last collapsible text index; ends in (or at) a space
    for k, (kind, src, name) in enumerate(segs):
        if kind in ("start", "end"):
            if kind == "start" and name not in VOID_TAGS and (name in WS_KEEP_TAGS or name in ("pre", "code")
                                                                or STYLE_ATTR_RE.search(src)):
                keep.append(name)
            elif kind == "end" and keep and keep[-1] == name:
                keep.pop()
            if name in BLOCK_TAGS:                            # a block boundary: no space survives on either side
                if last is not None:
                    text[last] = text[last].rstrip(" ")
                last, space = None, True
            elif kind == "start" and name in VOID_TAGS:       # an image or input is visible content
                last, space = None, False
            continue
        if kind == "raw" or keep:
            last, space = None, space and not src
            continue
        t = re.sub(r"[ \t\n\r\f]+", " ", text[k])
        if space and t.startswith(" "):
            t = t[1:]
        elif t.startswith(" ") and last is not None:          # only inline tags since the last text: one canonical
            text[last], t = text[last] + " ", t[1:]           # place for the space (`x<a> y` reads as `x <a>y`)
        if t:
            last, space = k, t.endswith(" ")
        text[k] = t
    if last is not None:
        text[last] = text[last].rstrip(" ")
    return "".join(text).strip(WS)


def visible(n: Node) -> bool:
    """Does this top-level block render anything? Only raw HTML can be invisible."""
    return n.kind != "html_block" or any(kind != "hidden" and (kind != "text" or src.strip(WS))
                                         for kind, src, _ in html_segments(n.t.content))


def h2s(doc: Doc, n: Node) -> list[str]:
    """Every H2 inside `n` (block quotes and list items included), ATX or Setext."""
    out = []
    for d in walk(n):
        if d.kind == "heading" and d.t.tag == "h2":
            if d.t.markup in ("-", "="):
                out.append(doc.line(d).strip(WS)[:60] + " / " + doc.line(d, d.t.map[1] - d.t.map[0] - 1).strip(WS)[:20])
            else:
                out.append(doc.line(d).strip(" \t"))
    return out


# --- lessons ---------------------------------------------------------------------
def inline_tokens(inline) -> list:
    """The paragraph's inline tokens without the empty text tokens the parser leaves around delimiters."""
    return [c for c in inline.children if not (c.type == "text" and c.content == "")]


def invisible_inline(c) -> bool:
    """An inline raw-HTML token a browser never displays (a comment, PI, declaration, CDATA)."""
    return c.type == "html_inline" and all(kind == "hidden" for kind, _, _ in html_segments(c.content))


def raw_step(stack: list[str], c) -> None:
    """Follow raw HTML elements through an inline html token: a non-void start tag opens one; an end
    tag closes it only when it matches the innermost open element (a stray end tag is ignored, so a
    hidden region is never left early)."""
    for kind, _, name in html_segments(c.content):
        if kind == "start" and name not in VOID_TAGS:
            stack.append(name)
        elif kind == "end" and stack and stack[-1] == name:
            stack.pop()


def visible_text(tokens, code_text: bool = False) -> str:
    """The text a reader is sure to see in a run of inline tokens. Formatting delimiters and
    never-displayed markup are zero-width; line breaks read as a space; code and images become SEP
    (code becomes its own text with code_text). A raw HTML tag, and everything inside a raw HTML
    element (it may be `hidden`, a template, or styled away), becomes SPLIT: it splits words but
    never counts as a value."""
    out: list[str] = []
    depth: list[str] = []
    for c in tokens:
        if c.type == "html_inline":
            raw_step(depth, c)
            if not invisible_inline(c):
                out.append(SPLIT)
        elif depth:
            out.append(SPLIT)
        elif c.type == "text":
            out.append(c.content)
        elif c.type in ("softbreak", "hardbreak"):
            out.append(" ")
        elif c.type == "code_inline" and code_text:
            out.append(c.content)
        elif c.type in ("code_inline", "image"):
            out.append(SEP)
    return "".join(out)


def lead_text(tokens) -> str:
    """The paragraph's leading plain text (invisible raw HTML skipped): where a field label must sit."""
    out = []
    for c in tokens:
        if c.type == "text":
            out.append(c.content)
        elif not invisible_inline(c):
            break
    return "".join(out)


def parse_source(inline) -> int | None:
    """Confidence N for a Source field rendering as `Source: <link to http(s)> … confidence N%`,
    else None. Only visible text after the link counts — never link text, code or HTML attributes.
    The link must be written inline, `[title](https://…)`: the paragraph is re-read without the
    file's reference definitions, so a `[title][ref]` link does not count."""
    toks = [c for c in inline_tokens(MD.parseInline(inline.content, {})[0]) if not invisible_inline(c)]
    k, lead = 0, ""
    while k < len(toks) and toks[k].type == "text":
        lead += toks[k].content
        k += 1
    if not lead.startswith("Source:") or lead[len("Source:"):].strip(" \t"):
        return None
    while k < len(toks) and toks[k].type == "softbreak":
        k += 1
    if k >= len(toks) or toks[k].type != "link_open" or toks[k].markup == "autolink":
        return None
    if not re.match(r"https?://[^ \t]+$", toks[k].attrGet("href") or ""):
        return None
    close = next((j for j in range(k + 1, len(toks)) if toks[j].type == "link_close"), None)
    if close is None or not visible_text(toks[k + 1:close]).replace(SPLIT, "").strip(WS):   # needs a visible title
        return None
    tail = visible_text(toks[k + 1:close])[-1:] + visible_text(toks[close + 1:])   # the link text's last character
    m = CONFIDENCE_RE.search(tail, 1)                                              # takes part in the word boundary
    return int(m.group(1)) if m else None


def title_of(inline) -> tuple[str | None, bool]:
    """(title, continues) when the paragraph opens with ONE `**strong**` span holding no other
    strong span — `continues` when the paragraph goes on past it on later lines. (None, _)
    when it is not a bold lesson title at all."""
    ch = [c for c in inline_tokens(inline) if not invisible_inline(c)]
    if not ch or ch[0].type != "strong_open" or ch[0].markup != "**":
        return None, False
    depth, end = 0, None
    for k, c in enumerate(ch):
        if c.type == "strong_open":
            depth += 1
            if depth > 1:
                return None, False
        elif c.type == "strong_close":
            depth -= 1
            if depth == 0:
                end = k
                break
    if end is None:
        return None, False
    title = visible_text(ch[1:end], code_text=True).replace(SPLIT, "").replace(SEP, "")   # what a reader sees
    rest = ch[end + 1:]
    if rest and rest[0].type not in ("softbreak", "hardbreak"):
        return None, False                        # `**a** b **c**`, `**foo***`: not one bold span
    return (title if title.strip(WS) else None), bool(rest)


def has_value(doc: Doc, n: Node) -> bool:
    """Does this block show a reader something: visible text, code or an image in Markdown (never
    inside raw HTML, which may be hidden)? An empty heading or a rule does not."""
    for t in doc.tokens[n.i:n.j + 1]:
        if t.type == "inline" and visible_text(inline_tokens(t)).replace(SPLIT, "").strip(WS):
            return True
        if t.type in ("fence", "code_block") and t.content.strip(WS):
            return True
    return False


def raw_html_in(doc: Doc, n: Node) -> bool:
    """Does this block hold raw HTML other than `<!-- comments -->`? Lessons are plain Markdown:
    raw HTML can hide, restyle or swallow what a reader sees, so only comments are allowed."""
    def only_comments(html: str) -> bool:
        return all((kind == "hidden" and src.startswith("<!--")) or (kind == "text" and not src.strip(WS))
                   for kind, src, _ in html_segments(html))
    for t in doc.tokens[n.i:n.j + 1]:
        if t.type == "html_block" and not only_comments(t.content):
            return True
        if t.type == "inline" and any(c.type == "html_inline" and not only_comments(c.content) for c in t.children):
            return True
    return False


def parse_lesson(doc: Doc, item: Node) -> dict:
    """{title, problems, key, parts} for one top-level list item of a day section."""
    lesson = {"problems": [], "key": doc.html(item), "parts": {}, "seen": {k: False for k in FIELDS}}
    if raw_html_in(doc, item):
        lesson["problems"].append("raw HTML in a lesson (only <!-- comments --> are allowed)")
    head = item.kids[0] if item.kids and item.kids[0].kind == "paragraph" else None
    title, continues = title_of(head.kids[0].t) if head and item.t.markup == "-" else (None, False)
    if title is None:
        raw = MARKER_RE.sub("", doc.line(item), count=1).strip(WS)
        lesson["title"] = "MALFORMED: " + (raw or "(empty list item)")
        lesson["problems"].append("not-a-bold-lesson-bullet")
        return lesson
    lesson["title"] = title
    lesson["parts"]["title"] = doc.html(head)
    if continues:
        lesson["problems"].append("title paragraph continues past the bold span")
    order: list[str] = []
    for block in item.kids[1:]:
        if block.kind != "bullet_list" or block.t.markup != "-":
            continue
        for field in block.kids:
            fk = field.kids
            para = fk[0].kids[0].t if fk and fk[0].kind == "paragraph" else None
            toks = inline_tokens(para) if para else []
            m = FIELD_RE.match(lead_text(toks)) if para else None
            if not m:
                continue                          # a sub-bullet that is not a field: compared, not counted
            key = LABELS[m.group(1)]
            order.append(key)
            lesson["parts"][key] = doc.html(field)
            if lesson["seen"][key]:
                lesson["problems"].append(f"duplicate {key}")
            lesson["seen"][key] = True
            # empty = nothing a reader is sure to see after the label: not in the paragraph, and no
            # later Markdown block (raw HTML never counts as a value — it may be hidden)
            empty = (not visible_text(toks)[m.end():].replace(SPLIT, "").strip(WS)
                     and not any(has_value(doc, b) for b in fk[1:]))
            if key == "source":
                conf = None if empty else parse_source(para)
                if conf is None:
                    lesson["problems"].append("source line is not `[title](https://…) … confidence N%`")
                elif conf > 100:
                    lesson["problems"].append(f"confidence {conf}% out of 0-100")
            elif empty:
                lesson["problems"].append(f"missing or empty {key}")
    lesson["parts"]["order"] = " ".join(order)
    lesson["problems"] += [f"missing {k}" for k in FIELDS if not lesson["seen"][k]]
    lesson["problems"] += [f"heading {h[:30]!r} nested inside the lesson" for h in h2s(doc, item)]
    return lesson


def parse_sections(doc: Doc, nodes: list[Node], day: str | None = None) -> dict:
    """Walk top-level blocks. knowledge.md mode (day None): `## YYYY-MM-DD` opens a section,
    anything visible outside one is misplaced. Day-file mode: everything is that day's."""
    res = {"sections": {day: []} if day else {}, "dups": [], "bad": [], "misplaced": [], "stray": []}
    current = day
    for n in nodes:
        if n.kind == "heading" and n.t.tag == "h2" and not day:
            m = SECTION_RE.match(doc.line(n)) if n.t.markup == "##" else None
            if m:
                current = m.group(1)
                if current in res["sections"]:
                    res["dups"].append(current)
                else:
                    res["sections"][current] = []
            else:
                res["bad"] += h2s(doc, n)
                current = None                    # nothing after a bad heading belongs to a day
            continue
        if not visible(n):
            continue                              # a comment block renders nothing
        quoted = h2s(doc, n) if n.kind == "blockquote" and not day else []
        if n.kind in ("bullet_list", "ordered_list") and current:
            res["sections"][current] += [parse_lesson(doc, item) for item in n.kids]
        elif current is None and not (n.kind == "heading" and n.t.tag == "h1" and n.t.map[0] == 0):
            res["misplaced"] += [doc.line(k).strip(WS)[:60] for k in (n.kids if n.kind.endswith("list") else [n])]
        elif current:
            res["stray"].append(doc.line(n).strip(WS)[:60] or n.kind)
        if quoted:
            res["bad"] += quoted
            current = None
    return res


def shape_errors(sections: dict[str, list[dict]]) -> list[str]:
    """Problems as 'date#n: problem'."""
    return [f"{d}#{i}: {p}" for d, ls in sections.items() for i, l in enumerate(ls, 1) for p in l["problems"]]


def compare(k_lessons: list[dict], d_lessons: list[dict]) -> str | None:
    """None when both copies render identically lesson by lesson, else a diagnosis."""
    if [l["key"] for l in k_lessons] == [l["key"] for l in d_lessons]:
        return None
    titles_k = {l["title"] for l in k_lessons}
    titles_d = {l["title"] for l in d_lessons}
    only_k = [l["title"][:40] for l in k_lessons if l["title"] not in titles_d]
    only_d = [l["title"][:40] for l in d_lessons if l["title"] not in titles_k]
    diff = []
    for a, b in zip(k_lessons, d_lessons):
        if a["key"] != b["key"] and a["title"] == b["title"]:
            parts = [p for p in ("title", "why", "do", "source", "order") if a["parts"].get(p) != b["parts"].get(p)]
            diff.append(a["title"][:30] + ": " + (",".join(parts) or "other content"))
    detail = f"{len(d_lessons)} lesson(s) here vs {len(k_lessons)} in knowledge.md"
    if diff:
        detail += f"; same title, different content: {diff[:3]}"
    if only_k:
        detail += f"; only in knowledge.md: {only_k[:3]}"
    if only_d:
        detail += f"; only here: {only_d[:3]}"
    if not diff and not only_k and not only_d:
        detail += "; same set, different order" if len(d_lessons) == len(k_lessons) else "; a lesson repeats"
    return detail


# --- knowledge.md ------------------------------------------------------------------
kpath = ROOT / "knowledge.md"
sections: dict[str, list[dict]] = {}
if kpath.is_symlink():
    fail("knowledge.md", "is a symlink — the managed file must be a real file inside the repo (connector writes would go to the target)")
elif not kpath.is_file():
    fail("knowledge.md", "missing")
else:
    text = read_text(kpath) or ""
    first_line = text.split("\n", 1)[0]
    if first_line == KNOWLEDGE_H1:                   # exact: trailing whitespace would break the connector's anchor too
        ok("knowledge:h1", "exact connector heading present")
    else:
        fail("knowledge:h1", f"first line must be {KNOWLEDGE_H1!r}, got {first_line[:70]!r}")
    kdoc = Doc(text)
    kres = parse_sections(kdoc, kdoc.top)
    sections = kres["sections"]
    if kdoc.unclosed():
        fail("knowledge:unclosed", "; ".join(kdoc.unclosed()) + " — everything after it is hidden from readers")
    if kres["bad"]:
        fail("knowledge:headings", f"H2 headings that are not `## YYYY-MM-DD`: {kres['bad'][:4]}")
    else:
        ok("knowledge:headings", "every H2 is a day heading")
    if kres["misplaced"]:
        fail("knowledge:misplaced", f"{len(kres['misplaced'])} visible block(s) outside any `## YYYY-MM-DD` section: {kres['misplaced'][:3]}")
    if kres["stray"]:
        fail("knowledge:stray", f"{len(kres['stray'])} visible block(s) inside a day section that are not lessons (no day file carries them): {kres['stray'][:3]}")
    dates = list(sections)
    if not dates:
        fail("knowledge:sections", "no `## YYYY-MM-DD` sections")
    else:
        ok("knowledge:sections", f"{len(dates)} day section(s), {sum(len(v) for v in sections.values())} lesson(s)")
        if dates == sorted(dates, reverse=True):
            ok("knowledge:order", "newest first")
        else:
            fail("knowledge:order", f"sections not newest-first: {dates}")
        if kres["dups"]:
            fail("knowledge:unique-dates", f"day section repeated: {sorted(set(kres['dups']))}")
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

# --- lessons/ ------------------------------------------------------------------------
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
    unreadable = [p.name for p in entries if not regular_file(p)]
    if unreadable:
        fail("lessons:readable", f"not regular files (symlinks and directories are rejected): {unreadable}")
    files = [p.name for p in entries if regular_file(p)]
    badnames = [f for f in files if not f.endswith(".md") or not DATE_RE.match(f[:-3]) or not valid_date(f[:-3])]
    if badnames:
        fail("lessons:names", f"not a real YYYY-MM-DD.md: {badnames}")
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
        text = read_text(p)
        if text is None:
            continue
        ddoc = Doc(text)
        problems = ddoc.unclosed()
        shown = [n for n in ddoc.top if visible(n)]
        head = shown[0] if shown else None
        first = ddoc.line(head) if head else ""
        hm = DAY_H1_RE.match(first) if head and head.kind == "heading" and head.t.tag == "h1" else None
        if not hm:
            problems.append(f"first visible line must be `# Lessons — {d}`, got {first[:40]!r}")
        elif hm.group(1) != d:
            problems.append(f"H1 date {hm.group(1)} does not match filename {d}")
        headings = [h for n in ddoc.top for h in h2s(ddoc, n)]
        if headings:
            problems.append(f"contains H2 heading(s) {headings[:4]} — a per-day file has no `## ` headings")
        body = [n for n in ddoc.top if n is not head or not hm]
        body = [n for n in body if not (n.kind == "heading" and n.t.tag == "h2")]
        dres = parse_sections(ddoc, body, day=d)
        if dres["stray"]:
            problems.append(f"visible block(s) that are not lessons: {dres['stray'][:3]}")
        day_lessons = dres["sections"][d]
        bad_day = shape_errors({d: day_lessons})
        if bad_day:
            problems.append(f"shape: {bad_day[:4]}")
        detail = compare(sections[d], day_lessons)
        if detail:
            problems.append(detail)
        if problems:
            fail(f"lessons:{d}", "; ".join(problems))
        else:
            ok(f"lessons:{d}", f"{len(day_lessons)} lesson(s), identical content and order to knowledge.md")

# --- verified/ -------------------------------------------------------------------------
vdir = ROOT / "verified"
if vdir.is_symlink():
    fail("verified/", "is a symlink — the managed directory must be a real directory inside the repo")
elif not vdir.is_dir():
    warn("verified/", "directory missing")
else:
    ventries = sorted(vdir.iterdir())
    vunreadable = [p.name for p in ventries if not regular_file(p)]
    if vunreadable:
        fail("verified:readable", f"not regular files (symlinks and directories are rejected): {vunreadable}")
    vfiles = [p for p in ventries if regular_file(p)]
    badnames = [p.name for p in vfiles if not VERIFIED_NAME_RE.match(p.name) or not valid_date(p.name[:10])]
    if badnames:
        fail("verified:names", f"not a real YYYY-MM-DD_topic_vN.md: {badnames}")
    else:
        ok("verified:names", f"{len(vfiles)} sheet(s), all dated and versioned")
    noh1 = []
    for p in vfiles:
        text = read_text(p)
        if text is None:
            continue
        vdoc = Doc(text)
        head = next((n for n in vdoc.top if visible(n)), None)
        heading_text = ("".join(c.content for c in head.kids[0].t.children if c.type in ("text", "code_inline"))
                        if head and head.kind == "heading" and head.t.tag == "h1" and head.t.markup == "#" else "")
        if not heading_text.strip(WS):
            noh1.append(p.name)
    if noh1:
        fail("verified:h1", f"first visible block is not an ATX H1 with text (comments and reference definitions ignored; code and raw HTML count): {noh1}")
    elif vfiles:
        ok("verified:h1", "every sheet starts with an H1")

# --- summary ---------------------------------------------------------------------------
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
