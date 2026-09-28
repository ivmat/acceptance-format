---
type: proposal
digest: The acceptance/0 manifest schema — class fields, typed locators, applicability, reference evidence, spec-inventory coverage (B19) and explicit compatibility; profile vocabularies are declared separately under the 2026-09-22 v2 base-format design.
---

# The acceptance manifest — format v0 (`acceptance/0`)

**Class text LOCKED at 0.3.2 (2026-09-27).** This text is frozen: a change needs a new `[[lock]]` entry
(new version + reason) in `CLASS-LOCK.toml`, enforced by `gates/check_class_lock.py`. Locked is not
ratified: the status below stays CANDIDATE until the owning authority ratifies the class.

The unit is the claim: governing clause, subject item, evidence and assumptions,
under the rule that decides. One TOML `acceptance.toml` records one subject and its
explicit gaps. [core.md](core.md) states the base rules; [profiles.md](profiles.md)
states profile composition. This schema transcribes the CANDIDATE design and identifies
the rules that the shipped validators check.

## §0 Class→Instance→Run

The class fields in this file are implemented by the shared grammar and core checks.
A meaning and optional binding supply the instance vocabularies; one manifest with
its exact subject locators and evidence is a run. Carriers are listed in core.md §0.
The retained compatibility entry point is `tools/check_acceptance.py` (core + verification);
`tools/check_core.py` is the design's class entry point.

## Design rules and compatibility (F1–F4)

The seven binding design rules are stated in core.md §2. The genericity fixes F1–F4
remain explicit, with the B-rules extending them rather than silently reinterpreting
old fields.

**F1 — Open subject-kind registry.** `[subject].kind` is not a closed enum of one
profile's vocabulary. The base registry below recognizes 9 tokens;
`[format].kind_registry` declares additional tokens. An unknown, undeclared token
is an error. B14 separately requires admission by the selected binding: recognition
does not imply admission. The two base tokens that named a single language's artifact
shapes moved to that language's own binding registry at 0.3.0 (B14): a token naming one
binding's artifact shape belongs in that binding's own `admits` declaration, not in the
shared base.

**F2 — External governing-document identity.** `[spec].provenance` defaults to
`in-tree`; when omitted, the prior free-form `version` behavior is retained.
`provenance = "external"` requires a self-describing
`normative-reference:sha-512:<128-hex>` digest over the governing document bytes.
For a conformance external standard this means the local clause-inventory bytes,
not the standard's text. The `external` list cites additional normative references;
it does not replace the primary `path`/`version` identity. See
[hash-domains.md](hash-domains.md) for the shared construction. B6 tightens pointer
containment: absolute paths are no longer admissible, and an externally owned
inventory is mirrored inside the consuming repository.

**F3 — Certified identity and read identity are distinct.** Omitted `mode` still
means `retrospective`; `commit` keeps its original meaning and git-revision shorthand,
so existing git-identified retrospective manifests need no migration. A new
`prospective` subject uses a required read-locator and has no certified identity.
It MAY also carry informational `commit`/`digest`, including an all-zero placeholder;
these fields MUST be excluded from certified-identity counting, their presence is
not an error, and they MUST NOT replace the read-locator. B1 adds
`content-digest` and `components` identities, and `read_at_digest` alongside
`read_at_commit`; either read-locator may be `"unpinned"`. A retrospective producer
may retain a read-locator for context; it does not replace the certified identity.

**F4 — Honest prospective verdict.** Zero `evidenced`/`partial` claims must never
be presented as plain PASS. The successful structural result is `PASS-PROSPECTIVE`,
subject to earlier B11 rows (including empty-manifest failure and retrospective
all-not-applicable INDETERMINATE). `not-applicable` contributes no checked evidence.
The ordered table in core.md §4 governs.
This preserves the distinction between validating assertions and checking evidence.

`[format].profile` is REQUIRED at 0.3.0; omitting it is an ERROR naming the field (B12).
Conformance `0.1.0-draft`'s legacy not-applicable encoding reads with a warning
and becomes an error at `0.2` (B5). Its legacy source-claim/source-manifest fields
remain accepted at `0.1.0-draft` and are lowered to reference records at `0.2` (B8).
These are explicit profile-version migrations, not changes to `commit` semantics.

## Stability: `acceptance/0` is UNSTABLE-UNTIL-FROZEN

The format id does not bump its integer on every rule tightening. Until deliberately
FROZEN for external consumption, `acceptance/0` is an evolving validator-defined
contract. Producer and validator move in lockstep; a manifest is meaningful against
the validator revision recorded beside it, not whatever the id meant on another day.
Pinning that revision supplies the stability guarantee. The integer changes at the
deliberate frozen-contract boundary. A paired private repository's pin closure adds byte
identity for the definitions and tools it consumes.

