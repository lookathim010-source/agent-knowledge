#!/usr/bin/env bash
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; W=$(mktemp -d); trap 'rm -rf "$W"' EXIT; n=0; bad=0
# Apply one case's mutation inside the copy. If any command in it fails, the copy's checker is replaced by a
# stub that names the failure, so a case can never pass (or fail as expected) on an unmutated repo.
mutate() { ( set -e; cd "$W/r"; "$1" ); local rc=$?
  [ "$rc" -eq 0 ] || printf 'print("MUTATION DID NOT APPLY: %s (rc=%s)"); raise SystemExit(3)\n' "$1" "$rc" > "$W/r/harness/check-knowledge.py"; }
split() { python3 -c "$1" knowledge.md; python3 -c "$2" lessons/2026-08-24.md; }   # different copies (round-22 rewrite)
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

# 1. escaped closing asterisk: `\**` is `\*` + `*`, no strong closer -> malformed
t1() { both 'LESSON=["- **Broken closing escape\\**","'"$L3"']'"$INS"; }
run "1 escaped-closing-star" "not-a-bold-lesson-bullet" t1
# 1b. escaped backslash before the closer is fine -> PASS
t1b() { both 'LESSON=["- **Ends with a backslash\\\\**","'"$L3"']'"$INS"; }
pos "1b escaped-backslash-then-closer" t1b

# 2. an escaped backtick does not open a code span, so the comment after it is real -> fields hidden -> FAIL
t2() { split 'LESSON=["- **Escaped tick**","  - Why it matters here: visible \\` <!-- hidden","    hidden too --> tail","  - Do: y","'"$F"'"]'"$INS" \
             'LESSON=["- **Escaped tick**","  - Why it matters here: visible \\` tail","  - Do: y","'"$F"'"]'"$INS"; }
pos "2 escaped-backtick-not-a-span" t2   # the comment is real (closer inside the paragraph) → stripped → copies match; a span-opening `\`` would mask it and FAIL

# 3. the whole dated content wrapped in a <pre> HTML block is not Markdown -> FAIL
t3() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().rstrip('\n').split('\n'); s.insert(1,'<pre>'); s.append('</pre>'); open(p,'w').write('\n'.join(s)+'\n')
p='lessons/2026-08-24.md'; s=open(p).read().rstrip('\n').split('\n'); s.insert(1,'<pre>'); s.append('</pre>'); open(p,'w').write('\n'.join(s)+'\n')
PY
}
run "3 pre-block-hides-everything" "knowledge:sections" t3
# 3b. a <div> block ends at the first blank line; lessons after it are visible -> PASS
t3b() { both 'LESSON=["<div>","banner","</div>","","- **After div**","'"$L3"']'"$INS"; }
stray_only "3b div-block-ends-at-blank-line" "FAIL knowledge:sections" t3b "6 lesson(s)"
# 3c. <div> with the fields inside the block (no blank line) -> hidden -> FAIL
t3c() { both 'LESSON=["- **Div swallows**","  - Why it matters here: x","<div>","  - Do: y","'"$F"'","</div>"]'"$INS"; }
run "3c div-block-swallows-fields" "missing do" t3c

# 4. `text\` is a hard break, `text\ ` is not -> copies differ -> FAIL
t4() { python3 -c 'LESSON=["- **Slash space**","  - Why it matters here: x","  - Do: y\\","    more","'"$F"'"]'"$INS" knowledge.md
       python3 -c 'LESSON=["- **Slash space**","  - Why it matters here: x","  - Do: y\\ ","    more","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
run "4 backslash-space-not-a-break" "same title, different content" t4

# 5. CORRECTED 2026-09-27 (harness v2): `<` / `>` INSIDE a bare destination are allowed — only a leading `<`
#    changes the form. commonmark.js 0.31.2 renders [T](https://x.y/<bad>) as a link (href https://x.y/%3Cbad%3E),
#    so the round-18 expectation ("not a link -> FAIL") was wrong -> PASS
t5() { both 'LESSON=["- **Angle dest**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y/<bad>) — A · confidence 80%"]'"$INS"; }
pos "5 angle-brackets-inside-destination-are-a-link" t5
# 5b. the intent that survives: a destination OPENED with `<` and never closed is not a link (reference: literal text) -> FAIL
t5b() { both 'LESSON=["- **Angle open**","  - Why it matters here: x","  - Do: y","  - Source: [T](<https://x.y) — A · confidence 80%"]'"$INS"; }
run "5b unclosed-pointy-destination-is-text" "source line is not" t5b

# 6. U+2028 inside one physical line does not make new lines -> fields are not real -> FAIL
t6() { both 'LESSON=["- **Line sep**","  - Why it matters here: x   - Do: y   - Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
run "6 unicode-line-separator" "missing do" t6

echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
