"""knowledge_md.py — the one Markdown parser and HTML tokenizer every harness script uses.

markdown-it-py with the CommonMark preset, plus the patches that close the gaps between it and
the CommonMark 0.31.2 reference implementation (commonmark.js) that this repo's checks depend
on. harness/conformance/check.py proves the combination against the reference on all 652 spec
examples and on cases.json; a new markdown-it-py release that drifts fails CI there first.

html_segments() splits rendered HTML the way a browser's tokenizer does, so the checker can
drop only what a browser never displays. harness/conformance/html_oracle.py checks it against
html5lib (a WHATWG-conformant tokenizer) on a fixed corpus and on seeded fuzz.
"""
from __future__ import annotations

import re
import sys

import markdown_it.rules_block  # noqa: F401  (loads the html_block module patched below)
from markdown_it import MarkdownIt
from markdown_it.rules_block.reference import reference as _reference


def _reference_999(state, start: int, end: int, silent: bool) -> bool:
    """markdown-it-py 4.0.0 accepts link-reference labels of any length; CommonMark caps them at
    999 characters (the reference implementation renders a longer one as a paragraph). Undo such
    a definition so the line stays visible prose. Pinned by harness/conformance/cases.json (label-999, label-1000)."""
    if silent:                                      # a probe only: nothing is recorded, nothing to undo
        return _reference(state, start, end, silent)
    before = dict(state.env.get("references", {}))
    n_tokens = len(state.tokens)
    if not _reference(state, start, end, silent):
        return False
    raw = state.src[state.bMarks[start] + state.tShift[start]:state.eMarks[state.line - 1]]
    m = re.match(r"\[((?:\\.|[^\\\[\]])*)\]:", raw, re.S)
    if m and len(m.group(1)) > 999:
        state.env["references"] = before
        del state.tokens[n_tokens:]
        state.line = start
        return False
    return True


def _patch_html_blocks() -> None:
    """markdown-it-py 4.0.0 starts a type-4 (declaration) HTML block only for an UPPERCASE letter
    after `<!` — CommonMark 0.31.2 takes any ASCII letter — and uses Python's `\\s`, which also
    matches a NBSP, where the spec allows only space and tab. Rewrite those start patterns in
    place (the rule reads the module table at call time). Pinned by cases.json
    (lowercase-decl, nbsp-after-tag, type7-nbsp)."""
    seqs = sys.modules["markdown_it.rules_block.html_block"].HTML_SEQUENCES
    for k, (start, end, can_interrupt) in enumerate(seqs):
        pattern = start.pattern.replace("<![A-Z]", "<![A-Za-z]").replace(r"\s", "[ \t]")
        seqs[k] = (re.compile(pattern, start.flags), end, can_interrupt)


_patch_html_blocks()
MD = MarkdownIt("commonmark")
MD.block.ruler.at("reference", _reference_999)


# --- raw HTML, tokenized the way a browser does ----------------------------------------------
HTML_WS = "\t\n\f\r "
RAWTEXT_TAGS = frozenset({"script", "style", "textarea", "title", "xmp", "iframe", "noembed", "noframes",
                          "noscript"})                      # content is text to the matching end tag
VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
                       "track", "wbr"})                     # never have content, `/>` or not
_NAME_RE = re.compile(r"</?([A-Za-z][^\t\n\f\r />]*)")
_COMMENT_RE = re.compile(r"<!--(?:-?>|.*?(?:--!?>|\Z))", re.S)   # `<!-->`, `<!--->` are complete; `--!>` ends one too


def _tag_end(s: str, i: int) -> int:
    """Index just past the tag starting at s[i] (WHATWG attribute states: a quote only opens a
    value right after `=`, and `>` anywhere else ends the tag), or -1 when it never ends."""
    j, n, state = _NAME_RE.match(s, i).end(), len(s), "before"
    while j < n:
        c = s[j]
        if state == "value":                                 # right after `=`
            if c in HTML_WS:
                j += 1
                continue
            if c in "\"'":
                k = s.find(c, j + 1)
                if k < 0:
                    return -1
                j, state = k + 1, "before"
                continue
            state = "unquoted"
        if c == ">":
            return j + 1
        if state == "unquoted":
            state = "before" if c in HTML_WS else "unquoted"
        elif c == "=" and state in ("name", "after"):
            state = "value"
        elif c in HTML_WS:
            state = "after" if state == "name" else state
        elif c == "/":
            state = "before"
        else:
            state = "name"                                   # a new attribute name (a leading `=` included)
        j += 1
    return -1


