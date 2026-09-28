#!/usr/bin/env bash
# Round-31 negative tests (Codex reviews of 9eda147, 2fb93c2 and 9afc610, harness v2 on PR #2).
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

# Q2 (4117305791): a quoted `</script>` in the start tag does not close the element; the browser swallows what follows
t2() { both 'LESSON=["- **Script attr**","  - Why it matters here: x","  - Do: y","","    <script data-end=\"</script>\">","",'"$F"']'"$INS"; }
run "Q2 quoted-end-marker-leaves-script-open" "HTML block never closes" t2
t2b() { both 'LESSON=["- **Script ok**","  - Why it matters here: x","  - Do: y","","    <script>x</script>","",'"$F"']'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the browser behaviour it pinned no longer decides the verdict.
run "Q2+ closed-script-block -> raw-html-now-fails" "raw HTML in a lesson" t2b

# Q3 (4117305795): the confidence label must stand alone after the link text too
t3() { both 'LESSON=["- **Glued conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y)confidence 80%"]'"$INS"; }
run "Q3 label-glued-to-link-text" "source line is not" t3
t3b() { both 'LESSON=["- **Spaced conf**","  - Why it matters here: x","  - Do: y","  - Source: [T.](https://x.y)confidence 80%"]'"$INS"; }
pos "Q3+ punctuation-before-label" t3b

# Q4 (4117383769): an unrelated end tag does not close the hidden element (Chromium: `</bogus>` ignored)
t4() { both 'LESSON=["- **Bogus end**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) <span hidden>x</bogus>confidence 80%</span>"]'"$INS"; }
run "Q4 unmatched-end-tag-keeps-hidden-region" "source line is not" t4
t4b() { both 'LESSON=["- **Closed span**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) <kbd>K</kbd> · confidence 80%"]'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the browser behaviour it pinned no longer decides the verdict.
run "Q4+ label-after-a-closed-element -> raw-html-now-fails" "raw HTML in a lesson" t4b

# Q5 (4117383771): the title is what a reader sees in the bold span
t5() { both 'LESSON=["- **<span hidden>Invisible</span>**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "Q5 hidden-title" "not-a-bold-lesson-bullet" t5
t5b() { both 'LESSON=["- **Press <kbd>K</kbd>**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the browser behaviour it pinned no longer decides the verdict.
run "Q5+ title-with-visible-text-beside-raw-html -> raw-html-now-fails" "raw HTML in a lesson" t5b

# Q6 (4117383777): whitespace collapses across inline element boundaries, as in a browser
t6() { split 'LESSON=["- **Inline space**","  - Why it matters here: x","  - Do: x <span> y</span>",'"$F"']'"$INS" \
             'LESSON=["- **Inline space**","  - Why it matters here: x","  - Do: x<span> y</span>",'"$F"']'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the browser behaviour it pinned no longer decides the verdict.
run "Q6 space-across-raw-inline-boundary -> raw-html-now-fails" "raw HTML in a lesson" t6
t6b() { split 'LESSON=["- **Link space**","  - Why it matters here: x","  - Do: x [ y](https://x.y)",'"$F"']'"$INS" \
              'LESSON=["- **Link space**","  - Why it matters here: x","  - Do: x[ y](https://x.y)",'"$F"']'"$INS"; }
pos "Q6+ space-across-link-boundary" t6b
t6c() { split 'LESSON=["- **Real space**","  - Why it matters here: x","  - Do: x [y](https://x.y)",'"$F"']'"$INS" \
              'LESSON=["- **Real space**","  - Why it matters here: x","  - Do: x[y](https://x.y)",'"$F"']'"$INS"; }
run "Q6++ a-missing-space-still-differs" "same title, different content" t6c

# Q7 (4117383781): a later block only counts when it renders visible content
t7() { both 'LESSON=["- **Empty heading**","  - Why it matters here: x","  - Do:","","    ###","",'"$F"']'"$INS"; }
run "Q7 empty-heading-is-no-value" "missing or empty do" t7
t7b() { both 'LESSON=["- **Rule only**","  - Why it matters here: x","  - Do:","","    ***","",'"$F"']'"$INS"; }
run "Q7+ thematic-break-is-no-value" "missing or empty do" t7b
t7c() { both 'LESSON=["- **Hidden para**","  - Why it matters here: x","  - Do:","","    <span hidden>y</span> <!-- c -->","",'"$F"']'"$INS"; }
run "Q7++ raw-html-only-paragraph-is-no-value" "missing or empty do" t7c
t7d() { both 'LESSON=["- **Code value**","  - Why it matters here: x","  - Do:","","    ```","    make","    ```","",'"$F"']'"$INS"; }
pos "Q7+++ code-block-is-a-value" t7d

# Q8 (4117383783): after </svg>, CDATA is an HTML bogus comment again (invisible)
t8() { split 'LESSON=["- **After svg**","  - Why it matters here: x","  - Do: y <svg></svg><![CDATA[A]]>",'"$F"']'"$INS" \
             'LESSON=["- **After svg**","  - Why it matters here: x","  - Do: y <svg></svg><![CDATA[B]]>",'"$F"']'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the browser behaviour it pinned no longer decides the verdict.
run "Q8 cdata-after-closed-svg-is-hidden -> raw-html-now-fails" "raw HTML in a lesson" t8
t8b() { split 'LESSON=["- **In svg**","  - Why it matters here: x","  - Do: y <svg><![CDATA[A]]></svg>",'"$F"']'"$INS" \
              'LESSON=["- **In svg**","  - Why it matters here: x","  - Do: y <svg><![CDATA[B]]></svg>",'"$F"']'"$INS"; }
run "Q8+ cdata-inside-svg-is-compared" "same title, different content" t8b

# Q9 (4117383785): a `>` inside a quoted DOCTYPE identifier ENDS the DOCTYPE (WHATWG abrupt-doctype-public-identifier;
#    html5lib and Chromium 141 both show `confidence 80%">`), so the label is visible and the source is valid
t9() { both 'LESSON=["- **Doctype conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) <!DOCTYPE html PUBLIC \"x>confidence 80%\">"]'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the browser behaviour it pinned no longer decides the verdict.
run "Q9 gt-in-quoted-doctype-identifier-ends-it -> raw-html-now-fails" "raw HTML in a lesson" t9

# Q10 (4117425621): preserved whitespace is scoped to the element that asks for it; a <style> element keeps it lesson-wide
t10() { split 'LESSON=["- **Scoped**","  - Why it matters here: x","  - Do: a  b <textarea>x</textarea>",'"$F"']'"$INS" \
              'LESSON=["- **Scoped**","  - Why it matters here: x","  - Do: a b <textarea>x</textarea>",'"$F"']'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the browser behaviour it pinned no longer decides the verdict.
run "Q10 whitespace-outside-textarea-collapses -> raw-html-now-fails" "raw HTML in a lesson" t10
t10b() { split 'LESSON=["- **Styled scope**","  - Why it matters here: x","  - Do: a  b <span style=\"white-space:pre\">c</span>",'"$F"']'"$INS" \
               'LESSON=["- **Styled scope**","  - Why it matters here: x","  - Do: a b <span style=\"white-space:pre\">c</span>",'"$F"']'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the browser behaviour it pinned no longer decides the verdict.
run "Q10+ whitespace-outside-styled-element-collapses -> raw-html-now-fails" "raw HTML in a lesson" t10b
t10c() { split 'LESSON=["- **Sheet**","  - Why it matters here: x","  - Do: a  b <style>li{white-space:pre}</style>",'"$F"']'"$INS" \
               'LESSON=["- **Sheet**","  - Why it matters here: x","  - Do: a b <style>li{white-space:pre}</style>",'"$F"']'"$INS"; }
run "Q10++ a-style-element-keeps-whitespace-everywhere" "same title, different content" t10c

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
[ $bad -eq 0 ]
