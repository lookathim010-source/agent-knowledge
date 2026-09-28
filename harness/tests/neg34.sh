#!/usr/bin/env bash
# Round-34 negative tests (Codex and Kilo reviews of 4187200).
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

# T1 (Codex 4118069781): a verified sheet's H1 text must be Markdown text or code — text inside raw HTML never counts
t1() { printf '# <span>Visible</span>\n\nbody\n' > verified/2026-01-25_span-h1_v1.md; }
run "T1 raw-html-only-h1-text" "verified:h1" t1

# T2 (Kilo 4118066660): an empty ATX heading is a FAIL, never a crash
t2() { printf '# \n\nbody\n' > verified/2026-01-26_empty-h1_v1.md; }
run "T2 empty-h1-fails-cleanly" "verified:h1" t2
t2b() { printf '#\n\nbody\n' > verified/2026-01-27_bare-h1_v1.md; }
run "T2+ bare-hash-h1-fails-cleanly" "verified:h1" t2b

# T3 (Kilo 4118066651): lead_text() is always a prefix of visible_text(), so the label's match offset is valid in both
n=$((n+1))
if python3 - "$SRC/harness" <<'PY'
import sys, pathlib
h = pathlib.Path(sys.argv[1]); sys.path.insert(0, str(h))
src = (h / "check-knowledge.py").read_text()
g = {"__file__": str(h / "check-knowledge.py"), "__name__": "ck"}
exec(compile(src[:src.index("# --- knowledge.md")], "ck", "exec"), g)
MD, inline_tokens, lead_text, visible_text = g["MD"], g["inline_tokens"], g["lead_text"], g["visible_text"]
samples = ["Why it matters here: <span>x</span>", "Why it matters here: `x`", "Why<!-- n --> it matters here: x",
           "Do: ![i](https://x.y/i.png) z", "Do:\nnext line", "Do: **b** <!-- c --> <kbd>k</kbd>", "Source: [T](https://x.y) x",
           "Why it matters here: <!-- c --><!-- d -->", "Do: a\\\nb", "Do: &amp; &#65; <br> c"]
for s in samples:
    toks = inline_tokens(MD.parseInline(s, {})[0])
    for c in (False, True):
        assert visible_text(toks, code_text=c).startswith(lead_text(toks)), (s, c)
PY
then echo "PASS T3 lead-text-is-a-prefix-of-visible-text"; else bad=$((bad+1)); echo "FAIL T3 lead-text-is-a-prefix-of-visible-text"; fi

# T4 (Codex 4118069784): the conformance canonicalizer never touches a newline inside <pre>
n=$((n+1))
if python3 - "$SRC/harness/conformance/check.py" <<'PY'
import re, sys
src = open(sys.argv[1]).read()
ns = {"re": re}
exec(src[src.index("BLOCK_NL = "):src.index("ALLOWED = {")], ns)   # code anchors, not comments
exec(src[src.index("def canon"):src.index("ref = json.load")], ns)
c = ns["canon"]
assert c("<pre>x\n</pre>") != c("<pre>x</pre>")                       # the newline before </pre> is visible
assert c("<pre><code>x\n</code></pre>\n") != c("<pre><code>x</code></pre>\n")
assert c("<pre>x\n<!-- c --></pre>") != c("<pre>x<!-- c --></pre>")
assert c("<li>a\n<pre>x</pre>") == c("<li>a<pre>x</pre>")
PY
then echo "PASS T4 newline-inside-pre-is-compared"; else bad=$((bad+1)); echo "FAIL T4 newline-inside-pre-is-compared"; fi

echo "----"
echo "RESULT: $([ $bad -eq 0 ] && echo PASS || echo FAIL) — $((n-bad)) pass, $bad fail ($n cases)"
[ $bad -eq 0 ]
