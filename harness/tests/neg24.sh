#!/usr/bin/env bash
# Round-24 negative tests (Codex review of e7edf49).
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

# H1 (4116065528): a NBSP before an end-of-line inline comment is content; a copy with a plain space differs
t1() { split 'LESSON=["- **Nbsp comment**","  - Why it matters here: x\u00a0<!-- c -->","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Nbsp comment**","  - Why it matters here: x <!-- c -->","  - Do: y",'"$F"']'"$INS"; }
run "H1 nbsp-before-eol-comment" "same title, different content" t1

# H2 (4116065538): a 1000-character label is not a reference definition (999 is)
t2() { python3 -c 'open("verified/2026-01-08_biglabel_v1.md","w").write("[" + "a"*1000 + "]: https://x.y\n\n# Real heading\n")'; }
run "H2 label-over-999-is-prose" "verified:h1" t2
t2b() { python3 -c 'open("verified/2026-01-09_maxlabel_v1.md","w").write("[" + "a"*999 + "]: https://x.y\n\n# Real heading\n")'; }
pos "H2+ label-of-999-accepted" t2b

# H3 (4116065523): raw HTML before a verified sheet's H1 is visible content
t3() { printf '<div>visible before heading</div>\n\n# Real heading\n' > verified/2026-01-10_htmlfirst_v1.md; }
run "H3 raw-html-before-h1" "verified:h1" t3
t3b() { printf '```\ncode first\n```\n\n# Real heading\n' > verified/2026-01-11_codefirst_v1.md; }
run "H3+ fence-before-h1" "verified:h1" t3b
t3c() { printf '<!-- comment -->\n\n# Real heading\n' > verified/2026-01-12_commentfirst_v1.md; }
pos "H3++ comment-before-h1-still-fine" t3c

# H4 (4116065549): `<hgroup>` is NOT a type-6 tag (commonmark.js 0.31.2 list has none); under a title it is
#    lazy inline HTML that extends the title paragraph past the bold span → the shape check must flag it
t4() { both 'LESSON=["- **Hgroup**","  <hgroup>","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "H4 hgroup-is-title-continuation" "title paragraph continues" t4

# H5 (4116065545): `\<!-- visible -->` is literal text, not a comment
#    knowledge.md: `x \<!-- visible -->` (literal); day copy: `x \` — a harness that wrongly strips the escaped
#    opener leaves `x \` on both sides and PASSes; the correct reading differs
t5() { split 'LESSON=["- **Escaped opener**","  - Why it matters here: x \\<!-- visible -->","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Escaped opener**","  - Why it matters here: x \\","  - Do: y",'"$F"']'"$INS"; }
run "H5 escaped-comment-opener-is-text" "same title, different content" t5
t5b() { split 'LESSON=["- **Escaped backslash opener**","  - Why it matters here: x \\\\<!-- hidden -->","  - Do: y",'"$F"']'"$INS" \
              'LESSON=["- **Escaped backslash opener**","  - Why it matters here: x \\\\","  - Do: y",'"$F"']'"$INS"; }
pos "H5+ even-backslashes-then-real-comment" t5b

# H6 (4116065532): a thematic break inside a lesson renders as <hr>; a copy without it differs
t6() { split 'LESSON=["- **Hr lesson**","  - Why it matters here: x","","  ---","  - Do: y",'"$F"']'"$INS" \
             'LESSON=["- **Hr lesson**","  - Why it matters here: x","","  - Do: y",'"$F"']'"$INS"; }
run "H6 nested-thematic-break-counts" "same title, different content" t6
t6b() { both 'LESSON=["- **Hr lesson**","  - Why it matters here: x","","  ---","  - Do: y",'"$F"']'"$INS"; }
pos "H6+ nested-thematic-break-both" t6b

# H7 (4116065540): lazy text after the bold title is outside the strong span → shape problem
t7() { both 'LESSON=["- **title**","  unbold text","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "H7 prose-after-bold-title" "title paragraph continues" t7
t7b() { both 'LESSON=["- **title**","unbold lazy at column 0","  - Why it matters here: x","  - Do: y",'"$F"']'"$INS"; }
run "H7+ lazy-prose-after-bold-title" "title paragraph continues" t7b

# H8 (4116065555): `# ##` is an H1 with no content
t8() { printf '# ##\n\nbody\n' > verified/2026-01-13_emptyh1_v1.md; }
run "H8 empty-h1-closing-sequence" "verified:h1" t8
t8b() { printf '# Title ##\n\nbody\n' > verified/2026-01-14_closedh1_v1.md; }
pos "H8+ h1-with-closing-sequence-accepted" t8b
t8c() { printf '# \\#\n\nbody\n' > verified/2026-01-15_escapedhash_v1.md; }
pos "H8++ escaped-hash-is-content" t8c

# H9 (4116065550): an escaped `>` inside an angle-bracket destination does not close it
t9() { printf '[docs]: <https://example.com/a\\>b>\n\n# Real heading\n' > verified/2026-01-16_anglesc_v1.md; }
pos "H9 escaped-gt-in-angle-destination" t9
t9b() { printf '[docs]: <https://example.com/a>b>\n\n# Real heading\n' > verified/2026-01-17_angleunesc_v1.md; }
run "H9+ unescaped-gt-then-text-is-prose" "verified:h1" t9b

# H10 (4116065552): the day file must not be sanitized twice — a code payload holding `<!-- hidden -->` in BOTH copies is identical
t10() { both 'LESSON=["- **Payload lesson**","  - Why it matters here: x","    ```","    <!-- hidden --> in code","    ```","  - Do: y",'"$F"']'"$INS"; }
pos "H10 payload-not-resanitized" t10

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
rm -rf "$W"
[ $bad -eq 0 ]
