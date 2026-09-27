#!/usr/bin/env bash
# Round-27 negative tests (Codex review of a0fa435).
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

# K1 (4116219332): text after a comment block's closer on the same line is visible raw HTML
t1() { printf '<!-- hidden -->VISIBLE BEFORE H1\n\n# Real heading\n' > verified/2026-01-18_tail_v1.md; }
run "K1 text-after-comment-closer-before-h1" "verified:h1" t1
t1b() { printf '<!-- hidden\nstill hidden -->TAIL\n\n# Real heading\n' > verified/2026-01-19_tail2_v1.md; }
run "K1+ multiline-comment-tail-before-h1" "verified:h1" t1b
t1c() { split 'LESSON=["- **Tail lesson**","  - Why it matters here: x","","  <!-- c -->shown","  - Do: y",'"$F"']'"$INS" \
              'LESSON=["- **Tail lesson**","  - Why it matters here: x","","  <!-- c -->","  - Do: y",'"$F"']'"$INS"; }
run "K1++ comment-tail-in-lesson-counts" "same title, different content" t1c
t1d() { printf '<!-- hidden -->   \n\n# Real heading\n' > verified/2026-01-20_tailws_v1.md; }
pos "K1+++ whitespace-after-closer-still-invisible" t1d

# K2 (4116219333): a complete type-7 tag as the FIRST content of a child item opens a raw HTML block
t2() { both 'LESSON=["- **Sub lesson**","  - <sub>","    - Why it matters here: x","    - Do: y","",'"$F"']'"$INS"; }
run "K2 type7-first-in-item-swallows-fields" "missing why" t2
# K2+ the same hole for a fence as the first content of an item: `- ```` opens a fence inside the item
t2b() { split 'LESSON=["- **Fence first**","  - ```","    hidden one","    ```","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS" \
              'LESSON=["- **Fence first**","  - ```","    hidden two","    ```","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "K2+ fence-first-in-item-is-a-fence" "same title, different content" t2b

# K3 (4116219327): reference-style links resolve through definitions that must match between copies
t3() { split 'LESSON=["- **Ref link**","  - Why it matters here: see [docs][ref]","  - Do: y",'"$F"',"","[ref]: https://knowledge.example"]'"$INS" \
             'LESSON=["- **Ref link**","  - Why it matters here: see [docs][ref]","  - Do: y",'"$F"',"","[ref]: https://daily.example"]'"$INS"; }
run "K3 ref-definition-differs" "same title, different content" t3
t3b() { split 'LESSON=["- **Ref link**","  - Why it matters here: see [docs][ref]","  - Do: y",'"$F"',"","[ref]: https://knowledge.example"]'"$INS" \
              'LESSON=["- **Ref link**","  - Why it matters here: see [docs][ref]","  - Do: y",'"$F"']'"$INS"; }
run "K3+ ref-definition-missing-in-one-copy" "same title, different content" t3b
t3c() { both 'LESSON=["- **Ref link**","  - Why it matters here: see [docs][REF]","  - Do: y",'"$F"',"","[ref]: https://knowledge.example \"t\""]'"$INS"; }
pos "K3++ same-definition-case-insensitive" t3c

# K4 (4116219329): a confidence hidden in an HTML attribute is not a visible label
t4() { both 'LESSON=["- **Attr conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A <br title=\"confidence 80%\">"]'"$INS"; }
run "K4 confidence-in-attribute" "source line is not" t4
t4b() { both 'LESSON=["- **Tag then conf**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — A <br> confidence 80%"]'"$INS"; }
pos "K4+ visible-confidence-after-tag" t4b

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
rm -rf "$W"
[ $bad -eq 0 ]
