#!/usr/bin/env bash
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; W=$(mktemp -d); n=0; bad=0
both() { for p in knowledge.md lessons/2026-08-24.md; do python3 -c "$1" "$p"; done; }
INS='
import sys
p=sys.argv[1]; s=open(p).read().split("\n")
i=next(k for k,l in enumerate(s) if l.startswith("## ") or l.startswith("# Lessons"))
s[i+1:i+1]=[""]+LESSON
open(p,"w").write("\n".join(s))
'
run() { local name="$1" expect="$2"; n=$((n+1)); rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; ( cd "$W/r" && "$3" )
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then echo "PASS $name — FAIL fired: $(printf '%s' "$out" | grep -F -- "$expect" | head -1 | cut -c1-150)"
  else bad=$((bad+1)); echo "FAIL $name — rc=$rc, expected '$expect' in:"; echo "$out" | sed 's/^/    /'; fi; }
# stray_only: the mutation plants visible top-level content inside a day section — since round 25 that is a
# `knowledge:stray` FAIL — so the test asserts that stray fires AND that the WRONG diagnosis stays absent.
stray_only() { local name="$1" absent="$2" present="${4:-}"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; ( cd "$W/r" && "$3" )
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "knowledge:stray" && ! printf '%s' "$out" | grep -qF -- "$absent" \
     && { [ -z "$present" ] || printf '%s' "$out" | grep -qF -- "$present"; }; then
    echo "PASS $name — stray fired, no '$absent'${present:+, saw '$present'}"
  else bad=$((bad+1)); echo "FAIL $name — rc=$rc, wanted knowledge:stray without '$absent'${present:+ and with '$present'}:"; echo "$out" | sed 's/^/    /'; fi; }
pos() { local name="$1"; n=$((n+1)); rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; ( cd "$W/r" && "$2" )
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "PASS $name — still PASS"; else bad=$((bad+1)); echo "FAIL $name — unexpected FAIL:"; echo "$out" | sed 's/^/    /'; fi; }

# 1. top-level fence between Why and Do closes the list -> FAIL (same in both copies)
t1() { both 'LESSON=["- **Split by fence**","  - Why it matters here: x","","```","code","```","","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
run "1 top-level-fence-splits" "missing do" t1
# 1b. same without blank lines around the fence -> still FAIL (a fence interrupts a paragraph)
t1b() { both 'LESSON=["- **Split by fence tight**","  - Why it matters here: x","```","code","```","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
run "1b tight-fence-splits" "missing do" t1b
# 2. fence nested INSIDE the lesson (2 spaces) between fields -> PASS (item continues)
t2() { both 'LESSON=["- **Fence inside item**","  - Why it matters here: x","  ```","  code","  ```","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "2 fence-inside-item-keeps-lesson" t2
# 3. fence nested under a field (4 spaces) then fields -> PASS
t3() { both 'LESSON=["- **Fence under field**","  - Why it matters here: x","    ```","    code","    ```","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "3 fence-under-field-keeps-lesson" t3
# 4. top-level fence AFTER a complete lesson, then another lesson -> PASS
t4() { both 'LESSON=["- **Complete**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%","","```","code","```","","- **Second**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
stray_only "4 fence-between-lessons" "missing" t4 "7 lesson(s)"
# 5. a fenced block under Why is VISIBLE to readers (rewritten 2026-09-27, round 23): a copy without it
#    differs, and the raw sentinel must never surface in a diagnostic. Same block in both copies -> PASS.
t5() { python3 -c 'LESSON=["- **Leak check**","  - Why it matters here: x","    ```","    secret","    ```","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS" knowledge.md
       python3 -c 'LESSON=["- **Leak check**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS" lessons/2026-08-24.md; }
run "5 fence-in-one-copy-differs" "same title, different content" t5
t5b() { for p in knowledge.md lessons/2026-08-24.md; do python3 -c 'LESSON=["- **Leak check**","  - Why it matters here: x","    ```","    secret","    ```","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS" "$p"; done; }
pos "5b fence-in-both-copies-identical" t5b
n=$((n+1)); rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; ( cd "$W/r" && t5 )
if (cd "$W/r" && python3 harness/check-knowledge.py 2>&1) | grep -qaP '\x00'; then bad=$((bad+1)); echo "FAIL 5c raw sentinel leaked into a diagnostic"; else echo "PASS 5c no raw sentinel in diagnostics"; fi
echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
