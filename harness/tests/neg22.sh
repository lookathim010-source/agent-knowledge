#!/usr/bin/env bash
# Round-22 negative tests (Codex review of 5319f30). Mutations hit BOTH copies where the
# structural check — not the copy comparison — must catch them.
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W=$(mktemp -d)
n=0; bad=0
both() { for p in knowledge.md lessons/2026-08-24.md; do python3 -c "$1" "$p"; done; }
one()  { python3 -c "$1" knowledge.md; }
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
SRC_LINE='"  - Source: [T](https://x.y) — A · confidence 50%"'

# F1 (4115921652): lowercase `<!foo>` is NOT an HTML block — it is lazy continuation text, so a
#    knowledge.md carrying it must differ from a day copy without it.
t1() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.lstrip().startswith('- Source:')][0]   # after the LAST field: nothing follows to trip on
s.insert(i+1,'<!foo> extra visible context only in knowledge.md')
open(p,'w').write('\n'.join(s))
PY
}
# CORRECTED 2026-09-27 (harness v2): under CommonMark 0.31.2 `<!foo>` at column 0 starts a declaration block, so
# this line closes the list and its visible tail becomes a top-level block no day file carries -> knowledge:stray.
# The mutation is still caught; only the diagnosis changed (GitHub/0.29 reads it as lazy text -> a content diff).
run "F1 lowercase-declaration-line-is-caught" "knowledge:stray" t1
# F1+ uppercase `<!FOO>` at column 0 IS an HTML block (type 4): closes the list, later fields are stray → FAIL missing
t1b() { both 'LESSON=["- **Decl lesson**","  - Why it matters here: x","<!FOO>","  - Do: y",'"$SRC_LINE"']'"$INS"; }
run "F1+ uppercase-declaration-is-block" "missing do" t1b

# F2 (4115921656): a ref def that already has a title must not swallow the next quoted line
t2() { printf '[docs]: https://example.com "first"\n"visible second title"\n\n# Real heading\n' > verified/2026-01-04_two-titles_v1.md; }
run "F2 second-title-is-paragraph" "verified:h1" t2
# F2+ a ref def WITHOUT a title followed by its title on the next line is still fine
t2b() { printf '[docs]: https://example.com\n"the title"\n\n# Real heading\n' > verified/2026-01-05_split-title_v1.md; }
pos "F2+ next-line-title-accepted" t2b

# F3 (4115921662): 8 spaces after a blank = indented code inside the field; 4 spaces = a new paragraph.
#    Different structures must not compare equal.
t3() { python3 - <<'PY'
for p,ind in (('knowledge.md',8),('lessons/2026-08-24.md',4)):
    s=open(p).read().split('\n')
    i=[k for k,l in enumerate(s) if l.lstrip().startswith('- Do:')][0]
    s[i+1:i+1]=['',' '*ind+'trailing text']
    open(p,'w').write('\n'.join(s))
PY
}
run "F3 indented-code-vs-paragraph" "same title, different content" t3
# F3+ the same 4-space paragraph in both copies is fine
t3b() { both 'LESSON=["- **Para lesson**","  - Why it matters here: x","  - Do: y","","    a second paragraph of Do",'"$SRC_LINE"']'"$INS"; }
pos "F3+ same-paragraph-both-copies" t3b

# F4 (4115921672): a Setext H2 nested in a field (blank, text, dashes at the field's content column)
t4() { both 'LESSON=["- **Setext lesson**","  - Why it matters here: x","","    Nested heading","    --------------","  - Do: y",'"$SRC_LINE"']'"$INS"; }
run "F4 nested-setext-h2" "nested inside the lesson" t4
# F4+ a Setext underline directly under a field label line makes THAT line an H2 too
t4b() { both 'LESSON=["- **Setext label**","  - Why it matters here: x","    ---","  - Do: y",'"$SRC_LINE"']'"$INS"; }
run "F4+ setext-under-field-label" "nested inside the lesson" t4b

# F5 (4115921661): `- **alpha\\**beta**` — even backslashes leave the inner ** active
t5() { both 'LESSON=["- **alpha\\\\**beta**","  - Why it matters here: x","  - Do: y",'"$SRC_LINE"']'"$INS"; }
run "F5 inner-strong-after-even-backslashes" "not-a-bold-lesson-bullet" t5
# F5+ `- **alpha\\*\\*beta**` (odd backslashes each) is one bold span → PASS
t5b() { both 'LESSON=["- **alpha\\*\\*beta**","  - Why it matters here: x","  - Do: y",'"$SRC_LINE"']'"$INS"; }
pos "F5+ escaped-inner-stars-accepted" t5b

# F6 (4115921665): trailing whitespace on the connector H1 is not the exact line
t6() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n'); s[0]=s[0]+'  '; open(p,'w').write('\n'.join(s))
PY
}
run "F6 h1-trailing-space" "knowledge:h1" t6

# F7 (4115921669): `<!--` at the end of a field, next line a sibling field, `-->` later:
#    the list item ends the paragraph, so the opener is literal and both copies are VALID → PASS
t7() { both 'LESSON=["- **Opener lesson**","  - Why it matters here: x <!--","  - Do: y -->",'"$SRC_LINE"']'"$INS"; }
pos "F7 opener-literal-across-list-item" t7
# F7+ but a closer INSIDE the same paragraph (lazy line) still hides the text between
t7b() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.lstrip().startswith('- Do:')][0]
s[i]=s[i]+' <!-- hidden'
s.insert(i+1,'still hidden --> visible tail only in knowledge.md')
open(p,'w').write('\n'.join(s))
PY
}
run "F7+ closer-in-same-paragraph" "same title, different content" t7b

# Adjacent (found during the audit): prose after a code block inside a field must count
t8() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.lstrip().startswith('- Do:')][0]
s[i+1:i+1]=['    ```','    code','    ```','    prose after the fence, only in knowledge.md']
open(p,'w').write('\n'.join(s))
PY
}
run "A1 prose-after-nested-fence-counts" "same title, different content" t8
# Adjacent: a lesson-level paragraph after the fields (indent between lesson col and field col) must count
t9() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.lstrip().startswith('- Source:')][0]
s[i+1:i+1]=['','  a trailing lesson-level paragraph only in knowledge.md']
open(p,'w').write('\n'.join(s))
PY
}
run "A2 lesson-tail-paragraph-counts" "same title, different content" t9
# Adjacent: a nested `## x` deeper than 3 spaces but ≤3 relative to the lesson's content column is still an H2
t10() { both 'LESSON=["- **Deep heading**","  - Why it matters here: x","","    ## 2026-01-01","  - Do: y",'"$SRC_LINE"']'"$INS"; }
run "A3 nested-h2-relative-indent" "nested inside the lesson" t10

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
rm -rf "$W"
[ $bad -eq 0 ]
