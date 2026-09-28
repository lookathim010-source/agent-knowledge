#!/usr/bin/env bash
# Round-32 negative tests (Codex review of b30cdaf) and the raw-HTML ban (T's decision, 2026-09-27):
# lessons are plain Markdown; any raw HTML other than a <!-- comment --> FAILs the lesson.
# Browser behaviour here is checked by harness/conformance/html_oracle.py (html5lib) and in Chromium 141.
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
# Apply one case's mutation inside the copy. If any command in it fails, the copy's checker is replaced by a
# stub that names the failure, so a case can never pass (or fail as expected) on an unmutated repo.
mutate() { ( set -e; cd "$W/r"; "$1" ); local rc=$?
  [ "$rc" -eq 0 ] || printf 'print("MUTATION DID NOT APPLY: %s (rc=%s)"); raise SystemExit(3)\n' "$1" "$rc" > "$W/r/harness/check-knowledge.py"; }
n=0; bad=0
both() { for p in knowledge.md lessons/2026-08-24.md; do python3 -c "$1" "$p"; done; }
split() { python3 -c "$1" knowledge.md; python3 -c "$2" lessons/2026-08-24.md; }
run() { local name="$1" expect="$2"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; mutate "$3"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then
    echo "PASS $name — FAIL fired: $(printf '%s' "$out" | grep -F -- "$expect" | head -1 | cut -c1-160)"
  else bad=$((bad+1)); echo "FAIL $name — rc=$rc, expected '$expect' in:"; echo "$out" | sed 's/^/    /'; fi; }
pos() { local name="$1"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; mutate "$2"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "PASS $name — still PASS"; else bad=$((bad+1)); echo "FAIL $name — unexpected FAIL:"; echo "$out" | sed 's/^/    /'; fi; }
INS='
import sys
p=sys.argv[1]; s=open(p).read().split("\n")
i=next(k for k,l in enumerate(s) if l.startswith("## ") or l.startswith("# Lessons"))
s[i+1:i+1]=[""]+LESSON
open(p,"w").write("\n".join(s))
'
F='"  - Source: [T](https://x.y) — A · confidence 50%"'

