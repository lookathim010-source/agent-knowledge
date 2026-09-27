#!/usr/bin/env bash
# Round-29 negative tests (second Codex review of 78d12a9, harness v2 on PR #2).
# Browser behaviour in N5/N6/N1 was checked in Chromium 141 (textContent / computed white-space).
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
# Apply one case's mutation inside the copy. If any command in it fails, the copy's checker is replaced by a
# stub that names the failure, so a case can never pass (or fail as expected) on an unmutated repo.
mutate() { ( set -e; cd "$W/r"; "$1" ); local rc=$?
  [ "$rc" -eq 0 ] || printf 'print("MUTATION DID NOT APPLY: %s (rc=%s)"); raise SystemExit(3)\n' "$1" "$rc" > "$W/r/harness/check-knowledge.py"; }
n=0; bad=0
both() { for p in knowledge.md lessons/2026-08-24.md; do python3 -c "$1" "$p"; done; }
split() { python3 -c "$1" knowledge.md; python3 -c "$2" lessons/2026-08-24.md; }
run() { local name="$1" expect="$2"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; mutate "$3"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then
    echo "PASS $name — FAIL fired: $(printf '%s' "$out" | grep -F -- "$expect" | head -1 | cut -c1-160)"
  else bad=$((bad+1)); echo "FAIL $name — rc=$rc, expected '$expect' in:"; echo "$out" | sed 's/^/    /'; fi; }
pos() { local name="$1"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; mutate "$2"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "PASS $name — still PASS"; else bad=$((bad+1)); echo "FAIL $name — unexpected FAIL:"; echo "$out" | sed 's/^/    /'; fi; }
INS='
import sys
p=sys.argv[1]; s=open(p).read().split("\n")
i=next(k for k,l in enumerate(s) if l.startswith("## ") or l.startswith("# Lessons"))
s[i+1:i+1]=[""]+LESSON
open(p,"w").write("\n".join(s))
'
F='"  - Source: [T](https://x.y) — A · confidence 50%"'

# N1 (4117161110): raw HTML that keeps whitespace visible (textarea, xmp, listing, a white-space style) is compared exactly.
#    (Each Do: carries plain text beside the raw HTML: since round 30, content inside raw HTML never counts as a value.)
t1() { split 'LESSON=["- **Textarea**","  - Why it matters here: x","  - Do: type <textarea>a  b</textarea>",'"$F"']'"$INS" \
             'LESSON=["- **Textarea**","  - Why it matters here: x","  - Do: type <textarea>a   b</textarea>",'"$F"']'"$INS"; }
run "N1 textarea-whitespace-is-visible" "same title, different content" t1
t1b() { split 'LESSON=["- **Styled**","  - Why it matters here: x","  - Do: type <span style=\"white-space:pre\">a  b</span>",'"$F"']'"$INS" \
              'LESSON=["- **Styled**","  - Why it matters here: x","  - Do: type <span style=\"white-space:pre\">a b</span>",'"$F"']'"$INS"; }
run "N1+ white-space-style-is-visible" "same title, different content" t1b
t1c() { split 'LESSON=["- **Block textarea**","  - Why it matters here: x","  - Do: y","","    <textarea>","    a  b","    </textarea>","",'"$F"']'"$INS" \
              'LESSON=["- **Block textarea**","  - Why it matters here: x","  - Do: y","","    <textarea>","    a   b","    </textarea>","",'"$F"']'"$INS"; }
run "N1++ textarea-block-whitespace-is-visible" "same title, different content" t1c
t1d() { both 'LESSON=["- **Textarea**","  - Why it matters here: x","  - Do: type <textarea>a  b</textarea>",'"$F"']'"$INS"; }
pos "N1+++ identical-textarea-copies-pass" t1d

# N3 (4117161124): a source link needs visible link text
t3() { both 'LESSON=["- **Empty label**","  - Why it matters here: x","  - Do: y","  - Source: [](https://x.y) — A · confidence 80%"]'"$INS"; }
run "N3 empty-link-label" "source line is not" t3
t3b() { both 'LESSON=["- **Blank label**","  - Why it matters here: x","  - Do: y","  - Source: [ ](https://x.y) — A · confidence 80%"]'"$INS"; }
run "N3+ whitespace-link-label" "source line is not" t3b
t3c() { both 'LESSON=["- **Hidden label**","  - Why it matters here: x","  - Do: y","  - Source: [<!-- c -->](https://x.y) — A · confidence 80%"]'"$INS"; }
run "N3++ invisible-link-label" "source line is not" t3c
t3d() { both 'LESSON=["- **Code label**","  - Why it matters here: x","  - Do: y","  - Source: [`api`](https://x.y) — A · confidence 80%"]'"$INS"; }
pos "N3+++ code-link-label-is-visible" t3d
t3e() { both 'LESSON=["- **Image label**","  - Why it matters here: x","  - Do: y","  - Source: [![logo](https://x.y/l.png)](https://x.y) — A · confidence 80%"]'"$INS"; }
pos "N3++++ image-link-label-is-visible" t3e

