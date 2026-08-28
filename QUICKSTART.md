# Quickstart

*Role: runtime view / usage — indexed from README §6 and §7.*

Requirements: `python3` 3.11+. The validator uses only the standard library.

---

## 1. Check the checker (10 seconds)

```sh
python3 tools/check_acceptance.py --selftest
```

Expected: `SELFTEST PASS: <N> fixtures`, ending in `PASS`. **`<N>` is whatever number the tool
prints, not a number typed here.** A typed count beside the thing it counts is exactly the drift §W5
refuses in a ledger; this page holds itself to the same rule.

Run this first and after any validator change. The fixtures include malformed envelopes that the
validator must *reject*, confirming that the checker can fail.

---

## 2. Validate an envelope (one command)

```sh
python3 tools/check_acceptance.py examples/minimal.acceptance.toml
```

(any manifest works the same way — `path/to/your/acceptance.toml` once you have one).

Add `--strict` to promote one specific gap to an error: a `record` pointer that does not resolve to
a file. `--strict` does not make every warning fatal — it does exactly this one thing, and only on a
non-illustrative manifest (`[format].illustrative = true` manifests stay shape-only and are exempt
even under `--strict`, ADR-005 / core.md §0.6). **On the command above `--strict` is therefore a
visible no-op** — `examples/minimal.acceptance.toml` is illustrative, so the output is
byte-identical with or without the flag; that is not the flag being broken. See it actually bite on
`examples/weighted-toy/acceptance.toml`, a real (non-illustrative) certificate where `--strict`
and `--strict-weight` are live checks — start there to write your own weighted manifest
(`examples/weighted-toy/README.md`). Multiple files are accepted.

The validator prints message-level tags on individual lines — `ERROR` (the document failed a
structural or weight obligation) and `WARN` (well-formed, but a reference could not be confirmed,
most commonly because an evidence record is missing from the given path) — but the file-level
**verdict** is one of three mutually exclusive states, each its own exit code (ADR-005, core.md
§8.3): `valid` (0), `invalid` (1, printed as `FAIL`), or `indeterminate` (2, printed as
`INDETERMINATE`, for cases the validator cannot decide, such as an unprofiled method or an unknown
`[subject].kind`). `indeterminate` is never accepting; a gate may not treat it as a pass.

If an envelope cites `evidence/some-run.log` but does not ship it, the validator reports a `WARN` by
default (an `ERROR` under `--strict`, on a non-illustrative manifest). The validator checks whether
the record was shipped, not its contents. This distinguishes a shipped record from an unsupported
assertion.

A `PASS` means the validator checked document structure and the required machinery for weighted
claims. It did **not**, by default, check that a referenced artifact exists — that check only runs
under `--strict`, and only against a non-illustrative manifest. The validator never ran proofs or
recipes, re-derived counts, or judged whether a harness verifies the right property.

---

## 3. Write your first ledger row

Pick **one rule** in the spec and answer four questions:

1. **What rule?** Cite the clause, not the module. "X.690 §10.1: length uses the shortest definite
   form", not "`length.rs` is verified".
2. **What decides it?** Name the harness, theorem, test, or lint. If nothing does, write
   `not-covered`.
3. **How strong is that?** Record bounded evidence as bounded. A fixture covers points rather than a
   domain. A panic-freedom proof does not decide an encoding rule. When uncertain, use the weaker
   label.
4. **What command would falsify the row?** Write it out. If you cannot write one, the row is
   admitted, **unweighted**, not weighted.

**Computing `record_hash`.** Every weighted claim's evidence needs a `record_hash` (the M11 content
hash of the file its `record` field points at, `spec/evidence-types.md`). Compute it with:

```sh
python3 tools/m11.py evidence-record path/to/your/evidence-file
```

That prints the `sha-512:<hex>` value to paste into `record_hash`. `python3 tools/m11.py --help`
lists the other hash domains (`manifest`, `subject`, `bundle-root`); a bare or wrong-argument
invocation prints usage and exits nonzero, never a silent no-op.

### Two traps that cost real time

**Proving a negative.** For `not-covered` rows, prefer **positive enumeration** of a closed set, such
as an error enum covering a function's full return surface, a registry, or a manifest. Print all
decided items. Show that the rule is absent. If an absence-grep is necessary, include a
**positive control** with input that *would* match. In the flagship sample, a grep-zero returned 14
hits and had been wrong from the first version. The control distinguishes "no hits" from "wrong
pattern".

**Counts.** Read counts from the subject's generator. If the subject has a documentation gate,
register the envelope so a stale count fails the build. Deliberately stale each count. Confirm
that the gate goes red. In the flagship sample, three of nine count claims were invisible to it.

---

## 4. A worked example

The worked sample in this repo is [`examples/rs-verified-der/ENVELOPE.md`](examples/rs-verified-der/ENVELOPE.md).
The same ledger ships as `COVERAGE.md` in the DER crate. For other subjects, keep the ledger beside
the code, link it from the subject's README, and wire its counts into the documentation gate.

The example shows:

- the identity table, especially the **freshness condition** stating when the receipt still speaks
  for HEAD and ending in *"run that command; do not trust this sentence"*;
- the recipe table, where each recipe class is defined once and then referenced per row, so rows
  stay short;
- weighted and unweighted rows in the same table, distinguished by the strength column;
- the section stating what the certification procedure does *not* establish.
