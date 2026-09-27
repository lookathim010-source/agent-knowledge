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

# 1. a malformed definition (unquoted trailing text) is a visible paragraph -> FAIL
t1() { printf '[docs]: https://example.com extra junk\n\n# Heading\n\nbody\n' > verified/2026-01-14_badref_v1.md; }
run "1 invalid-ref-def-is-text" "verified:h1" t1
# 1b. a definition with a quoted title on the same line is valid -> PASS
t1b() { printf '[docs]: https://example.com "Docs"\n\n# Heading\n\nbody\n' > verified/2026-01-15_okref_v1.md; }
pos "1b ref-def-with-title" t1b

# 2. a Setext H2 (paragraph + dashes) is a non-date H2 -> FAIL in knowledge.md and in the day file
t2() { both 'LESSON=["- **Complete**","'"$L3"',"","Unexpected heading","------------------",""]'"$INS"; }
run "2 setext-h2" "knowledge:headings" t2
# 2b. dashes after a BLANK line are a thematic break, not a heading -> PASS
t2b() { both 'LESSON=["- **Complete**","'"$L3"',"","---",""]'"$INS"; }
stray_only "2b dashes-after-blank-are-a-break" "FAIL knowledge:headings" t2b

# 3. a closing fence followed by NBSP does not close: that line is code, and the block ends with its list
#    item (commonmark.js 0.31.2: Do/Source render as items). Rewritten 2026-09-27 (round 23) — the old
#    "missing do" expectation was wrong. knowledge.md has the NBSP closer, the day copy a real one -> the
#    code blocks differ -> FAIL; a harness that accepted the NBSP closer would see them equal.
t3() { python3 -c 'LESSON=["- **NBSP closer**","  - Why it matters here: x","    ```","    code","    ```\u00a0","  - Do: y","'"$F"'"]'"$INS" knowledge.md
       python3 -c 'LESSON=["- **NBSP closer**","  - Why it matters here: x","    ```","    code","    ```","  - Do: y","'"$F"'"]'"$INS" lessons/2026-08-24.md; }
run "3 nbsp-after-closing-fence" "same title, different content" t3

# 4. visible prose between the H1 and the first day section -> FAIL
t4() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n'); s[1:1]=['','Some visible prose here.']; open(p,'w').write('\n'.join(s))
PY
}
run "4 prose-before-first-section" "knowledge:misplaced" t4

echo "----"; echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"; rm -rf "$W"; [ $bad -eq 0 ]
