#!/usr/bin/env bash
# Round-28 negative tests (Codex review of 78d12a9, harness v2 on PR #2).
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

# L1 (4117111332): whitespace dropped after a <pre> must not shift the offsets of later code spans.
#     The copies differ only in the character right after an inline code span that follows a code block.
t1() { split 'LESSON=["- **Pre then code**","  - Why it matters here: x","","    ```","    x","    ```","","  - Do: `y`A",'"$F"']'"$INS" \
             'LESSON=["- **Pre then code**","  - Why it matters here: x","","    ```","    x","    ```","","  - Do: `y`B",'"$F"']'"$INS"; }
run "L1 text-after-code-after-pre-is-compared" "same title, different content" t1
t1b() { split 'LESSON=["- **Pre code code**","  - Why it matters here: x","","    ```","    x","    ```","","  - Do: `y` then `z`A tail",'"$F"']'"$INS" \
              'LESSON=["- **Pre code code**","  - Why it matters here: x","","    ```","    x","    ```","","  - Do: `y` then `z`B tail",'"$F"']'"$INS"; }
run "L1+ two-code-spans-after-pre" "same title, different content" t1b
t1c() { both 'LESSON=["- **Pre then code**","  - Why it matters here: x","","    ```","    x","    ```","","  - Do: `y`A",'"$F"']'"$INS"; }
pos "L1++ identical-copies-still-pass" t1c

# L2 (4117111335): a field whose only content is invisible is empty.
t2() { both 'LESSON=["- **Hidden why**","  - Why it matters here: <!-- hidden -->","  - Do: y",'"$F"']'"$INS"; }
run "L2 comment-only-why-is-empty" "missing or empty why" t2
t2b() { both 'LESSON=["- **Hidden do**","  - Why it matters here: x","  - Do:","","    <!-- hidden block -->","",'"$F"']'"$INS"; }
run "L2+ invisible-block-only-do-is-empty" "missing or empty do" t2b
t2c() { both 'LESSON=["- **Code why**","  - Why it matters here: `x`","  - Do: <!-- c --> real",'"$F"']'"$INS"; }
pos "L2++ code-or-text-beside-a-comment-is-content" t2c
t2d() { both 'LESSON=["- **Hidden source**","  - Why it matters here: x","  - Do: y","  - Source: <!-- hidden -->"]'"$INS"; }
run "L2+++ comment-only-source" "source line is not" t2d

# L3 (4117111338): an invisible comment inside a field label does not hide the field.
t3() { both 'LESSON=["- **Label comment**","  - Why<!-- note --> it matters here: x","  - Do<!-- n -->: y","  - Source<!-- n -->: [T](https://x.y) — A · confidence 50%"]'"$INS"; }
pos "L3 comment-inside-labels-is-invisible" t3
t3b() { both 'LESSON=["- **Label code**","  - Why `it` matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "L3+ code-inside-a-label-is-not-the-label" "missing why" t3b

# L4 (4117111343): --json keeps its one-JSON-object contract when markdown-it-py is missing.
n=$((n+1))
rm -rf "$W/r" "$W/stub"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; mkdir -p "$W/stub/markdown_it"
echo 'raise ImportError("stub: markdown-it-py hidden by neg28 L4")' > "$W/stub/markdown_it/__init__.py"
out=$(cd "$W/r" && PYTHONPATH="$W/stub" python3 harness/check-knowledge.py --json 2>&1); rc=$?
if [ $rc -eq 1 ] && printf '%s' "$out" | python3 -c '
import json, sys
d = json.loads(sys.stdin.read())
assert d["ok"] is False and d["fail"] == 1 and d["checks"][0]["name"] == "harness:deps", d
'; then echo "PASS L4 json-mode-without-deps — one JSON object, ok=false, rc=1"
else bad=$((bad+1)); echo "FAIL L4 json-mode-without-deps — rc=$rc, output:"; echo "$out" | sed 's/^/    /'; fi
n=$((n+1))
out=$(cd "$W/r" && PYTHONPATH="$W/stub" python3 harness/check-knowledge.py 2>&1); rc=$?
if [ $rc -eq 1 ] && printf '%s\n' "$out" | grep -q '^FAIL harness:deps' && printf '%s\n' "$out" | grep -q '^RESULT: FAIL'; then
  echo "PASS L4+ text-mode-without-deps — FAIL line + RESULT line, rc=1"
else bad=$((bad+1)); echo "FAIL L4+ text-mode-without-deps — rc=$rc, output:"; echo "$out" | sed 's/^/    /'; fi

# L5 (4117111346): visible non-text content splits words; only formatting and invisible markup are zero-width.
t5() { both 'LESSON=["- **Split conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confi`code`dence 80%"]'"$INS"; }
run "L5 code-span-splits-the-label" "source line is not" t5
t5b() { both 'LESSON=["- **Img conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confi![i](https://x.y/i.png)dence 80%"]'"$INS"; }
run "L5+ image-splits-the-label" "source line is not" t5b
t5c() { both 'LESSON=["- **Tag conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confidence<br>80%"]'"$INS"; }
run "L5++ raw-tag-splits-label-and-number" "source line is not" t5c
t5d() { both 'LESSON=["- **Code conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · `confidence 80%`"]'"$INS"; }
run "L5+++ label-inside-code-is-not-a-label" "source line is not" t5d
t5e() { both 'LESSON=["- **Bold conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · **confidence 80%**"]'"$INS"; }
pos "L5++++ formatting-is-zero-width" t5e
t5f() { both 'LESSON=["- **Comment conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A · confi<!-- x -->dence 80%"]'"$INS"; }
pos "L5+++++ comment-inside-label-is-invisible" t5f

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
[ $bad -eq 0 ]
