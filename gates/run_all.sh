#!/usr/bin/env bash
# Complete public suite; continue after failures so the final report is complete.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
fail=0
run() {
  echo "-- $*"
  "$@"
  rc=$?
  if [ "$rc" -ne 0 ]; then echo "GATE FAIL (exit $rc): $*"; fail=1; fi
}
negative() {
  local expected="$1"; shift
  local output rc
  output=$("$@" 2>&1); rc=$?
  echo "$output"
  if [ "$rc" -ne 1 ] || [[ "$output" != *"$expected"* ]]; then
    echo "GATE FAIL: expected exit 1 and diagnostic $expected: $*"; fail=1
  else echo "PASS negative control: $expected"; fi
}
for tool in check_acceptance check_core hashdomains check_ledger check_execute spec_inventory; do
  run python3 "format_acceptance/tools/$tool.py" --selftest
done
run python3 format_acceptance/tools/check_parity_selftest.py --quiet
for tool in profiles/conformance profiles/troubleshooting bindings/code bindings/code_rust; do
  run python3 "format_acceptance/tools/$tool.py" --selftest
done
run python3 protocol_acceptance/tools/m11.py --selftest
run python3 protocol_acceptance/tools/acceptance_protocol.py --selftest
run python3 protocol_acceptance/tools/acceptance_protocol.py check-states
rd=protocol_acceptance/examples/rust-delivery
run python3 format_acceptance/tools/check_acceptance.py --root . --strict --strict-weight "$rd/acceptance.toml"
run python3 protocol_acceptance/tools/acceptance_protocol.py check-contract "$rd/acceptance-contract.toml"
run python3 protocol_acceptance/tools/acceptance_protocol.py check-package "$rd/acceptance.toml" --contract "$rd/acceptance-contract.toml" --root .
run python3 protocol_acceptance/tools/acceptance_protocol.py check-decision "$rd/acceptance-decision.toml" --contract "$rd/acceptance-contract.toml" --package "$rd/acceptance.toml" --root .
# The shipped decision must also be EFFECT-eligible
# on a date inside its validity window (not merely VALID) -- a regression gate the earlier
# one-day UTC-drift defect would have failed.
run python3 protocol_acceptance/tools/acceptance_protocol.py check-decision "$rd/acceptance-decision.toml" --contract "$rd/acceptance-contract.toml" --package "$rd/acceptance.toml" --effect --allow-conditions --now 2026-09-28 --root .
run python3 gates/check_decision_expiry.py
# Minimal is a fictional producer-only shape example; strict evidence-pointer checks
# apply to the real weighted certificate below, whose records must exist.
run python3 format_acceptance/tools/check_acceptance.py --root . format_acceptance/examples/minimal.acceptance.toml
run python3 format_acceptance/tools/check_acceptance.py --root . --strict --strict-weight examples/weighted-toy/acceptance.toml
run python3 format_acceptance/tools/check_execute.py --yes-run-untrusted-commands --subject-root examples/weighted-toy examples/weighted-toy/acceptance.toml
run python3 protocol_acceptance/tools/acceptance_protocol.py check-contract examples/weighted-toy/acceptance-contract.toml
run python3 protocol_acceptance/tools/acceptance_protocol.py check-package examples/weighted-toy/acceptance.toml --contract examples/weighted-toy/acceptance-contract.toml --root .
conf=format_acceptance/profiles/conformance/examples
run python3 format_acceptance/tools/check_core.py --root . --strict "$conf/valid/acceptance.toml"
run python3 format_acceptance/tools/profiles/conformance.py --root . "$conf/valid/acceptance.toml"
negative 'C3:' python3 format_acceptance/tools/profiles/conformance.py --root . "$conf/invalid/acceptance.toml"
ts=format_acceptance/profiles/troubleshooting/examples
run python3 format_acceptance/tools/check_core.py --root . --strict "$ts/valid.acceptance.toml"
negative 'C-T' python3 format_acceptance/tools/check_core.py --root . --strict "$ts/invalid.acceptance.toml"
run python3 gates/check_class_lock.py
run python3 gates/check_class_lock.py --selftest
run python3 gates/check_assumptions.py
run python3 gates/check_assumptions.py --selftest
run python3 gates/check_build_inputs.py
run python3 gates/check_adoption_templates.py
run python3 gates/check_export_closure.py
if [ "$fail" -ne 0 ]; then echo 'PUBLIC SUITE RED'; exit 1; fi
echo 'PUBLIC SUITE GREEN'