## Base subject-kind registry (B14)

| token | subject definition |
|---|---|
| `doc` | A written artifact such as a report or manual. |
| `tool` | A tool or toolchain treated as the subject. |
| `prospective-feature` | A proposed feature of an existing tool or artifact that is not yet built. |
| `other` | An artifact not described by a more specific base token. |
| `ml-model` | A machine-learning model artifact. |
| `dataset` | A collection of data treated as the subject. |
| `spec` | A normative specification treated as the subject. |
| `design` | A design artifact describing a proposed structure or solution. |
| `agent-output` | An agent-produced output treated as the subject. |

A binding MAY admit further, binding-specific kind tokens (e.g. a language's own artifact
shapes) through its own declared `admits = [...]` block; the Class validator recognizes a
subject kind if it is a base token above, is named in `[format].kind_registry` (F1), or is
admitted by the manifest's declared binding chain (B14). No binding-specific token is a base
token; see the relevant `code/*` binding document for its kinds.

The token definitions above are the base registry itself, not profile-shaped example
values. Verification evidence kinds/families and ladder values are declared in
`evidence-types.md` and `assurance-bands.md`;
profile composition is defined in profiles.md.

## Manifest schema

Angle-bracket strings below are placeholders, not literal admitted values. Alternative
identity and evidence shapes are commented where they cannot coexist in one run.
The sample claim is a gap so it makes no assertion of admissible evidence.

