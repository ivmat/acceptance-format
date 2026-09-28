# Conformance example pair

These examples use the B5 encoding: not-applicable claims have `status = "not-applicable"`, `applicability` and `applicability_reason`, with no `grade` or `scope_ref`; excluded claims retain their gap status and C4 companions.

These self-contained fixtures invent the five-clause standard
`example-wire-format-1` and a Rust crate, `example-wire-decoder`. Neither the
standard nor the evidence quotes or represents X.690, any RFC, or a real run.
The zero commit and JSON records are explicitly synthetic. All claims are A0
and unweighted; no observed-red control or higher assurance is claimed.

Both fixtures use the plain meaning id `acceptance/conformance`. `valid/`
contains two applicable, evidenced clauses; one applicable gap; one
not-applicable encoder clause; and one excluded decoder clause with a reason.
`invalid/` differs by one evidence entry on the not-applicable claim
`CONF/EWF-3`. Its single conformance finding is **C3**. Both parse as TOML;
the core also rejects the invalid fixture with
`claim 'CONF/EWF-3': status 'not-applicable' must have NO evidence entries`.

## Commands and verdicts

From the repository root:

```sh
python3 format_acceptance/tools/check_core.py --strict format_acceptance/profiles/conformance/examples/valid/acceptance.toml
python3 format_acceptance/tools/profiles/conformance.py format_acceptance/profiles/conformance/examples/valid/acceptance.toml
python3 format_acceptance/tools/profiles/conformance.py format_acceptance/profiles/conformance/examples/invalid/acceptance.toml
```

The first two exit 0; the last exits 1. Expected verdict lines and findings:

```text
PASS format_acceptance/profiles/conformance/examples/valid/acceptance.toml (4 warnings) [weighted: 0, unweighted: 5]
PASS format_acceptance/profiles/conformance/examples/valid/acceptance.toml [applicable: 3, not-applicable: 1, excluded: 1; evidenced: 2, gap: 2]
FAIL format_acceptance/profiles/conformance/examples/invalid/acceptance.toml: B5: not-applicable / excluded carries no evidence
FAIL format_acceptance/profiles/conformance/examples/invalid/acceptance.toml: claim 'CONF/EWF-3': status 'not-applicable' must have NO evidence entries
FAIL format_acceptance/profiles/conformance/examples/invalid/acceptance.toml: C3: claim 'CONF/EWF-3': not-applicable clause must carry no evidence
FAIL format_acceptance/profiles/conformance/examples/invalid/acceptance.toml [applicable: 3, not-applicable: 1, excluded: 1; evidenced: 2, gap: 2]
```

The core emits four warnings on `valid/` (five on `invalid/`, which adds one
more legacy record-hash warning for its extra evidence entry): two or three
legacy record-hash warnings, the experimental `[coverage].denominator =
'slice'` warning, and the legacy slice-boundary warning. No conformance fields
needed relocation or omission. Applicability counts use inventory clauses'
record rows; status counts use their claims. The conformance checker's `gap: 2`
is a literal `status = "gap"` count: it includes both the one applicable,
unevidenced clause (`EWF-2`) AND the one excluded clause (`EWF-4`, which is
`status = "gap"` with `applicability = "excluded"` per B5/C4) — the not-applicable
clause (`EWF-3`) is a different status and is not counted here. The core's
separate effective-coverage count treats the excluded clause differently and
reports `gap: 1` for the same fixture, counting only the genuinely open
applicable gap. Both are inventory counts, never a score. Failed fixtures'
counts describe declarations; missing or ambiguous rows cannot increase them.

`python3 format_acceptance/tools/profiles/conformance.py --selftest` builds independent fixtures.
Each case checks its exact verdict, exit status, CLI/library output agreement,
and a diagnostic substring identifying the relevant claim and sub-condition.

## Meaning rules, as currently shipped

For `not-applicable` (C3, the current B5 encoding), the checker requires
`applicability = "not-applicable"`, nonempty `applicability_reason`, no
evidence, and unweighted or omitted weight; `status = "not-applicable"` is
B5's class-level pairing, not this meaning's own rule, and `grade` on such a
claim is either absent or `out-of-scope` — B5 permits either, it does not
forbid `grade`. For `excluded` (C4), the checker additionally requires
`grade = "out-of-scope"` and nonempty `scope_ref`, with `status = "gap"` per
B5. The example scope locator is `applicability.toml`. An applicable clause
cannot use `grade = "out-of-scope"` (C5). The core grammar defines
out-of-scope as a grade, not a status. C10 requires nonempty `[spec].axis` and
`clause_source` equal to `external-standard` or `spec-document` on every
claim, regardless of weight.

C8 unconditionally refuses a weighted claim when every cited `kani-harness`
entry explicitly declares `cover_only = true` on the record; ref names are
never interpreted (the legacy `_witnessed`-suffix and `[conformance].cover_only`
list forms are read-only, with a deprecation warning at `0.1.0-draft` and
rejected at `0.2`). Independently, a `cover_tally` key anywhere in the
manifest is rejected by C8, including on an unweighted claim, in an evidence
entry, or in a nested table. Record-level tally projection remains open question C4.
Adding a non-cover-only Kani harness removes the cover-only condition, but
cannot exempt a manifest-side tally key. Adding only a unit test does not
remove the cover-only condition. C9 forbids aggregate keys anywhere in the manifest, applicability
record, or inventory, including claims, evidence, nested tables, and arrays.

