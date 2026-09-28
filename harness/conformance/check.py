#!/usr/bin/env python3
"""check.py — differential conformance gate: the harness's Markdown parser (knowledge_md.MD)
must render every CommonMark 0.31.2 spec example and every case in cases.json exactly like the
reference implementation (commonmark.js 0.31.2). Output follows the harness contract.

Usage: python3 harness/conformance/check.py ref.json   (ref.json from reference.cjs)
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from knowledge_md import MD  # noqa: E402

import re  # noqa: E402

# Renderer whitespace that no browser shows: the two libraries place a newline differently
# right before some block-level tags (`<li>b<pre>` vs `<li>b\n<pre>`, an empty
# `<blockquote>\n</blockquote>`). Both sides are compared with exactly that newline removed —
# never inside <pre>, where a newline is visible; every other byte must match.
BLOCK_NL = re.compile(r"\n(?=</?(?:blockquote|ul|ol|li|p|h[1-6]|hr|div|table)[\s/>])|\n(?=<pre[\s>])|\n(?=<!--)")
PRE = re.compile(r"<pre[\s>].*?(?=</pre>)", re.S)   # a newline inside <pre> is visible: never canonicalized
# Reviewed cases where the REFERENCE departs from the spec text; we follow the spec. Each entry
# pins OUR exact output (cmark-gfm 0.29.0.gfm.13's output, checked 2026-09-27) and must still differ
# from the reference, so an entry can neither hide a regression nor outlive its reason.
ALLOWED = {
    "nbsp-after-tag": ("commonmark.js matches HTML-block starts with JS `\\s`, which includes U+00A0; spec 0.31.2 "
                       "section 4.6 allows only space, tab, end of line, `>` or `/>` after the tag name, and 6.6 "
                       "only spaces, tabs and a line ending inside a tag. cmark and cmark-gfm (GitHub): text.",
                       "<p>&lt;div\xa0class=x&gt;\ntext</p>\n"),
    "type7-nbsp": ("same root cause: an attribute must be preceded by space, tab or a line ending (spec 6.6); "
                   "cmark and cmark-gfm render the tag as text.", "<p>&lt;span\xa0a=b&gt;</p>\n"),
    "nbsp-in-inline-tag": ("same root cause inline: commonmark.js takes `<span` + U+00A0 + `a=b>` as raw HTML; spec 6.6 and "
                           "cmark-gfm make it text.", "<p>x &lt;span\xa0a=b&gt; y</p>\n"),
}


def canon(html: str) -> str:
    inside = [m.span() for m in PRE.finditer(html)]
    return BLOCK_NL.sub(lambda m: m.group(0) if any(a < m.start() < b for a, b in inside) else "", html)

ref = json.load(open(sys.argv[1], encoding="utf-8"))
bad, allowed_hit = [], []
for group in ("spec", "cases"):
    for ex in ref[group]:
        ours = canon(MD.render(ex["markdown"]))
        if ex["id"] in ALLOWED and ours != canon(ALLOWED[ex["id"]][1]):
            bad.append(ex["id"])                           # an exception must render exactly as pinned
        elif ours != canon(ex["html"]):
            (allowed_hit if ex["id"] in ALLOWED else bad).append(ex["id"])
n_spec, n_cases = len(ref["spec"]), len(ref["cases"])
def differing(group_is_spec: bool) -> int:
    return sum(1 for x in bad + allowed_hit if x.startswith("spec#") == group_is_spec)


print(f"{'PASS' if not bad else 'FAIL'} conformance:spec+cases   {n_spec - differing(True)}/{n_spec} spec examples identical, "
      f"{n_cases - differing(False)}/{n_cases} edge cases identical, {len(allowed_hit)} reviewed exception(s) {sorted(allowed_hit)}")
for b in bad:
    ex = next(e for g in ("spec", "cases") for e in ref[g] if e["id"] == b)
    print(f"  DIVERGES {b}: {ex.get('why', ex.get('section'))}\n    input {ex['markdown']!r}\n    ref   {ex['html']!r}\n    ours  {MD.render(ex['markdown'])!r}")
stale = sorted(set(ALLOWED) - set(allowed_hit) - set(bad))   # a mis-pinned entry is reported above
for a in sorted(allowed_hit):
    print(f"  allowed {a}: {ALLOWED[a][0]}")
if stale:
    print(f"FAIL conformance:allowlist      allowed divergence(s) no longer diverge — remove them: {stale}")
print("----")
ok = not bad and not stale
print(f"RESULT: {'PASS' if ok else 'FAIL'} — {len(bad)} unexpected divergence(s)")
sys.exit(0 if ok else 1)
