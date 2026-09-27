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

# 1. top-level HTML comment block between fields closes the list -> FAIL
t1() { both 'LESSON=["- **Split by comment**","  - Why it matters here: x","<!-- note -->","  - Do: y","'"$F"'"]'"$INS"; }
run "1 comment-block-splits" "missing do" t1
# 1b. multi-line top-level comment -> FAIL
t1b() { both 'LESSON=["- **Split by long comment**","  - Why it matters here: x","<!-- note","more -->","  - Do: y","'"$F"'"]'"$INS"; }
run "1b multiline-comment-splits" "missing do" t1b
# 1c. INLINE comment inside the Why text does not split -> PASS
t1c() { both 'LESSON=["- **Inline comment**","  - Why it matters here: x <!-- c --> y","  - Do: y","'"$F"'"]'"$INS"; }
pos "1c inline-comment-keeps-lesson" t1c
# 1d. comment block nested inside the item (2 spaces) -> PASS
t1d() { both 'LESSON=["- **Nested comment**","  - Why it matters here: x","  <!-- c -->","  - Do: y","'"$F"'"]'"$INS"; }
pos "1d nested-comment-keeps-lesson" t1d

# 2. `- - -` thematic break in a section is NOT a malformed lesson -> PASS
t2() { both 'LESSON=["- **Complete**","  - Why it matters here: x","  - Do: y","'"$F"'","","- - -",""]'"$INS"; }
stray_only "2 dash-space-hr-not-a-bullet" "not-a-bold-lesson-bullet" t2
# 2b. `* * *` before the first section is NOT misplaced -> PASS
t2b() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n'); s.insert(1,'* * *'); open(p,'w').write('\n'.join(s))
PY
}
run "2b hr-before-first-section-is-misplaced-not-malformed" "knowledge:misplaced" t2b   # a visible rule outside any day section (round 21); never a malformed lesson (round 14)
n=$((n+1)); prep t2b; if (cd "$W/r" && python3 harness/check-knowledge.py 2>&1) | grep -q "not-a-bold-lesson-bullet"; then bad=$((bad+1)); echo "FAIL 2b+ hr reported as malformed lesson"; else echo "PASS 2b+ hr not reported as a malformed lesson"; fi
# 2c. but `- - -` between Why and Do still splits the lesson -> FAIL
t2c() { both 'LESSON=["- **Split by dash hr**","  - Why it matters here: x","- - -","  - Do: y","'"$F"'"]'"$INS"; }
run "2c dash-space-hr-splits" "missing do" t2c

# 3. verified sheet: a fenced code block before the H1 RENDERS (<pre>), so the H1 is not the first visible
#    content -> FAIL. Rewritten 2026-09-27 (round 24): the old PASS expectation treated code as invisible.
t3() { printf '```\ncode\n```\n\n# Real heading\n' > verified/2026-01-04_fence_v1.md; }
run "3 verified-fence-then-h1" "verified:h1" t3
# 3b. verified sheet: fence then NO H1 -> FAIL
t3b() { printf '```\ncode\n```\n\nNot a heading\n' > verified/2026-01-05_nofence_v1.md; }
run "3b verified-fence-then-no-h1" "verified:h1" t3b

# 4. `- **First** plain **second**` is two strong spans -> malformed
t4() { both 'LESSON=["- **First** plain **second**","  - Why it matters here: x","  - Do: y","'"$F"'"]'"$INS"; }
run "4 two-strong-spans" "not-a-bold-lesson-bullet" t4
# 4b. escaped \*\* inside a title is fine -> PASS
t4b() { both 'LESSON=["- **Use \\*\\*bold\\*\\* sparingly**","  - Why it matters here: x","  - Do: y","'"$F"'"]'"$INS"; }
pos "4b escaped-stars-in-title" t4b

# 5. `-\t**T**` has content column 4: 2-space fields are siblings -> FAIL
t5() { both 'LESSON=["-\t**Tab lesson**","  - Why it matters here: x","  - Do: y","'"$F"'"]'"$INS"; }
run "5 tab-marker-2-space-fields" "missing why" t5
# 5b. same lesson with 4-space fields -> PASS
t5b() { both 'LESSON=["-\t**Tab lesson**","    - Why it matters here: x","    - Do: y","    - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "5b tab-marker-4-space-fields" t5b
# 5c. `-    **T**` (4 spaces after marker, content col 5): 2-space fields are siblings -> FAIL
t5c() { both 'LESSON=["-    **Wide gap**","  - Why it matters here: x","  - Do: y","'"$F"'"]'"$INS"; }
run "5c wide-gap-2-space-fields" "missing why" t5c
# 5d. `-     **T**` (5 spaces after marker) is code inside the item, not a bold title -> malformed
t5d() { both 'LESSON=["-     **Five spaces**","  - Why it matters here: x","  - Do: y","'"$F"'"]'"$INS"; }
run "5d five-space-gap-is-code" "not-a-bold-lesson-bullet" t5d
# 2d. `- * -` mixes characters: NOT a thematic break, so it is a malformed bullet -> FAIL
t2d() { both 'LESSON=["- * -"]'"$INS"; }
run "2d mixed-chars-not-hr" "not-a-bold-lesson-bullet" t2d

# 6. lessons/ as a symlink to a real dir -> FAIL; same for verified/
t6() { mv lessons real-lessons && ln -s real-lessons lessons; }
run "6 lessons-dir-symlink" "lessons/" t6
t6b() { mv verified real-verified && ln -s real-verified verified; }
run "6b verified-dir-symlink" "verified/" t6b

echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
