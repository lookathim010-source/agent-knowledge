#!/usr/bin/env bash
# Run every negative-test suite in this directory against the checker in this repo.
# Each suite copies the repo to a temp dir, applies one mutation per case, and asserts the checker's
# verdict. Prints one RESULT line per suite and a TOTAL line; exits non-zero if any case fails.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
total=0; failed=0; suites=0
for s in neg*.sh; do
  out=$(bash "./$s" 2>&1); rc=$?
  line=$(printf '%s\n' "$out" | grep -E '^RESULT' | tail -1)
  n=$(printf '%s' "$line" | grep -oE '\(([0-9]+) cases\)' | grep -oE '[0-9]+'); f=$(printf '%s' "$line" | grep -oE '[0-9]+ fail' | grep -oE '[0-9]+')
  printf '%-10s %s\n' "${s%.sh}" "${line:-RESULT: FAIL — suite did not report (rc=$rc)}"
  printf '%s\n' "$out" | grep -E '^FAIL' | sed 's/^/    /'
  total=$((total + ${n:-0})); failed=$((failed + ${f:-1})); suites=$((suites + 1))
  [ "$rc" -ne 0 ] && [ "${f:-0}" -eq 0 ] && failed=$((failed + 1))
done
echo "----"
echo "TOTAL: $([ $failed -eq 0 ] && echo PASS || echo FAIL) — $suites suites, $total cases, $failed failing"
[ $failed -eq 0 ]
