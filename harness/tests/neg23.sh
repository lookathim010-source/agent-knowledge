#!/usr/bin/env bash
# Round-23 negative tests (Codex review of 320a5cc).
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
NB=$(printf '\xc2\xa0')

# G1 (4115994843): NBSP after the section date is heading content, not Markdown whitespace
t1() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.startswith('## ')][0]; s[i]=s[i]+' '; open(p,'w').write('\n'.join(s))
PY
}
run "G1 nbsp-after-section-date" "knowledge:headings" t1
# G1+ NBSP after a day-file H1 is not the exact H1
t1b() { python3 - <<'PY'
p='lessons/2026-08-24.md'; s=open(p).read().split('\n'); s[0]=s[0]+' '; open(p,'w').write('\n'.join(s))
PY
}
run "G1+ nbsp-after-day-h1" "first visible line must be" t1b
# G1++ a NBSP-only line is a paragraph line (lazy continuation), not a blank: knowledge.md carries it, the day copy does not
t1c() { python3 - <<'PY'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.lstrip().startswith('- Do:')][0]; s.insert(i+1,' visible nbsp-led lazy line'); open(p,'w').write('\n'.join(s))
PY
}
run "G1++ nbsp-line-is-text" "same title, different content" t1c

# G2 (4115994845): a ref def whose bare destination has an unbalanced `(` is prose, not a definition
t2() { printf '[docs]: https://example.com/(oops\n\n# Real heading\n' > verified/2026-01-06_unbalanced_v1.md; }
run "G2 unbalanced-paren-destination" "verified:h1" t2
# G2+ balanced parens and an escaped paren are fine
t2b() { printf '[docs]: https://example.com/a_(b)\n[more]: https://example.com/\\(c "t"\n\n# Real heading\n' > verified/2026-01-07_balanced_v1.md; }
pos "G2+ balanced-and-escaped-parens" t2b

# G3 (4115994849): `\\` before a backtick escapes the backslash, so the backtick opens a code span whose ** is opaque → valid title
t3() { both 'LESSON=["- **a \\\\`**` b**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
pos "G3 even-backslashes-before-backtick" t3
# G3+ a single backslash before the backtick escapes the backtick: the ** is live → malformed
t3b() { both 'LESSON=["- **a \\`**` b**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "G3+ odd-backslash-before-backtick" "not-a-bold-lesson-bullet" t3b

# G4 (4115994853): a raw HTML block nested in a lesson is visible — a copy without it differs
t4() { split 'LESSON=["- **Html lesson**","  - Why it matters here: x","","    <div>visible only here</div>","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Html lesson**","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "G4 nested-html-block-counts" "same title, different content" t4
# G4+ same block in both copies → PASS
t4b() { both 'LESSON=["- **Html lesson**","  - Why it matters here: x","","    <div>same in both</div>","  - Do: y",'"$F"']'"$INS"; }
# CHANGED 2026-09-27 (raw-HTML ban, T's decision on PR #2): this lesson carries raw HTML other than a
# comment, so it now FAILs whatever the HTML does; the parse this case pinned no longer decides the verdict.
run "G4+ nested-html-block-both -> raw-html-now-fails" "raw HTML in a lesson" t4b
# G4++ nested fenced code with different content differs too (readers see the code)
t4c() { split 'LESSON=["- **Code lesson**","  - Why it matters here: x","    ```","    print(1)","    ```","  - Do: y",'"$F"']'"$INS" \
              'LESSON=["- **Code lesson**","  - Why it matters here: x","    ```","    print(2)","    ```","  - Do: y",'"$F"']'"$INS"; }
run "G4++ nested-code-content-counts" "same title, different content" t4c

# G5 (4115994859): `overconfidence 80%` is not a standalone confidence label
t5() { both 'LESSON=["- **Conf lesson**","  - Why it matters here: x","  - Do: y","  - Source: [T](https://x.y) — overconfidence 80%"]'"$INS"; }
run "G5 overconfidence-not-a-label" "source line is not" t5

# G6 (4115994856): an H2 inside a block quote is still an H2
t6() { both 'LESSON=["- **Quote lesson**","  - Why it matters here: x","  - Do: y",'"$F"',"","> ## Unexpected"]'"$INS"; }
run "G6 h2-in-blockquote" "knowledge:headings" t6
# G6+ nested inside the lesson too
t6b() { both 'LESSON=["- **Quote nested**","  - Why it matters here: x","","  > ## Unexpected","  - Do: y",'"$F"']'"$INS"; }
run "G6+ h2-in-blockquote-nested" "nested inside the lesson" t6b
# G6++ day file only (knowledge.md clean): the per-day no-H2 check must see it
t6c() { python3 - <<'PY'
p='lessons/2026-08-24.md'; s=open(p).read().split('\n'); s.append(''); s.append('> > ## Deep quote'); open(p,'w').write('\n'.join(s))
PY
}
run "G6++ h2-in-nested-quote-dayfile" "contains H2 heading" t6c

# G6+++ Setext H2 inside a top-level block quote (`> Foo` / `> ---`)
t6d() { both 'LESSON=["- **Quote setext**","  - Why it matters here: x","  - Do: y",'"$F"',"","> Foo","> ---"]'"$INS"; }
run "G6+++ setext-in-blockquote" "knowledge:headings" t6d
# G6++++ …and nested inside a lesson
t6e() { both 'LESSON=["- **Quote setext nested**","  - Why it matters here: x","","  > Foo","  > ---","  - Do: y",'"$F"']'"$INS"; }
run "G6++++ setext-in-blockquote-nested" "nested inside the lesson" t6e
# G6 negative: a quoted paragraph followed by a DEEPER quoted dash line is not its underline → PASS
t6f() { both 'LESSON=["- **Quote depth**","  - Why it matters here: x","","  > Foo","  > > ---","  - Do: y",'"$F"']'"$INS"; }
pos "G6 quote-depth-mismatch-not-setext" t6f

# Container end (found via G4): a nested fence with no closer ends with its list item — the sibling field survives
t7() { both 'LESSON=["- **Implicit close**","  - Why it matters here: x","    ```","    code without a closer","  - Do: y",'"$F"']'"$INS"; }
pos "C1 nested-fence-closed-by-container-end" t7
# …but the same fence at TOP level (base 0) swallows everything to EOF → unclosed FAIL stands
t7b() { both 'LESSON=["- **Top fence**","  - Why it matters here: x","```","  - Do: y",'"$F"']'"$INS"; }
run "C1+ top-level-unclosed-fence" "never closes" t7b
# G1 negatives: NBSP after a marker is not a list item (a lazy paragraph line instead)
t8() { both 'LESSON=["- **Nbsp marker**","  - Why it matters here: x","  -'"$NB"'Do: y","  - Do: y",'"$F"']'"$INS"; }
pos "G1+++ nbsp-after-marker-is-text" t8

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
rm -rf "$W"
[ $bad -eq 0 ]