```toml
[format]
id = "acceptance/0"           # evolving until deliberately frozen; see Stability
profile = "acceptance/<meaning>[/<binding path>]"  # REQUIRED at 0.3.0; no compatibility default (B12)
# kind_registry = ["<additional subject-kind token>"] # optional declared extension (F1)

[subject]
name = "example-subject"
kind = "other"               # base registry above, then binding admits (B14)
# mode = "retrospective"      # default; retrospective | prospective
commit = "<40-hex sha>"      # git-revision shorthand; exact certified content (B1)
dirty = false               # true if uncommitted changes were present
# Alternative certified identity: content-digest (do not also supply commit)
# digest = "subject:sha-512:<128-hex>"
# Alternative components identity: see the complete subject example below.
# Its aggregate [subject].digest IS that identity, not a second one (B1).
# Prospective alternative: set mode = "prospective" and supply the required
# read-locator admitted by the binding; commit/digest MAY remain informational
# (including all-zero placeholders), excluded from certified-identity counting:
# read_at_commit = "<40-hex sha>"          # or "unpinned"
# read_at_digest = "subject:sha-512:<128-hex>" # or "unpinned"
# Retrospective read-locators are optional, contextual, never certified identity (F3).

[spec]
path = "SPEC.md"            # relative and repo-contained after symlink resolution (B6)
version = "<sha|tag>"        # free-form for default in-tree provenance
# provenance = "in-tree"    # default; in-tree | external
# External version MUST be "normative-reference:sha-512:<128-hex>" (F2/B16).
# axis = "<what the item list enumerates>" # required once any claim claims weight
# external = ["<additional normative reference>"] # optional citation list
# inventory = "<path>"      # optional: a generic spec inventory (B19); repo-contained (B6)
# inventory_digest = "inventory:sha-512:<128-hex>" # required with inventory; B16 domain
# Absent inventory: no B19 check runs. Present: every declared item id needs >=1 citing
# claim (or a not-applicable/excluded row, B5); an id outside the inventory needs
# claim.addition = true (below), reported separately from coverage, never merged into it.

[coverage]
clauses_total = 1           # declared governing-clause count; clauses_total >= 1
claims_total = 1            # claims_total == len([[claim]]) exactly (B11)
# Many claims per clause are permitted. A clause may have zero claims only with slice.
# A meaning may narrow cardinality (conformance C1 requires a bijection).
# denominator = "complete" # optional: complete | slice; slice remains EXPERIMENTAL
# slice_note = "<why this is a slice>"     # required for slice
# slice_boundary = "<what this slice includes and excludes>" # absent on slice: WARNING in /0, error from /1 (B15)
# not-applicable counts in totals, but not F4's checked-anything set (B5).

[[claim]]
id = "A-001"               # stable, unique in this file, never reused
clause = "S-1"             # governing clause id; a spec-inventory item id when [spec].inventory is set (B19)
item = "<subject item>"
statement = "<what is asserted about the item>"
# supersedes = "<old claim id>" # new id rather than reuse of a published id
# addition = true           # B19, only with [spec].inventory: clause names an id the
# inventory does NOT declare — a delivered item beyond the spec; counted and reported
# separately from inventory coverage, never merged into it. Omitted or false: clause
# MUST name a declared inventory item id instead (when [spec].inventory is present).
status = "gap"             # evidenced | partial | gap | parked | blocked | not-applicable
# parked_reason = "<why parked>" # required when parked
# blocked_by = "<what prevents reaching the item>" # required when blocked
# band = "<meaning-declared token>" # B2: omit when no ladder; not a class token enum
# gaps = ["<what the evidence does not decide>"] # optional; warning if absent on partial
# applicability = "applicable" # omitted: infer not-applicable for that status, else applicable
# Valid pairs (B5): applicable with any status except not-applicable;
# not-applicable with status not-applicable; excluded with status gap. Mismatch is an error.
# applicability_reason = "<why not-applicable or excluded>"
# not-applicable: nonempty reason, no evidence, unweighted/absent weight,
#                grade out-of-scope/absent; reported separately from gap.
# excluded: status gap, applicability excluded, reason, no evidence, unweighted,
#           grade out-of-scope and nonempty scope_ref (C4 retained); distinct report row.
# scope_ref = "<scope section locator>"
weight = "unweighted"       # default when absent; weighted | unweighted
# Weight eligibility removes EVERY acceptance-claim record first; remaining native
# evidence must independently satisfy every weight condition. No native evidence: unweighted.
# References contribute to status and coverage, never weight (B8).
# grade = "<grade token>"   # required for weighted; optional for unweighted
# Class grade vocabulary: contract | probe | test-only | mechanical | not-covered |
# out-of-scope | inspection-argued | unspecified | ungraded.
# Last three are never weight-eligible. Band is evidence strength; grade is deciding role.
# Status × grade must cohere: gap/parked/blocked cannot claim a successful check;
# evidenced/partial cannot be not-covered/out-of-scope. Error if weighted, warning otherwise.
# B5's not-applicable constraints apply regardless of this old warning distinction.
# clause_source = "<source token>" # required for weighted, optional otherwise
# Class source vocabulary: spec-document | external-standard | doc-comment | test-name | none.
# test-name and none cannot carry weight; unweighted use is warned.
# item_kind = "predicate"   # optional, default item; a claim ranging over a second list
# over = "<the enumerated second list>" # required with predicate
# covered = "0/1"           # required with predicate: N/M, N <= M
# Weighted predicate missing over or covered is refused weight.

# [claim.self_verify]       # class shape when present; command + expect required
# Per-grade recipe/bounds/positive-control requirements belong to verification (8b);
# recipe carriers are binding declarations (profiles.md D1/A1).
# command = "<deciding command>"
# expect = "<expected output>" # required with command
# precondition = "<freshness/environment guard>" # optional
# expect_stream = "stdout" # default; stdout | stderr | combined
# positive_control = "<positive control recipe>" # per-grade requirement: verification profile
# A recipe is permitted on gap/parked: a recipe is not an evidence record.
# [claim.self_verify.watched_fail]
# of_command = "<same command as self_verify.command>" # whitespace-normalized comparison
# perturbed = "<what was changed>"
# observed = "<failure actually observed>"
# date = "<ISO date>"
# The class retains this watched_fail shape when present. Verification owns which
# grades require a witness/control and when positive_control may substitute.
# Non-whitespace command characters, including quoting, are not normalized.

# [[claim.evidence]]        # >=1 for evidenced/partial; none for gap/parked/blocked/not-applicable
# kind = "<declared kind>"  # class registry below; other kinds are profile-declared
# family = "<declared family>" # class judgment (ceiling T5) / reference (derived), or meaning-declared
# Class human-review: family judgment, extra-required reviewer.
# Class llm-review: family judgment, extra-required reviewer identifying the model id.
# Class acceptance-claim: family reference, extras in the B8 example below.
# check_core.check_evidence_record owns these rows; meanings MUST NOT redefine them.
# reviewer = "<reviewer identity or model id>" # required for the corresponding review kind
# ref = "<checkable evidence name>"
# result = "pass"           # pass | fail | unsupported; producer never self-overrides
# tool = "<tool identity at build granularity>"
# record = "evidence/run.txt" # raw record pointer, B6 contained; payload opaque to B7
# record_hash = "record:sha-512:<128-hex>" # optional universal field
# epistemic_tier = "<declared tier>" # class-shared T1 > T2 > T3 > T4 > T5; no stronger than family ceiling
# bounds = "<boundedness declaration>" # kind requirements: see evidence-types.md
# semantics = "<semantics in force>" # same profile registry supplies extra-field requirements
# captured_at_commit = "<40-hex>" # optional; MUST be full 40-hex when present (B20); shorter is an ERROR
# [[claim.evidence.toolchain]]     # optional; nonempty when present (B20)
# name = "<component name>"
# version = "<component version>" # optional
# commit = "<40-hex>"             # optional; at least one of commit/digest required per entry
# digest = "artifact:sha-512:<128-hex>" # optional; shape-checked only, never recomputed
# [[claim.evidence.build_inputs]]  # optional; nonempty when present (B20)
# path = "<repository-relative path>" # B6-contained
# digest = "artifact:sha-512:<128-hex>" # recomputed over the file's bytes when resolvable
# A binding MAY declare required_build_inputs paths for a weighted claim once any
# build_inputs entry is present; see core.md B20 and the declaring binding's own document.
# [claim.evidence.control]  # optional generic mechanism; no transfer via B8
# kind = "<control kind>"   # vocabulary belongs to the meaning; verification declares mutation/ablation/planted-twin
# expectation = "red"       # red | green | sat
# observed = "red"          # literal red/red required for a lift (B2)
# of_claim = "A-001"         # resolves and names THIS claim
# See assurance-bands.md for species ceilings and control whitelist.

# Alternative evidence entry: B8 records-mode reference (under an evidenced/partial claim).
# [[claim.evidence]]
# kind = "acceptance-claim"
# family = "reference"
# manifest = "sources/acceptance.toml"  # relative and repo-contained
# manifest_hash = "manifest:sha-512:<128-hex>" # source bytes verified BEFORE parsing
# claim = "<source claim id>"
# records = ["record:sha-512:<128-hex>"] # REQUIRED nonempty; native non-control pass entries ONLY
# Citing a source acceptance-claim entry is an error; manifest: MUST NOT appear in records.
# ref = "sources/acceptance.toml#<source claim id>"
# result = "pass"
# tool = "<referencing validator id and version>"
# record = "sources/acceptance.toml"
# record_hash = "manifest:sha-512:<128-hex>" # equals manifest_hash; not a cited records hash
# Reference tier = minimum cited-record tier on the class ordinal; never weight-bearing.
# Referencing claim has no control; remove ALL references before evaluating weight.
# Same registered ladder: band <= source minimum AND destination control-free ceiling.
# Different ladder or band-less source: destination is band-less; if it has a ladder,
# comparisons use that ladder's first token (floor), disclosed in statement.
# See core.md B8 for source validation, status, termination and migration rules.
```

