#!/usr/bin/env bash
# run_example.sh — end-to-end walkthrough of the acceptance protocol over the iban-check crate.
# Runs from this directory regardless of caller cwd.
set -euo pipefail
cd "$(dirname "$0")"

TOOLS_DIR="../../tools"
CHECK_ACCEPTANCE="../../../format_acceptance/tools/check_acceptance.py"
PROTOCOL_TOOL="${TOOLS_DIR}/acceptance_protocol.py"

echo "== 1/5: generate the package (runs cargo test/clippy/doc/kani + 5 mutation controls) =="
if command -v cargo >/dev/null 2>&1; then
  python3 gen_package.py
else
  echo "cargo not found on PATH -- skipping gen_package.py (it requires cargo/clippy/kani); the"
  echo "example's acceptance.toml, if already generated, will be used as-is."
fi

echo
echo "== 2/5: validate the package with the format's own validator (--strict --strict-weight) =="
python3 "${CHECK_ACCEPTANCE}" --strict --strict-weight acceptance.toml

echo
echo "== 3/5: issue the consumer's decision (re-executes every basis claim's recipe for real) =="
if command -v cargo >/dev/null 2>&1; then
  python3 make_decision.py
else
  echo "cargo not found on PATH -- skipping make_decision.py (it re-runs cargo/kani commands)."
fi

echo
if [ -f "${PROTOCOL_TOOL}" ]; then
  echo "== 4/5: protocol-level checks (check-contract, check-package, coverage, check-decision) =="
  python3 "${PROTOCOL_TOOL}" check-contract acceptance-contract.toml
  python3 "${PROTOCOL_TOOL}" check-package acceptance.toml --contract acceptance-contract.toml
  python3 "${PROTOCOL_TOOL}" coverage acceptance.toml --contract acceptance-contract.toml
  if [ -f acceptance-decision.toml ]; then
    # Two-commit re-stamp (README "The one-commit self-reference lag", core.md B1): this example's
    # crate lives inside the very repo whose tooling validates it, so [subject].dirty is only
    # false when iban-check/ was fully committed BEFORE gen_package.py ran (a separate, earlier
    # commit from the one carrying the regenerated acceptance.toml + evidence/). When that
    # discipline was followed, check-decision below reports no error at all. If you ran this
    # script after editing iban-check/ WITHOUT committing first, [subject].dirty will honestly
    # read true again, and check-decision will report exactly one error
    # (format_acceptance/profiles/verification/code/rust.md's "dirty must be false" rule) -- not
    # a defect in the decision's own reasoning, just the
    # same disclosed self-reference lag recurring. Not papered over either way: shown, and the
    # script continues rather than aborting, because the change-impact demo below does not depend
    # on check-decision's verdict on this document.
    set +e
    python3 "${PROTOCOL_TOOL}" check-decision acceptance-decision.toml \
      --contract acceptance-contract.toml --package acceptance.toml
    decision_check_rc=$?
    set -e
    if [ "${decision_check_rc}" -ne 0 ]; then
      echo "NOTE: check-decision reported the error above. If the ONLY error is the package's"
      echo "      [subject].dirty rule (format_acceptance/profiles/verification/code/rust.md), this is the documented"
      echo "      self-reference friction (see README \"Friction\"), not a defect in the decision's"
      echo "      own reasoning -- continuing rather than treating it as fatal."
    fi
  else
    echo "acceptance-decision.toml not present (make_decision.py was skipped) -- skipping check-decision"
  fi

  echo
  echo "== 5/5: change-impact demo (a hypothetical edit to checksum.rs) =="
  # Path is `src/checksum.rs` (relative to iban-check/, cwd of every recipe), matching the
  # [[claim.evidence.inputs]] paths gen_package.py declares -- `impact` matches --changed values
  # against declared input paths by exact string, so the path convention must agree.
  if [ -f acceptance-decision.toml ]; then
    python3 "${PROTOCOL_TOOL}" impact acceptance-decision.toml \
      --contract acceptance-contract.toml --package acceptance.toml \
      --new-commit 1111111111111111111111111111111111111111 \
      --changed src/checksum.rs \
      --out-events impact-events.jsonl
  else
    echo "acceptance-decision.toml not present -- skipping impact demo"
  fi
else
  echo "protocol tool not present; skipping protocol verbs"
  rm -rf iban-check/target
  exit 0
fi

echo
echo "== cleanup: removing iban-check/target (cargo doc/test/kani build output; gitignored but"
echo "   not excluded from the repo's own filesystem-sweep gates -- see README) =="
rm -rf iban-check/target

echo
echo "== done =="
