#!/usr/bin/env bash
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; W=$(mktemp -d); trap 'rm -rf "$W"' EXIT; n=0; bad=0
# Apply one case's mutation inside the copy. If any command in it fails, the copy's checker is replaced by a
# stub that names the failure, so a case can never pass (or fail as expected) on an unmutated repo.
mutate() { ( set -e; cd "$W/r"; "$1" ); local rc=$?
  [ "$rc" -eq 0 ] || printf 'print("MUTATION DID NOT APPLY: %s (rc=%s)"); raise SystemExit(3)\n' "$1" "$rc" > "$W/r/harness/check-knowledge.py"; }
both() { for p in knowledge.md lessons/2026-08-24.md; do python3 -c "$1" "$p"; done; }
INS='
import sys
p=sys.argv[1]; s=open(p).read().split("\n")
i=next(k for k,l in enumerate(s) if l.startswith("## ") or l.startswith("# Lessons"))
s[i+1:i+1]=[""]+LESSON
open(p,"w").write("\n".join(s))
'
prep() { rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; mutate "$1"; }
run() { local name="$1" expect="$2"; n=$((n+1)); prep "$3"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then echo "PASS $name — FAIL fired: $(printf '%s' "$out" | grep -F -- "$expect" | head -1 | cut -c1-150)"
  else bad=$((bad+1)); echo "FAIL $name — rc=$rc, expected '$expect' in:"; echo "$out" | sed 's/^/    /'; fi; }
# stray_only: the mutation plants visible top-level content inside a day section — since round 25 that is a
# `knowledge:stray` FAIL — so the test asserts that stray fires AND that the WRONG diagnosis stays absent.
stray_only() { local name="$1" absent="$2" present="${4:-}"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; mutate "$3"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "knowledge:stray" && ! printf '%s' "$out" | grep -qF -- "$absent" \
     && { [ -z "$present" ] || printf '%s' "$out" | grep -qF -- "$present"; }; then
    echo "PASS $name — stray fired, no '$absent'${present:+, saw '$present'}"
  else bad=$((bad+1)); echo "FAIL $name — rc=$rc, wanted knowledge:stray without '$absent'${present:+ and with '$present'}:"; echo "$out" | sed 's/^/    /'; fi; }
pos() { local name="$1"; n=$((n+1)); prep "$2"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "PASS $name — still PASS"; else bad=$((bad+1)); echo "FAIL $name — unexpected FAIL:"; echo "$out" | sed 's/^/    /'; fi; }
F='  - Source: [T](https://x.y) — A · confidence 50%'
L3='  - Why it matters here: x","  - Do: y","'"$F"'"'

# 1. `  ## 2026-08-23` nested inside a lesson item is NOT a day section; a lessons/2026-08-23.md is then an orphan -> FAIL
t1() { printf '\n- **Complete**\n  - Why it matters here: x\n  - Do: y\n%s\n\n  ## 2026-08-23\n\n- **Nested day lesson**\n  - Why it matters here: x\n  - Do: y\n%s\n' "$F" "$F" >> knowledge.md
       printf '\n- **Complete**\n  - Why it matters here: x\n  - Do: y\n%s\n' "$F" >> lessons/2026-08-24.md
       printf '# Lessons — 2026-08-23\n\n- **Nested day lesson**\n  - Why it matters here: x\n  - Do: y\n%s\n' "$F" > lessons/2026-08-23.md; }
run "1 nested-date-heading-not-a-section" "lessons:orphans" t1

# 2. `<div>boundary</div>` at top level between Why and Do closes the list -> FAIL
t2() { both 'LESSON=["- **Split by div**","  - Why it matters here: x","<div>boundary</div>","  - Do: y","'"$F"'"]'"$INS"; }
run "2 html-block-splits" "missing do" t2
# 2b. a type-7 tag (`<span>`) directly under the paragraph is lazy continuation -> PASS
t2b() { both 'LESSON=["- **Span ok**","  - Why it matters here: x","<span>note</span>","  - Do: y","'"$F"'"]'"$INS"; }
pos "2b type7-tag-is-lazy-continuation" t2b

# 3. a 10-digit "ordered marker" is a paragraph, not a list item -> PASS
t3() { both 'LESSON=["- **Complete**","'"$L3"',"","1234567890. This is an identifier",""]'"$INS"; }
stray_only "3 ten-digit-number-is-paragraph" "not-a-bold-lesson-bullet" t3
# 3b. a 9-digit one IS a list item (malformed lesson) -> FAIL
t3b() { both 'LESSON=["123456789. still a list item"]'"$INS"; }
run "3b nine-digit-marker-is-list" "not-a-bold-lesson-bullet" t3b

# 4. `**` inside a code span in the title is opaque -> PASS
t4() { both 'LESSON=["- **Use `**` as the delimiter.**","'"$L3"']'"$INS"; }
pos "4 stars-in-title-code-span" t4
# 4b. real inner ** still malformed -> FAIL
t4b() { both 'LESSON=["- **a** b **c**","'"$L3"']'"$INS"; }
run "4b real-inner-strong-still-malformed" "not-a-bold-lesson-bullet" t4b

# 5. hard break (2 trailing spaces) in one copy only -> content differs -> FAIL
t5() { python3 -c 'LESSON=["- **Hard**","  - Why it matters here: x","  - Do: y  ","    more","'"$F"'"]'"$INS" knowledge.md
       python3 -c 'LESSON=["- **Hard**","  - Why it matters here: x","  - Do: y","    more","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
run "5 hard-break-differs" "same title, different content" t5
# 5b. hard break in both copies -> PASS
t5b() { both 'LESSON=["- **Hard both**","  - Why it matters here: x","  - Do: y  ","    more","'"$F"'"]'"$INS"; }
pos "5b hard-break-in-both" t5b
# 5c. trailing spaces on the LAST line of a field are not a break -> copies identical -> PASS
t5c() { python3 -c 'LESSON=["- **Tail**","  - Why it matters here: x","  - Do: y  ","'"$F"'"]'"$INS" knowledge.md
        python3 -c 'LESSON=["- **Tail**","  - Why it matters here: x","  - Do: y","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
pos "5c trailing-spaces-without-continuation" t5c
# 5d. backslash hard break in one copy only -> FAIL
t5d() { python3 -c 'LESSON=["- **Slash**","  - Why it matters here: x","  - Do: y\\","    more","'"$F"'"]'"$INS" knowledge.md
        python3 -c 'LESSON=["- **Slash**","  - Why it matters here: x","  - Do: y","    more","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
run "5d backslash-break-differs" "same title, different content" t5d

echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