# N4 (4117161130): a case whose mutation fails must be reported as a failure, never as PASS
tbad() { python3 -c 'import sys; next(k for k in [] if k)' knowledge.md; }
probe=$(pos "probe-pos" tbad 2>&1); n=$((n+1))
if printf '%s' "$probe" | grep -q '^FAIL probe-pos'; then echo "PASS N4 pos-with-failed-mutation-is-reported"
else bad=$((bad+1)); echo "FAIL N4 pos-with-failed-mutation-is-reported — got:"; echo "$probe" | sed 's/^/    /'; fi
probe=$(run "probe-run" "MUTATION DID NOT APPLY" tbad 2>&1); n=$((n+1))
if printf '%s' "$probe" | grep -q '^PASS probe-run'; then echo "PASS N4+ failed-mutation-names-itself"
else bad=$((bad+1)); echo "FAIL N4+ failed-mutation-names-itself — got:"; echo "$probe" | sed 's/^/    /'; fi
tbad2() { both 'raise SystemExit(1)'; }
probe=$(pos "probe-both" tbad2 2>&1); n=$((n+1))
if printf '%s' "$probe" | grep -q '^FAIL probe-both'; then echo "PASS N4++ first-of-two-mutations-failing-is-reported"
else bad=$((bad+1)); echo "FAIL N4++ first-of-two-mutations-failing-is-reported — got:"; echo "$probe" | sed 's/^/    /'; fi

# N5 (4117161134): a minimal processing instruction or empty comment closes on its own line
t5() { both 'import sys
p=sys.argv[1]; s=open(p).read().split("\n")
i=next(k for k,l in enumerate(s) if l.startswith("## ") or l.startswith("# Lessons"))
s[i+1:i+1]=["","<?>"]
open(p,"w").write("\n".join(s))'; }
pos "N5 minimal-processing-instruction-closes" t5
t5b() { both 'import sys
p=sys.argv[1]; s=open(p).read().split("\n")
i=next(k for k,l in enumerate(s) if l.startswith("## ") or l.startswith("# Lessons"))
s[i+1:i+1]=["","<!-->"]
open(p,"w").write("\n".join(s))'; }
pos "N5+ empty-comment-closes" t5b
t5c() { both 'import sys
p=sys.argv[1]; s=open(p).read().split("\n")
i=next(k for k,l in enumerate(s) if l.startswith("## ") or l.startswith("# Lessons"))
s[i+1:i+1]=["","<?"]
open(p,"w").write("\n".join(s))'; }
run "N5++ open-processing-instruction-never-closes" "HTML block never closes" t5c

# N6 (found while fixing N5): invisible raw HTML ends where a browser ends it, not later
t6() { split 'LESSON=["- **Abrupt comment**","  - Why it matters here: x","  - Do: y <!-->A",'"$F"']'"$INS" \
             'LESSON=["- **Abrupt comment**","  - Why it matters here: x","  - Do: y <!-->B",'"$F"']'"$INS"; }
run "N6 text-after-empty-comment-is-visible" "same title, different content" t6
t6b() { split 'LESSON=["- **Minimal PI**","  - Why it matters here: x","  - Do: y <?>A",'"$F"']'"$INS" \
              'LESSON=["- **Minimal PI**","  - Why it matters here: x","  - Do: y <?>B",'"$F"']'"$INS"; }
run "N6+ text-after-minimal-pi-is-visible" "same title, different content" t6b
t6c() { split 'LESSON=["- **CDATA gt**","  - Why it matters here: x","  - Do: y <![CDATA[ a > b ]]>",'"$F"']'"$INS" \
              'LESSON=["- **CDATA gt**","  - Why it matters here: x","  - Do: y <![CDATA[ a > c ]]>",'"$F"']'"$INS"; }
run "N6++ cdata-ends-at-first-gt" "same title, different content" t6c
t6d() { split 'LESSON=["- **Bang close**","  - Why it matters here: x","  - Do: y <!-- a --!>A -->",'"$F"']'"$INS" \
              'LESSON=["- **Bang close**","  - Why it matters here: x","  - Do: y <!-- a --!>B -->",'"$F"']'"$INS"; }
run "N6+++ comment-ends-at-bang-close" "same title, different content" t6d
t6e() { split 'LESSON=["- **Comment gt**","  - Why it matters here: x","  - Do: y <!-- a > b -->",'"$F"']'"$INS" \
              'LESSON=["- **Comment gt**","  - Why it matters here: x","  - Do: y <!-- a > c -->",'"$F"']'"$INS"; }
pos "N6++++ comment-text-stays-hidden" t6e

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
[ $bad -eq 0 ]