R='raw HTML in a lesson'
# R0: the ban itself — every kind of raw HTML except comments, inline and as a block
t0() { both 'LESSON=["- **Inline tag**","  - Why it matters here: x","  - Do: press <kbd>K</kbd>",'"$F"']'"$INS"; }
run "R0 inline-tag" "$R" t0
t0b() { both 'LESSON=["- **Block tag**","  - Why it matters here: x","  - Do: y","","    <div>z</div>","",'"$F"']'"$INS"; }
run "R0+ html-block" "$R" t0b
t0c() { both 'LESSON=["- **Void tag**","  - Why it matters here: x","  - Do: y<br>z",'"$F"']'"$INS"; }
run "R0++ void-tag" "$R" t0c
t0d() { both 'LESSON=["- **Declaration**","  - Why it matters here: x","  - Do: y <!DOCTYPE html>",'"$F"']'"$INS"; }
run "R0+++ declaration" "$R" t0d
t0e() { both 'LESSON=["- **PI**","  - Why it matters here: x","  - Do: y <?php x ?>",'"$F"']'"$INS"; }
run "R0++++ processing-instruction" "$R" t0e
t0f() { both 'LESSON=["- **CDATA**","  - Why it matters here: x","  - Do: y <![CDATA[ z ]]>",'"$F"']'"$INS"; }
run "R0+++++ cdata" "$R" t0f
t0g() { both 'LESSON=["- **Tag in title <b>B</b>**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "R0++++++ tag-in-title" "$R" t0g
t0h() { both 'LESSON=["- **Comments ok**<!-- a -->","  - Why it matters here: x <!-- b -->","  - Do: y","","    <!-- c -->","",'"$F"']'"$INS"; }
pos "R0+++++++ comments-inline-and-block-are-allowed" t0h
t0i() { both 'LESSON=["- **Code ok**","  - Why it matters here: `<span>` in code is text","  - Do: y","","    ```html","    <div>z</div>","    ```","",'"$F"']'"$INS"; }
pos "R0++++++++ html-inside-code-is-not-raw-html" t0i
t0j() { both 'LESSON=["- **Autolink ok**","  - Why it matters here: see <https://x.y>","  - Do: y",'"$F"']'"$INS"; }
pos "R0+++++++++ autolink-is-not-raw-html" t0j

# R1 (4117489564): a title that is inline code is a valid bold title (regression from b30cdaf)
t1() { both 'LESSON=["- **`Title`**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
pos "R1 code-title" t1
t1b() { both 'LESSON=["- **Use `make` first**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
pos "R1+ title-with-code" t1b

# R2-R6 (4117489575, 4117489572, 4117489569, 4117489581, 4117489588): raw-HTML semantics in lessons — superseded by the ban
t2() { split 'LESSON=["- **Style color**","  - Why it matters here: x","  - Do: <span style=\"color:red\">a  b</span>",'"$F"']'"$INS" \
             'LESSON=["- **Style color**","  - Why it matters here: x","  - Do: <span style=\"color:red\">a b</span>",'"$F"']'"$INS"; }
run "R2 style-attribute" "$R" t2
t3() { both 'LESSON=["- **Pop**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) <span hidden><b>x</span>confidence 80%"]'"$INS"; }
run "R3 intervening-element" "$R" t3
t4() { both 'LESSON=["- **Kbd link**","  - Why it matters here: x","  - Do: y","  - Source: [T<kbd>K</kbd>](https://x.y)confidence 80%"]'"$INS"; }
run "R4 raw-html-at-link-end" "$R" t4
t5() { both 'LESSON=["- **Hidden div**","","  <div hidden>","","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "R5 open-div-before-fields" "$R" t5
t6() { split 'LESSON=["- **Char ref**","  - Why it matters here: x","  - Do: <input value=\"A\">",'"$F"']'"$INS" \
             'LESSON=["- **Char ref**","  - Why it matters here: x","  - Do: <input value=\"&#65;\">",'"$F"']'"$INS"; }
run "R6 character-reference-in-attribute" "$R" t6

# R8 (4117888333): the source link must be inline `[title](https://…)` — a reference-style link does not count
t8() { both 'LESSON=["- **Ref source**","  - Why it matters here: x","  - Do: y","  - Source: [Title][src] — A · confidence 80%","","[src]: https://x.y"]'"$INS"; }
run "R8 full-reference-source-link" "source line is not" t8
t8b() { both 'LESSON=["- **Shortcut source**","  - Why it matters here: x","  - Do: y","  - Source: [src] — A · confidence 80%","","[src]: https://x.y"]'"$INS"; }
run "R8+ shortcut-reference-source-link" "source line is not" t8b
t8c() { both 'LESSON=["- **Ref in why**","  - Why it matters here: see [docs][src]","  - Do: y",'"$F"',"","[src]: https://x.y"]'"$INS"; }
pos "R8++ reference-links-elsewhere-still-fine" t8c

# R7 (4117489584): `</svg/>` is an end tag; the tokenizer leaves foreign content (CDATA is a bogus comment again)
n=$((n+1))
if python3 - "$SRC/harness" <<'PY'
import sys; sys.path.insert(0, sys.argv[1])
from knowledge_md import html_segments
segs = html_segments("<svg></svg/><![CDATA[A]]>z")
assert segs[-2][0] == "hidden" and segs[-1] == ("text", "z", ""), segs
PY
then echo "PASS R7 slash-marked-end-tag-leaves-svg"; else bad=$((bad+1)); echo "FAIL R7 slash-marked-end-tag-leaves-svg"; fi

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
[ $bad -eq 0 ]
