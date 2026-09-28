#!/usr/bin/env bash
# Round-35 negative tests (Codex review of 868313f).
# Browser behaviour here is checked by harness/conformance/html_oracle.py (html5lib) and in Chromium 141.
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

# U1 (4118171927): the conformance canonicalizer protects <pre> in any letter case
n=$((n+1))
if python3 - "$SRC/harness/conformance/check.py" <<'PY'
import re, sys
src = open(sys.argv[1]).read()
ns = {"re": re}
exec(src[src.index("BLOCK_NL = "):src.index("# Reviewed cases")], ns)
exec(src[src.index("def canon"):src.index("ref = json.load")], ns)
c = ns["canon"]
assert c("<PRE>x\n<!-- c --></PRE>") != c("<PRE>x<!-- c --></PRE>")
assert c("<Pre>x\n</pRe>") != c("<Pre>x</pRe>")
PY
then echo "PASS U1 uppercase-pre-is-protected"; else bad=$((bad+1)); echo "FAIL U1 uppercase-pre-is-protected"; fi

# U2 (4118171930): a would-be closer indented 4+ columns past its container is content, so the fence never closes
t2() { both 'import sys
p=sys.argv[1]; s=open(p).read().rstrip("\n").split("\n")
s += ["", "- **Deep fence**", "  - Why it matters here: x", "  - Do: y", "  - Source: [T](https://x.y) — A · confidence 50%", "", "    ```", "    code", "          ```", ""]
open(p,"w").write("\n".join(s))'; }
run "U2 over-indented-closer-leaves-fence-open" "never closes" t2
t2b() { both 'import sys
p=sys.argv[1]; s=open(p).read().rstrip("\n").split("\n")
s += ["", "- **Near fence**", "  - Why it matters here: x", "  - Do: y", "  - Source: [T](https://x.y) — A · confidence 50%", "", "    ```", "    code", "       ```", ""]
open(p,"w").write("\n".join(s))'; }
pos "U2+ closer-within-three-columns-closes" t2b

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
[ $bad -eq 0 ]