On an `acceptance-claim` entry the universal fields read: `kind = "acceptance-claim"`, `family = "reference"`, `ref = "<manifest>#<claim>"`, `result = "pass"`, `tool` = the referencing validator's id and version, `record` = the `manifest` path, `record_hash` = `manifest_hash`; `manifest`, `manifest_hash`, `claim`, `records` are the kind's extra-required fields.

## Components subject shape (B1)

This complete subject block replaces the schema's git-revision subject block. Placeholder
hex strings must be replaced by lowercase locator hex and the recomputed aggregate.
The `[subject].digest` is the components identity, not a second identity; no top-level
`commit` accompanies it.

```toml
[subject]
name = "example-system"
kind = "other"
mode = "retrospective"
digest = "subject:sha-512:<128-hex aggregate over the canonical component lines>"

[[subject.components]]
name = "code"
commit = "<40-hex lowercase sha>"
dirty = false

[[subject.components]]
name = "document"
digest = "subject:sha-512:<128-hex lowercase component digest>"
```

Component names MUST be unique and match `[a-z0-9][a-z0-9._-]*`. Serialize one
`<name>=<locator wire form>` line per component, sorted by name bytewise, joined by
`\n` with a trailing `\n`, UTF-8. The wire forms are `git-revision:<40-hex>` and
`content-digest:subject:sha-512:<128-hex>`, with lowercase locator hex. The aggregate
is the `subject:` digest of those bytes; digest hex is compared case-insensitively
and written lowercase. This serialization MUST always be recomputed from the component
table, independent of whether a binding declares a subject payload (hash-domains.md).

## What `/0` deliberately does not do

The class has no cryptographic signing, no automatic clause count derived from arbitrary
spec prose, no trust arithmetic and no cross-file/workspace aggregate certification.
B8 records-mode references do not change those limits. See core.md §5 for the complete
class boundary and stated residuals.
