"""knowledge_md.py — the one Markdown parser every harness script uses.

markdown-it-py with the CommonMark preset, plus the patches that close the gaps between it and
the CommonMark 0.31.2 reference implementation (commonmark.js) that this repo's checks depend
on. harness/conformance/check.py proves the combination against the reference on all 652 spec
examples and on cases.json; a new markdown-it-py release that drifts fails CI there first.
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
    raw =state.src[state.bMarks[start] + state.tShift[start]:state.eMarks[state.line - 1]]
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
