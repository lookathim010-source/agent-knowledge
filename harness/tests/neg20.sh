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

# 1. an inline `<!--` with no `-->` before the paragraph ends (blank line) is literal text -> fields stay visible -> PASS
t1() { both 'LESSON=["- **Literal opener**","  - Why it matters here: text <!--","","  - Do: y","'"$F"'","","-->"]'"$INS"; }
stray_only "1 unclosed-comment-ends-at-paragraph" "missing do" t1

# 2. an unmatched backtick in Why must not carry into the next list item: the comment on the Do line is real -> Source hidden -> FAIL
t2() { split 'LESSON=["- **Tick then comment**","  - Why it matters here: x `","  - Do: action <!-- hidden","    hidden too --> tail","'"$F"'"]'"$INS" \
             'LESSON=["- **Tick then comment**","  - Why it matters here: x `","  - Do: action tail","'"$F"'"]'"$INS"; }
pos "2 code-span-reset-at-block-start" t2   # the Do line starts a new item, so Why's open backtick is literal and the comment on Do is real → stripped → copies match

# 3. a two-line reference definition (title on the next line) before the H1 -> PASS
t3() { printf '[docs]: https://example.com\n  "Docs title"\n\n# Heading\n\nbody\n' > verified/2026-01-11_reftitle_v1.md; }
pos "3 multiline-ref-def-before-h1" t3

# 4. `<div<NBSP>x>` is not an HTML block (NBSP is not tag whitespace) -> visible text before the H1 -> FAIL
t4() { printf '<div\xc2\xa0x>\n\n# Heading\n\nbody\n' > verified/2026-01-12_nbsp_v1.md; }
run "4 nbsp-in-tag-is-text" "verified:h1" t4

# 5. a non-ASCII digit in the version suffix -> bad name -> FAIL
t5() { printf '# Heading\n' > "verified/2026-01-13_topic_v١.md"; }
run "5 unicode-digit-version" "verified:names" t5

# 6. 2-4 spaces after a nested field marker are valid -> PASS
t6() { both 'LESSON=["- **Wide field gap**","  -  Why it matters here: x","  -   Do: y","  -    Source: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "6 field-marker-2-4-spaces" t6
# 6b. 5+ spaces after the marker make the field an indented code block -> not a field -> FAIL
t6b() { both 'LESSON=["- **Code field**","  - Why it matters here: x","  -     Do: y","'"$F"'"]'"$INS"; }
run "6b field-marker-5-spaces-is-code" "missing do" t6b

# 7. a blank line before the continuation makes a new paragraph in one copy only -> copies differ -> FAIL
t7() { python3 -c 'LESSON=["- **Para break**","  - Why it matters here: x","  - Do: y","    more","'"$F"'"]'"$INS" knowledge.md
       python3 -c 'LESSON=["- **Para break**","  - Why it matters here: x","  - Do: y","","    more","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
run "7 paragraph-break-differs" "same title, different content" t7
# 7b. the same paragraph break in both copies -> PASS
t7b() { both 'LESSON=["- **Para both**","  - Why it matters here: x","  - Do: y","","    more","'"$F"'"]'"$INS"; }
pos "7b paragraph-break-in-both" t7b

echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
