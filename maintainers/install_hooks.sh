#!/usr/bin/env bash
# Install this repo's git hooks — copies maintainers/hooks/pre-commit into .git/hooks/pre-commit
# so the gate suite (gates/run_all.sh) runs on every commit. Idempotent.
set -eu
cd "$(dirname "$0")/.."
[ -d .git/hooks ] || { echo "no .git/hooks — not a git repo?"; exit 2; }
cp maintainers/hooks/pre-commit .git/hooks/pre-commit
chmod +x maintainers/hooks/pre-commit .git/hooks/pre-commit gates/run_all.sh
echo "installed: .git/hooks/pre-commit (copied from maintainers/hooks/pre-commit; gates/run_all.sh runs on every commit)"
