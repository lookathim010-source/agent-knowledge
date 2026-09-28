#!/usr/bin/env bash
# Round-26 negative tests (Codex review of 03bb96e).
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

# J1 (4116180182): a code span that opens on one field line and closes on the next keeps its inner spaces
t1() { split 'LESSON=["- **Span lines**","  - Why it matters here: `a  x","    b` tail","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Span lines**","  - Why it matters here: `a   x","    b` tail","  - Do: y",'"$F"']'"$INS"; }
run "J1 cross-line-code-span-spaces-differ" "same title, different content" t1
t1b() { both 'LESSON=["- **Span lines**","  - Why it matters here: `a  x","    b` tail","  - Do: y",'"$F"']'"$INS"; }
pos "J1+ cross-line-code-span-same" t1b
# J1++ prose (outside any span) still collapses: two vs three spaces in plain text compare equal
t1c() { split 'LESSON=["- **Prose spaces**","  - Why it matters here: a  x","  - Do: y",'"$F"']'"$INS" \
              'LESSON=["- **Prose spaces**","  - Why it matters here: a   x","  - Do: y",'"$F"']'"$INS"; }
pos "J1++ prose-spaces-still-collapse" t1c

# J2 (4116180191): the opener's 0-3 spaces of indentation are not payload
t2() { split 'LESSON=["- **Html indent**","  - Why it matters here: x","","    <div>same</div>","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Html indent**","  - Why it matters here: x","","      <div>same</div>","  - Do: y",'"$F"']'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the parse this case pinned no longer decides the verdict.
run "J2 html-opener-indent-ignored -> raw-html-now-fails" "raw HTML in a lesson" t2
t2b() { split 'LESSON=["- **Html indent**","  - Why it matters here: x","","    <div>same</div>","  - Do: y",'"$F"']'"$INS" \
              'LESSON=["- **Html indent**","  - Why it matters here: x","","    <div>other</div>","  - Do: y",'"$F"']'"$INS"; }
run "J2+ html-content-still-compared" "same title, different content" t2b

# J3 (4116180187): a two-line reference definition inside a day section renders nothing
t3() { both 'LESSON=["- **Ref def**","  - Why it matters here: x","  - Do: y",'"$F"',"","[docs]: https://example.com","  \"the title\""]'"$INS"; }
pos "J3 two-line-ref-def-in-section" t3
t3b() { both 'LESSON=["- **Ref def**","  - Why it matters here: x","  - Do: y",'"$F"',"","[docs]: https://example.com \"t\"","  \"visible second\""]'"$INS"; }
run "J3+ second-title-is-stray" "knowledge:stray" t3b

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
rm -rf "$W"
[ $bad -eq 0 ]