def html_segments(html: str) -> list[tuple[str, str, str]]:
    """[(kind, source, tag name)] with kind "text", "start", "end", "raw" (a raw-text element's
    content, or CDATA inside svg/math) or "hidden" (a comment, PI, declaration, CDATA or
    `</>`: a browser never displays it). A tag cut off by the end of the input is kept, because in a
    fragment the browser would read on into whatever follows."""
    out: list[tuple[str, str, str]] = []
    i, n, foreign = 0, len(html), 0                         # foreign: open svg/math elements
    while i < n:
        j = html.find("<", i)
        if j < 0:
            out.append(("text", html[i:], ""))
            break
        if j > i:
            out.append(("text", html[i:j], ""))
        nm = _NAME_RE.match(html, j)
        if html.startswith("<!--", j):
            k = _COMMENT_RE.match(html, j).end()
            out.append(("hidden", html[j:k], ""))
        elif nm:
            k, name = _tag_end(html, j), nm.group(1).lower()
            k = n if k < 0 else k
            end = html[j + 1] == "/"
            out.append(("end" if end else "start", html[j:k], name))
            if name in ("svg", "math"):                     # `/>` self-closes a foreign START tag only
                foreign = max(0, foreign - 1) if end else foreign + (not html[j:k].endswith("/>"))
            if not end and (name in RAWTEXT_TAGS or name == "plaintext"):
                close = None if name == "plaintext" else re.compile(
                    r"</" + re.escape(name) + r"[\t\n\f\r />]", re.I).search(html, k)
                stop = close.start() if close else n
                if stop > k:
                    out.append(("raw", html[k:stop], name))
                k = stop
        elif foreign and html.startswith("<![CDATA[", j):   # real CDATA in svg/math: kept verbatim
            e = html.find("]]>", j)
            k = n if e < 0 else e + 3
            out.append(("raw", html[j:k], ""))
        elif html.startswith("</>", j):
            k = j + 3
            out.append(("hidden", "</>", ""))
        elif html[j + 1:j + 2] in ("!", "?") or (html[j + 1:j + 2] == "/" and j + 2 < n):
            e = html.find(">", j)                            # a bogus comment: ends at the first `>`
            k = n if e < 0 else e + 1
            out.append(("hidden", html[j:k], ""))
        else:
            k = j + (2 if html.startswith("</", j) else 1)   # a lone `<`, or `</` at the very end
            out.append(("text", html[j:k], ""))
        i = k
    return out


def strip_hidden(html: str) -> str:
    """The HTML without what a browser never displays, a literal `<` in text written as `&lt;`
    so that removing a comment can never splice two pieces into a new tag."""
    return "".join(src.replace("<", "&lt;") if kind == "text" else src
                   for kind, src, _ in html_segments(html) if kind != "hidden")


def html_open_at_end(html: str) -> str | None:
    """Why a browser would still be inside something when this HTML ends — and so read on into
    whatever follows — or None: a cut-off tag, comment or bogus comment, or an open raw-text element."""
    segs = html_segments(html)
    if not segs:
        return None
    kind, src, name = segs[-1]
    if kind in ("start", "end") and _tag_end(src, 0) < 0:
        return "a tag is cut off"
    if kind == "hidden" and src.startswith("<!--") and not (src.endswith(("-->", "--!>")) or src in ("<!-->", "<!--->")):
        return "comment"
    if kind == "hidden" and not src.endswith(">"):
        return "no '>'"
    if kind == "raw" and not name and not src.endswith("]]>"):
        return "no ']]>'"
    if (kind == "raw" or kind == "start") and (name in RAWTEXT_TAGS or name == "plaintext"):
        return f"<{name}> is still open"
    return None
