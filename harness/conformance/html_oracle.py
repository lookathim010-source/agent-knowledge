#!/usr/bin/env python3
"""html_oracle.py — differential gate for knowledge_md.html_segments(): it must split HTML into
tags, text and never-displayed markup exactly where html5lib (a WHATWG-conformant tokenizer)
does, on the fixed corpus in html_cases.json and on seeded random fragments.

The comparison drives html5lib's tokenizer the way its tree builder does (RCDATA / RAWTEXT /
PLAINTEXT after the matching start tags) and compares what is left once never-displayed markup
(comments, bogus comments, doctypes, `</>`) is removed: start and end tag names, and the text. Out of scope by design, documented
in the README: `<script>` (its escape states only move boundaries inside content no browser
displays), svg/math (CDATA there is kept verbatim, which is stricter), and a tag cut off by the end
of the input (kept, because inside a fragment the browser reads on into what follows).

Usage: python3 harness/conformance/html_oracle.py [N_FUZZ]   (default 100000; seed fixed)
"""
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from knowledge_md import _tag_end, html_segments  # noqa: E402

from html5lib._tokenizer import HTMLTokenizer  # noqa: E402
from html5lib.constants import tokenTypes as T  # noqa: E402

RCDATA, RAWTEXT = {"textarea", "title"}, {"style", "xmp", "iframe", "noembed", "noframes", "noscript"}


def reference(s: str) -> list:
    tk, out = HTMLTokenizer(s), []
    for tok in tk:
        ty = tok["type"]
        if ty == T["StartTag"]:
            out.append(("start", tok["name"]))
            tk.state = (tk.rcdataState if tok["name"] in RCDATA else tk.rawtextState if tok["name"] in RAWTEXT
                        else tk.plaintextState if tok["name"] == "plaintext" else tk.state)
        elif ty == T["EndTag"]:
            out.append(("end", tok["name"]))
        elif ty in (T["Characters"], T["SpaceCharacters"]):
            out.append(("text", tok["data"]))
        elif ty in (T["Comment"], T["Doctype"]):
            out.append(("hidden",))
    return merge(out)


def ours(s: str) -> list:
    segs = html_segments(s)
    if segs and segs[-1][0] in ("start", "end") and _tag_end(segs[-1][1], 0) < 0:
        segs = segs[:-1]                                   # cut off by the end: html5lib drops it (see above)
    return merge([("text", src) if kind in ("text", "raw") else (kind, name) if kind in ("start", "end")
                  else ("hidden",) for kind, src, name in segs])


def merge(toks: list) -> list:
    out: list = []
    for t in toks:
        if t[0] == "text" and out and out[-1][0] == "text":
            out[-1] = ("text", out[-1][1] + t[1])
        elif t[0] == "hidden":
            continue                                       # what is never displayed only has to disappear
        elif t != ("text", ""):
            out.append(t)
    return out


ATOMS = ["<", ">", "!", "-", "--", "?", "/", "=", '"', "'", " ", "\n", "\t", "a", "b", "x", "p", "div", "span",
         "input", "textarea", "title", "style", "xmp", "plaintext", "value", "<!--", "-->", "--!>", "<?", "<!",
         "</", "[CDATA[", "]]>", "DOCTYPE", "<a ", "<p>", "</p>", "<textarea>", "</textarea>", "<style>",
         "</style", "<title>", "</title>", "<!-->", "<!--->", "=\"", "='", "<b/>", "</>"]

cases = json.loads((pathlib.Path(__file__).parent / "html_cases.json").read_text(encoding="utf-8"))
rng = random.Random(20260927)
n_fuzz = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
fuzz = ["".join(rng.choice(ATOMS) for _ in range(rng.randint(1, 24))) for _ in range(n_fuzz)]
bad = []
for label, s in [(c["id"], c["html"]) for c in cases] + [(f"fuzz#{k}", s) for k, s in enumerate(fuzz)]:
    if ours(s) != reference(s):
        bad.append((label, s))
print(f"{'PASS' if not bad else 'FAIL'} conformance:html-tokens   {len(cases) - sum(not b[0].startswith('fuzz#') for b in bad)}/"
      f"{len(cases)} corpus cases and {n_fuzz - sum(b[0].startswith('fuzz#') for b in bad)}/{n_fuzz} fuzzed fragments "
      f"split exactly like html5lib")
for label, s in bad[:10]:
    print(f"  DIVERGES {label}: {s!r}\n    ref  {reference(s)}\n    ours {ours(s)}")
print("----")
print(f"RESULT: {'PASS' if not bad else 'FAIL'} — {len(bad)} divergence(s)")
sys.exit(0 if not bad else 1)
