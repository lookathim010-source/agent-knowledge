#!/usr/bin/env bash
# Round-25 negative tests (Codex review of 0446523).
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W=$(mktemp -d)
n=0; bad=0
both() { for p in knowledge.md lessons/2026-08-24.md; do python3 -c "$1" "$p"; done; }
split() { python3 -c "$1" knowledge.md; python3 -c "$2" lessons/2026-08-24.md; }
run() { local name="$1" expect="$2"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; ( cd "$W/r" && "$3" )
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then
    echo "PASS $name — FAIL fired: $(printf '%s' "$out" | grep -F -- "$expect" | head -1 | cut -c1-160)"
  else bad=$((bad+1)); echo "FAIL $name — rc=$rc, expected '$expect' in:"; echo "$out" | sed 's/^/    /'; fi; }
pos() { local name="$1"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"; ( cd "$W/r" && "$2" )
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

# I1 (4116126983): a backtick run with no closer anywhere in the paragraph is literal; the comment after it is real
t1() { split 'LESSON=["- **Loose tick**","  - Why it matters here: x ` open","    more <!-- hidden --> text","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Loose tick**","  - Why it matters here: x ` open","    more text","  - Do: y",'"$F"']'"$INS"; }
pos "I1 unmatched-run-is-literal" t1
# I1+ a run that DOES close on a later line keeps the comment-like text inside as code (visible)
t1b() { split 'LESSON=["- **Closed tick**","  - Why it matters here: x `open","    <!-- shown --> close` text","  - Do: y",'"$F"']'"$INS" \
              'LESSON=["- **Closed tick**","  - Why it matters here: x `open","    close` text","  - Do: y",'"$F"']'"$INS"; }
run "I1+ closer-ahead-keeps-span" "same title, different content" t1b

# I2 (4116126973): content indentation is measured from the fence's own indentation
t2() { split 'LESSON=["- **Fence indent**","  - Why it matters here: x","      ```","        code","      ```","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Fence indent**","  - Why it matters here: x","       ```","        code","       ```","  - Do: y",'"$F"']'"$INS"; }
run "I2 fence-indent-changes-content" "same title, different content" t2
t2b() { both 'LESSON=["- **Fence indent**","  - Why it matters here: x","      ```","        code","      ```","  - Do: y",'"$F"']'"$INS"; }
pos "I2+ same-fence-indent-both" t2b

# I3 (4116126977): indented code blocks inside a lesson are compared
t3() { split 'LESSON=["- **Indented code**","  - Why it matters here: x","","        alpha","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Indented code**","  - Why it matters here: x","","        beta","  - Do: y",'"$F"']'"$INS"; }
run "I3 indented-code-payload-differs" "same title, different content" t3
t3b() { both 'LESSON=["- **Indented code**","  - Why it matters here: x","","        alpha","","        gamma","  - Do: y",'"$F"']'"$INS"; }
pos "I3+ same-indented-code-both" t3b
t3c() { split 'LESSON=["- **Indented code blank**","  - Why it matters here: x","","        alpha","","        gamma","  - Do: y",'"$F"']'"$INS" \
              'LESSON=["- **Indented code blank**","  - Why it matters here: x","","        alpha","        gamma","  - Do: y",'"$F"']'"$INS"; }
run "I3++ blank-line-inside-code-counts" "same title, different content" t3c

# I4 (4116126989): visible top-level content inside a day section that is not a lesson
t4() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.startswith('## ')][0]; s[i+1:i+1]=['','Visible only in knowledge.']; open(p,'w').write('\n'.join(s))
PY
}
run "I4 stray-paragraph-in-section" "knowledge:stray" t4
t4b() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.startswith('## ')][0]; s[i+1:i+1]=['','### Sub-heading']; open(p,'w').write('\n'.join(s))
PY
}
run "I4+ stray-h3-in-section" "knowledge:stray" t4b
t4c() { python3 - <<'PY'
p='lessons/2026-08-24.md'; s=open(p).read().split('\n'); s[2:2]=['','A paragraph only in the day file.']; open(p,'w').write('\n'.join(s))
PY
}
run "I4++ stray-paragraph-in-dayfile" "lessons:2026-08-24" t4c
t4d() { both 'LESSON=["- **Comment ok**","  - Why it matters here: x","  - Do: y",'"$F"',"","<!-- a top-level comment between lessons renders nothing -->"]'"$INS"; }
pos "I4+++ top-level-comment-not-stray" t4d

# I5 (4116126996): field order is part of the comparison
t5() { split 'LESSON=["- **Order**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Order**","  - Do: y","  - Why it matters here: x",'"$F"']'"$INS"; }
run "I5 field-order-differs" "same title, different content" t5

# I6 (4116127003): a fenced block inside a block quote inside a lesson is a fence (quote marker removed first)
t6() { split 'LESSON=["- **Quoted fence**","  - Why it matters here: x","","  > ```","  > <!-- alpha -->","  > ```","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Quoted fence**","  - Why it matters here: x","","  > ```","  > <!-- beta -->","  > ```","  - Do: y",'"$F"']'"$INS"; }
run "I6 quoted-fence-payload-differs" "same title, different content" t6
t6b() { both 'LESSON=["- **Quoted fence**","  - Why it matters here: x","","  > ```","  > <!-- alpha -->","  > ```","  - Do: y",'"$F"']'"$INS"; }
pos "I6+ same-quoted-fence-both" t6b

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
rm -rf "$W"
[ $bad -eq 0 ]
