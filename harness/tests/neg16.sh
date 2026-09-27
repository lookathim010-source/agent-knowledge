#!/usr/bin/env bash
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; W=$(mktemp -d); n=0; bad=0
split() { python3 -c "$1" knowledge.md; python3 -c "$2" lessons/2026-08-24.md; }   # different copies (round-22 rewrite)
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
W1='  - Why it matters here: x'

# 1. knowledge.md as a symlink -> FAIL
t1() { mv knowledge.md real.md && ln -s real.md knowledge.md; }
run "1 knowledge-symlink" "knowledge.md" t1

# 2. whitespace inside inline code differs -> FAIL
t2() { python3 -c 'LESSON=["- **Code ws**","'"$W1"'","  - Do: run `printf '"'"'a b'"'"'`","'"$F"'"]'"$INS" knowledge.md
       python3 -c 'LESSON=["- **Code ws**","'"$W1"'","  - Do: run `printf '"'"'a  b'"'"'`","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
run "2 code-span-whitespace-differs" "same title, different content" t2
# 2b. whitespace in PROSE still normalized -> PASS
t2b() { python3 -c 'LESSON=["- **Prose ws**","'"$W1"'","  - Do: run  it   now","'"$F"'"]'"$INS" knowledge.md
        python3 -c 'LESSON=["- **Prose ws**","'"$W1"'","  - Do: run it now","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
pos "2b prose-whitespace-still-normalized" t2b

# 3. unbalanced paren in the link destination -> not a link -> FAIL
t3() { both 'LESSON=["- **Bad link**","'"$W1"'","  - Do: y","  - Source: [T](https://x.y/(broken) — A · confidence 50%"]'"$INS"; }
run "3 unbalanced-dest-paren" "source line is not" t3
# 3b. balanced parens in the destination -> PASS
t3b() { both 'LESSON=["- **Ok link**","'"$W1"'","  - Do: y","  - Source: [T](https://x.y/(ok)) — A · confidence 50%"]'"$INS"; }
pos "3b balanced-dest-paren" t3b

# 4. `- Do:` with its value on the continuation line -> PASS
t4() { both 'LESSON=["- **Deferred**","'"$W1"'","  - Do:","    y","'"$F"'"]'"$INS"; }
pos "4 value-on-continuation-line" t4
# 4b. `- Do:` with nothing after -> still FAIL
t4b() { both 'LESSON=["- **Empty do**","'"$W1"'","  - Do:","'"$F"'"]'"$INS"; }
run "4b empty-do-still-fails" "missing or empty do" t4b
# 4c. `- Source:` with the link on the continuation line -> PASS
t4c() { both 'LESSON=["- **Deferred source**","'"$W1"'","  - Do: y","  - Source:","    [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "4c source-on-continuation-line" t4c

# 5. verified sheet with a tab after `#` -> PASS
t5() { printf '#\tTab heading\n\nbody\n' > verified/2026-01-06_tab_v1.md; }
pos "5 tab-after-hash-is-h1" t5

# 6. code span crossing a line boundary with `<!--` on the second line, in both copies -> PASS
t6() { both 'LESSON=["- **Cross-line code**","  - Why it matters here: see `git log","    --oneline <!-- not a comment` here","  - Do: y","'"$F"'"]'"$INS"; }
pos "6 code-span-across-lines" t6
# 6b. but `<!--` at the START of the next line is an HTML block (blocks parse before inlines) -> comment opens -> FAIL
t6b() { both 'LESSON=["- **Block wins**","  - Why it matters here: see `git log","    <!-- a real comment block` here","  - Do: y","'"$F"'"]'"$INS"; }
run "6b html-block-start-beats-open-span" "never closes" t6b
# 6c. the span closes on line 2 and a real `<!--` follows AFTER the closer -> comment opens -> FAIL
t6c() { split 'LESSON=["- **After closer**","  - Why it matters here: see `git log","    --oneline` <!-- hidden","    still hidden --> visible","  - Do: y","'"$F"'"]'"$INS" \
              'LESSON=["- **After closer**","  - Why it matters here: see `git log","    --oneline` visible","  - Do: y","'"$F"'"]'"$INS"; }
pos "6c comment-after-closer" t6c   # a real comment after the closer is stripped → the copies match; a harness that kept the span open would see `<!--` as code and FAIL

echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
