#!/usr/bin/env bash
# Round-12 negative tests. Each mutation is applied to BOTH copies (knowledge.md and the day file)
# so the copy-comparison cannot be what catches it; the structural check must.
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W=$(mktemp -d)
n=0; bad=0
both() { # python snippet that mutates one file given as sys.argv[1]
  for p in knowledge.md lessons/2026-08-24.md; do python3 -c "$1" "$p"; done
}
run() { # name expected mutation-fn
  local name="$1" expect="$2"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"
  ( cd "$W/r" && "$3" )
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then
    echo "PASS $name — FAIL fired: $(printf '%s' "$out" | grep -F -- "$expect" | head -1 | cut -c1-160)"
  else
    bad=$((bad+1)); echo "FAIL $name — rc=$rc, expected '$expect' in:"; echo "$out" | sed 's/^/    /'
  fi
}
pos() { # name mutation-fn : must stay PASS
  local name="$1"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"
  ( cd "$W/r" && "$2" )
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "PASS $name — still PASS"; else bad=$((bad+1)); echo "FAIL $name — unexpected FAIL:"; echo "$out" | sed 's/^/    /'; fi
}

# helper: insert a lesson right after the first heading line (## date / # Lessons)
INS='
import sys
p=sys.argv[1]; s=open(p).read().split("\n")
i=next(k for k,l in enumerate(s) if l.startswith("## ") or l.startswith("# Lessons"))
s[i+1:i+1]=[""]+LESSON
open(p,"w").write("\n".join(s))
'

# 1. fence nested under a field at 4 absolute spaces hides Do/Source -> must FAIL missing do/source
t1() { both 'LESSON=["- **Nested fence lesson**","  - Why it matters here: x","    ```","    - Do: hidden in code","    - Source: [T](https://x.y) — A · confidence 50%","    ```"]'"$INS"; }
run "1 nested-fence-hides-fields" "missing do" t1

# 1b. same, but fence nested at the lesson level (2 spaces) — already ≤3, must FAIL too (regression guard)
t1b() { both 'LESSON=["- **Two-space fence lesson**","  ```","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%","  ```"]'"$INS"; }
run "1b two-space-fence" "missing why" t1b

# 1c. fence nested at 4 spaces that closes, followed by real fields -> must PASS
t1c() { both 'LESSON=["- **Nested fence then fields**","  - Why it matters here: x","    ```","    code sample","    ```","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "1c nested-fence-then-fields" t1c

# 2a. thematic break between fields closes the lesson -> later fields are stray bullets -> FAIL
t2a() { both 'LESSON=["- **Split by hr**","  - Why it matters here: x","","---","","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
run "2a thematic-break-splits" "missing do" t2a

# 2b. non-lazy paragraph after a blank line closes the lesson -> FAIL
t2b() { both 'LESSON=["- **Split by paragraph**","  - Why it matters here: x","","A top-level paragraph.","","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
run "2b paragraph-splits" "missing do" t2b

# 2c. H3 heading between fields closes the lesson -> FAIL
t2c() { both 'LESSON=["- **Split by h3**","  - Why it matters here: x","### Sub","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
run "2c heading-splits" "missing do" t2c

# 2d. lazy continuation (no blank line) must still NOT split -> PASS
t2d() { both 'LESSON=["- **Lazy ok**","  - Why it matters here: x","lazy tail","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "2d lazy-continuation-keeps-lesson" t2d

# 2e. blank line between fields (no block) must still NOT split -> PASS
t2e() { both 'LESSON=["- **Blank ok**","  - Why it matters here: x","","  - Do: y","","  - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "2e blank-lines-keep-lesson" t2e

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
rm -rf "$W"
[ $bad -eq 0 ]
