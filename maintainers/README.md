# maintainers/

This directory holds working material for repo maintainers and their agents: worklists,
obligation inventories, and other tracking documents used to build and keep this repository.

A user of the acceptance-format needs nothing in this directory. The entry point for users is
the root [`README.md`](../README.md).

## What is here

| file | purpose |
|---|---|
| `OBLIGATIONS.md` | inventory of every weight-gating rule and where it is enforced; read by `tools/check_parity_selftest.py` as part of the gate suite |
| `VALIDATOR-TODO.md` | open validator-implementation worklist |
| `hooks/pre-commit` | the git pre-commit hook; runs the gate suite (`gates/run_all.sh`) before every commit |
| `install_hooks.sh` | installs `hooks/pre-commit` into `.git/hooks/pre-commit`; run once per clone |
| `capture_evidence.py` + `repin_manifest.py` | re-certification tooling: regenerate the root `acceptance.toml`'s `evidence/*.txt` transcripts at the current HEAD (including its mutation-control fixtures, genuinely re-run and reverted) and re-pin the manifest's identity fields (`spec_sha`/`validator_sha`/`subject.commit`, `generated_at`, every `record_hash`) to match — run `capture_evidence.py <repo-root>` then `repin_manifest.py <repo-root>` against a clean checkout, then re-run `gates/run_all.sh`. Mechanical only: claim statements and `self_verify.expect`/`watched_fail` prose are never touched, so a recapture that changes an environment fact (e.g. the repo's tracked-file count) still needs a reviewed, hand-made prose edit alongside it |
