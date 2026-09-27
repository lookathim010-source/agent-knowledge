#!/usr/bin/env bash
# Round-30 negative tests (Codex review of d2be01d, harness v2 on PR #2).
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

# P1 (4117250121): text inside raw HTML can be hidden (hidden, template, CSS) — it never satisfies a required value
t1() { both 'LESSON=["- **Hidden conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A <span hidden>confidence 80%</span>"]'"$INS"; }
run "P1 confidence-inside-raw-html" "source line is not" t1
t1b() { both 'LESSON=["- **Hidden why**","  - Why it matters here: <span hidden>x</span>","  - Do: y",'"$F"']'"$INS"; }
run "P1+ why-only-inside-raw-html" "missing or empty why" t1b
t1c() { both 'LESSON=["- **Template do**","  - Why it matters here: x","  - Do: <template>y</template>",'"$F"']'"$INS"; }
run "P1++ do-only-inside-template" "missing or empty do" t1c
t1d() { both 'LESSON=["- **Block why**","  - Why it matters here:","","    <div hidden>x</div>","","  - Do: y",'"$F"']'"$INS"; }
run "P1+++ why-only-a-raw-html-block" "missing or empty why" t1d
t1e() { both 'LESSON=["- **Kbd do**","  - Why it matters here: x","  - Do: press <kbd>Ctrl</kbd> twice",'"$F"']'"$INS"; }
pos "P1++++ text-beside-raw-html-counts" t1e
t1f() { both 'LESSON=["- **Hidden title**","  - Why it matters here: x","  - Do: y","  - Source: [<span hidden>T</span>](https://x.y) — A · confidence 80%"]'"$INS"; }
run "P1+++++ link-title-only-inside-raw-html" "source line is not" t1f

# P2 (4117250127): invisible markup after or inside the bold title is invisible.
#    A comment BEFORE it cannot be: a list item whose content starts with `<!--` opens an HTML block, so
#    `**Commented title**` is raw text shown with its asterisks (commonmark.js 0.31.2:
#    `<li>\n<!-- note -->**Commented title**`; pinned as `comment-before-title` in cases.json) -> FAIL
t2() { both 'LESSON=["- <!-- note -->**Commented title**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "P2 comment-before-title-is-an-html-block" "not-a-bold-lesson-bullet" t2
t2d() { both 'LESSON=["- **Commented<!-- c --> title**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
pos "P2+++ comment-inside-title" t2d
t2b() { both 'LESSON=["- **Commented title**<!-- c -->","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
pos "P2+ comment-after-title" t2b
t2c() { both 'LESSON=["- <span>**Wrapped title**</span>","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "P2++ raw-html-around-title" "not-a-bold-lesson-bullet" t2c

# P3 (4117250134): only real markup nodes are removed or normalized — never attribute values or raw text
t3() { split 'LESSON=["- **Attr comment**","  - Why it matters here: x","  - Do: <input value=\"<!-- A -->\">",'"$F"']'"$INS" \
             'LESSON=["- **Attr comment**","  - Why it matters here: x","  - Do: <input value=\"<!-- B -->\">",'"$F"']'"$INS"; }
run "P3 comment-like-text-in-attribute-is-content" "same title, different content" t3
t3b() { split 'LESSON=["- **Textarea comment**","  - Why it matters here: x","  - Do: <textarea><!-- A --></textarea> y",'"$F"']'"$INS" \
              'LESSON=["- **Textarea comment**","  - Why it matters here: x","  - Do: <textarea><!-- B --></textarea> y",'"$F"']'"$INS"; }
run "P3+ comment-like-text-in-textarea-is-content" "same title, different content" t3b
t3c() { split 'LESSON=["- **Attr space**","  - Why it matters here: x","  - Do: <input value=\"a  b\"> y",'"$F"']'"$INS" \
              'LESSON=["- **Attr space**","  - Why it matters here: x","  - Do: <input value=\"a b\"> y",'"$F"']'"$INS"; }
run "P3++ attribute-whitespace-is-not-collapsed" "same title, different content" t3c
t3d() { split 'LESSON=["- **Tooltip**","  - Why it matters here: x","  - Do: <abbr title=\"a <p> b\">y</abbr>",'"$F"']'"$INS" \
              'LESSON=["- **Tooltip**","  - Why it matters here: x","  - Do: <abbr title=\"a <p>b\">y</abbr>",'"$F"']'"$INS"; }
run "P3+++ block-tag-text-inside-attribute-is-content" "same title, different content" t3d
t3e() { split 'LESSON=["- **Real comment**","  - Why it matters here: x","  - Do: y <!-- A --> z",'"$F"']'"$INS" \
              'LESSON=["- **Real comment**","  - Why it matters here: x","  - Do: y <!-- B --> z",'"$F"']'"$INS"; }
pos "P3++++ real-comments-stay-invisible" t3e

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
[ $bad -eq 0 ]
