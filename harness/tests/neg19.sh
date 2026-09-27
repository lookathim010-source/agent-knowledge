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

# 1. CORRECTED 2026-09-27 (harness v2): CommonMark 0.31.2 starts a declaration block at `<!` + ANY ASCII letter,
#    so `<!foo>` is an invisible declaration and the H1 IS the first visible block (commonmark.js 0.31.2: raw
#    `<!foo>` then <h1>) -> PASS. Note: GitHub renders with cmark-gfm (spec 0.29), where `<!foo>` is visible text;
#    this harness targets 0.31.2 (see harness/conformance/check.py).
t1() { printf '<!foo>\n# Heading\n\nbody\n' > verified/2026-01-08_decl_v1.md; }
pos "1 lowercase-decl-is-a-declaration" t1
# 1b. `<!DOCTYPE html>` IS a declaration block -> skipped -> PASS
t1b() { printf '<!DOCTYPE html>\n\n# Heading\n\nbody\n' > verified/2026-01-09_doctype_v1.md; }
pos "1b uppercase-decl-is-a-block" t1b

# 2. `<PRE>` … `</PRE>` closes case-insensitively -> nothing hidden -> PASS
t2() { both 'LESSON=["<PRE>","raw","</PRE>","","- **After PRE**","'"$L3"']'"$INS"; }
stray_only "2 uppercase-terminator" "FAIL knowledge:sections" t2 "6 lesson(s)"

# 3. `- **foo***` leaves a star outside the strong span -> malformed
t3() { both 'LESSON=["- **foo***","'"$L3"']'"$INS"; }
run "3 surplus-closing-star" "not-a-bold-lesson-bullet" t3
# 3b. `- ***foo**` likewise -> malformed
t3b() { both 'LESSON=["- ***foo**","'"$L3"']'"$INS"; }
run "3b surplus-opening-star" "not-a-bold-lesson-bullet" t3b
# 3c. an escaped star at the end of the title is fine -> PASS
t3c() { both 'LESSON=["- **foo\\***","'"$L3"']'"$INS"; }
pos "3c escaped-star-at-end" t3c

# 4. balanced brackets inside the link label -> valid -> PASS
t4() { both 'LESSON=["- **Nested label**","  - Why it matters here: x","  - Do: y","  - Source: [RFC [draft]](https://x.y) — A · confidence 80%"]'"$INS"; }
pos "4 balanced-brackets-in-label" t4

# 5. a lazy continuation at column 0 must not drop the list containers: a fence at 4 spaces after it is still a fence -> fields hidden -> FAIL
t5() { both 'LESSON=["- **Lazy then fence**","  - Why it matters here: x","lazy","    ```","    - Do: hidden","    - Source: [T](https://x.y) — A · confidence 50%","    ```"]'"$INS"; }
run "5 containers-survive-lazy-continuation" "missing do" t5

# 6. a type-7 tag right after the H1 (no blank line) starts an HTML block that swallows the sections -> FAIL
t6() { python3 - <<'PY'
for p in ('knowledge.md','lessons/2026-08-24.md'):
    s=open(p).read().split('\n'); assert s[1]=='' ; s[1]='<x>'; open(p,'w').write('\n'.join(s))
PY
}
run "6 type7-after-heading-starts-block" "knowledge:sections" t6

# 7. `##` + NBSP is a paragraph, not a heading -> PASS
t7() { both 'LESSON=["- **Complete**","'"$L3"',"","## note",""]'"$INS"; }
stray_only "7 nbsp-after-hashes-not-a-heading" "FAIL knowledge:headings" t7

# 8. text after a multi-line inline comment's `-->` stays in the paragraph: `--> - Do: y` is not a field -> FAIL
t8() { both 'LESSON=["- **Suffix**","  - Why it matters here: text <!--","-->   - Do: y","'"$F"'"]'"$INS"; }
run "8 comment-suffix-stays-in-paragraph" "missing do" t8

# 9. a link reference definition before the verified H1 renders nothing -> PASS
t9() { printf '[docs]: https://example.com\n\n# Heading\n\nbody\n' > verified/2026-01-10_refdef_v1.md; }
pos "9 link-ref-def-before-h1" t9

# 10. CORRECTED 2026-09-27 (harness v2): `2. more` at column 0 after a lesson is NOT lazy continuation. The
#     no-interrupt rule for `2.` applies only when a paragraph is the line's direct container; here the line
#     leaves every list item first, so it opens a new top-level list (commonmark.js 0.31.2: `<ol start="2">`
#     after the `</ul>`). The round-19 expectation (PASS) was wrong -> a malformed top-level item -> FAIL
t10() { both 'LESSON=["- **Two dot**","'"$L3"',"2. additional source context"]'"$INS"; }
run "10 ordered-marker-at-column-0-opens-a-list" "not-a-bold-lesson-bullet" t10
# 10c. the intent that survives: `2. more` INSIDE the Source item (its content column) cannot interrupt that
#      paragraph -> lazy continuation of Source (reference: "…confidence 50%\n2. more" in one <li>) -> PASS
t10c() { both 'LESSON=["- **Two dot inside**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confidence 50%","    2. additional source context"]'"$INS"; }
pos "10c ordered-marker-inside-field-is-lazy" t10c
# 10b. `1. more` in the same spot DOES start a list -> malformed bullet -> FAIL
t10b() { both 'LESSON=["- **One dot**","'"$L3"',"1. starts a list"]'"$INS"; }
run "10b ordered-marker-one-interrupts" "not-a-bold-lesson-bullet" t10b

echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