`[spec].path` and `applicability_record` must be relative to the manifest
directory. Their resolved paths, including symlinks, must stay inside the
nearest ancestor containing a `.git` file or directory. `--root DIR`
explicitly overrides that root, including for exported bundles without
`.git`. An absolute path or an escape outside the root now fails at the class
level (`B6: <field>: absolute path forbidden` / `B6: <field>: path escapes
repository root`), not as a meaning-specific C6/C7 finding; `..` is legal when
resolution stays inside the root. No root and no override is INDETERMINATE.
Optional `source_manifest`'s path is no longer independently checked this way
— see "Content bindings," below, for what does still fire on it. Inventory
identity is bound only by its digest: a consumer compares `[spec].version`
with the canonical inventory digest out-of-band.

## Content bindings

Hashes use raw file bytes, including their final newline:

- `spec.version`: `normative-reference:sha-512:` followed by
  `SHA-512(b"normative-reference:" + inventory_bytes)` in lowercase hex.
- `conformance.applicability_hash`: `applicability-record:sha-512:` followed by
  `SHA-512(b"applicability-record:" + applicability_bytes)` in lowercase hex.
  The former bare `sha-512:` value is rejected (R-7).
- `conformance.source_manifest_hash` — a **legacy, pre-`/0` field**; see "Cross-manifest
  borrowing" and the retirement rules below for its current, flagged-not-validated status. Where
  it appears at all it was `manifest:sha-512:` followed by
  `SHA-512(b"manifest:" + source_manifest_bytes)` in lowercase hex, replicating
  the manifest domain in `../protocol_acceptance/tools/m11.py`.
- Evidence `record_hash` in these fixtures uses the **untyped legacy wire**: `sha-512:` followed by
  `SHA-512(b"evidence-record:" + record_bytes)` in lowercase hex (M11). This is accepted read-only
  with a WARNING throughout 0.3.x (`hash-domains.md` "Read-only legacy record wires"); a producer
  should emit the registered `record:sha-512:<hex>` construction instead.

C7 requires matching applicability and reason strings for every inventory row,
matching standard ids, and present, equal RFC 3339-shaped strings in record
`declared_at` and manifest `applicability_declared_at`. This binds **CONTENT**.
That the declaration preceded evidence reading is **producer-asserted**, not
mechanically established by the hash or the timestamps.

Cross-manifest borrowing at `/0` is class B8: a `kind = "acceptance-claim"`,
`family = "reference"` evidence entry citing `manifest` (B6-relative), `manifest_hash`,
`claim` (the source claim id), and a nonempty `records` list of cited native, non-control
`record_hash` values — see `spec/core.md` B8 for the full admission order (hash-before-parse,
source-claim status, weight recomputed with references removed, band/tier ceilings, cycle and
depth guards). Neither example fixture in this directory carries a B8 reference; both are
self-contained.

The pre-`/0` lineage fields this section used to validate — a claim's `source_claim` /
`source_claims_other`, and `[conformance].source_manifest` / `source_manifest_hash` — are
retired: no C11-shaped validation of them (uniqueness, hash checks, required-on-evidence) runs
any more, at any declared `profile_version`. Their presence is only flagged, and what that flag
is depends on the manifest's own declared `[format].profile_version`, verified directly against
this checker: left undeclared (as in both examples here) or declared `"0.1.0-draft"`, each legacy
field is a `C8:`-prefixed WARNING (`'<field>' is deprecated dead metadata (no C11 validation
runs); cite the source claim with a class B8 acceptance-claim evidence entry instead`); declared
`"0.2.0"` or any other value, the same field is a hard `C8:`-prefixed FAIL (`'<field>' is retired
at conformance 0.2; cite the source claim with a class B8 acceptance-claim evidence entry
instead`).

Other core evidence, band/species, and recipe checks still require the core
validator. The core's F2 implementation recomputes the digest, not just its shape
(`check_core.check_spec`, under every profile); `check_core.check_record_hashes` likewise
recomputes every resolvable evidence `record_hash` on every validation path — strict mode
additionally turns a missing native record pointer into an error rather than a warning.

## Scope and leaf verdicts

The plain `acceptance/conformance` id gets a normal composed PASS/FAIL. The
known leaf ids `acceptance/conformance/code` and `acceptance/conformance/code/rust`
run the meaning rules AND the binding's own checks; both bindings are implemented
today, so a leaf manifest that satisfies both halves PASSes (exit 0) exactly like
the plain-id examples in this directory, and a genuine meaning or binding failure
remains FAIL (exit 1) — a leaf is not stuck at INDETERMINATE by default. `--meaning-only`
only changes anything for a KNOWN binding path whose binding is not yet implemented;
with both halves present, as here, it is a no-op and the tool says so:

```text
NOTE <file>: scoping flag ignored: both halves present; full composed verdict
```

followed by the ordinary composed verdict — never `PASS-MEANING-ONLY` in that case.
An UNKNOWN suffix (a token this profile has never registered) is always
INDETERMINATE regardless of `--meaning-only`:
`B12: unknown suffix regardless of scoping flags ([format].profile = '<profile>')`.
Neither example fixture in this directory declares a leaf id.
`provenance = "in-tree"` or omitted provenance is INDETERMINATE with
`in-tree conformance standards not implemented in 0.1.0-draft`. Unrelated or
absent profiles, unknown suffixes, missing inputs, and unparseable TOML also
produce INDETERMINATE. Across files, FAIL takes precedence over INDETERMINATE.
Protocol binding and gate wiring are covered elsewhere, not by this profile's own checker.
