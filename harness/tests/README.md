# Negative-test suites

Each `negNN.sh` copies the repository to a temporary directory, applies one
mutation per case (usually to both `knowledge.md` and the day file, so the
structural check, not the copy comparison, has to catch it), runs
`harness/check-knowledge.py`, and asserts the verdict. `run` expects a FAIL
containing a given string, `pos` expects PASS, and `stray_only` expects a
`knowledge:stray` FAIL without the wrong diagnosis. A mutation runs under
`set -e`; if any step of it fails, the copy's checker is replaced by a stub
that prints `MUTATION DID NOT APPLY`, so no case can pass on an unchanged repo.

The suite numbers follow the review rounds that produced them (rounds 11 to
27 of the review on PR #1, rounds 28 and 29 on PR #2). Cases marked
`CORRECTED 2026-09-27` encoded a CommonMark reading that the reference
implementation (commonmark.js 0.31.2) proved wrong. Each correction keeps a
replacement case for the intent that survives.

```bash
pip install -r harness/requirements.txt
bash harness/tests/run.sh      # one RESULT line per suite, then TOTAL
```
