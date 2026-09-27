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
prep() { rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; ( cd "$W/r" && "$1" ); }
run() { local name="$1" expect="$2"; n=$((n+1)); prep "$3"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then echo "PASS $name — FAIL fired: $(printf '%s' "$out" | grep -F -- "$expect" | head -1 | cut -c1-150)"
  else bad=$((bad+1)); echo "FAIL $name — rc=$rc, expected '$expect' in:"; echo "$out" | sed 's/^/    /'; fi; }
pos() { local name="$1"; n=$((n+1)); prep "$2"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "PASS $name — still PASS"; else bad=$((bad+1)); echo "FAIL $name — unexpected FAIL:"; echo "$out" | sed 's/^/    /'; fi; }
F='  - Source: [T](https://x.y) — A · confidence 50%'
L3='  - Why it matters here: x","  - Do: y","'"$F"'"'

# 1. closing ** preceded by whitespace cannot close -> not bold -> malformed
t1() { both 'LESSON=["- **Not actually strong **","'"$L3"']'"$INS"; }
run "1 trailing-space-before-closer" "not-a-bold-lesson-bullet" t1
# 1b. opening ** followed by whitespace cannot open -> malformed
t1b() { both 'LESSON=["- ** Not strong**","'"$L3"']'"$INS"; }
run "1b space-after-opener" "not-a-bold-lesson-bullet" t1b

# 2. verified sheet saved with a UTF-8 BOM -> H1 still recognised -> PASS
t2() { printf '\xef\xbb\xbf# BOM heading\n\nbody\n' > verified/2026-01-07_bom_v1.md; }
pos "2 bom-before-h1" t2

# 3. two spaces before a stripped inline comment are NOT a hard break -> copies identical -> PASS
t3() { python3 -c 'LESSON=["- **Comment spaces**","  - Why it matters here: text  <!-- note -->","    more","  - Do: y","'"$F"'"]'"$INS" knowledge.md
       python3 -c 'LESSON=["- **Comment spaces**","  - Why it matters here: text","    more","  - Do: y","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
pos "3 spaces-before-comment-not-a-break" t3
# 3b. two spaces AFTER the comment are a real hard break -> copies differ -> FAIL
t3b() { python3 -c 'LESSON=["- **Real break**","  - Why it matters here: text <!-- note -->  ","    more","  - Do: y","'"$F"'"]'"$INS" knowledge.md
        python3 -c 'LESSON=["- **Real break**","  - Why it matters here: text","    more","  - Do: y","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
run "3b spaces-after-comment-are-a-break" "same title, different content" t3b

# 4. backslash-escaped paren in the destination is text -> PASS
t4() { both 'LESSON=["- **Escaped paren**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y/\\() — A · confidence 80%"]'"$INS"; }
pos "4 escaped-paren-in-destination" t4

echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
