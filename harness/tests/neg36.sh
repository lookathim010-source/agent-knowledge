#!/usr/bin/env bash
# Round-36 negative tests (Codex review of caeed36).
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

# V1 (4118216332): a comment block at the start of a field item is invisible; the field paragraph after it counts
t1() { both 'LESSON=["- **Field comment**","  - <!-- note -->","    Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
pos "V1 comment-block-before-field-paragraph" t1
t1b() { both 'LESSON=["- **Field comment empty**","  - <!-- note -->","    Why it matters here:","  - Do: y",'"$F"']'"$INS"; }
run "V1+ comment-block-then-empty-field" "missing or empty why" t1b

# V2 (4118216337): raw HTML nested in an image description is still raw HTML in a lesson
t2() { both 'LESSON=["- **Image html**","  - Why it matters here: x","  - Do: ![<b>x</b>](https://x.y/i.png) y",'"$F"']'"$INS"; }
run "V2 raw-html-inside-image-description" "raw HTML in a lesson" t2
t2b() { both 'LESSON=["- **Image comment**","  - Why it matters here: x","  - Do: ![a <!-- c --> b](https://x.y/i.png) y",'"$F"']'"$INS"; }
pos "V2+ comment-inside-image-description" t2b

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
[ $bad -eq 0 ]
