---
type: validator-worklist
date: 2026-08-28
status: **FULL TRUTH PASS, 2026-08-28.** The previous banner on this file ("everything else in this
    file is still open exactly as recorded") was false and was flagged independently by three
    reviewers in a cold review. It described a 2026-08-27 snapshot (CS-1..CS-23 applied as spec text,
    nothing under `tools/`/`gates/` touched yet) that a series of 2026-08-28 passes overtook without
    this file being updated to match. As of this pass, re-derived entry by entry against the live
    code (`tools/check_acceptance.py`, `tools/check_ledger.py`, `tools/check_execute.py`,
    `gates/run_all.sh`): **most of the manifest-validator (`check_acceptance.py`) worklist is DONE.**
    CS-1, CS-2, CS-3, CS-4 (both conjuncts), CS-8, CS-10, CS-11, CS-12, CS-13, CS-16, CS-17, CS-18,
    CS-20, CS-21, CS-22, and CS-23 are implemented and selftested there. CS-6/CS-7 ([[claim.assumes]]
    shape-only validation) and CS-19's bundle-validator wiring remain genuinely OPEN — no code exists
    for either. CS-9 and CS-14/CS-15 are correctly NOT validator work (see the reservations section).
    **`check_ledger.py` mirrors NONE of CS-1/CS-3/CS-4/CS-8/CS-20/CS-21/CS-22/CS-23** — grepped for
    every marker below and found zero hits; it keeps a plain two-state (pass/fail) exit contract
    with no `epistemic_tier`/`method` handling and no `illustrative` marker. That whole worklist
    (below, under `tools/check_ledger.py`) is still open exactly as originally recorded — this is
    the one section of the old banner's claim that held up. `check_execute.py` also still has no
    CS-21 illustrative handling. `gates/run_all.sh` DOES now thread strictness the way CS-22 asked
    for, just not by the mechanism this file originally proposed: the gate script passes `--strict
    --strict-weight` uniformly, and the illustrative exemption lives inside `validate()` in
    `check_acceptance.py` (`effective_strict = strict and not illustrative`) rather than in the gate
    script itself. The freeze-obligations section below was re-verified against the code and is
    accurate as written; it was extended on 2026-08-28 (the `FREEDOM_WORDS` entry marked DONE) and
    that entry is kept.
governs_via: the applied change-set (CS-1..CS-23, folded into spec text and archived out of this
    repo once applied); the normative spec files themselves (core.md, format.md, evidence-types.md,
    assurance-bands.md) are authoritative
    for WHAT the rule says — this file only tracks WHETHER `tools/check_acceptance.py` /
    `tools/check_ledger.py` / `tools/check_execute.py` implement it yet (today: see the per-CS
    status table below).
---

# Validator TODO — what `tools/` must implement per applied CS entry

## Per-CS status summary (2026-08-28 full truth pass)

| CS | `check_acceptance.py` | `check_ledger.py` | note |
|---|---|---|---|
| CS-1/CS-2 | **DONE** — `check_evidence_record`, `tools/check_acceptance.py:665-690` | OPEN — no mirror | `method`/`epistemic_tier` parsed; omission WARNs (freeze ratchet booked below) |
| CS-3 | **DONE** — `tools/check_acceptance.py:80-93` (table), `692-710` (ceiling check) | OPEN — no mirror | ceiling, not equality (2026-08-28 fix) |
| CS-4 | **DONE**, both conjuncts — `tools/check_acceptance.py:1642-1672` (coherence), `1268` `_check_contract_scope_coverage` (scope) | OPEN — no mirror | scope conjunct still structural/token-only; freeze obligation below |
| CS-6/CS-7 | **OPEN** — no `assumes`/`void_if`/`defeater` code anywhere in the file | OPEN | unchanged from the original worklist; still explicitly optional this revision |
| CS-8 | **DONE** (dimensionally fixed) — `check_subject:489-500`, `check_evidence_record:781-801` | OPEN — no mirror | compares two M11-domain hashes, not `subject_hash` vs `commit` |
| CS-9 | N/A — reservation, not validator work | N/A | `format.md` design rule 4b; unchanged |
| CS-10/CS-11 | **DONE** — `tools/check_acceptance.py:71-73` (registry), `414-424` (enforcement) | — | `bundle` → whole-file `indeterminate` |
| CS-12/CS-13 | **DONE** — `tools/check_acceptance.py:66-69` (registry), `472-482` (fail-closed enforcement) | — | unknown `kind` → `indeterminate`, never `invalid` |
| CS-14/CS-15 | N/A this revision — no field exists yet to enforce the shape against | N/A | unchanged; gate on schema when a real field lands |
| CS-16 | **DONE**, including shape checks added 2026-08-28 — `tools/check_acceptance.py:426-452` | — | sha/date regex, not just nonemptiness |
| CS-17/CS-18 | **DONE** — `tools/m11.py` (whole file), wired at `check_acceptance.py` `record_hash`/`subject_hash` sites | — | SHA-512, self-describing, per owner ratification 2026-08-28 |
| CS-19 | **PARTIAL** — hash function exists (`tools/m11.py`'s `bundle-root` domain); no bundle validator wired to it | — | blocked on CS-11 (bundle validation itself is not first-revision work) |
| CS-20 | **DONE** — `Reporter` tri-state at `tools/check_acceptance.py:301,318`; exit-code mapping in `main()` at `~6025-6065` | OPEN — plain 0/1 exit only (`tools/check_ledger.py:2832-2851`) | |
| CS-21/CS-22 | **DONE** on the manifest side — `check_format:454-462` (parse), `validate:1764-1767` (`effective_strict`), multiple skip-sites (record_hash recompute, watched-fail, CS-4 coherence) | OPEN — no `illustrative` marker or skip logic anywhere in `check_ledger.py` | |
| CS-23 | **DONE** — `check_evidence_record:651-663` | OPEN — no control-block handling in `check_ledger.py` at all | F4 contradiction guard |

## `tools/check_acceptance.py` (manifest validator)

- **CS-1/CS-2 — `epistemic_tier` + `method` parsed, `kind` demoted to a hint — DONE.**
  `check_evidence_record` (`tools/check_acceptance.py:665-690`) parses `method` (open) and
  `epistemic_tier` (closed `T1`-`T5`) on every `[[claim.evidence]]` record. Omission of either draws
  a `WARN` naming the field (ruled 2026-08-28: the freeze promotion to a hard error is a separate,
  still-open obligation, booked below under "Flip the `method`/`epistemic_tier` ratchet"). `kind` is
  checked against the registry for shape but never used to resolve `method`/`epistemic_tier`
  (comment at `tools/check_acceptance.py:76-79` states this explicitly as a design constraint, not
  an oversight).
- **CS-3 — the `method → epistemic_tier` profile ceiling — DONE.** The shipped FV profile's table is
  `METHOD_EPISTEMIC_TIER` (`tools/check_acceptance.py:80-93`). Enforcement is at
  `tools/check_acceptance.py:692-710`: a record's declared `epistemic_tier` may not exceed what the
  profile assigns its `method` (an ERROR if it does); a *weaker* declared tier is accepted
  (conservative deflation, `_tier_rank`'s docstring at `tools/check_acceptance.py:96-106` explains
  why the checker used to enforce equality and that was itself a bug, fixed 2026-08-28). A `method`
  with no profile entry resolves to `indeterminate` (exit 2), not silently accepted and not a hard
  error. Selftested at `tools/check_acceptance.py:5432-5476`.
- **CS-4 — the `epistemic_tier`/grade coherence rule — DONE, both conjuncts.** For every weighted
  `contract` claim (`tools/check_acceptance.py:1642-1672`): conjunct 1 requires at least one
  evidence record with `result = "pass"` AND `epistemic_tier ∈ {T1, T2}` (a plain existence check,
  refused into `weight-pending` if absent, per the §8.1 transition ratchet). Conjunct 2, SCOPE
  COVERAGE, is `_check_contract_scope_coverage` (`tools/check_acceptance.py:1268`, called at line
  1672): it compares the claim's own `bounds` token against the qualifying evidence's `bounds` token
  structurally — `unbounded` claim + only `bounded` qualifying evidence is a hard error; `unbounded`
  claim + a qualifying `unbounded` record is accepted; every other combination (two `bounded` records
  with incomparable free-text tails, or a qualifying record with no parseable `bounds` at all) draws
  a transitional "UNDECIDABLE THIS REVISION" warning. That the checker auto-demotes rather than hard
  errors in the undecidable case, and does not yet compare structured domains, is disclosed and
  booked as a freeze obligation below ("Decide `contract` scope coverage properly") — the original
  open design question this entry flagged ("does the checker auto-demote or refuse weight?") is
  answered: it demotes to `weight-pending`/warns, per the code as it ships today.
- **CS-6/CS-7 — `[[claim.assumes]]` shape-only validation — OPEN, unchanged.** No code anywhere in
  `tools/check_acceptance.py` reads `assumes`, `void_if`, or `defeater` (grepped; zero matches). This
  matches the original worklist's framing: shipping this is optional for the revision, and it should
  stay a no-op on weight/status computation until H4 (Reserved hooks) lands. Nothing to correct here
  beyond noting it is still exactly as open as originally recorded.
- **CS-8 — evidence-subject binding — DONE (2026-08-28), WITH A DIMENSIONAL FIX from what this
  entry originally specified.** The original text compared an M11 content-hash against
  `[subject].commit`; that is a category error (`commit` is git-domain SHA-1 over the repository
  tree, not an M11-domain hash over one artifact's bytes) and was caught before implementation.
  **What actually shipped:** `[[claim.evidence]].subject_hash` (self-describing `sha-512:…`, when
  present) is compared against `[subject].subject_hash` (same form, OPTIONAL on `[subject]`) —
  both M11-domain hashes, dimensionally consistent. Mismatch is a hard `invalid` error,
  unconditionally; `[subject].commit` is untouched by this check and is validated exactly as before.
  Implemented in `check_subject` (`tools/check_acceptance.py:489-500`) and `check_evidence_record`
  (subject_hash comparison block, `tools/check_acceptance.py:781-801`). Selftest fixtures: match /
  mismatch / absent / malformed-shape, `tools/check_acceptance.py:5687-5765`.
- **CS-9 — label-binding.** Unchanged: explicitly NOT mechanically checkable per the spec text
  itself (`format.md` design rule 4b, `spec/format.md:74-78`). No validator work, this is
  reviewer-only, permanently.
- **CS-10/CS-11 — `shape` field — DONE.** `SHAPE_VALUES = {"single-file", "bundle"}`
  (`tools/check_acceptance.py:71-73`), REQUIRED from this revision, enforced in `check_format`
  (`tools/check_acceptance.py:414-424`). A manifest declaring `shape = "bundle"` returns
  `indeterminate` (exit 2) for the whole file, unconditionally. `shape = "single-file"` validates
  exactly as before. Selftested at `tools/check_acceptance.py:5213-5230, 5337-5346`.
- **CS-12/CS-13 — five new `[subject].kind` tokens + fail-closed registry — DONE.**
  `SUBJECT_KINDS` (`tools/check_acceptance.py:66-69`) adds `ml-model`, `dataset`, `spec`, `design`,
  `agent-output` to the original `rust-crate | rust-workspace | doc | tool | other`. An unknown
  `kind` with no profile declaring it draws `indeterminate` (exit 2), never a hard `invalid` and
  never silently accepted — `check_subject` (`tools/check_acceptance.py:472-482`). Selftested at
  `tools/check_acceptance.py:4117` ("kind-registry check as INDETERMINATE, not invalid").
- **CS-14/CS-15 — tagged number-XOR-null shape.** Unchanged: no concrete field ships this revision
  that needs it (no `[claim.independence].edge`, `calibration` stays a checked-nonempty-string, not
  a tagged shape — `tools/check_acceptance.py:731-736`). Still forward-looking; track as a gate on
  schema, not on validator logic, per the original entry.
- **CS-16 — `[format]` self-location fields — DONE, including the shape checks added 2026-08-28.**
  `spec_id`, `spec_sha`, `validator_sha`, `generated_by`, `generated_at` are all REQUIRED
  (`tools/check_acceptance.py:426-433`); absence is a hard error. `spec_sha`/`validator_sha` are
  additionally checked against `SELF_LOCATION_SHA_RE` (7-40 lowercase hex, `tools/check_acceptance.py
  :135, 439-446`) and `generated_at` against `GENERATED_AT_RE` (ISO-8601 UTC, `:138, 447-452`) — a
  fix over the original nonemptiness-only check, which let `validator_sha = "also-not-a-sha"` pass.
  Selftested extensively at `tools/check_acceptance.py:5231-5337`.
- **CS-17/CS-18 — M11 content-hash algorithm — DONE (2026-08-28), AMENDED at ratification.**
  Owner ratification (2026-08-28) changed the algorithm from the sha-256 this entry originally
  named to **SHA-512**, with digest values self-describing (`"sha-512:<128-hex>"`) and
  algorithm-baked field names renamed algorithm-neutral (`record_sha256`→`record_hash`). The
  input-side domain-separation construction this entry already specified is otherwise unchanged:
  `digest = sha512(prefix_bytes || file_bytes)`, UTF-8 literal prefix including its trailing colon,
  no added delimiter. Implemented once, shared, in `tools/m11.py` (`digest_bytes`/`digest_file`/
  `is_well_formed`, hard-coding SHA-512 as the one canonical algorithm this format revision
  accepts); imported by both `tools/check_acceptance.py` (`record_hash`/`subject_hash` checks) and
  `tools/check_execute.py` (P9's record-binding check, `check_record_hash`). The four prefixes
  `manifest:`, `bundle-root:`, `evidence-record:`, `claim:` ship as named in `PREFIXES`; `claim:`
  remains RESERVED — `tools/m11.py` refuses to compute under it (a caller bug, not a normal
  validator path). The rule this entry's obligation states — `record_hash` REQUIRED on weighted
  evidence, OPTIONAL on unweighted — is P9, stated in `format.md`'s "Content-hashing (M11)" section
  and in `evidence-types.md`'s Content-hashing section directly (no external citation needed to
  find it).
- **CS-19 — bundle-root inventory — PARTIAL, matches the original entry.** The hash FUNCTION exists
  (`tools/m11.py` supports the `bundle-root` domain and the self-describing SHA-512 form), but
  nothing wires it into an actual bundle validator, matching CS-11's deferral (bundle validation
  itself is not first-revision work). Not implementable further in isolation from CS-11. Grepped
  `tools/check_acceptance.py` for `bundle` — every hit is the `shape = "bundle"` → `indeterminate`
  path (CS-10/CS-11), none is a bundle-inventory check.
- **CS-20 — tri-state exit codes — DONE.** `Reporter` (`tools/check_acceptance.py:294`) carries a
  real third state (`indet()` at line 318, distinct from `error()`/`warn()`). `main()`
  (`tools/check_acceptance.py:5992-6065`) maps per-file state to `{"valid": 0, "invalid": 1,
  "indeterminate": 2}`, and the worst state across multiple files wins in the documented priority
  order (invalid > indeterminate > valid). Every "cannot decide" case named in the original entry
  (CS-11's bundle rule, CS-13's kind-registry rule, CS-3's unprofiled-method rule) routes through
  `rep.indet(...)`, not the error path — confirmed by reading each call site above.
- **CS-21/CS-22 — `illustrative` field + strict-vs-shape-only gating — DONE on the manifest side.**
  `[format].illustrative` parses (optional, default false) in `check_format`
  (`tools/check_acceptance.py:454-462`). When true, `validate()` computes
  `effective_strict = strict and not illustrative` (`tools/check_acceptance.py:1764-1767, 1781`) and
  every downstream check that takes `strict` (currently: record-pointer existence, line 744) skips
  the promotion to error. The watched-fail witness requirement and CS-4's coherence rule are each
  independently gated on `not illustrative` at their own call sites (e.g. line 1663's `and not
  illustrative`). `record_hash` recomputation and its required-on-weighted obligation are likewise
  skipped for an illustrative manifest (comment block above line 754). `main()`'s PASS/valid line
  carries an ` ILLUSTRATIVE` tag whenever `rep.illustrative` is true (`tools/check_acceptance.py
  :6045-6046`) — this is the CS-22 "visible label" requirement. Selftested at
  `tools/check_acceptance.py:5485-5509`.
- **CS-23 — the F4 contradiction guard — DONE.** `check_evidence_record`
  (`tools/check_acceptance.py:651-663`): if `control.kind == "mutation"` and
  `control.observed == "red"`, the carrier record's own `result` must not be `"pass"` — an ERROR if
  it is. Selftested at `tools/check_acceptance.py:5520-5555`.

## `tools/check_ledger.py` (rendered-ledger checker)

**Every item below is still open exactly as the original worklist recorded it.** Grepped
`tools/check_ledger.py` for `epistemic_tier`, `method`, `CS-1`, `CS-3`, `CS-4`, `CS-8`, `CS-20`,
`CS-21`, `CS-22`, `CS-23`, `indeterminate`, and `illustrative` — zero matches for all of them.
`check_ledger.py`'s exit contract is a plain `{0, 1}` (`main()`, `tools/check_ledger.py:2832-2851`:
`return 1 if total_errors > 0 else 0`), with no third state anywhere in `RowResult`
(`tools/check_ledger.py:999-1030`). This is the one part of the previous banner's blanket claim
("everything else in this file is still open") that was actually true — it just wasn't true of the
file as a whole.

- Mirror CS-1/CS-3/CS-4 (epistemic_tier/method/coherence) in the rendered-row grammar, per this
  repo's existing parity discipline (`tools/acceptance_grammar.py` — put shared logic there, not
  duplicated per checker, per the existing lesson in `core.md`'s "(a) CLEAN" history).
- Mirror CS-8 (binding) as far as a rendered ledger can express it — likely a declared-hash cell
  the checker compares, shape TBD; the manifest-side check is authoritative regardless.
- Mirror CS-20's tri-state contract: `check_ledger.py` needs its own `indeterminate` outcome
  wherever it currently only has pass/fail.
- Mirror CS-21/CS-22: an `illustrative` row/rendering marker, parsed the same declarative way
  `core.md` §4.1's "general rule" requires for every other structured obligation — never by
  scanning free prose for the word "illustrative".
- Mirror CS-23 (F4 guard) if this repo's rendered-ledger form ever carries control blocks directly
  (today's worked envelopes reference them by evidence record, not restate them — check whether
  this is even reachable in the Markdown form before building it).

## `tools/check_execute.py` (recipe-execution mode)

- No direct obligations from CS-1..CS-23. `--execute` already runs `self_verify.command`
  regardless of grade/tier; nothing here changes that surface. Revisit only if CS-21's illustrative
  flag should suppress `--execute` by default for teaching-example manifests (not specified either
  way in the applied spec text — flag back to spec if this matters; grepped, no `illustrative`
  handling exists in `tools/check_execute.py` today).
- Not a CS-numbered item, but worth recording here since it changed the file's contract since the
  original pass: a 2026-08-28 soundness fix made `--only` matching zero claims a hard error naming
  the id, rather than a vacuous green run (`tools/check_execute.py:333-343`, selftested `:619-646`
  as `ONLY-0`/`ONLY-1`).

## `gates/run_all.sh`

- **CS-22 — DONE, by a different mechanism than this entry originally proposed.** The original
  text asked for the gate script itself to "thread an illustrative-aware strictness flag" through
  the checkers. What actually shipped instead: `gates/run_all.sh` passes `--strict --strict-weight`
  uniformly at steps 2 and 9 (`gates/run_all.sh:22-23, 79`), and the illustrative exemption is
  computed inside `check_acceptance.py`'s `validate()` (`effective_strict = strict and not
  illustrative`, see the CS-21/CS-22 entry above) rather than by the gate script choosing a
  different flag per file. The observable outcome the original entry wanted — strict record-pointer
  enforcement applies only to non-illustrative manifests — is achieved; `gates/run_all.sh:18-21`'s
  own comment documents this. `check_ledger.py` has no illustrative concept at all (see above), so
  step 4's `--strict-weight`-only invocation (`gates/run_all.sh:34`) cannot thread anything CS-22
  asks for on that side either.
- No other CS entry requires a `gates/run_all.sh` change; CS-11/CS-13/CS-20's tri-state work is
  entirely inside the checkers the gate already calls.

## Freeze obligations — what must be settled before `0.1.0-draft` becomes `0.1.0`

Distinct from the per-CS worklist above: these are ratchets and deliberate softenings that are
correct *while the format is a draft* and must not survive the freeze unexamined. Each names the
decision owed, not a patch to apply blindly. Re-verified against the code as part of this pass;
unchanged in substance from the prior version of this section (kept, not rewritten, except for the
two private-citation fixes below).

- **Flip the `method`/`epistemic_tier` ratchet — ONE freeze act, five parts, all or none.**
  `spec/evidence-types.md` says both fields are REQUIRED AT FREEZE and transitional in this
  revision (CS-1/CS-2 — validated when present, admissible when absent). **DONE (2026-08-28):
  omission now draws a WARN** (`check_acceptance.py` `check_evidence_record`, "CS-1/CS-2" region)
  — a producer is told the field is missing, the record stays admissible. What remains booked for
  freeze is the promotion, and it lands as one change or not at all: any partial flip leaves spec
  prose, validator and schema disagreeing about the same two fields, which is the state this file
  exists to prevent.
  1. **Delete every transitional qualifier in `evidence-types.md`, not just the `†` note.** The
     `†` markers themselves, the "required at freeze and TRANSITIONAL in this revision" clauses in
     the `epistemic_tier` section and in the `method` section, the "on the transitional terms
     above" clause in the `family` paragraph, the Overview's "a field this revision requires"
     hedge, and the "Where a record declares both fields" opener on the profile-table rule. Delete
     them; do not reword them into softer versions.
  2. **Collapse the required-field list.** `evidence-types.md`'s "Required fields (every kind)"
     currently splits into "required in this revision" and "required at freeze, transitional in
     this revision". It becomes one list of eight: `kind`, `family`, `epistemic_tier`, `method`,
     `ref`, `result`, `tool`, `record`. Fix the Overview's reading order, which points at the
     split list.
  3. **Flip the validator.** `check_acceptance.py` must require both on every `[[claim.evidence]]`
     record: add them to `UNIVERSAL_EVIDENCE_FIELDS` and turn the two omission WARNs into hard
     errors.
  4. **Flip the schema in the same pass.** The artifact is generated (ADR-008), so the evidence
     record's `required` array follows (3) mechanically — `tools/emit_schema.py` reads the same
     `UNIVERSAL_EVIDENCE_FIELDS` — but the two field descriptions it writes by hand still say
     `OPTIONAL` for `epistemic_tier` and `method`. Rewrite those, regenerate
     `schema/acceptance-0.1.0-draft.schema.json`, and re-run the drift check (`gates/run_all.sh`
     step 8). A validator that errors while the schema still calls the field optional is exactly
     the schema/validator divergence the next obligation is about.
  5. **Fix the manifests that would newly fail.** `examples/minimal.acceptance.toml` and
     `examples/rs-verified-der/acceptance.toml` declare neither field on any evidence record (they
     WARN today, and would become `invalid`); `acceptance.toml` already declares
     both on all 12 records. The selftest fixtures asserting the WARN become fixtures asserting
     the error.
- **Decide `contract` scope coverage properly — comparable structured domains.** `core.md` §2
  requires a weighted `contract` claim's qualifying evidence to have "declared scope (`bounds`, §5)
  [that] covers the claim's declared domain". As of 2026-08-28 `check_acceptance.py` decides that
  conjunct **structurally, on the `bounded`/`unbounded` tokens alone**
  (`_check_contract_scope_coverage`): an `unbounded` claim whose only qualifying T1/T2 records are
  `bounded` is a hard error, a qualifying `unbounded` record satisfies it, and **every other case
  draws a transitional "UNDECIDABLE THIS REVISION" warning** — `bounded` against `bounded` (two
  free-text tails), and qualifying records declaring no `bounds` at all. In practice that warning
  fires on most honest bounded contract claims, which is the point: it is a disclosed gap, not a
  pass. What is owed at freeze, and it is a FORMAT change, not just a validator one:
  1. **A comparable domain representation.** `bounds` is one string carrying a token plus prose.
     Containment needs the two sides expressible in the same terms — a structured domain field, or
     a profile-declared domain vocabulary the two `bounds` values resolve into. Design this before
     implementing anything; a checker that parses `unwind=16, input<=12B` out of prose and compares
     it to `inputs up to 8 bytes` is guessing.
  2. **Then decide what happens to case 3.** Either it becomes decidable (the warning disappears),
     or the undecidable case is refused weight for `contract` at freeze — which is what §2's
     "an evidence record with no parseable `bounds` text does not satisfy this conjunct" already
     implies, and which cannot ship today without refusing every `lean-theorem`-backed contract
     claim (that kind requires `axioms`/`semantics`, not `bounds`).
  3. **Mirror it in `check_ledger.py`** under the existing parity discipline, and put the shared
     part in `tools/acceptance_grammar.py` — this rule exists in the manifest checker only today,
     which is precisely the divergence that module was created to prevent.
- **Profile selection has NO wire mechanism — one hard-coded profile.** `evidence-types.md` says a
  profile that declares any `method` token must publish a `method → epistemic_tier` mapping, and
  the tier rule resolves "the tier its ACTIVE profile's table assigns". There is no active-profile
  concept on the wire: no `[format].profile` field, no mapping table a manifest can carry or point
  at, and `tools/check_acceptance.py` hard-codes the single FV table (`METHOD_EPISTEMIC_TIER`) for
  every manifest it reads. A second profile cannot be expressed at all today, and a manifest
  produced under one would be silently graded against FV's table. Disclosed in
  `evidence-types.md`'s profile-table section as of 2026-08-28. Owed at freeze: decide the
  selection mechanism (a `[format].profile` id resolving against a registry the validator ships,
  versus an in-manifest table, versus staying single-profile and saying so normatively), and how a
  consumer authenticates the mapping it resolves — an unauthenticated profile table is a place to
  manufacture epistemic strength, which is the exact thing ADR-002 split the two fields to prevent.
- **Bind `[format].validator_sha` to the validator actually run.** As of 2026-08-28 the field's
  SHAPE is enforced (7–40 lowercase hex; `generated_at` likewise ISO-8601 UTC), which closes
  `validator_sha = "also-not-a-sha"`. It does not close `validator_sha = <some other real commit>`:
  nothing compares the named identity against the running validator. `format.md` calls pinning to
  this field "the only real stability guarantee", so at freeze either the validator verifies the
  binding for a certificate-grade manifest, or that sentence is weakened to what the field actually
  provides.
- **Revisit the two schema softenings carried in `x-semantic-only-rules`.**
  `subject-kind-registry-fail-closed` (the schema states `[subject].kind` as a closed `enum` while
  the validator fails *open* to `indeterminate` — a known, accepted divergence) and
  `shape-bundle-indeterminate` (a `bundle` manifest is whole-file `indeterminate`). Freezing either
  as-is publishes a schema that disagrees with the validator; decide which side moves.
- **Tighten `[[claim.assumes]]` and the reserved hooks in the schema when their machinery lands.**
  Both are deliberately unconstrained today (`claim-open-extension-fields`): parseable TOML that no
  validator function reads. The schema must not gain a hand-written shape for them — it gains one
  when the registry that generates it does, and not before (ADR-008, design rule 7).
- **`FREEDOM_WORDS` heuristic fix (`tools/check_acceptance.py` ~916) — DONE (2026-08-28).** The
  warning used to assume dynamic-only evidence at A1 must be a freedom claim, missing
  `assurance-bands.md` rule 4's other path — oracle-bearing dynamic evidence lifted to A1 by a
  mechanically-verified red mutation control. The heuristic now suppresses the warn when that
  rule-4 shape is present (reusing the same control-gate check the band-lift ERROR already
  computes) and falls back to the keyword check otherwise. `SELF-1`/`SELF-3`/`SELF-5` no longer
  WARN.

## Explicitly NOT validator work (reservations, per design rule 7 / the overclaim guard)

CS-5 (documentation only), CS-9 (label-binding, reviewer-only by the spec's own words), CS-14/
CS-15 (no field exists yet to enforce the shape against), CS-18 (a pointer, not a rule), and all of
H1-H8 (Reserved hooks, `format.md`) are explicitly reserved with no engine in this revision. Do not
build ahead of the spec for any of these — a validator that reads a reserved hook for a verdict
before its shape is fully ruled is exactly the overclaim design rule 7 exists to prevent.
