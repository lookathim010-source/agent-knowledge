#!/usr/bin/env bash
# Round-11 negative tests: each case copies the repo, applies one mutation, and
# expects the named check to FAIL (or the named behaviour). Prints PASS/FAIL per case.
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
# Apply one case's mutation inside the copy. If any command in it fails, the copy's checker is replaced by a
# stub that names the failure, so a case can never pass (or fail as expected) on an unmutated repo.
mutate() { ( set -e; cd "$W/r"; "$1" ); local rc=$?
  [ "$rc" -eq 0 ] || printf 'print("MUTATION DID NOT APPLY: %s (rc=%s)"); raise SystemExit(3)\n' "$1" "$rc" > "$W/r/harness/check-knowledge.py"; }
n=0; bad=0
run() { # name expected-substring-in-output mutation-fn
  local name="$1" expect="$2"; n=$((n+1))
  rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"
  mutate "$3"
  out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
  if [ $rc -ne 0 ] && printf '%s' "$out" | grep -qF -- "$expect"; then
    echo "PASS $name — FAIL fired: $(printf '%s' "$out" | grep -F -- "$expect" | head -1 | cut -c1-150)"
  else
    bad=$((bad+1)); echo "FAIL $name — rc=$rc, expected '$expect' in:"; echo "$out" | sed 's/^/    /'
  fi
}

# 1. backtick fence opener whose info string has a backtick must NOT open a fence
#    -> the lesson after it stays visible; put a broken lesson after such a line so shape FAILs
t1() { python3 - <<'EOF'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.startswith('## ')][0]
s.insert(i+1,'```py `x`')            # not a fence per CommonMark
s.insert(i+2,'- **Visible lesson with no fields**')
open(p,'w').write('\n'.join(s))
EOF
}
run "1 fence-info-backtick" "missing why" t1

# 2. lazy continuation at indent 0 after a field is content -> copies differ
t2() { python3 - <<'EOF'
p='lessons/2026-08-24.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.lstrip().startswith('- Do:')][0]
s.insert(i+1,'extra lazy text only in the day file')
open(p,'w').write('\n'.join(s))
EOF
}
run "2 lazy-continuation" "same title, different content" t2

# 3. tab after the list marker is a top-level item -> `-\tNot bold` is malformed
t3() { python3 - <<'EOF'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.startswith('## ')][0]
s.insert(i+1,'-\tTab-marked bullet that is not a bold lesson')
open(p,'w').write('\n'.join(s))
EOF
}
run "3 tab-after-marker" "not-a-bold-lesson-bullet" t3

# 4a. live symlink in verified/ rejected
t4a() { ln -s ../README.md verified/2026-01-01_link_v1.md; }
run "4a verified-symlink" "verified:readable" t4a
# 4b. live symlink in lessons/ rejected
t4b() { ln -s ../README.md lessons/2026-01-01.md; }
run "4b lessons-symlink" "lessons:readable" t4b

# 5. whitespace-only bold title is malformed
t5() { python3 - <<'EOF'
p='knowledge.md'; s=open(p).read().split('\n')
i=[k for k,l in enumerate(s) if l.startswith('## ')][0]
s.insert(i+1,'- ** **')
open(p,'w').write('\n'.join(s))
EOF
}
run "5 whitespace-bold-title" "not-a-bold-lesson-bullet" t5

# 6. verified sheet whose first line is an HTML comment then NO H1 -> must FAIL
#    (previously the comment line itself was tested; now the visible first line is)
t6() { printf '<!-- lead comment -->\nNot a heading\n' > verified/2026-01-02_nohead_v1.md; }
run "6 verified-h1-sanitized" "verified:h1" t6

# 7. a lesson before the first `## date` -> misplaced FAIL
t7() { python3 - <<'EOF'
p='knowledge.md'; s=open(p).read().split('\n')
s.insert(1,'- **Lesson placed before any day heading**')
open(p,'w').write('\n'.join(s))
EOF
}
run "7 misplaced-lesson" "knowledge:misplaced" t7

# 6-positive: a verified sheet that STARTS with a comment and then a real H1 must PASS
n=$((n+1))
rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"
printf '<!-- lead comment -->\n\n# Real heading\n\nbody\n' > "$W/r/verified/2026-01-03_lead_v1.md"
out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
if [ $rc -eq 0 ]; then echo "PASS 6+ comment-then-H1 accepted"; else bad=$((bad+1)); echo "FAIL 6+ comment-then-H1 rejected:"; echo "$out" | sed 's/^/    /'; fi

# 3-positive: `-\t**Title**` lesson with tab-marked fields in BOTH copies must PASS
n=$((n+1))
rm -rf "$W/r"; cp -r "$SRC" "$W/r"; rm -rf "$W/r/.git"
( cd "$W/r" && python3 - <<'EOF'
add=['-\t**Tab lesson**','    -\tWhy it matters here: tabs','    -\tDo: nothing','    -\tSource: [T](https://x.y) — A · confidence 50%']   # content column is 4 after a tab
for p,marker in (('knowledge.md','## '),('lessons/2026-08-24.md','# Lessons')):
    s=open(p).read().split('\n'); i=[k for k,l in enumerate(s) if l.startswith(marker)][0]
    s[i+1:i+1]=['']+add
    open(p,'w').write('\n'.join(s))
EOF
)
out=$(cd "$W/r" && python3 harness/check-knowledge.py 2>&1); rc=$?
if [ $rc -eq 0 ] && printf '%s' "$out" | grep -q "6 lesson(s)"; then echo "PASS 3+ tab-marked lesson counted (6 lessons)"; else bad=$((bad+1)); echo "FAIL 3+ tab lesson:"; echo "$out" | sed 's/^/    /'; fi

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
rm -rf "$W"
[ $bad -eq 0 ]
