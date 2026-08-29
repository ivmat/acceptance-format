#!/usr/bin/env bash
# run_all.sh — the acceptance-format gate suite. Runs from repo root regardless of caller cwd.
#
# This is the same suite the format's working repo runs, minus two steps that do not apply to a
# public repo. The content-leak gate below replaces one of them.
#
# The leak gate runs with an EMPTY baseline (see gates/leak_baseline.json). No baselining is
# permitted here: any leak-gate hit is a real failure to fix in the source file, never in
# gates/leak_baseline.json.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "-- 1/9: manifest validator selftest (tools/check_acceptance.py) --"
python3 tools/check_acceptance.py --selftest
python3 tools/m11.py --selftest

echo "-- 2/9: examples validate --"
# --strict: record-pointer existence is enforced (core.md §0.6 / CS-21..23: strict applies only
# to non-illustrative manifests -- the illustrative examples below are marked
# illustrative = true, so this stays a no-op on record-pointer existence for them; they are also
# wholly unweighted, so --strict-weight is a no-op on them too. examples/weighted-toy/ is
# illustrative = false and weighted, so both flags are LIVE checks on it, not no-ops -- see its
# own README for why it is the template to copy, not the illustrative ones.
python3 tools/check_acceptance.py --strict --strict-weight \
  examples/minimal.acceptance.toml examples/rs-verified-der/acceptance.toml \
  examples/verify-rust-std-pr618/acceptance.toml \
  examples/weighted-toy/acceptance.toml
python3 tools/check_execute.py --yes-run-untrusted-commands \
  --subject-root examples/weighted-toy examples/weighted-toy/acceptance.toml

echo "-- 3/9: row-rule checker selftest (tools/check_ledger.py) --"
python3 tools/check_ledger.py --selftest > /dev/null

echo "-- 4/9: shipped envelopes obey the row rules --"
shopt -s nullglob
envelopes=(examples/*/ENVELOPE.md)
shopt -u nullglob
if [ ${#envelopes[@]} -gt 0 ]; then
  # --strict-weight: core.md §8.1's ratchet -- safe, currently a no-op on shipped envelopes.
  python3 tools/check_ledger.py --strict-weight "${envelopes[@]}"
else
  echo "no sample envelopes present -- skipping"
fi

echo "-- 5/9: recipe-execution mode selftest (tools/check_execute.py) --"
python3 tools/check_execute.py --selftest > /dev/null

echo "-- 6/9: cross-representation parity harness --"
# The two checkers must reach the same VERDICT on the same claim. Nothing else in this suite could
# notice when they diverged, because every other step exercises one checker at a time -- which is
# how `out-of-scope` came to grant weight in Markdown and refuse it in TOML for a full day.
# This step includes its own watched-break proof; a green line here means the harness was also
# shown able to fail.
python3 tools/check_parity_selftest.py --quiet

echo "-- 7/9: content-leak gate (empty baseline; any hit is a real failure) --"
python3 gates/test_check_content_leaks.py
python3 gates/check_content_leaks.py

echo "-- 8/9: schema artifact (tools/emit_schema.py) -- drift + example validation --"
python3 tools/emit_schema.py --selftest > /dev/null
schema_tmp="$(mktemp)"
trap 'rm -f "$schema_tmp"' EXIT
python3 tools/emit_schema.py > "$schema_tmp"
if ! cmp -s "$schema_tmp" schema/acceptance-0.1.0-draft.schema.json; then
  echo "schema drift: run 'python3 tools/emit_schema.py > schema/acceptance-0.1.0-draft.schema.json'"
  exit 1
fi
rm -f "$schema_tmp"
trap - EXIT
python3 tools/emit_schema.py --check examples/minimal.acceptance.toml \
  examples/rs-verified-der/acceptance.toml examples/verify-rust-std-pr618/acceptance.toml \
  examples/weighted-toy/acceptance.toml

echo "-- 9/9: self-manifest validates as a CERTIFICATE (acceptance.toml) --"
# This gate validates the manifest that DESCRIBES this gate suite, under the same --strict
# --strict-weight flags a real certificate must clear -- no exemption for being about this repo.
# The circularity is disclosed, not hidden: acceptance.toml's own [[claim]] "SELF-1"
# claims exactly "step 1 of this script passes", and so on through "SELF-8" naming this script's own
# step 8. This is fine because the format's anchor against self-reference is never the manifest's
# own say-so -- it is that every claim carries a `self_verify.command` a reader re-executes
# themselves. A broken checker cannot hide behind this step: it would first have to keep passing its
# OWN embedded fixture suites (steps 1/3/5, each backed by a recorded, reverted mutation-control
# witness in acceptance.toml) to even reach here, and this step re-validates the resulting manifest
# from a cold read, not from anything cached.
python3 tools/check_acceptance.py --strict --strict-weight acceptance.toml

echo "== acceptance-format gates: PASS =="
